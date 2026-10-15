"""Frozen M10R descriptive mechanism contrasts; no fits or receiver outcomes."""
from __future__ import annotations
import importlib.util
import itertools
import json
import math
import statistics as st
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
def module(name,file):
    s=importlib.util.spec_from_file_location(name,REPO/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('m10_registration','tools/measure_mechanism_observability_m10r.py')
a=module('m10_frozen_m9r_functions','tools/analyze_phase_state_m9r.py')
v=m.v

def metric(value=None,reason=None):return {'status':'present' if value is not None else 'unavailable','value':value,'reason':reason}
def present(field):return field.get('status')=='present'
def window(rows,cutoff,period):
    q=[n for n in rows if cutoff-6000<n['available_ms']<=cutoff]
    gaps=[b['available_ms']-a['available_ms'] for a,b in zip(q,q[1:])]
    ok=len(q)>=6000/period*.9 and bool(gaps) and max(gaps)<=250 and q[0]['available_ms']<=cutoff-5750 and q[-1]['available_ms']>=cutoff-250
    return q,ok

def delta(rows,cutoff,key,group=None,denominator=None):
    before=[n for n in rows if n['available_ms']<=cutoff-6000];after=[n for n in rows if n['available_ms']<=cutoff]
    if not before or not after:return metric(reason='missing causal endpoint')
    x,y=before[-1],after[-1]
    if cutoff-y['available_ms']>250 or cutoff-6000-x['available_ms']>250:return metric(reason='endpoint stale')
    if group=='outbound' and x['outbound_id']!=y['outbound_id']:return metric(reason='sender identity changed')
    def value(n,k):
        z=n[group][k] if group else n[k]
        return z['value'] if isinstance(z,dict) and present(z) else z if not isinstance(z,dict) else None
    old,new=value(x,key),value(y,key)
    if old is None or new is None or new<old:return metric(reason='missing, invalid or decreasing counter')
    if denominator:
        d0,d1=value(x,denominator),value(y,denominator)
        if d0 is None or d1 is None or d1<=d0:return metric(reason='nonpositive or missing denominator')
        return metric((new-old)/(d1-d0))
    return metric((new-old)*1000/(y['available_ms']-x['available_ms']))

def causal_features(native,relay,cutoff,optional):
    ns,nok=window(native,cutoff,25)
    # Browser receipt is the only relay availability clock.
    rows=[{'available_ms':r['browser_receive_ms'],**r['snapshot']} for r in relay if r['status']=='present']
    rs,rok=window(rows,cutoff,100);features={}
    def mean_field(group,key):
        good=[n[group][key]['value'] for n in ns if present(n[group][key])]
        return metric(st.mean(good)) if nok and len(good)>=.9*len(ns) else metric(reason='six-second native field coverage')
    if rok:
        features['queue_equivalent_ms']=metric(st.mean(r['a_to_b']['queued_wire_bytes']/(r['capacity_mbps']*125) for r in rs))
        features['queue_wire_bytes']=metric(st.mean(r['a_to_b']['queued_wire_bytes'] for r in rs))
        features['reverse_queue_equivalent_ms']=metric(st.mean(r['b_to_a']['queued_wire_bytes']/(r['capacity_mbps']*125) for r in rs))
        features['oldest_queue_ms']=metric(st.mean(r['a_to_b']['oldest_queued_age_ms'] for r in rs))
    else:
        for k in ('queue_equivalent_ms','queue_wire_bytes','reverse_queue_equivalent_ms','oldest_queue_ms'):features[k]=metric(reason='six-second relay coverage')
    for key,name in [('served_wire_bytes','served_bps'),('offered_wire_bytes','offered_bps')]:
        q=delta(rows,cutoff,key,'a_to_b');q['value']=q['value']*8 if q['value'] is not None else None;features[name]=q
    q=delta(native,cutoff,'bytesSent','outbound');q['value']=q['value']*8 if q['value'] is not None else None;features['send_bps']=q
    features['target_bps']=mean_field('outbound','targetBitrate')
    q=delta(native,cutoff,'totalEncodeTime','outbound','framesEncoded');q['value']=q['value']*1000 if q['value'] is not None else None;features['encode_ms_per_frame']=q
    features['encoded_fps']=delta(native,cutoff,'framesEncoded','outbound')
    q=delta(native,cutoff,'totalPacketSendDelay','outbound','packetsSent');q['value']=q['value']*1000 if q['value'] is not None else None;features['send_delay_ms_per_packet']=q
    q=mean_field('rtcp','roundTripTime');q['value']=q['value']*1000 if q['value'] is not None else None
    features['rtcp_rtt_ms']=q if optional['rtcp_rtt'] else metric(reason='RTCP channel did not qualify in every original')
    prior=[n for n in native if n['available_ms']<=cutoff];latest=prior[-1] if prior else None
    feedback=latest['feedback'] if latest else {}
    features['observed_feedback_age_upper_ms']=metric(feedback['observed_age_bounds_ms'][1]+cutoff-latest['available_ms']) if (
        optional['observed_feedback_counter_age'] and latest and cutoff-latest['available_ms']<=250 and feedback.get('status')=='present') else metric(reason='counter age unavailable/unqualified')
    features['cap_bps']=latest['encoder_cap_bps'] if latest else metric(reason='no native record')
    features['cutoff_ms']=cutoff
    features['latest_native_available_ms']=latest['available_ms'] if latest else None
    known=[r for r in relay if r['browser_receive_ms']<=cutoff]
    features['latest_relay_receipt_ms']=known[-1]['browser_receive_ms'] if known else None
    assert features['latest_native_available_ms'] is None or features['latest_native_available_ms']<=cutoff
    assert features['latest_relay_receipt_ms'] is None or features['latest_relay_receipt_ms']<=cutoff
    return features

def matching(sa,sz):
    if not sa.get('census_passed') or not sz.get('census_passed'):return {'eligible':False},False,False
    checks={'eligible':True,'current_x':abs(sa['current_x']-sz['current_x'])<=.25,
        'recent_drift':sa['recent_mean_drift_octaves'] is not None and sz['recent_mean_drift_octaves'] is not None and abs(sa['recent_mean_drift_octaves']-sz['recent_mean_drift_octaves'])<=.05,
        'long_contrast':sa['long_drift_octaves'] is not None and sz['long_drift_octaves'] is not None and abs(sa['long_drift_octaves']-sz['long_drift_octaves'])<=.05,
        'direction':sa['last_service_change_direction']==sz['last_service_change_direction'],
        'age':abs(sa['known_service_age_ms']-sz['known_service_age_ms'])<=250,
        'service_6s':sa['service_mean_6s'] is not None and sz['service_mean_6s'] is not None and abs(sa['service_mean_6s']-sz['service_mean_6s'])<=.01,
        'service_16s':sa['service_mean_16s'] is not None and sz['service_mean_16s'] is not None and abs(sa['service_mean_16s']-sz['service_mean_16s'])<=.01}
    return checks,checks['current_x'],all(checks.values())

def contrasts(x,z):
    results={}
    for key,threshold in m.DESIGN['contrast_resolution'].items():
        logarithmic=key.endswith('_octaves');name=key.removesuffix('_octaves')
        p,q=x[name],z[name]
        if p['status']!='present' or q['status']!='present' or (logarithmic and min(p['value'],q['value'])<=0):
            results[name]={'available':False,'difference':None,'resolution_flag':None};continue
        difference=math.log2(q['value']/p['value']) if logarithmic else q['value']-p['value']
        flag=abs(difference)>0 if threshold==0 else abs(difference)>=threshold
        results[name]={'available':True,'a':p['value'],'z':q['value'],'difference':difference,
            'unit':'octaves' if logarithmic else name,'resolution':threshold,'resolution_flag':flag}
    return results

def analyze():
    m.verify();root=m.ROOT/'development';gate=v.read(root/'mechanism_qualification_gate.json')
    assert gate['passed'],'global acquisition gate required before mechanism interpretation'
    p,_=v.core.check_capture_integrity(root);instrument=v.read(m.ROOT/'instrumentation/mechanism_qualification_gate.json')
    optional={k:gate['optional_channels_qualified_every_original'][k] and instrument['optional_channels_qualified_every_original'][k] for k in gate['optional_channels_qualified_every_original']}
    records=[]
    for t in p['trials']:
        d=root/'sessions'/t['id'];sender=v.read(d/'sender_observations.json');points=m.parent.m.parent.points_for(sender)
        start=v.read(d/'phase_windows.json')['phase_windows'][1]['start_ms'];common=start+24000
        command=v.read(d/'system_id_evidence.json')['commands'][0]
        events=[{'browser_ack_ms':start,'service_mbps':.5,'direction':0},
            {'browser_ack_ms':command['browser_receive_ms'],'service_mbps':m.DESIGN['service_mbps'][1],'direction':1}]
        native=v.read(d/'mechanism_native.json')['records'];relay=v.read(d/'mechanism_relay_browser.json')['records']
        entries={};first={k:None for k in ('B0','D1','P2')}
        for age in m.DESIGN['entry_grid_ms']:
            state=a.state_at(points,events,common+age);future=a.b.future_truth(points,state,common+63800)
            item={'age_ms':age,'state':state,'future':future}
            if age in m.DESIGN['landmarks_ms']:
                item['future_8s']=a.future_distribution(points,state)
                item['mechanism']=causal_features(native,relay,state['cutoff_ms'],optional) if state['census_passed'] else None
            entries[str(age)]=item
            for k in first:
                if first[k] is None and state['tags'][k]:first[k]=age
        records.append({**{k:t[k] for k in ('id','content_id','prefix','repetition','input_x')},'entries':entries,'first_tags_ms':first})
    pairs=[]
    for content in sorted({r['content_id'] for r in records}):
        originals=sorted([r for r in records if r['content_id']==content],key=lambda r:(m.parent.m.PREFIXES.index(r['prefix']),r['repetition']))
        for age in m.DESIGN['landmarks_ms']:
            for x,z in itertools.combinations(originals,2):
                left,right=x['entries'][str(age)],z['entries'][str(age)];sx,sz=left['state'],right['state']
                checks,b0,compact=matching(sx,sz);fx,fz=left['future_8s'],right['future_8s']
                observable=fx['observable'] and fz['observable'];distance=a.winf(fx['values_x'],fz['values_x']) if observable else None
                kind='within_history' if x['prefix']==z['prefix'] else 'prepaired_cross_history' if x['repetition']==z['repetition'] else 'crossed_repeat_cross_history'
                pairs.append({'content':content,'age_ms':age,'a_id':x['id'],'z_id':z['id'],'a_history':x['prefix'],'z_history':z['prefix'],
                    'a_repeat':x['repetition'],'z_repeat':z['repetition'],'pair_type':kind,'matching_checks':checks,'B0_matched':b0,'compact_matched':compact,
                    'future_observable':observable,'future_w_infinity_octaves':distance,'future_divergent':distance>.25 if distance is not None else None,
                    'future_max_1s_mean_difference_octaves':max(abs(q-r) for q,r in zip(fx['one_second_mean_x'],fz['one_second_mean_x'],strict=True)) if observable else None,
                    'future_change_residual_octaves':fz['mean_change_from_current']-fx['mean_change_from_current'] if observable else None,
                    'both_future_stationary':left['future']['passed'] and right['future']['passed'],
                    'mechanism_contrasts':contrasts(left['mechanism'],right['mechanism']) if checks['eligible'] else {}})
    mechanism_summary={};repeat_audit=[]
    for key in m.DESIGN['contrast_resolution']:
        name=key.removesuffix('_octaves');groups={}
        for content in sorted({r['content_id'] for r in records}):
            groups[content]={}
            for kind in ('prepaired_cross_history','crossed_repeat_cross_history','within_history'):
                groups[content][kind]={}
                for label,predicate in [('compact_divergent',lambda r:r['compact_matched'] and r['future_divergent']),
                    ('compact_nondivergent',lambda r:r['compact_matched'] and r['future_divergent'] is False)]:
                    chosen=[r for r in pairs if r['content']==content and r['pair_type']==kind and predicate(r)]
                    values=[r['mechanism_contrasts'][name] for r in chosen]
                    groups[content][kind][label]={'nested_pairs':len(values),'available':sum(q['available'] for q in values),
                        'resolution_contrasts':sum(q['resolution_flag'] is True for q in values),
                        'differences':[q['difference'] for q in values if q['available']]}
            for age in m.DESIGN['landmarks_ms']:
                chosen=[r for r in pairs if r['content']==content and r['age_ms']==age and r['pair_type']=='prepaired_cross_history']
                relevant=len(chosen)==2 and all(r['compact_matched'] and r['future_divergent'] for r in chosen)
                differences=[r['mechanism_contrasts'].get(name,{}) for r in chosen]
                repeats=bool(relevant and all(q.get('available') and q.get('resolution_flag') for q in differences) and differences[0]['difference']*differences[1]['difference']>0)
                controls=[r for r in pairs if r['content']==content and r['age_ms']==age and r['compact_matched'] and r['future_divergent'] is False]
                repeat_audit.append({'channel':name,'content':content,'age_ms':age,'two_matched_divergent_prepaired_repeats':relevant,
                    'same_direction_contrast_both_repeats':repeats,'nondivergent_controls':len(controls),
                    'within_history_controls':sum(r['pair_type']=='within_history' for r in controls),
                    'criterion_met':repeats and any(r['pair_type']=='within_history' for r in controls)})
        mechanism_summary[name]=groups
    counts={k:{'first_tags':sum(r['first_tags_ms'][k] is not None for r in records),
        'first_future_verified':sum(r['entries'][str(r['first_tags_ms'][k])]['future']['passed'] for r in records if r['first_tags_ms'][k] is not None),
        'nested_tags':sum(e['state']['tags'][k] for r in records for e in r['entries'].values()),
        'nested_future_verified_tags':sum(e['state']['tags'][k] and e['future']['passed'] for r in records for e in r['entries'].values())} for k in ('B0','D1','P2')}
    positives=sum(e['future']['passed'] for r in records for e in r['entries'].values())
    contents=sorted({r['content_id'] for r in records})
    motivated=[name for name in mechanism_summary if all(any(q['channel']==name and q['content']==content and q['criterion_met'] for q in repeat_audit) for content in contents)]
    result={'abi':'native_mechanism_observability_m10r_analysis_v1','technical_qualified':True,'originals':len(records),
        'protocol_sha256':v.sha(root/'protocol.json'),'gate_sha256':v.sha(root/'mechanism_qualification_gate.json'),
        'optional_channels_qualified':optional,'methods':counts,'positive_future_stationarity_labels_nested':positives,
        'total_nested_queries':len(records)*len(m.DESIGN['entry_grid_ms']),
        'compact_matched_pairs_nested':sum(r['compact_matched'] for r in pairs),
        'compact_matched_future_divergent_pairs_nested':sum(r['compact_matched'] and r['future_divergent'] for r in pairs),
        'compact_matched_moving_repeatable_pairs_nested':sum(r['compact_matched'] and r['future_divergent'] is False for r in pairs),
        'pair_records':pairs,'channel_contrast_summary':mechanism_summary,'repeatability_audit':repeat_audit,
        'trajectory_followup_motivation_channels':motivated,'trajectory_formulation_requires_new_preregistration':True,
        'native_common_support_established':False,'unchanged_gate_constraints':{'four_members_per_history':False,'multi_input_range_sd_overlap':False},
        'no_classifier_reason':'no positive stationary labels' if not positives else 'frozen descriptive assay; no fit permitted',
        'classifier_fitted':False,'controller_fitted':False,'actions':False,'receiver_outcomes_read':False,
        'scope':'eight fresh development originals; two reused contents, one controlled input; nested pairs/ages are not independent; contrasts are not causal mechanism effects'}
    v.write(root/'mechanism_records.json',records);v.write(root/'mechanism_analysis.json',result)
    v.write(REPO/'reports/native-mechanism-observability-m10r-summary.json',result)
    return {k:result[k] for k in ('originals','methods','positive_future_stationarity_labels_nested','compact_matched_pairs_nested',
        'compact_matched_future_divergent_pairs_nested','trajectory_followup_motivation_channels')}

if __name__=='__main__':print(json.dumps(analyze()))
