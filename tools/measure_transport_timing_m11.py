"""Preregistered M11 transport-control diagnostic capability; support only."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m11_qualified_m10r',REPO/'tools/measure_mechanism_observability_m10r.py')
parent=importlib.util.module_from_spec(s);s.loader.exec_module(parent);v=parent.v
ROOT=v.CACHE/'native-transport-timing-m11'
DISCOVERY=v.CACHE/'native-transport-timing-m11-discovery'
CONFIG=REPO/'configs/native_transport_timing_m11.json'
FREEZE=REPO/'data/native-m11/prior-freeze-sha256.json'
ANCHOR='b4bbde9524c0d4fc4cb30ff23c4cc43be10d41ae'
RECORDER=REPO/'benchmarks/native_m11/transport_timing_episode_m11.mjs'
SEED=2026101603
DESIGN={'stage':'capability','originals':2,'main_ms':88000,'initial_ms':24000,'common_ms':64000,
 'service_mbps':[.5,.5*2**1.5],'native_poll_ms':25,'diagnostic_poll_ms':100,'file_tail_poll_ms':25,
 'clock_query_ms':1000,'maximum_clock_uncertainty_ms':50,'maximum_sender_ack_ms':100,
 'maximum_event_freshness_ms':250,'minimum_fresh_fraction':.9,'maximum_live_blackout_ms':1000,
 'minimum_tcc_events':10,'minimum_estimator_events':10,'minimum_probe_creation_events':1,'minimum_probe_result_events':1,
 'required_channels':['transport_cc_arrival','pacer_or_probe_events','native_bwe_update'],
 'raw_budget_bytes':1000000000,'external_peak_budget_bytes':4000000000,'minimum_free_bytes':5000000000,
 'trace_budget_bytes':250000000,'maximum_single_rtc_log_bytes':100000000,
 'all_originals_required':True,'retries':0,'future_labels_read':False,'receiver_outcomes_read':False,
 'fit_predictor':False,'fit_controller':False,'development_opened':False,
 'minimum_native_observations':3168,'maximum_native_gap_ms':250,'existing_support_gates':parent.DESIGN['original_state_gates']}
SOURCES=['tools/measure_transport_timing_m11.py','tools/qualify_transport_timing_m11.py',
 'tools/survey_transport_diagnostics_m11.mjs','docs/NATIVE_TRANSPORT_TIMING_M11_PLAN.md',
 'data/native-m11/prior-freeze-sha256.json','data/native-m11/source-survey.json','data/native-m11/WEBRTC_LICENSE',
 'reports/native-transport-timing-m11-preflight.json',
 *['benchmarks/native_m11/'+name for name in ['transport_timing_episode_m11.mjs','mechanism_observer_m11.mjs',
    'transport_diagnostic_browser_m11.mjs','transport_diagnostic_node_m11.mjs','rtc_log_decoder_m11.mjs']]]

def inventory():return {**parent.inventory(),**{name:v.sha(REPO/name) for name in SOURCES}}
def activate():v.core.source_inventory=inventory
def old_closed():return parent.old_closed()

def prepare():
    assert not ROOT.exists() and not CONFIG.exists(),'preserve M11 original evidence'
    parent.verify();assets=parent.parent.m.assets_verified()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',ANCHOR],cwd=REPO,text=True).splitlines()
    v.write(FREEZE,{'anchor_commit':ANCHOR,'files':{name:v.sha(REPO/name) for name in names},'old_closed':old_closed()})
    assert shutil.disk_usage(v.CACHE).free>=DESIGN['minimum_free_bytes']
    root=ROOT/'capability';trials=[]
    profile=next(p for p in assets['network_profiles'] if p['profile_id']=='att_lte_driving_2016-uplink-lower')
    for i,(content,prefix) in enumerate(zip(assets['content_sources'],parent.parent.m.PREFIXES,strict=True)):
        tid=f'm11-timing-c-{i:03d}-support';pair=f'm11-capability-{i}';sequence=DESIGN['service_mbps']
        early=sorted(profile['rates_mbps'][:10],reverse=i==1)
        panel=v.panel_for(tid,content,profile,pair,i,SEED,True);e=panel['episodes'][0]
        e.update(m11_verbose_diagnostic=False,support_poll_ms=25,support_initial_bwe_kbps=1200,setup_delay_ms=0,system_id_sequence_mbps=sequence,
            video_segment=[0,130000],episode_timeout_s=160,
            schedule=[[early[0],'block_0',10000,early],[sequence[0],'block_1',88000,[sequence[0]]],
                [profile['rates_mbps'][10],'block_2',12600,profile['rates_mbps'][10:22]]])
        panel['episode_timeout_s']=160;panel['measurement_recipe'].update(scientific_role='M11 instrumentation-only capability',action_ratios=[],instrumentation_version='M11')
        relative=f'panels/{tid}.json';v.write(root/relative,panel)
        trials.append({'id':tid,'condition':'micro','panel':relative,'panel_sha256':v.sha(root/relative),'pair_id':pair,'pair_slot':i,
            'repetition':0,'content_id':content['content_id'],'prefix':prefix,'input_x':1.5,'target_x':1.5,'input_order':'rise',
            'service_sequence_mbps':sequence,'setup_delay_ms':0,'support_only':True,'network_family':profile['family_id'],
            'network_profile_id':profile['profile_id'],'block':content['content_id']+'__capability','cell_cluster':content['content_id']})
    protocol=v.protocol_for(root,trials,'development',SEED)
    protocol.update(abi='native_transport_timing_m11_capability_v1',anchor_commit=ANCHOR,stage='capability',design=DESIGN,
        source_hashes=inventory(),source_manifest_sha256=v.sha(parent.parent.m.ASSETS),
        scientific_role='Instrumentation only; no native state, future labels or receiver outcomes',
        analysis={'outcomes_read':False,'fit_or_promote_controller':False,'fit_predictor':False,'future_BWE_labels':False},
        capture_timeout_seconds=180,randomization={'order':'frozen Kampar ascending then Volga descending; no scientific effect comparison'})
    protocol['trace_replay'].update(phase_duration_ms=[10000,88000,12600],measured_ticks=22,source_ticks=22,
        synthetic_service_settings=2,tick_tolerance_ms=150)
    v.seal(root,protocol)
    v.write(CONFIG,protocol);return verify()

def verify():
    p=v.read(CONFIG);assert p['source_hashes']==inventory() and p['design']==DESIGN
    freeze=v.read(FREEZE)
    for name,checksum in freeze['files'].items():assert v.sha(REPO/name)==checksum,name
    assert old_closed()==freeze['old_closed'];parent.parent.m.assets_verified()
    root=ROOT/'capability';assert v.sha(root/'protocol.json')==v.sha(CONFIG)==(root/'protocol.sha256').read_text().split()[0]
    assert len(p['trials'])==2 and p['randomized_order']==[t['id'] for t in p['trials']]
    for t in p['trials']:
        assert v.sha(root/t['panel'])==t['panel_sha256'];panel=v.read(root/t['panel'])
        assert v.sha(Path(panel['video_source']['path']))==panel['video_source']['sha256'] and t['support_only']
    for name,meta in v.read(REPO/'data/native-m11/source-survey.json')['files'].items():
        path=DISCOVERY/name;assert path.stat().st_size==meta['size'] and v.sha(path)==meta['sha256']
    activate();return {'verified':True,'prior_files_unchanged':len(freeze['files']),'capability_originals':2,
        'old_panels_closed':True,'development_opened':False,'receiver_outcomes_read':False}

def gate():
    verify();root=ROOT/'capability';p,index=v.core.check_capture_integrity(root);rows=[]
    for t,item in zip(p['trials'],index['sessions'],strict=True):
        row=parent.parent.session_gate(root,t,item,p)
        if row['passed']:
            try:row['mechanism']=parent.mechanism_gate(root/'sessions'/t['id'],row);row['passed'] &= row['mechanism']['passed']
            except (AssertionError,KeyError,ValueError,TypeError,IndexError) as error:row.update(passed=False,mechanism_error=str(error))
        rows.append(row)
    result={'abi':'native_transport_timing_m11_acquisition_v1','protocol_sha256':v.sha(root/'protocol.json'),
        'capture_index_sha256':v.sha(root/'capture_index.json'),'planned_sessions':2,'qualified_sessions':sum(r['passed'] for r in rows),
        'passed':all(r['passed'] for r in rows),'sessions':rows,'gate_is_acquisition_only':True,
        'future_BWE_labels_read':False,'receiver_outcomes_read':False,'fit_predictor':False,'controller_fitted':False}
    v.write(root/'support_clock_transport_gate.json',result);v.write(REPO/'reports/native-transport-timing-m11-acquisition-gate.json',result)
    return {'qualified':result['qualified_sessions'],'planned':2,'passed':result['passed']}

def capture():
    verify()
    for name in SOURCES+[str(CONFIG.relative_to(REPO))]:
        assert subprocess.check_output(['git','show','HEAD:'+name],cwd=REPO)==(REPO/name).read_bytes(),'commit before capture'
    root=ROOT/'capability';p=v.read(CONFIG);current,_=v.frozen.base.runtime_provenance(Path(p['preflight_reference']['path']))
    assert current==p['runtime'];v.frozen.v2.set_runtime_env(p);assert v.read(root/'clock_report.json')['passed'];v.core.verify_sources(p)
    assert shutil.disk_usage(v.CACHE).free>=DESIGN['minimum_free_bytes']
    sessions=root/'sessions';sessions.mkdir(exist_ok=False)
    index={'abi':'native_clock_action_capture_index_v1','protocol_sha256':v.sha(root/'protocol.json'),'sessions':[]}
    for t in p['trials']:
        d=sessions/t['id']
        try:
            proc=subprocess.run(['node',str(RECORDER),str(d),str(root/t['panel']),t['id'],t['condition']],cwd=REPO,
                env=os.environ.copy(),capture_output=True,text=True,timeout=180)
            status='sealed' if proc.returncode==0 else 'failed';error=None if proc.returncode==0 else f'exit code{proc.returncode}';stdout,stderr=proc.stdout,proc.stderr
        except subprocess.TimeoutExpired as exc:
            status,error='failed','bounded180s timeout';stdout,stderr=exc.stdout or '',exc.stderr or ''
            if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
        d.mkdir(parents=True,exist_ok=True);(d/'capture_stdout.log').write_text(stdout);(d/'capture_stderr.log').write_text(stderr)
        seal=v.core.seal_directory(d,'native_action_session' if status=='sealed' else 'native_action_session_failed')
        index['sessions'].append({'trial':t['id'],'status':status,'error':error,'integrity_manifest_sha256':v.sha(d/'integrity.json'),'file_count':seal['file_count']})
        v.write(root/'capture_index.json',index) if len(index['sessions'])==1 else (root/'capture_index.json').write_text(json.dumps(index,sort_keys=True,indent=2)+'\n')
        print(json.dumps({'original':t['id'],'status':status,'completed':len(index['sessions'])}),flush=True)
    return gate()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','verify','capture','gate']);a=p.parse_args();print(json.dumps(globals()[a.command]()))
