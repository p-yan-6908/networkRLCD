"""Frozen M8 support-only response metrics and prospective settling-rule selection.

Future plateau samples are verification labels, never state inputs. No delivery,
QoE, encoder action value, learned controller or previous validation telemetry.
"""
from __future__ import annotations
import importlib.util
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m8_analysis_registration',REPO/'tools/measure_bwe_transients_m8.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
v=m.v


def valid(p,eligible=False):
    return p['valid'] and p['bwe']>0 and (not eligible or 240000<=p['bwe']<=3800000)


def xs(points):return [math.log2(p['bwe']/500000) for p in points]


def section(points,lo,hi):return [p for p in points if lo<p['ms']<=hi]


def drift(points,cutoff):
    a,b=section(points,cutoff-1000,cutoff),section(points,cutoff-2000,cutoff-1000)
    return st.mean(xs(a))-st.mean(xs(b)) if min(len(a),len(b))>=7 and all(valid(p,True) for p in a+b) else None


def causal_state(points,events,endpoint):
    q=m.parent.census(points,endpoint)
    if not q['passed']:return {'census_passed':False,'baseline_tag':False,'dynamic_tag':False}
    cutoff=q['cutoff_ms'];history=section(points,cutoff-3000,cutoff)
    known=[e for e in events if e['browser_ack_ms']<=cutoff]
    assert known and max(p['ms'] for p in history)<=cutoff
    last_change=known[0]
    for e in known[1:]:
        if e['service_mbps']!=last_change['service_mbps']:last_change=e
    service=known[-1]['service_mbps'];age=cutoff-last_change['browser_ack_ms']
    center=q['instantaneous_x'];recent=xs(history) if all(valid(p,True) for p in history) else []
    d=drift(points,cutoff);gaps=[b['ms']-a['ms'] for a,b in zip(history,history[1:])]
    components={'past_three_seconds_eligible':len(history)>=27 and len(recent)==len(history) and bool(gaps) and max(gaps)<=250,
                'bounded_past_trajectory':bool(recent and max(abs(x-center) for x in recent)<=.125+1e-12),
                'small_recent_drift':d is not None and abs(d)<=.05+1e-12,'known_service_constant_three_seconds':age>=3000}
    return {'census_passed':True,'baseline_tag':True,'dynamic_tag':all(components.values()),'components':components,
            'cutoff_ms':cutoff,'census_x':q['x'],'current_x':center,'recent_mean_drift_octaves':d,
            'recent_range_octaves':max(recent)-min(recent) if recent else None,'known_service_mbps':service,
            'known_service_age_ms':age,'last_service_change_direction':last_change['direction'],
            'latest_input_ack_ms':known[-1]['browser_ack_ms'],'latest_feature_sample_ms':max(p['ms'] for p in history)}


