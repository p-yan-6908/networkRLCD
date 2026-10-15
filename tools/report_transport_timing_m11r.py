"""Describe M11R diagnostic availability only; never compute future BWE labels."""
from __future__ import annotations
import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m11r_diagnostic_reporting',REPO/'tools/qualify_transport_timing_m11r.py')
q=importlib.util.module_from_spec(s);s.loader.exec_module(q);m=q.m;v=m.v
REGISTRATION='86ac6f45ffc96e19bb7320c1a9f3f2d14810133c'

def report():
    m.verify();root=m.ROOT/'capability';protocol,index=v.core.check_capture_integrity(root)
    qualification=v.read(root/'transport_channel_qualification.json');acquisition=v.read(root/'support_clock_transport_gate.json')
    assert qualification['protocol_sha256']==v.sha(root/'protocol.json')
    assert qualification['acquisition_gate_sha256']==v.sha(root/'support_clock_transport_gate.json')
    rows=[]
    for trial,item,gate in zip(protocol['trials'],index['sessions'],qualification['sessions'],strict=True):
        row={'original':trial['id'],'content_id':trial['content_id'],'prefix':trial['prefix'],
            'capture_status':item['status'],'instrumentation_checks_passed':gate.get('instrumentation_checks_passed',False),
            'required_channels_passed':gate.get('all_required_channels_passed',False),'channels':gate.get('channels',{})}
        if item['status']!='sealed':
            rows.append(row);continue
        directory=root/'sessions'/trial['id']
        b=v.read(directory/'transport_diagnostic_browser.json');n=v.read(directory/'transport_diagnostic_summary.json')
        events=v.read(directory/'transport_diagnostic_events.json');sender=v.read(directory/'sender_observations.json')
        start,cutoff=sender['measurement_start_ms'],sender['measurement_cutoff_ms']
        delivered=[e for receipt in b['receipts'] for e in receipt['events'] if e['sender_available_ms']<=cutoff]
        native=[e for e in delivered if e['source']=='rtc_event_log_v2' and e['sender_identity_status']=='uniquely_linked']
        primary=[f for f in n['files'] if b['sender_ssrc'] in f['send_ssrcs']]
        row['direct_sender_binding']={'live_ssrc':b['sender_ssrc'],'matching_files':len(primary),
            'logged_configuration_ssrcs':sorted({s for f in primary for s in f['config_send_ssrcs']}),
            'exact_outgoing_header_ssrcs':sorted({s for f in primary for s in f['send_ssrcs']}),
            'filename_order_used':False,'future_identity_used':False}
        row['online_rtc_kinds']=dict(Counter(e['kind'] for e in native))
        row['rtc_available_batch_times_from_measurement_start_ms']=sorted({e['sender_available_ms']-start for e in native})
        row['first_sender_identified_rtc_receipt_from_measurement_start_ms']=min((e['sender_available_ms']-start for e in native),default=None)
        row['trace']=gate['trace']
        verbose=[e for e in events if e['source']=='chrome_verbose']
        verbose_online=[e for e in delivered if e['source']=='chrome_verbose']
        updates=[e for e in verbose_online if e['kind']=='verbose_bwe_update']
        timestamped=[e for e in updates if e['availability_delay_bounds_ms'] is not None]
        row['verbose']={'captured_events':len(verbose),'sender_acknowledged_events':len(verbose_online),
            'kinds':dict(Counter(e['kind'] for e in verbose)),
            'source_timestamped_update_events':len(timestamped),
            'native_to_sender_delay_upper_ms':q.describe([e['availability_delay_bounds_ms'][1] for e in timestamped]),
            'fresh_update_events_250ms':sum(e['availability_delay_bounds_ms'][1]<=250 for e in timestamped),
            'explicit_sender_identity_events':sum(e['sender_identity_status']=='uniquely_linked' for e in verbose_online),
            'native_tcc_arrival_schema_exposed':False,'native_probe_identity_schema_exposed':False,
            'unknown_generation_time_events':sum(e['native_ms'] is None for e in verbose_online),
            'unknown_identity_retained':True}
        row['clock_and_receipt']={k:gate[k] for k in ('past_clock_anchors','valid_past_clock_anchors',
            'maximum_valid_anchor_width_ms','maximum_snapshot_ack_ms','maximum_snapshot_gap_ms')}
        rows.append(row)
    passed=qualification['passed']
    result={'abi':'native_transport_timing_m11r_reporting_v1','scientific_registration_commit':REGISTRATION,
        'protocol_sha256':v.sha(root/'protocol.json'),'capture_index_sha256':v.sha(root/'capture_index.json'),
        'acquisition_gate_sha256':v.sha(root/'support_clock_transport_gate.json'),
        'channel_gate_sha256':v.sha(root/'transport_channel_qualification.json'),
        'primary_originals':len(rows),'acquisition_passed':acquisition['passed'],
        'classification':'qualified transport channels' if passed else 'transport-control causal-availability instrumentation failure',
        'required_channels_qualified':passed,'sessions':rows,'development_allowed':passed,'development_opened':False,
        'future_BWE_labels_read':False,'receiver_outcomes_read':False,'state_search':False,
        'predictor_or_controller_fitted':False,'actions_opened':False,
        'native_common_support_established':False,'prior_qualified_failures_reclassified':False,
        'supported_routes_attempted':['public local RTC event log','DevTools tracing ReportEvents','targeted v1 WebRTC stderr'],
        'missing_capability':'Repeated uniquely attributed native transport-CC/probe/estimator events available within the frozen sender causal deadline',
        'external_proxy_equivalence_established':False,'transport_timing_irrelevance_inferred':False,
        'fine_grained_native_conditional_action_value_identified':False,'old_closed_panels':m.old_closed()}
    v.write(REPO/'reports/native-transport-timing-m11r-reporting.json',result)
    return {'classification':result['classification'],'acquisition_passed':result['acquisition_passed'],
        'required_channels_qualified':passed,'originals':len(rows),'development_opened':False}

if __name__=='__main__':print(json.dumps(report()))
