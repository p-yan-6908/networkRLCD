"""Report supported diagnostic routes and zero-peer metadata controls only."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m11r_alternatives',REPO/'tools/measure_transport_timing_m11r.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v
PROBES={'console':'4b7cd10f05b0ee6786cafd55239ed7b129df4785',
 'perfetto':'971af241564b002b3eda704985f4533a4ee9cdef',
 'perfetto-temp':'369dcad70ac1b285157eb1a073899f60d6f550e6'}

def report():
    m.verify();root=m.ROOT/'capability';v.core.check_capture_integrity(root)
    rows=[]
    for name,commit in PROBES.items():
        directory=v.CACHE/f'native-transport-timing-m11r-{name}-probe';p=v.read(directory/'probe.json')
        assert p['native_sessions_created']==0 and not p['receiver_outcomes_read'] and p['policy_unchanged']
        marker_names=[x['name'] for x in p['artificial_markers']];files={}
        for file in sorted(directory.iterdir()):
            if not file.is_file():continue
            metadata={'size':file.stat().st_size,'sha256':v.sha(file)}
            if file.name not in ('probe.json','stderr_chunks.json','config.pb'):
                data=file.read_bytes();metadata['artificial_marker_names_in_final_file']=[n for n in marker_names if n.encode() in data]
            files[file.name]=metadata
        rows.append({'probe':name,'registration_commit':commit,'error':p['error'],
            'marks_acknowledged':len(p['marks']),'online_marker_observations':p['artificial_markers'],
            'files':files,'native_contexts':0,'receiver_outcomes_read':False,'policy_unchanged':True,
            'process_exit_code':p.get('process_exit_code'),'process_signal_code':p.get('process_signal_code'),
            'process_exit_status_recorded':'process_exit_code' in p})
    references=v.CACHE/'native-transport-timing-m11r-additional-references'
    schemas=[]
    for directory in sorted((root/'sessions').iterdir()):
        # Strictly names/argument-key schema of the predeclared transport families.
        # No receiver event, argument value, frame timestamp or outcome is read.
        events=v.read(directory/'transport_diagnostic_events.json');names={}
        for event in events:
            if event['source']!='cdp_trace':continue
            e=event['event'];name=e.get('name','')
            if name!='TransportFeedback::Parse' and not name.startswith('TaskQueuePacedSender::'):continue
            row=names.setdefault(name,{'count':0,'argument_keys':set()});row['count']+=1;row['argument_keys'].update(e.get('args',{}))
        schemas.append({'original':directory.name,'transport_trace_schemas':{n:{'count':x['count'],
            'argument_keys':sorted(x['argument_keys'])} for n,x in names.items()}})
    result={'abi':'native_transport_timing_m11r_supported_alternatives_v1','metadata_probes':rows,
        'source_files':{str(p.relative_to(references)):{'size':p.stat().st_size,'sha256':v.sha(p)}
            for p in sorted(references.rglob('*')) if p.is_file()},'transport_trace_schemas':schemas,
        'native_gate_reclassified':False,'complete_required_channel_set_qualified':False,
        'development_opened':False,'future_BWE_labels_read':False,'receiver_outcomes_read':False,
        'console_interpretation':'Failed before DevTools; no marker injected. Pinned multiprocess Perfetto config rejects ECHO_TO_CONSOLE with NOTREACHED. Exact process exit status was not captured by that frozen probe.',
        'direct_file_interpretation':'Both marks acknowledged; requested file absent. A retained temporary file contains both markers only in the final inventory; online visibility of that file was not measured.',
        'temporary_file_repair_interpretation':'Both marks acknowledged; actual Chromium temporary file observed, but neither marker is in the live or final trace. Recording control did not reproduce; no latency claim or native qualification follows.',
        'private_api':{'name':'webrtcLoggingPrivate.startEventLogging','immediate_output_parameter':'outputPeriodMs=0',
            'normal_page_api_present':False,'required_permission':'explicit allowlisted extension identity',
            'approved_extension_access_available':False,'allowlist_bypassed':False},
        'external_proxy_equivalence':{
            'relay_or_socket_receipt':'Some SRTCP common-header bytes may be visible; relay enqueue/forward or socket arrival is not browser decryption, transport-feedback parse/dispatch or estimator consumption time.',
            'RTP_bursts':'Packet spacing mixes encoder production, pacing, retransmission and probing; no native probe cluster/active state is identified by a burst alone.',
            'getStats_or_RTT_age':'Polled BWE changes and RTT-measurement detection age do not identify every internal update or transport-CC arrival.',
            'offline_logs':'Producer timestamps and later learned source identity cannot be backdated into the sender information set.',
            'equivalent_proxy_qualified':False},
        'boundary':'No supported complete, uniquely attributed and sufficiently fresh transport-control channel set established in this binary/fixture. This is not a test that transport timing is irrelevant.',
        'fine_grained_native_conditional_action_value_identified':False,
        'native_common_support_established':False,'predictor_state_search_actions_or_controller':False}
    v.write(REPO/'reports/native-transport-timing-m11r-supported-alternatives.json',result)
    return {'metadata_originals':len(rows),'native_contexts_created_by_metadata':0,
        'required_channels_qualified':False,'development_opened':False}

if __name__=='__main__':print(json.dumps(report()))