def future_truth(points,state,end):
    if not state['census_passed']:return {'passed':False,'reason':'no eligible causal census'}
    cutoff,center=state['cutoff_ms'],state['current_x'];future=section(points,cutoff,end)
    gaps=[b['ms']-a['ms'] for a,b in zip(future,future[1:])]
    observable=bool(future and end-cutoff>=8000 and future[0]['ms']<=cutoff+250 and future[-1]['ms']>=end-250
                    and len(future)>=(end-cutoff)/100*.9 and all(valid(p) for p in future) and bool(gaps) and max(gaps)<=250)
    eligible=observable and all(valid(p,True) for p in future)
    distances=[abs(x-center) for x in xs(future)] if observable else []
    drifts=[drift(points,cutoff+1000*j) for j in range(2,int((end-cutoff)//1000)+1)]
    components={'future_observable':observable,'original_bwe_bounds':eligible,
                'future_in_frozen_caliper':bool(distances and max(distances)<=.125+1e-12),
                'future_drift_at_fixed_seconds':bool(drifts and all(d is not None and abs(d)<=.05+1e-12 for d in drifts))}
    return {'passed':all(components.values()),'components':components,'verification_ms':end-cutoff,
            'maximum_future_distance_octaves':max(distances) if distances else None,
            'maximum_future_absolute_drift_octaves':max(abs(d) for d in drifts if d is not None) if any(d is not None for d in drifts) else None}


def sustained_crossing(points,bounds,pre,sign,threshold,end):
    post=[p for p in points if bounds[1]<=p['ms']<=end and valid(p)]
    consecutive=[];previous_ms=bounds[1]
    for p in post:
        if sign*(math.log2(p['bwe']/500000)-pre)>=threshold:
            if not consecutive:previous_ms=next((q['ms'] for q in reversed(points) if q['ms']<p['ms']),bounds[1])
            consecutive.append(p)
        else:consecutive=[]
        if len(consecutive)>=11 and consecutive[-1]['ms']-consecutive[0]['ms']>=900:
            return {'observed':True,'onset_delay_ms_bounds':[max(0.,previous_ms-bounds[1]),max(0.,consecutive[0]['ms']-bounds[0])],
                    'confirmed_delay_ms':p['ms']-st.mean(bounds),'confirmation_samples':len(consecutive)}
    return {'observed':False,'right_censored_at_ms':end-bounds[1],'onset_delay_ms_bounds':None}


def response(points,event,old_service,new_service,plateau_start):
    bounds=event['browser_applied_ms_bounds'];prepoints=section(points,bounds[0]-1000,bounds[0]);end=plateau_start+23800
    pre_ok=len(prepoints)>=7 and all(valid(p) for p in prepoints)
    if not pre_ok:return {'estimable':False,'reason':'pre-step native BWE window not observable'}
    pre=st.mean(xs(prepoints));delta=math.log2(new_service/old_service) if old_service>0 else None
    post=section(points,bounds[1],end);late=section(points,end-4000,end)
    output={'estimable':True,'pre_x':pre,'service_before_mbps':old_service,'service_after_mbps':new_service,
            'input_log2_step':delta,'input_change':bool(delta),'late_mean_x':st.mean(xs(late)) if late else None,
            'late_range_octaves':max(xs(late))-min(xs(late)) if late else None,
            'late_drift_octaves_per_second':drift(points,end),'late_native_bwe_eligible':bool(late and all(valid(p,True) for p in late)),
            'clock_input_application_width_ms':bounds[1]-bounds[0],'observation_horizon_ms':end-bounds[1]}
    if not delta:
        output.update(natural_drift_from_pre_octaves=output['late_mean_x']-pre,delay=None,fraction_crossings={},overshoot_octaves=None)
        return output
    sign=1 if delta>0 else -1;target=pre+delta
    output['direction']='rise' if sign>0 else 'fall'
    output['input_scaled_reference_x']=target
    output['delay']=sustained_crossing(points,bounds,pre,sign,.05,end)
    output['fraction_crossings']={str(f):sustained_crossing(points,bounds,pre,sign,abs(delta)*f,end) for f in (.1,.5,.9)}
    a,b=output['fraction_crossings']['0.1'],output['fraction_crossings']['0.9']
    output['t10_to_t90_ms_bounds']=([max(0.,b['onset_delay_ms_bounds'][0]-a['onset_delay_ms_bounds'][1]),
                                      max(0.,b['onset_delay_ms_bounds'][1]-a['onset_delay_ms_bounds'][0])] if a['observed'] and b['observed'] else None)
    output['overshoot_octaves']=max([0.]+[sign*(x-target) for x in xs(post)])
    output['late_error_from_input_scaled_reference_octaves']=output['late_mean_x']-target
    return output


def project():
    m.verify();root=m.ROOT/'characterization';gate=v.read(root/'mechanism_qualification_gate.json')
    assert gate['passed'],'all support/instrumentation originals must qualify before system identification'
    p,index=v.core.check_capture_integrity(root);by_id={x['trial']:x for x in gate['sessions']};records=[]
    for trial in p['trials']:
        d=root/'sessions'/trial['id'];sender=v.read(d/'sender_observations.json');points=m.parent.points_for(sender)
        windows=v.read(d/'phase_windows.json')['phase_windows'];start=windows[1]['start_ms'];row=by_id[trial['id']]
        control=v.read(d/'system_id_evidence.json');sequence=trial['service_sequence_mbps']
        events=[{**row['input_fidelity']['service_events'][0],'service_mbps':sequence[0],'direction':0}]
        for j,c in enumerate(control['commands'],1):
            events.append({**row['input_fidelity']['service_events'][j],'service_mbps':sequence[j],
                           'direction':1 if sequence[j]>sequence[j-1] else -1 if sequence[j]<sequence[j-1] else 0})
        # This is the registered controlled-input history; feature functions filter by ack time.
        panel=v.read(root/trial['panel']);old_service=panel['episodes'][0]['schedule'][0][3][-1]
        for j,level in enumerate(sequence):
            onset=start+j*24000;end=onset+23800
            candidates={}
            for age in m.DESIGN['candidate_ages_ms']:
                state=causal_state(points,events,onset+age);truth=future_truth(points,state,end)
                candidates[str(age)]={'state':state,'future':truth}
            settling=[]
            for age in m.DESIGN['settling_age_grid_ms']:
                state=causal_state(points,events,onset+age)
                if state['dynamic_tag'] and future_truth(points,state,end)['passed']:settling.append(age)
            diagnostic={}
            for age in m.DESIGN['diagnostic_age_grid_ms']:
                q=m.parent.census(points,onset+age)
                diagnostic[str(age)]={'passed':q['passed'],'x':q.get('x'),'recent_drift':drift(points,q['cutoff_ms']) if q['passed'] else None}
            records.append({**{k:trial[k] for k in ('id','content_id','prefix','input_order','repetition','block')},
                'plateau':j,'service_mbps':level,'predecessor_service_mbps':old_service,'candidates':candidates,
                'diagnostic_windows':diagnostic,'response':response(points,row['input_fidelity']['service_events'][j],old_service,level,onset),
                'first_verified_settling_age_ms':min(settling) if settling else None,'settling_onset_censored_after_ms':None if settling else 15000,
                'settling_verification_horizon_plateau_ms':23800})
            old_service=level
    assert len(records)==64
    return records,gate


def describe(values):
    return {'n':len(values),'mean':st.mean(values) if values else None,'median':st.median(values) if values else None,
            'minimum':min(values) if values else None,'maximum':max(values) if values else None,'values':values}


def contrasts(records):
    lookup={(x['content_id'],x['prefix'],x['input_order'],x['repetition'],x['plateau']):x for x in records}
    results=[]
    for content in sorted({x['content_id'] for x in records}):
        for plateau in (1,2,3):
            for age in (6000,12000,18000,23000):
                for order in m.ORDERS:
                    values=[]
                    for rep in (0,1):
                        a,b=[lookup[content,prefix,order,rep,plateau]['diagnostic_windows'][str(age)] for prefix in m.PREFIXES]
                        if a['passed'] and b['passed']:values.append(b['x']-a['x'])
                    results.append({'kind':'initial_prefix_descending_minus_ascending','content':content,'plateau':plateau,'age_ms':age,'order':order,
                                    'paired_repetition_differences_octaves':describe(values)})
                for prefix in m.PREFIXES:
                    values=[]
                    for rep in (0,1):
                        a,b=[lookup[content,prefix,order,rep,plateau]['diagnostic_windows'][str(age)] for order in m.ORDERS]
                        if a['passed'] and b['passed']:values.append(b['x']-a['x'])
                    results.append({'kind':'initial_service_high_minus_low_under_common_later_service','content':content,'plateau':plateau,'age_ms':age,'prefix':prefix,
                                    'paired_repetition_differences_octaves':describe(values)})
    return results


def select(records):
    screens={}
    for age in m.DESIGN['candidate_ages_ms']:
        key=str(age);observations=[x['candidates'][key] for x in records]
        cells={}
        for content in sorted({x['content_id'] for x in records}):
            for level in (.5,1.5):
                members=[x for x in records if x['content_id']==content and x['service_mbps']==level]
                values=[x['candidates'][key]['state'].get('current_x') for x in members]
                complete=all(x is not None for x in values)
                spread=max(values)-min(values) if complete else None
                arms=[[x['candidates'][key]['state'].get('current_x') for x in members if x['prefix']==prefix] for prefix in m.PREFIXES]
                winf=max(abs(a-b) for a,b in zip(sorted(arms[0]),sorted(arms[1]),strict=True)) if complete else None
                cells[content+'__'+str(level)]={'occurrences_nested_within_runs':len(members),'full_spread_octaves':spread,'prefix_w_infinity_octaves':winf,
                                               'passed':bool(complete and spread<=.25+1e-12 and winf<=.25+1e-12)}
        biases=[x['candidates'][key]['state']['current_x']-math.log2(x['service_mbps']/.5) for x in records if x['candidates'][key]['state']['census_passed']]
        bias_spread=max(biases)-min(biases) if len(biases)==64 else None
        # Equal weight to the four content/service calibration cells; never count phases as independent sources.
        cell_bias=[]
        for content in sorted({x['content_id'] for x in records}):
            for level in (.5,1.5):
                vals=[x['candidates'][key]['state']['current_x']-math.log2(level/.5) for x in records if x['content_id']==content and x['service_mbps']==level and x['candidates'][key]['state']['census_passed']]
                if vals:cell_bias.append(st.median(vals))
        bias=st.median(cell_bias) if len(cell_bias)==4 else None
        baseline=sum(x['state']['baseline_tag'] for x in observations);dynamic=sum(x['state']['dynamic_tag'] for x in observations)
        true_baseline=sum(x['state']['baseline_tag'] and x['future']['passed'] for x in observations)
        true_dynamic=sum(x['state']['dynamic_tag'] and x['future']['passed'] for x in observations)
        passed=dynamic==true_dynamic==64 and all(c['passed'] for c in cells.values()) and bias_spread is not None and bias_spread<=.25+1e-12
        inputs=[.5*2**target/2**bias for target in m.parent.TARGETS] if bias is not None else []
        passed=passed and bool(inputs) and all(.2<=u<=5 for u in inputs)
        screens[key]={'baseline_tags':baseline,'dynamic_tags':dynamic,'true_baseline_tags':true_baseline,'true_dynamic_tags':true_dynamic,
            'baseline_false_tags':baseline-true_baseline,'dynamic_false_tags':dynamic-true_dynamic,
            'native_runs':16,'nested_occurrences':64,'full_retention_required':True,'cells':cells,'full_bias_spread_octaves':bias_spread,
            'equal_cell_median_log2_bias':bias,'proposed_constant_services_mbps':inputs,'passed':bool(passed)}
    chosen=next((age for age in m.DESIGN['candidate_ages_ms'] if screens[str(age)]['passed']),None)
    result={'abi':'native_bwe_transients_m8_selection_v1','candidates':screens,'selected_age_ms':chosen,'eligible':chosen is not None,
            'native_common_support_established':False,'future_action_stage_enabled':False,'controller_fitted':False}
    if chosen is not None:
        q=screens[str(chosen)];result.update(selected_log2_bias=q['equal_cell_median_log2_bias'],conditioning_duration_ms=chosen+9000,
            constant_services_mbps=q['proposed_constant_services_mbps'],next_validation_must_be_registered_and_committed_before_native_capture=True)
    else:result['next_validation_status']='128 fresh allocations untouched; no duration or executable conditioning schedule can be derived under the frozen rule'
    return result


def analyze():
    records,gate=project();selection=select(records)
    responses={}
    for content in sorted({x['content_id'] for x in records}):
        for prefix in m.PREFIXES:
            for order in m.ORDERS:
                for plateau in range(4):
                    items=[x for x in records if (x['content_id'],x['prefix'],x['input_order'],x['plateau'])==(content,prefix,order,plateau)]
                    key='__'.join(map(str,(content,prefix,order,plateau)))
                    responses[key]={'original_runs':2,'per_run_response':[x['response'] for x in items],
                        'verified_settling_ages_ms':[x['first_verified_settling_age_ms'] for x in items],
                        'settling_unverified_originals':sum(x['first_verified_settling_age_ms'] is None for x in items)}
    asymmetry=[]
    for trial in sorted({x['id'] for x in records}):
        fall=next(x['response'] for x in records if x['id']==trial and x['plateau']==2)
        rise=next(x['response'] for x in records if x['id']==trial and x['plateau']==3)
        a,b=fall.get('fraction_crossings',{}).get('0.5',{}),rise.get('fraction_crossings',{}).get('0.5',{})
        difference=None
        if a.get('observed') and b.get('observed'):
            difference=[b['onset_delay_ms_bounds'][0]-a['onset_delay_ms_bounds'][1],b['onset_delay_ms_bounds'][1]-a['onset_delay_ms_bounds'][0]]
        asymmetry.append({'trial':trial,'rise_minus_fall_t50_ms_bounds':difference,'fall_observed':a.get('observed',False),'rise_observed':b.get('observed',False)})
    result={'abi':'native_bwe_transients_m8_summary_v1','characterization_gate_sha256':v.sha(m.ROOT/'characterization/mechanism_qualification_gate.json'),
        'design_sha256':v.sha(m.CONFIG),'fresh_native_runs':16,'source_contents':2,'measurement_program_replication':False,
        'nested_plateau_occurrences':64,'responses_by_content_history_order_phase':responses,'rise_fall_asymmetry_per_run':asymmetry,
        'history_contrasts':contrasts(records),'selection':selection,'settling_unverified_occurrences':sum(x['first_verified_settling_age_ms'] is None for x in records),
        'scope':'Development system identification on controlled service. No population pooling; repeated phases remain nested within their native runs.',
        'causal_feature_future_leakage':False,'future_samples_used_only_as_registered_verification_labels':True,
        'old_m7ra_panel_opened':False,'new_next_allocation_native_sessions_started':0,'delivery_qoe_action_outcomes_read':False,'controller_fitted':False,
        'native_common_support_established':False,'action_value_estimated':False}
    v.write(m.ROOT/'characterization/step_response_records.json',records)
    v.write(m.ROOT/'characterization/system_id_summary.json',result)
    v.write(m.ROOT/'characterization/settling_selection.json',selection)
    v.write(REPO/'reports/native-bwe-transients-m8-summary.json',result)
    v.write(REPO/'reports/native-bwe-transients-m8-selection.json',selection)
    return {'native_runs':16,'nested_occurrences':64,'selected_age_ms':selection['selected_age_ms'],'candidate_qualified':selection['eligible'],
            'settling_unverified_occurrences':result['settling_unverified_occurrences'],'next_untouched_allocations':128,'controller_fitted':False}


if __name__=='__main__':print(json.dumps(analyze()))
