"""Frozen M9 causal-state predictions, future labels and outcome-free residuals."""
from __future__ import annotations
import importlib.util
import itertools
import json
import math
import statistics as st
from fractions import Fraction
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m9_registration',REPO/'tools/measure_phase_state_m9.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
s=importlib.util.spec_from_file_location('m9_m8_baselines',REPO/'tools/analyze_bwe_transients_m8.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
v=m.v

def describe(a):
    return {'n':len(a),'values':a,'mean':st.mean(a) if a else None,'minimum':min(a) if a else None,'maximum':max(a) if a else None}

def service_mean(events,cutoff,window):
    known=[e for e in events if e['browser_ack_ms']<=cutoff];lo=cutoff-window
    if not known or known[0]['browser_ack_ms']>lo:return None
    level=next(e['service_mbps'] for e in reversed(known) if e['browser_ack_ms']<=lo);total=0.;cursor=lo
    for event in known:
        at=event['browser_ack_ms']
        if at<=lo:continue
        total+=(at-cursor)*math.log2(level/.5);cursor=at;level=event['service_mbps']
    return (total+(cutoff-cursor)*math.log2(level/.5))/window

def state_at(points,events,endpoint):
    state=b.causal_state(points,events,endpoint)
    if not state['census_passed']:return {**state,'tags':{k:False for k in m.DESIGN['state_rules']}}
    cutoff=state['cutoff_ms'];recent=b.section(points,cutoff-6000,cutoff)
    old,new=b.section(points,cutoff-6000,cutoff-3000),b.section(points,cutoff-3000,cutoff)
    long_drift=st.mean(b.xs(new))-st.mean(b.xs(old)) if min(len(old),len(new))>=27 and all(b.valid(p,True) for p in old+new) else None
    gaps=[q['ms']-p['ms'] for p,q in zip(recent,recent[1:])]
    direction=state['last_service_change_direction'];scale=m.DESIGN['phase_response_envelope_ms']['rise' if direction>0 else 'fall'] if direction else None
    phase=state['known_service_age_ms']/scale if scale else None
    components={'D1':state['dynamic_tag'],'six_second_eligible':len(recent)>=54 and all(b.valid(p,True) for p in recent) and bool(gaps) and max(gaps)<=250,
        'six_second_frozen_caliper':bool(recent and all(b.valid(p,True) for p in recent) and max(abs(x-state['current_x']) for x in b.xs(recent))<=.125+1e-12),
        'six_second_contrast':long_drift is not None and abs(long_drift)<=.05+1e-12,
        'six_second_acknowledged_service':state['known_service_age_ms']>=6000,
        'past_M8_response_envelope':phase is not None and phase>=1}
    state.update(long_drift_octaves=long_drift,response_phase=phase,service_mean_6s=service_mean(events,cutoff,6000),
        service_mean_16s=service_mean(events,cutoff,16000),P2_components=components,
        tags={'B0':True,'D1':state['dynamic_tag'],'P2':all(components.values())})
    assert state['latest_feature_sample_ms']<=cutoff and state['latest_input_ack_ms']<=cutoff
    return state

def quantiles(values):
    values=sorted(values);assert values
    def q(p):
        h=p*(len(values)-1);i=int(h);j=min(i+1,len(values)-1)
        return values[i]+(h-i)*(values[j]-values[i])
    return [q(i/100) for i in range(101)]

def weighted_winf(groups_a,groups_z):
    def dist(groups):return sorted((x,Fraction(1,len(groups)*len(g))) for g in groups for x in g)
    a,z=dist(groups_a),dist(groups_z);i=j=0;ar,zr=a[0][1],z[0][1];maximum=0.
    while i<len(a) and j<len(z):
        maximum=max(maximum,abs(a[i][0]-z[j][0]));mass=min(ar,zr);ar-=mass;zr-=mass
        if ar==0:
            i+=1
            if i<len(a):ar=a[i][1]
        if zr==0:
            j+=1
            if j<len(z):zr=z[j][1]
    assert i==len(a) and j==len(z)
    return maximum

def winf(a,c):return weighted_winf([a],[c])

def future_distribution(points,state):
    if not state['census_passed']:return {'observable':False}
    cutoff=state['cutoff_ms'];q=b.section(points,cutoff,cutoff+8000);gaps=[c['ms']-a['ms'] for a,c in zip(q,q[1:])]
    observable=bool(len(q)>=72 and q[0]['ms']<=cutoff+250 and q[-1]['ms']>=cutoff+7750 and gaps and max(gaps)<=250 and all(b.valid(p,True) for p in q))
    if not observable:return {'observable':False}
    values=b.xs(q);bins=[]
    for i in range(8):
        p=b.section(points,cutoff+i*1000,cutoff+(i+1)*1000)
        if len(p)<7 or not all(b.valid(x,True) for x in p):return {'observable':False}
        bins.append(st.mean(b.xs(p)))
    return {'observable':True,'samples':len(q),'mean_x':st.mean(values),'mean_change_from_current':st.mean(values)-state['current_x'],
        'quantiles_x':quantiles(values),'values_x':values,'one_second_mean_x':bins,'minimum_x':min(values),'maximum_x':max(values)}

def project():
    m.verify();root=m.ROOT/'validation';gate=v.read(root/'mechanism_qualification_gate.json')
    assert gate['passed'],'all originals must technically qualify before state interpretation'
    p,index=v.core.check_capture_integrity(root);rows={x['trial']:x for x in gate['sessions']};records=[]
    for t in p['trials']:
        d=root/'sessions'/t['id'];sender=v.read(d/'sender_observations.json');points=m.m.parent.points_for(sender)
        windows=v.read(d/'phase_windows.json')['phase_windows'];start=windows[1]['start_ms'];common=start+24000;end=common+63800
        evidence=v.read(d/'system_id_evidence.json');command=evidence['commands'][0];assert command['browser_receive_ms']==rows[t['id']]['input_fidelity']['common_service_ack_ms']
        events=[{'browser_ack_ms':start,'service_mbps':t['service_sequence_mbps'][0],'direction':0},
            {'browser_ack_ms':command['browser_receive_ms'],'service_mbps':t['service_sequence_mbps'][1],'direction':1 if t['input_x']>=1 else -1}]
        entries={};first={k:None for k in m.DESIGN['state_rules']};verified_onsets=[]
        for age in m.DESIGN['entry_grid_ms']:
            state=state_at(points,events,common+age);truth=b.future_truth(points,state,end)
            item={'age_ms':age,'state':state,'future':truth,'future_8s':future_distribution(points,state)};entries[str(age)]=item
            for method in first:
                if first[method] is None and state['tags'][method]:first[method]=age
            if state['tags']['D1'] and truth['passed']:verified_onsets.append(age)
        late={}
        for age in (16000,24000,32000,40000,48000,56000,63000):
            q=b.section(points,common+age-4000,common+age);vals=b.xs(q) if q and all(b.valid(x,True) for x in q) else []
            late[str(age)]={'mean_x':st.mean(vals) if vals else None,'four_second_range_octaves':max(vals)-min(vals) if vals else None,
                'final_drift_octaves':b.drift(points,common+age)}
        records.append({**{k:t[k] for k in ('id','content_id','prefix','input_x','input_order','repetition','pair_id')},'entries':entries,'first_tags_ms':first,
            'first_future_verified_D1_ms':min(verified_onsets) if verified_onsets else None,
            'settling_onset_right_censored_after_ms':None if verified_onsets else 55000,'late_support':late})
    assert len(records)==64
    return records,gate

def primary(records,method):
    cells=[];full=True;selected={}
    for c in sorted({x['content_id'] for x in records}):
        for level in m.TARGETS:
            rows=[x for x in records if x['content_id']==c and x['input_x']==level];first=[]
            for row in rows:
                age=row['first_tags_ms'][method];item=row['entries'][str(age)] if age is not None else None
                selected[row['id']]=item
                first.append({'trial':row['id'],'prefix':row['prefix'],'repetition':row['repetition'],'age_ms':age,
                    'cutoff_ms':item['state']['cutoff_ms'] if item else None,'census_x':item['state']['census_x'] if item else None,
                    'current_x':item['state']['current_x'] if item else None,'future_passed':bool(item and item['future']['passed']),
                    'future_components':item['future'].get('components') if item else None,
                    'maximum_future_distance_octaves':item['future'].get('maximum_future_distance_octaves') if item else None,
                    'maximum_future_drift_octaves':item['future'].get('maximum_future_absolute_drift_octaves') if item else None})
            groups=[[x for x in first if x['prefix']==h] for h in m.m.PREFIXES]
            tagged=all(x['age_ms'] is not None for x in first);future=all(x['future_passed'] for x in first)
            spread=max([x['census_x'] for x in first])-min([x['census_x'] for x in first]) if tagged else None
            prefix_w=winf(*[[x['census_x'] for x in g] for g in groups]) if tagged else None
            current_delta=max(abs(x['current_x']-x['census_x']) for x in first) if tagged else None
            elapsed=max(x['age_ms'] for x in first)-min(x['age_ms'] for x in first) if tagged else None
            # Actual endpoints add the native census offset, never a fitted clock.
            if tagged:
                elapsed=max(selected[x['id']]['age_ms']+selected[x['id']]['census_offset_ms'] for x in rows)-min(selected[x['id']]['age_ms']+selected[x['id']]['census_offset_ms'] for x in rows)
            distributions=[selected[x['id']]['future_8s'] for x in rows] if tagged else []
            observable=bool(distributions and all(x['observable'] for x in distributions))
            future_repeat=max(winf(selected[q['id']]['future_8s']['values_x'],selected[z['id']]['future_8s']['values_x'])
                for h in m.m.PREFIXES for q,z in itertools.combinations([x for x in rows if x['prefix']==h],2)) if observable else None
            pooled={}
            for h in m.m.PREFIXES:
                pooled[h]=[selected[x['id']]['future_8s']['values_x'] for x in rows if x['prefix']==h and selected[x['id']] and selected[x['id']]['future_8s']['observable']]
            future_prefix=weighted_winf(*pooled.values()) if observable else None
            gates={'four_originals_each_history':all(len(g)==4 for g in groups),'all_first_tags':tagged,'all_future_verified':future,
                'fixed_target_membership':tagged and all(abs(x['current_x']-level)<=.125+1e-12 for x in first),
                'full_census_repeat_spread':spread is not None and spread<=.25+1e-12,'prefix_census_w_infinity':prefix_w is not None and prefix_w<=.25+1e-12,
                'actual_current_census_distance':current_delta is not None and current_delta<=.25+1e-12,
                'entry_elapsed_spread':elapsed is not None and elapsed<=250,
                'future_distributions_observable':observable,'future_repeat_w_infinity':future_repeat is not None and future_repeat<=.25+1e-12,
                'future_prefix_w_infinity':future_prefix is not None and future_prefix<=.25+1e-12}
            cells.append({'content':c,'input_x':level,'first_predictions':first,'gates':gates,'passed':all(gates.values()),
                'first_tags':sum(x['age_ms'] is not None for x in first),'future_verified':sum(x['future_passed'] for x in first),
                'full_repeat_spread_octaves':spread,'prefix_w_infinity_octaves':prefix_w,'maximum_current_census_difference':current_delta,
                'maximum_entry_elapsed_spread_ms':elapsed,'future_repeat_w_infinity_octaves':future_repeat,'future_prefix_w_infinity_octaves':future_prefix})
    profiles=[]
    for c in sorted({x['content_id'] for x in records}):
        for h in m.m.PREFIXES:
            for rep in range(4):
                rows=[x for x in records if x['content_id']==c and x['prefix']==h and x['repetition']==rep]
                vals=[selected[x['id']]['state']['census_x'] for x in rows if selected[x['id']]]
                complete=len(vals)==4;span=max(vals)-min(vals) if complete else None;sd=st.stdev(vals) if complete else None
                profiles.append({'content':c,'prefix':h,'repetition':rep,'census_values':vals,'range_octaves':span,'sample_sd_octaves':sd,
                    'interval':[min(vals),max(vals)] if complete else None,'passed':complete and span>=1 and sd>=.35})
    overlap=min(x['interval'][1] for x in profiles)-max(x['interval'][0] for x in profiles) if all(x['interval'] for x in profiles) else None
    passed=all(x['passed'] for x in cells+profiles) and overlap is not None and overlap>=.5
    return {'method':method,'passed':passed,'cells':cells,'profiles':profiles,'common_overlap_octaves':overlap,
        'first_tags':sum(x['first_tags'] for x in cells),'future_verified':sum(x['future_verified'] for x in cells),'total_originals':64}

def paired_uncertainty(values):
    if len(values)!=4:return {'estimable_four_pairs':False,'paired_values':describe(values)}
    observed=st.mean(values);null=[st.mean(a*s for a,s in zip(values,signs,strict=True)) for signs in itertools.product((-1,1),repeat=4)]
    return {'estimable_four_pairs':True,'paired_values':describe(values),'exact_two_sided_sign_flip_p':sum(abs(x)>=abs(observed)-1e-12 for x in null)/16,
        'permutation_assignments':16,'minimum_attainable_two_sided_p':.125,'scope':'four paired native contexts; no broad population interval'}

def residuals(records):
    lookup={(x['content_id'],x['input_x'],x['prefix'],x['repetition']):x for x in records};results=[]
    for c in sorted({x['content_id'] for x in records}):
        for level in m.TARGETS:
            for age in m.DESIGN['diagnostic_ages_ms']:
                pairs=[]
                for rep in range(4):
                    a,z=[lookup[c,level,h,rep]['entries'][str(age)] for h in m.m.PREFIXES];sa,sz=a['state'],z['state'];fa,fz=a['future_8s'],z['future_8s']
                    eligible=sa['census_passed'] and sz['census_passed'] and fa['observable'] and fz['observable']
                    checks={'eligible':eligible};baseline=compact=False
                    if eligible:
                        checks.update(current_x=abs(sa['current_x']-sz['current_x'])<=.25,
                            recent_drift=sa['recent_mean_drift_octaves'] is not None and sz['recent_mean_drift_octaves'] is not None and abs(sa['recent_mean_drift_octaves']-sz['recent_mean_drift_octaves'])<=.05,
                            long_contrast=sa['long_drift_octaves'] is not None and sz['long_drift_octaves'] is not None and abs(sa['long_drift_octaves']-sz['long_drift_octaves'])<=.05,
                            direction=sa['last_service_change_direction']==sz['last_service_change_direction'],
                            age=abs(sa['known_service_age_ms']-sz['known_service_age_ms'])<=250,
                            service_6s=sa['service_mean_6s'] is not None and sz['service_mean_6s'] is not None and abs(sa['service_mean_6s']-sz['service_mean_6s'])<=.01,
                            service_16s=sa['service_mean_16s'] is not None and sz['service_mean_16s'] is not None and abs(sa['service_mean_16s']-sz['service_mean_16s'])<=.01)
                        baseline=checks['current_x'];compact=all(checks.values())
                    pairs.append({'repetition':rep,'checks':checks,'B0_matched':baseline,'compact_matched':compact,
                        'current_difference_octaves':sz['current_x']-sa['current_x'] if eligible else None,
                        'future_mean_difference_octaves':fz['mean_x']-fa['mean_x'] if eligible else None,
                        'future_change_residual_octaves':fz['mean_change_from_current']-fa['mean_change_from_current'] if eligible else None,
                        'future_w_infinity_octaves':winf(fa['values_x'],fz['values_x']) if eligible else None,
                        'future_maximum_1s_mean_difference_octaves':max(abs(x-y) for x,y in zip(fa['one_second_mean_x'],fz['one_second_mean_x'],strict=True)) if eligible else None})
                results.append({'content':c,'input_x':level,'age_ms':age,'pairs':pairs,
                    'unconditional_prefix_future_mean':paired_uncertainty([x['future_mean_difference_octaves'] for x in pairs if x['checks']['eligible']]),
                    'B0_matching_count':sum(x['B0_matched'] for x in pairs),'compact_matching_count':sum(x['compact_matched'] for x in pairs),
                    'B0_full_coverage':all(x['B0_matched'] for x in pairs),'compact_full_coverage':all(x['compact_matched'] for x in pairs),
                    'B0_conditional_change_residual':describe([x['future_change_residual_octaves'] for x in pairs if x['B0_matched']]),
                    'compact_conditional_change_residual':describe([x['future_change_residual_octaves'] for x in pairs if x['compact_matched']]),
                    'compact_conditional_future_w_infinity':describe([x['future_w_infinity_octaves'] for x in pairs if x['compact_matched']])})
    return results

def analyze():
    records,gate=project()
    # Store the causal census offset relative to the prospectively fixed grid.
    # Each session's common anchor is recovered from its own qualified phase window.
    for row in records:
        d=m.ROOT/'validation/sessions'/row['id'];common=v.read(d/'phase_windows.json')['phase_windows'][1]['start_ms']+24000
        for item in row['entries'].values():
            item['census_offset_ms']=item['state']['cutoff_ms']-(common+item['age_ms']) if item['state']['census_passed'] else None
    methods={k:primary(records,k) for k in m.DESIGN['state_rules']};res=residuals(records)
    emissions={}
    for method in m.DESIGN['state_rules']:
        emissions[method]=[]
        for age in m.DESIGN['entry_grid_ms']:
            for c in sorted({x['content_id'] for x in records}):
                items=[x['entries'][str(age)] for x in records if x['content_id']==c];tagged=[x for x in items if x['state']['tags'][method]]
                emissions[method].append({'content':c,'age_ms':age,'originals':len(items),'tags':len(tagged),
                    'true_tags':sum(x['future']['passed'] for x in tagged),'false_tags':sum(not x['future']['passed'] for x in tagged)})
    result={'abi':'native_phase_state_m9_analysis_v1','protocol_sha256':v.sha(m.ROOT/'validation/protocol.json'),
        'acquisition_gate_sha256':v.sha(m.ROOT/'validation/mechanism_qualification_gate.json'),'technical_qualified':gate['passed'],
        'methods':methods,'grid_prediction_counts_nested':emissions,'residuals':res,
        'future_verified_D1_onsets':[{'id':x['id'],'content':x['content_id'],'input_x':x['input_x'],'prefix':x['prefix'],'repetition':x['repetition'],
            'onset_ms':x['first_future_verified_D1_ms'],'right_censored_after_ms':x['settling_onset_right_censored_after_ms']} for x in records],
        'late_support':[{'id':x['id'],'content':x['content_id'],'input_x':x['input_x'],'prefix':x['prefix'],'repetition':x['repetition'],'windows':x['late_support']} for x in records],
        'P2_qualified':methods['P2']['passed'],'all_prior_panels_closed':m.old_closed(),'actions':False,'outcomes_read':False,'controller_fitted':False,
        'scope':'fresh native runs; two reused productions; synthetic service in one measurement program; repeated ages nested within originals'}
    v.write(m.ROOT/'validation/phase_state_records.json',records);v.write(m.ROOT/'validation/phase_state_summary.json',result)
    v.write(REPO/'reports/native-phase-state-m9-summary.json',result)
    return {'technical_qualified':gate['passed'],'originals':len(records),'first_prediction_counts':{k:{'tagged':x['first_tags'],'future_verified':x['future_verified'],'qualified':x['passed']} for k,x in methods.items()},
        'B0_four_pair_strata':sum(x['B0_full_coverage'] for x in res),'compact_four_pair_strata':sum(x['compact_full_coverage'] for x in res),'residual_strata':len(res)}

if __name__=='__main__':print(json.dumps(analyze()))
