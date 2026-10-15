"""M10R preregistered causal mechanism instrumentation; fresh support data only."""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m10_qualified_m9r',REPO/'tools/measure_phase_state_m9r.py')
parent=importlib.util.module_from_spec(s);s.loader.exec_module(parent)
v=parent.v
ROOT=v.CACHE/'native-mechanism-observability-m10r'
CONFIG=REPO/'configs/native_mechanism_observability_m10r.json'
FREEZE=REPO/'data/native-m10r/prior-freeze-sha256.json'
ANCHOR='1037fb924d56ce035f002d33892282225a311540'
SEED=2026101602
RECORDER=REPO/'benchmarks/native_m10r/mechanism_episode_m10r.mjs'
DESIGN={'main_ms':88000,'initial_ms':24000,'common_ms':64000,'service_mbps':[.5,.5*2**1.5],
 'qualification_originals':4,'development_originals':8,'development_repeats_per_history':2,
 'native_poll_ms':25,'relay_poll_ms':100,'maximum_gap_ms':250,'maximum_ack_ms':100,
 'minimum_relay_main_samples':792,'minimum_native_main_samples':3168,'minimum_channel_fraction':.9,
 'minimum_counter_advances_common':10,'conservation_tolerance_bytes':1e-5,
 'landmarks_ms':parent.DESIGN['diagnostic_ages_ms'],'entry_grid_ms':parent.DESIGN['entry_grid_ms'],
 'future_end_ms':63800,'mechanism_history_ms':6000,'all_originals_required':True,'retries':0,
 'raw_budget_bytes':600000000,'incremental_external_budget_bytes':2000000000,
 'online_clock_fit':False,'receiver_outcomes_read':False,'fit_predictor':False,'controller_fitted':False,
 'original_state_gates':parent.DESIGN['unchanged_state_gates'],
 'contrast_resolution':{'queue_equivalent_ms':10,'oldest_queue_ms':10,'reverse_queue_equivalent_ms':10,
  'served_bps_octaves':.125,'offered_bps_octaves':.125,'send_bps_octaves':.125,'target_bps_octaves':.125,
  'rtcp_rtt_ms':10,'observed_feedback_age_upper_ms':100,'encode_ms_per_frame':1,
  'encoded_fps':1,'send_delay_ms_per_packet':1,'cap_bps':0}}
SOURCES=['tools/measure_mechanism_observability_m10r.py','tools/analyze_mechanism_observability_m10r.py',
 'benchmarks/native_m10r/mechanism_episode_m10r.mjs','benchmarks/native_m10r/mechanism_observer_m10r.mjs',
 'docs/NATIVE_MECHANISM_OBSERVABILITY_M10R_PLAN.md','data/native-m10r/prior-freeze-sha256.json',
 'reports/native-mechanism-observability-m10r-preflight.json']

def old_closed():
    return {**parent.old_closed(),'M10_development_unopened':not (v.CACHE/'native-mechanism-observability-m10/development/sessions').exists(),
        'M10_development_protocol_sha256':v.sha(REPO/'configs/native_mechanism_observability_m10_development.json')}

def inventory():return {**parent.inventory(),**{n:v.sha(REPO/n) for n in SOURCES}}

def activate():v.core.source_inventory=inventory

