"""M11 instrumentation gates only: no future stability, matching, QoE or fit."""
from __future__ import annotations
import bisect
import importlib.util
import json
import statistics as st
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m11_registration',REPO/'tools/measure_transport_timing_m11.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v

def describe(values):
    q=sorted(values)
    return {'n':len(q),'minimum':min(q) if q else None,'median':st.median(q) if q else None,
        'p90':q[min(len(q)-1,int(.9*(len(q)-1)))] if q else None,'maximum':max(q) if q else None}

def family(event):
    if event['source']!='rtc_event_log_v2':return None
    if event['kind']=='incoming_rtcp' and event.get('tcc'):return 'transport_cc_arrival'
    if event['kind'] in ('delay_bwe_update','loss_bwe_update'):return 'native_bwe_update'
    if event['kind'] in ('probe_created','probe_success','probe_failure'):return 'pacer_or_probe_events'
    return None

def session(directory):
    browser=v.read(directory/'transport_diagnostic_browser.json');node=v.read(directory/'transport_diagnostic_summary.json')
    node_events=v.read(directory/'transport_diagnostic_events.json');native=v.read(directory/'mechanism_native.json')['records']
    sender=v.read(directory/'sender_observations.json');cutoff=sender['measurement_cutoff_ms']
    windows=v.read(directory/'phase_windows.json')['phase_windows'];start,end=windows[1]['start_ms'],windows[1]['end_ms']
    anchors={a['id']:a for a in browser['anchors']};receipts=browser['receipts'];events=[];checks={}
    checks['no_diagnostic_errors']=not browser['errors'] and not node['errors']
    checks['native_ssrc_identity']=browser['sender_ssrc'] is not None and all(n['outbound_ssrc']==browser['sender_ssrc'] for n in native)
    checks['diagnostic_causal_order']=True;maximum_ack=0
    for receipt in receipts:
        ack=receipt['browser_receive_ms']-receipt['browser_request_ms'];maximum_ack=max(maximum_ack,ack)
        checks['diagnostic_causal_order'] &= 0<=ack<=100 and receipt['status']=='present'
        for event in receipt['events']:
            if event['anchor_id'] is not None:
                anchor=anchors[event['anchor_id']]
                checks['diagnostic_causal_order'] &= (anchor['status']=='present' and anchor['browser_receive_ms']<=event['sender_available_ms']
                    and event['sender_available_ms']==receipt['browser_receive_ms'] and not event['used_future_clock_information'])
            events.append({**event,'snapshot_ack_ms':ack})
    checks['unique_delivered_events']=len({e['id'] for e in events})==len(events)
    main=[r for r in receipts if start<=r['browser_receive_ms']<=end]
    gaps=[b['browser_receive_ms']-a['browser_receive_ms'] for a,b in zip(main,main[1:])]
    checks['snapshot_liveness']=len(main)>=792 and bool(gaps) and max(gaps)<=250
    checks['complete_binary_logs']=bool(node['files']) and all(f['pending_bytes']==0 and f['parsed_bytes']==f['bytes'] for f in node['files'])
    # BWE changes are used solely to quantify how late diagnostic delivery is;
    # this is not a state label or causal response analysis.
    changes=[];previous=None
    for n in native:
        b=n['pair']['availableOutgoingBitrate']
        if b['status']!='present':continue
        if previous is not None and b['value']!=previous:changes.append(n['available_ms'])
        previous=b['value']
    channels={}
    for name in m.DESIGN['required_channels']:
        observed=[e for e in events if family(e)==name and e['sender_identity_status']=='uniquely_linked']
        # Permit startup/probe events before measurement; producer must precede
        # actual cutoff. Never use a post-cutoff receipt as an online event.
        available=[e for e in observed if e['native_event_sender_bounds_ms'] is not None and
            e['native_event_sender_bounds_ms'][1]<=cutoff and e['sender_available_ms']<=cutoff]
        timestamped=[e for e in available if e['clock_uncertainty_ms']<=50 and e['availability_delay_bounds_ms'][0]>=-2 and e['snapshot_ack_ms']<=100]
        fresh=[e for e in timestamped if e['availability_delay_bounds_ms'][1]<=250]
        receipt_times=sorted({e['sender_available_ms'] for e in timestamped});delivery_gaps=[b-a for a,b in zip(receipt_times,receipt_times[1:])]
        producer_times=sorted(e['native_ms'] for e in timestamped);producer_gaps=[b-a for a,b in zip(producer_times,producer_times[1:])]
        count=len(observed);fresh_fraction=len(fresh)/count if count else 0
        minimum=m.DESIGN['minimum_tcc_events'] if name=='transport_cc_arrival' else m.DESIGN['minimum_estimator_events'] if name=='native_bwe_update' else 2
        kinds={k:sum(e['kind']==k for e in observed) for k in sorted({e['kind'] for e in observed})}
        presence=count>=minimum
        if name=='pacer_or_probe_events':presence &= kinds.get('probe_created',0)>=1 and kinds.get('probe_success',0)+kinds.get('probe_failure',0)>=1
        # For the continuous feedback stream, file delivery must have no >1s
        # blackout. Probe lifecycle events themselves are legitimately sparse.
        blackout_ok=bool(receipt_times and max(delivery_gaps,default=0)<=1000) if name=='transport_cc_arrival' else checks['snapshot_liveness']
        late_changes=sum(bisect.bisect_left(changes,e['sender_available_ms'])>bisect.bisect_right(changes,e['native_event_sender_bounds_ms'][1]) for e in timestamped)
        channels[name]={'passed':bool(presence and fresh_fraction>=.9 and blackout_ok),
            'present_with_sender_identity':presence,'observed_events':count,'timestamped_online_events':len(timestamped),
            'fresh_before_sender_cutoff':len(fresh),'fresh_fraction':fresh_fraction,'native_kinds':kinds,
            'native_to_sender_delay_lower_ms':describe([e['availability_delay_bounds_ms'][0] for e in timestamped]),
            'native_to_sender_delay_upper_ms':describe([e['availability_delay_bounds_ms'][1] for e in timestamped]),
            'delivery_batch_gap_ms':describe(delivery_gaps),'producer_event_gap_ms':describe(producer_gaps),
            'no_feedback_delivery_blackout':blackout_ok,'events_first_visible_after_intervening_observed_BWE_change':late_changes,
            'intervening_change_is_not_attributed_causally':True}
    trace=[e for e in node_events if e['source']=='cdp_trace'];pacer=[e for e in trace if e.get('event',{}).get('name','').startswith('TaskQueuePacedSender::')]
    delivered_trace=[e for e in events if e['source']=='cdp_trace' and e['sender_available_ms']<=cutoff]
    summary={'checks':checks,'instrumentation_checks_passed':all(checks.values()),'channels':channels,
        'all_required_channels_passed':all(x['passed'] for x in channels.values()),
        'maximum_snapshot_ack_ms':maximum_ack,'maximum_snapshot_gap_ms':max(gaps,default=None),
        'past_clock_anchors':len(anchors),'valid_past_clock_anchors':sum(a['status']=='present' for a in anchors.values()),
        'maximum_valid_anchor_width_ms':max((a['offset_bounds_ms'][1]-a['offset_bounds_ms'][0] for a in anchors.values() if a['status']=='present'),default=None),
        'rtc_file_inventory':node['files'],'trace':{'events':len(trace),'pacer_events':len(pacer),'native_event_names':sorted({e['event'].get('name','') for e in pacer}),
            'sender_acknowledged_trace_events_during_measurement':len(delivered_trace),'explicit_sender_identity_available':False,
            'trace_envelopes':node['trace_envelopes'],'trace_complete':node['trace_complete']},
        'diagnostic_errors':node['errors'],'browser_errors':browser['errors'],'future_BWE_labels_read':False,
        'receiver_outcomes_read':False,'classifier_fitted':False,'actions':False}
    return summary