def prepare():
    assert not ROOT.exists() and not CONFIG.exists(),'preserve M10R'
    parent.verify();assets=parent.m.assets_verified()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',ANCHOR],cwd=REPO,text=True).splitlines()
    v.write(FREEZE,{'anchor_commit':ANCHOR,'files':{n:v.sha(REPO/n) for n in names},'old_closed':old_closed()})
    assert shutil.disk_usage(v.CACHE).free>=3000000000
    profile=next(p for p in assets['network_profiles'] if p['profile_id']=='att_lte_driving_2016-uplink-lower')
    stages={}
    for stage,nreps in [('instrumentation',1),('development',2)]:
        root=ROOT/stage;rng=random.Random(SEED+(stage=='development'));trials=[]
        contexts=[]
        for rep in range(nreps):
            for c in rng.sample(assets['content_sources'],2):
                block=[(c,rep,h) for h in parent.m.PREFIXES];rng.shuffle(block);contexts.extend(block)
        for i,(c,rep,h) in enumerate(contexts):
            tid=f'm10r-mechanism-{stage[0]}-{i:03d}-support';pair=f'm10r-{stage[0]}-{c["content_id"]}-r{rep}'
            early=sorted(profile['rates_mbps'][:10],reverse=h==parent.m.PREFIXES[1]);sequence=DESIGN['service_mbps']
            panel=v.panel_for(tid,c,profile,pair,parent.m.PREFIXES.index(h),SEED,True);e=panel['episodes'][0]
            e.update(support_poll_ms=25,support_initial_bwe_kbps=1200,setup_delay_ms=0,
                system_id_sequence_mbps=sequence,video_segment=[0,130000],episode_timeout_s=150,
                schedule=[[early[0],'block_0',10000,early],[sequence[0],'block_1',88000,[sequence[0]]],
                          [profile['rates_mbps'][10],'block_2',12600,profile['rates_mbps'][10:22]]])
            panel['episode_timeout_s']=150
            panel['measurement_recipe'].update(scientific_role='M10R fresh causal mechanism observability only',
                action_ratios=[],instrumentation_version='M10R',service_sources=assets['input_separation'])
            relative=f'panels/{tid}.json';v.write(root/relative,panel)
            trials.append({'id':tid,'condition':'micro','panel':relative,'panel_sha256':v.sha(root/relative),
                'pair_id':pair,'pair_slot':parent.m.PREFIXES.index(h),'repetition':rep,'content_id':c['content_id'],
                'prefix':h,'input_x':1.5,'target_x':1.5,'input_order':'rise','service_sequence_mbps':sequence,
                'setup_delay_ms':0,'support_only':True,'network_family':profile['family_id'],
                'network_profile_id':profile['profile_id'],'block':c['content_id']+'__'+str(rep),'cell_cluster':c['content_id']})
        p=v.protocol_for(root,trials,'development',SEED)
        p.update(abi='native_mechanism_observability_m10r_v1',stage=stage,anchor_commit=ANCHOR,design=DESIGN,
            source_hashes=inventory(),source_manifest_sha256=v.sha(parent.m.ASSETS),
            scientific_role='Fresh support-only causal observability, receiver outcomes closed',
            source_separation=assets['independence']+' '+assets['input_separation'],
            randomization={'seed':SEED+(stage=='development'),'unit':'prefix pair within content/repetition block'},
            analysis={'outcomes_read':False,'fit_or_promote_controller':False,'fit_predictor':False},capture_timeout_seconds=170)
        p['trace_replay'].update(phase_duration_ms=[10000,88000,12600],measured_ticks=22,source_ticks=22,
            synthetic_service_settings=2,tick_tolerance_ms=150)
        v.seal(root,p);config=REPO/f'configs/native_mechanism_observability_m10r_{stage}.json';v.write(config,p)
        stages[stage]={'protocol_sha256':v.sha(root/'protocol.json'),'committed_protocol':str(config.relative_to(REPO)),
            'sessions':len(trials)}
    v.write(CONFIG,{'abi':'native_mechanism_observability_m10r_design_v1','stages':stages,'design':DESIGN,
        'source_hashes':inventory(),'prior_freeze_sha256':v.sha(FREEZE),'development_untouched':True,'no_action_stage':True})
    return verify()

def verify():
    config=v.read(CONFIG);assert config['design']==DESIGN and config['source_hashes']==inventory()
    assert config['prior_freeze_sha256']==v.sha(FREEZE)
    freeze=v.read(FREEZE)
    for name,checksum in freeze['files'].items():assert v.sha(REPO/name)==checksum,name
    assert old_closed()==freeze['old_closed']
    parent.m.assets_verified()
    for stage,meta in config['stages'].items():
        root=ROOT/stage;p=v.read(root/'protocol.json')
        assert v.sha(root/'protocol.json')==v.sha(REPO/meta['committed_protocol'])==meta['protocol_sha256']==(root/'protocol.sha256').read_text().split()[0]
        assert p['source_hashes']==inventory() and p['design']==DESIGN
        assert len(p['trials'])==meta['sessions']==(4 if stage=='instrumentation' else 8)
        assert p['randomized_order']==[t['id'] for t in p['trials']]
        for t in p['trials']:
            assert v.sha(root/t['panel'])==t['panel_sha256'];panel=v.read(root/t['panel'])
            assert v.sha(Path(panel['video_source']['path']))==panel['video_source']['sha256']
            assert t['support_only'] and t['service_sequence_mbps']==DESIGN['service_mbps']
    activate()
    return {'verified':True,'prior_files_unchanged':len(freeze['files']),'old_panels_closed':True,
        'instrumentation_originals':4,'development_originals':8,'controller_fitted':False}

def field_present(row,name):return row.get(name,{}).get('status')=='present'

def mechanism_gate(d,technical):
    native=v.read(d/'mechanism_native.json');ns=native['records']
    br=v.read(d/'mechanism_relay_browser.json');rs=br['records'];node=v.read(d/'mechanism_relay_node.json')
    sender=v.read(d/'sender_observations.json');decisions=sender['decisions'];windows=v.read(d/'phase_windows.json')['phase_windows']
    start,end=windows[1]['start_ms'],windows[1]['end_ms'];common=start+24000
    _,_,origin,vertices=parent.clocks(d)
    receipt={r['sequence']:r for r in rs};checks={}
    persist=v.read(d/'mechanism_persistence_browser.json');node_persist=v.read(d/'mechanism_persistence_node.json')
    posted=v.read(d/'mechanism_persistence_browser_posted.json');drain=v.read(d/'terminal_drain.json')
    plo,phi=v.core.mapped_browser_range(node_persist['node_persisted_ms'],origin,vertices)
    checks['persistence_before_terminal_drain']=(persist==posted and persist['readback']==node_persist and
        persist['measurement_cutoff_ms']<persist['browser_request_ms']<=persist['browser_receive_ms']<drain['browser_send_ms'] and
        persist['connection_a']==persist['connection_b']=='closed' and
        persist['browser_request_ms']-1<=plo<=phi<=persist['browser_receive_ms']+1 and
        node_persist['native_records']==len(ns) and node_persist['relay_records']==len(rs))
    checks['no_errors']=not native['errors'] and not br['errors']
    checks['native_inventory']=len(ns)==len(decisions) and all(
        n['stats_request_ms']==s['poll_timing']['request_ms'] and n['stats_response_ms']==s['poll_timing']['response_ms']
        and n['stats_request_ms']<=n['stats_response_ms']<=n['available_ms']<=s['sample_ms']
        and not n['online_clock_mapping_used'] and not n['receiver_qoe_fields_read'] for n,s in zip(ns,decisions,strict=True))
    checks['receipt_only_online']=all(n['latest_relay_sequence'] is None or (
        n['latest_relay_sequence'] in receipt and n['latest_relay_receipt_ms']==receipt[n['latest_relay_sequence']]['browser_receive_ms']
        and n['latest_relay_receipt_ms']<=n['available_ms'] and n['relay_receipt_age_ms']>=0) for n in ns)
    checks['snapshot_copies']=len(rs)==len(node) and all(r['status']=='present' and r['snapshot']==z and r['sequence']==z['sequence']==i+1
        for i,(r,z) in enumerate(zip(rs,node,strict=True)))
    checks['snapshot_causality']=True;maximum_ack=0
    for r in rs:
        z=r['snapshot'];lo,hi=v.core.mapped_browser_range(z['node_snapshot_ms'],origin,vertices)
        ack=r['browser_receive_ms']-r['browser_request_ms'];maximum_ack=max(maximum_ack,ack)
        checks['snapshot_causality'] &= (0<=ack<=100 and z['node_receive_ms']<=z['node_snapshot_ms']<=z['node_send_ms'] and
            r['browser_request_ms']-1<=lo<=hi<=r['browser_receive_ms']+1 and z['observation_mutates_queue'] is False)
    main=[n for n in ns if start<=n['available_ms']<=end];relay=[r for r in rs if start<=r['browser_receive_ms']<=end]
    gaps=[b['browser_receive_ms']-a['browser_receive_ms'] for a,b in zip(relay,relay[1:])]
    checks['relay_coverage']=len(relay)>=792 and bool(gaps) and max(gaps)<=250
    checks['relay_counters']=True;maxconservation=0;previous={}
    cumulative=['offered_packets','offered_wire_bytes','dropped_wire_bytes','served_packets','served_wire_bytes',
        'forwarded_wire_bytes','forwarded_packets','overflow_packets','send_errors','max_queue_wire_bytes','capacity_integral_wire_bytes']
    for r in rs:
        for direction in ('a_to_b','b_to_a'):
            q=r['snapshot'][direction]
            if not isinstance(q,dict):checks['relay_counters']=False;continue
            numeric=[x for key,x in q.items() if key!='conservation_error_bytes']
            checks['relay_counters'] &= all(isinstance(x,(float,int)) and math.isfinite(x) and x>=0 for x in numeric)
            maxconservation=max(maxconservation,abs(q['conservation_error_bytes']))
            checks['relay_counters'] &= abs(q['conservation_error_bytes'])<=1e-5
            old=previous.get(direction)
            if old:checks['relay_counters'] &= all(q[k]+1e-5>=old[k] for k in cumulative)
            previous[direction]=q
    fraction=lambda predicate:sum(bool(predicate(n)) for n in main)/len(main) if main else 0
    mandatory={k:fraction(f) for k,f in {
        'unique_sender':lambda n:n['outbound_count']==1 and n['selected_pair_count']==1,
        'cap':lambda n:field_present({'cap':n['encoder_cap_bps']},'cap') and n['encoder_cap_bps']['value']==4000000,
        'send_counter':lambda n:field_present(n['outbound'],'bytesSent'),
        'encoder_frames':lambda n:field_present(n['outbound'],'framesEncoded'),
        'encoder_time':lambda n:field_present(n['outbound'],'totalEncodeTime')}.items()}
    checks['mandatory_native_channels']=all(x>=.9 for x in mandatory.values())
    advances=sorted({n['feedback']['last_detected_advance_ms'] for n in main if common<=n['available_ms']<=end and n['feedback']['last_detected_advance_ms'] is not None and n['feedback']['last_detected_advance_ms']>=common})
    optional={}
    for key,predicate in [('rtcp_rtt',lambda n:n['remote_inbound_count']==1 and field_present(n['rtcp'],'roundTripTime')),
        ('observed_feedback_counter_age',lambda n:n['feedback']['status']=='present' and n['feedback']['observed_age_bounds_ms'] is not None)]:
        frac=fraction(predicate);optional[key]={'qualified':frac>=.9 and len(advances)>=10,'main_available_fraction':frac,
            'distinct_common_counter_advances':len(advances)}
    statuses={}
    for group in ('outbound','rtcp','pair'):
        keys=sorted({k for n in ns for k in n[group]})
        statuses[group]={k:{status:sum(n[group][k]['status']==status for n in ns) for status in ('present','absent','invalid')} for k in keys}
    return {'passed':all(checks.values()),'checks':checks,'native_records':len(ns),'main_native_records':len(main),
        'relay_records':len(rs),'main_relay_records':len(relay),'maximum_relay_ack_ms':maximum_ack,
        'maximum_relay_gap_ms':max(gaps,default=None),'maximum_conservation_residual_bytes':maxconservation,
        'mandatory_channel_fractions':mandatory,'optional_channels':optional,'native_field_status_counts':statuses,
        'true_transport_cc_feedback_age_observed':False,'receiver_outcomes_read':False}