def qualify():
    m.verify();root=m.ROOT/'capability';p,index=v.core.check_capture_integrity(root)
    acquisition=v.read(root/'support_clock_transport_gate.json');rows=[]
    for trial,item in zip(p['trials'],index['sessions'],strict=True):
        row={'trial':trial['id'],'content_id':trial['content_id'],'prefix':trial['prefix'],'capture_status':item['status']}
        if item['status']=='sealed':
            try:row.update(session(root/'sessions'/trial['id']))
            except (AssertionError,KeyError,ValueError,TypeError,IndexError) as error:row.update(instrumentation_checks_passed=False,all_required_channels_passed=False,error=f'{type(error).__name__}: {error}')
        else:row.update(instrumentation_checks_passed=False,all_required_channels_passed=False,reason='failed original preserved')
        rows.append(row)
    passed=acquisition['passed'] and all(r['instrumentation_checks_passed'] and r['all_required_channels_passed'] for r in rows)
    report={'abi':'native_transport_timing_m11_channel_qualification_v1','protocol_sha256':v.sha(root/'protocol.json'),
        'acquisition_gate_sha256':v.sha(root/'support_clock_transport_gate.json'),'acquisition_passed':acquisition['passed'],
        'passed':passed,'originals':len(rows),'sessions':rows,'all_required_channels_repeatably_observed_online':passed,
        'development_allowed':passed,'development_opened':False,'future_BWE_labels_read':False,'receiver_outcomes_read':False,
        'fit_predictor':False,'controller_fitted':False,'old_panels_closed':m.old_closed()}
    v.write(root/'transport_channel_qualification.json',report);v.write(REPO/'reports/native-transport-timing-m11-channel-qualification.json',report)
    return {'acquisition_passed':acquisition['passed'],'required_channels_qualified':passed,'development_allowed':passed,
        'channels_by_original':[{k:r.get(k) for k in ('trial','instrumentation_checks_passed','all_required_channels_passed','error')} for r in rows]}

if __name__=='__main__':print(json.dumps(qualify()))