def gate(stage):
    verify();root=ROOT/stage;p,index=v.core.check_capture_integrity(root);rows=[]
    for t,i in zip(p['trials'],index['sessions'],strict=True):
        row=parent.session_gate(root,t,i,p)
        if row['passed']:
            try:row['mechanism']=mechanism_gate(root/'sessions'/t['id'],row);row['passed'] &= row['mechanism']['passed']
            except (AssertionError,KeyError,ValueError,TypeError,IndexError) as e:row.update(passed=False,mechanism_error=f'{type(e).__name__}: {e}')
        rows.append(row)
    common={}
    for block in sorted({x['block'] for x in rows}):
        items=[x for x in rows if x['block']==block];available=len(items)==2 and all(x['passed'] for x in items);error=elapsed=None
        if available:
            error=max(abs(math.log2(max(x['input_fidelity']['capacity_exposure_bytes_bounds'][ep][1] for x in items)/
                min(x['input_fidelity']['capacity_exposure_bytes_bounds'][ep][0] for x in items))) for ep in ('6000','12000'))
            times=[x['measurement_step_start_elapsed_ms'] for x in items];elapsed=max(times)-min(times)
        common[block]={'passed':bool(available and error<=.01 and elapsed<=250),
            'maximum_probe_exposure_difference_octaves':error,'step_start_elapsed_spread_ms':elapsed}
    optional={name:all(x.get('mechanism',{}).get('optional_channels',{}).get(name,{}).get('qualified',False) for x in rows)
        for name in ('rtcp_rtt','observed_feedback_counter_age')}
    result={'abi':'native_mechanism_observability_m10r_gate_v1','stage':stage,'protocol_sha256':v.sha(root/'protocol.json'),
        'capture_index_sha256':v.sha(root/'capture_index.json'),'planned_sessions':len(p['trials']),
        'qualified_sessions':sum(x['passed'] for x in rows),'passed':all(x['passed'] for x in rows) and all(x['passed'] for x in common.values()),
        'sessions':rows,'common_probe_checks':common,'optional_channels_qualified_every_original':optional,
        'receiver_outcomes_read':False,'native_common_support_established':False,'fit_predictor':False,'controller_fitted':False}
    for name in ('support_clock_transport_gate.json','mechanism_qualification_gate.json'):v.write(root/name,result)
    v.write(REPO/f'reports/native-mechanism-observability-m10r-{stage}-gate.json',result)
    return {'stage':stage,'qualified':result['qualified_sessions'],'planned':len(rows),'passed':result['passed'],'optional_channels':optional}

def capture(stage):
    verify()
    for n in SOURCES+[str(CONFIG.relative_to(REPO))]+[f'configs/native_mechanism_observability_m10r_{s}.json' for s in ('instrumentation','development')]:
        assert subprocess.check_output(['git','show','HEAD:'+n],cwd=REPO)==(REPO/n).read_bytes(),'commit before capture'
    if stage=='development':assert v.read(ROOT/'instrumentation/mechanism_qualification_gate.json')['passed']
    root=ROOT/stage;p=v.read(root/'protocol.json');current,_=v.frozen.base.runtime_provenance(Path(p['preflight_reference']['path']))
    assert current==p['runtime'];v.frozen.v2.set_runtime_env(p);assert v.read(root/'clock_report.json')['passed'];v.core.verify_sources(p)
    assert shutil.disk_usage(v.CACHE).free>=3000000000
    sessions=root/'sessions';sessions.mkdir(exist_ok=False)
    index={'abi':'native_clock_action_capture_index_v1','protocol_sha256':v.sha(root/'protocol.json'),'sessions':[]}
    for t in p['trials']:
        child=sessions/t['id'];assert v.sha(root/t['panel'])==t['panel_sha256']
        try:
            proc=subprocess.run(['node',str(RECORDER),str(child),str(root/t['panel']),t['id'],t['condition']],cwd=REPO,
                env=os.environ.copy(),capture_output=True,text=True,timeout=170)
            status='sealed' if proc.returncode==0 else 'failed';error=None if proc.returncode==0 else f'exit code {proc.returncode}';stdout,stderr=proc.stdout,proc.stderr
        except subprocess.TimeoutExpired as exc:
            status,error='failed','bounded 170-second timeout';stdout=exc.stdout or '';stderr=exc.stderr or ''
            if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
        child.mkdir(parents=True,exist_ok=True);(child/'capture_stdout.log').write_text(stdout);(child/'capture_stderr.log').write_text(stderr)
        seal=v.core.seal_directory(child,'native_action_session' if status=='sealed' else 'native_action_session_failed')
        index['sessions'].append({'trial':t['id'],'status':status,'error':error,'integrity_manifest_sha256':v.sha(child/'integrity.json'),'file_count':seal['file_count']})
        v.core.write_json(root/'capture_index.json',index)
        print(json.dumps({'stage':stage,'original':t['id'],'status':status,'completed':len(index['sessions'])}),flush=True)
    return gate(stage)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','verify','capture','gate'])
    p.add_argument('--stage',choices=['instrumentation','development'],default='instrumentation');a=p.parse_args()
    print(json.dumps(globals()[a.command](a.stage) if a.command in ('capture','gate') else globals()[a.command]()))
