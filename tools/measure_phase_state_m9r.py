"""Preregistered M9R phase-aware native support: acquisition and strict machinery gates."""
from __future__ import annotations
import argparse
import gzip
import importlib.util
import json
import math
import os
import random
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m9_qualified_parent',REPO/'tools/measure_bwe_transients_m8.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
v,r=m.v,m.r
ROOT=v.CACHE/'native-phase-state-m9r'
CONFIG=REPO/'configs/native_phase_state_m9r.json'
FREEZE=REPO/'data/native-m9r/prior-freeze-sha256.json'
DEVELOPMENT=REPO/'data/native-m9r/m8-development-horizon.json'
RECORDER=REPO/'benchmarks/native_m9r/phase_state_episode_m9r.mjs'
ANCHOR='26ab4acfd95f2e86cb1979f8e93a1a3369ac2844'
SEED=20261210
TARGETS=[0.,.5,1.,1.5]
DESIGN={'initial_ms':24000,'common_ms':64000,'main_ms':88000,'measurement_phases_ms':[10000,88000,12600],
        'input_log2_service_over_500k':TARGETS,'prefixes':list(m.PREFIXES),'repeats_per_history':4,
        'state_rules':['B0','D1','P2'],'entry_grid_ms':list(range(6000,55001,1000)),
        'diagnostic_ages_ms':[6000,12000,18000,24000,32000,40000,48000,55000],
        'future_end_ms':63800,'minimum_future_ms':8000,'trajectory_ms':6000,'trajectory_minimum_samples':54,
        'phase_response_envelope_ms':{'rise':16000,'fall':2000},
        'new_clock_brackets_ms':[12000,24000,36000,48000,60000,72000,80000,84000],
        'matching_x_octaves':.25,'matching_drift_octaves':.05,'matching_age_ms':250,'matching_service_octaves':.01,
        'future_quantiles':101,'retries':0,'all_originals_required':True,'actions':False,'outcomes_read':False,
        'controller_fitting':False,'native_common_support_established_before_study':False,'actual_poll_ms':25,'census_minimum_spacing_ms':90,
        'instrumentation_originals':8,'native_output_budget_bytes':3000000000,'incremental_external_budget_bytes':10000000000,
        'unchanged_state_gates':{k:m.parent.DESIGN[k] for k in ('targets_log2_bwe_over_500k','target_caliper_octaves',
            'history_state_ms','minimum_history_samples','maximum_recent_log2_drift','eligible_bwe_bounds_bps',
            'census_samples','minimum_census_span_ms','maximum_sample_gap_ms','minimum_profile_range_octaves',
            'minimum_profile_sample_sd_octaves','minimum_common_overlap_octaves','maximum_repeat_spread_octaves',
            'maximum_prefix_w_infinity_octaves','maximum_actual_census_difference_octaves','minimum_members_per_history',
            'maximum_probe_exposure_difference_octaves','maximum_entry_elapsed_difference_ms','all_original_attempts_required')}}
SOURCES=['tools/measure_phase_state_m9r.py','tools/analyze_phase_state_m9r.py','tools/build_phase_state_m9r.py','docs/NATIVE_PHASE_STATE_M9R_INHERITED_GATES.md',
         'benchmarks/native_m9r/phase_state_episode_m9r.mjs','benchmarks/native_m9r/phase_state_support_m9r.mjs',
         'docs/NATIVE_PHASE_STATE_M9R_PLAN.md','data/native-m9r/prior-freeze-sha256.json',
         'data/native-m9r/m8-development-horizon.json','reports/native-phase-state-m9r-preflight.json']

def inventory():return {**m.inventory(),**{name:v.sha(REPO/name) for name in SOURCES}}

def activate():v.core.source_inventory=inventory

def old_closed():
    roots=[m.parent.ROOT/'validation',v.CACHE/'native-state-conditioning-m7/validation',v.CACHE/'native-state-conditioning-m7r/validation']
    return {'m8_allocation_sha256':v.sha(m.ALLOCATION),'m8_schedule_uninstantiated':not (m.ROOT/'next-validation').exists(),
            'old_validation_session_directories':{str(p):bool((p/'sessions').exists()) for p in roots}}

def prepare():
    assert not ROOT.exists() and not CONFIG.exists(),'preserve existing M9R'
    m.verify();assets=m.assets_verified()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',ANCHOR],cwd=REPO,text=True).splitlines()
    v.write(FREEZE,{'anchor_commit':ANCHOR,'files':{n:v.sha(REPO/n) for n in names},'old_closed':old_closed()})
    assert not any(old_closed()['old_validation_session_directories'].values())
    dev=v.read(DEVELOPMENT);assert dev['common_horizon_ms']==64000 and dev['direction_envelope_ms']==DESIGN['phase_response_envelope_ms']
    profile=next(p for p in assets['network_profiles'] if p['profile_id']=='att_lte_driving_2016-uplink-lower')
    stages={}
    for stage in ('instrumentation','validation'):
        root=ROOT/stage;rng=random.Random(SEED+(stage=='validation'));trials=[]
        if stage=='instrumentation':
            contexts=[(c,0,x,h) for c in assets['content_sources'] for x in (0.,1.5) for h in m.PREFIXES];rng.shuffle(contexts)
        else:
            contexts=[]
            for rep in range(4):
                for c in rng.sample(assets['content_sources'],2):
                    block=[(c,rep,x,prefix) for x in TARGETS for prefix in m.PREFIXES];rng.shuffle(block);contexts.extend(block)
        for index,(c,rep,x,prefix) in enumerate(contexts):
            tid=f'm9r-phase-{stage[0]}-{index:03d}-support';pair=f'm9r-{stage[0]}-{c["content_id"]}-x{x}-r{rep}'
            early=sorted(profile['rates_mbps'][:10],reverse=prefix==m.PREFIXES[1]);sequence=[1.5 if x<1 else .5,.5*2**x]
            panel=v.panel_for(tid,c,profile,pair,m.PREFIXES.index(prefix),SEED,True);e=panel['episodes'][0]
            e.update(support_poll_ms=25,support_initial_bwe_kbps=1200,setup_delay_ms=0,system_id_sequence_mbps=sequence,video_segment=[0,130000],episode_timeout_s=150,
                     schedule=[[early[0],'block_0',10000,early],[sequence[0],'block_1',88000,[sequence[0]]],
                               [profile['rates_mbps'][10],'block_2',12600,profile['rates_mbps'][10:22]]])
            panel['episode_timeout_s']=150
            panel['measurement_recipe'].update(scientific_role='M9R prospective phase-state support only',action_ratios=[],instrumentation_version='M9R',
                service_sources=assets['input_separation'])
            relative=f'panels/{tid}.json';v.write(root/relative,panel)
            trials.append({'id':tid,'condition':'micro','panel':relative,'panel_sha256':v.sha(root/relative),'pair_id':pair,
                'pair_slot':m.PREFIXES.index(prefix),'repetition':rep,'content_id':c['content_id'],'prefix':prefix,'input_x':x,'target_x':x,
                'input_order':'fall' if x<1 else 'rise','service_sequence_mbps':sequence,'setup_delay_ms':0,'support_only':True,
                'network_family':profile['family_id'],'network_profile_id':profile['profile_id'],
                'block':c['content_id']+'__'+str(rep),'cell_cluster':c['content_id']+'__'+str(x)})
        p=v.protocol_for(root,trials,'development',SEED)
        p.update(abi='native_phase_state_m9r_protocol_v1',stage=stage,anchor_commit=ANCHOR,design=DESIGN,source_hashes=inventory(),
            source_manifest_sha256=v.sha(m.ASSETS),scientific_role='Prospective support-only; no bitrate actions or QoE',
            source_separation=assets['independence']+' '+assets['input_separation'],
            randomization={'seed':SEED+(stage=='validation'),'unit':'eight input/prefix combinations within content/repetition blocks'},
            analysis={'outcomes_read':False,'fit_or_promote_controller':False,'controller_fitting':False},capture_timeout_seconds=170)
        p['trace_replay'].update(phase_duration_ms=[10000,88000,12600],measured_ticks=22,source_ticks=22,synthetic_service_settings=2,tick_tolerance_ms=150)
        v.seal(root,p);config=REPO/f'configs/native_phase_state_m9r_{stage}.json';v.write(config,p)
        stages[stage]={'protocol_sha256':v.sha(root/'protocol.json'),'committed_protocol':str(config.relative_to(REPO)),'sessions':len(trials)}
    v.write(CONFIG,{'abi':'native_phase_state_m9r_design_v1','stages':stages,'design':DESIGN,'source_hashes':inventory(),
        'prior_freeze_sha256':v.sha(FREEZE),'validation_untouched':True,'no_action_stage':True})
    return verify()

def verify():
    assert RECORDER.is_file();config=v.read(CONFIG);assert config['design']==DESIGN and config['source_hashes']==inventory()
    assert config['prior_freeze_sha256']==v.sha(FREEZE)
    for name,checksum in v.read(FREEZE)['files'].items():assert v.sha(REPO/name)==checksum,name
    assert old_closed()==v.read(FREEZE)['old_closed'],'closed predecessor panel drift'
    m.assets_verified()
    for stage,meta in config['stages'].items():
        root=ROOT/stage;p=v.read(root/'protocol.json')
        assert v.sha(root/'protocol.json')==v.sha(REPO/meta['committed_protocol'])==meta['protocol_sha256']==(root/'protocol.sha256').read_text().split()[0]
        assert p['source_hashes']==inventory() and p['design']==DESIGN and len(p['trials'])==meta['sessions']==(8 if stage=='instrumentation' else 64)
        assert p['randomized_order']==[t['id'] for t in p['trials']]
        for t in p['trials']:
            assert v.sha(root/t['panel'])==t['panel_sha256']
            panel=v.read(root/t['panel']);assert v.sha(Path(panel['video_source']['path']))==panel['video_source']['sha256']
            assert t['support_only'] and t['service_sequence_mbps']==[1.5 if t['input_x']<1 else .5,.5*2**t['input_x']]
    activate()
    return {'verified':True,'instrumentation_sessions':8,'validation_sessions':64,'closed_predecessor_panels_unchanged':True,
            'prior_files_unchanged':len(v.read(FREEZE)['files']),'controller_fitted':False}

def census(points, endpoint):
    # Eleven real observations, with the original >=900ms span and <=250ms gaps.
    # At 100ms legacy cadence this selects exactly the legacy eleven-sample tail.
    for i,p in enumerate(points):
        if not endpoint<=p['ms']<=endpoint+300:continue
        tail=[p]
        for q in reversed(points[:i]):
            if tail[-1]['ms']-q['ms']>=90:
                tail.append(q)
                if len(tail)==11:break
        tail.reverse()
        if len(tail)==11 and tail[-1]['ms']-tail[0]['ms']>=900 and all(0<b['ms']-a['ms']<=250 for a,b in zip(tail,tail[1:])) and all(q['valid'] and 240000<=q['bwe']<=3800000 for q in tail):
            import statistics as st
            return {'passed':True,'cutoff_ms':p['ms'],'x':st.mean(math.log2(q['bwe']/500000) for q in tail),
                'instantaneous_x':math.log2(p['bwe']/500000),'samples':11,'history_span_ms':tail[-1]['ms']-tail[0]['ms']}
    return {'passed':False,'reason':'no eligible fixed-time census of eleven actual observations'}

def clocks(directory):
    original=v.core.load_marker_pair(directory/'clock_markers_browser.json',directory/'clock_markers_node.json')
    assert [x['marker_id'] for x in original]==[f'm{i:04d}' for i in range(1,13)]
    browser,node=v.read(directory/'instrument_clock_browser.json'),v.read(directory/'instrument_clock_node.json')
    assert [x['marker_id'] for x in node]==[f'x{i:04d}' for i in range(1,132)]
    assert [x['marker_id'] for x in browser]==[x['marker_id'] for x in node]
    for b,n in zip(browser,node,strict=True):assert all(b[k]==n[k] for k in ('marker_id','browser_send_ms','node_receive_ms','node_send_ms','role','label'))
    extra=[{**n,'browser_receive_ms':b['browser_receive_ms']} for b,n in zip(browser,node,strict=True)]
    train=[original[i] for i in (0,1,3,4,6,7,9,11)]+[x for x in extra if x['role']=='train']
    held=[original[i] for i in (2,5,8,10)]+[x for x in extra if x['role']=='holdout']
    assert (len(train),len(held))==(128,15)
    labels={name+suffix for name in ('session_open','pre_sdp','ready_inactive','block_0') for suffix in ('_before','_after')}
    start_train=[original[i] for i in (0,1,3)]+[x for x in extra if x['role']=='train' and x['label'] in labels]
    start_held=[original[2]]+[x for x in extra if x['role']=='holdout' and not x['label'].startswith('m9r_')]
    assert (len(start_train),len(start_held))==(35,4)
    check=lambda a,b:v.core.validate_markers(a+b,list(range(len(a))),list(range(len(a),len(a)+len(b))))
    full,beginning=check(train,held),check(start_train,start_held)
    origin,vertices=v.core.feasible_polygon(train)
    return {'full':full,'beginning':beginning,'training_ids':[x['marker_id'] for x in train],'holdout_ids':[x['marker_id'] for x in held]},original,origin,vertices

def fidelity(directory,trial,panel,origin,vertices,windows):
    phases,ticks,initial,updates=[],[],[],[]
    with gzip.open(directory/'events.jsonl.gz','rt') as stream:
        for line in stream:
            e=json.loads(line);kind=e.get('kind')
            if kind=='phase':phases.append(e)
            elif kind=='trace_capacity':ticks.append(e)
            elif kind=='system_id_initial':initial.append(e)
            elif kind=='system_id_service':updates.append(e)
    evidence=v.read(directory/'system_id_evidence.json');commands=evidence['commands'];done=evidence['completion'];start=windows[1]['start_ms']
    checks={'inventory':len(phases)==3 and len(ticks)==22 and len(initial)==len(updates)==len(commands)==1,
        'initial_setting':len(initial)==1 and initial[0]['capacity_mbps']==trial['service_sequence_mbps'][0] and evidence['initial']['at_ms']==initial[0]['at_ms'],
        'completion':done is not None and done['browser_start_ms']==start and 88000<=done['browser_end_ms']-start<=88250 and
            88000<=windows[1]['end_ms']-start<=88250 and done['service_sequence_mbps']==trial['service_sequence_mbps'] and done['commands']==1}
    worst_tick=0.;exact=True
    for phase,schedule in zip(phases,panel['episodes'][0]['schedule'],strict=True):
        _,name,_,rates=schedule;actual=initial if name=='block_1' else [t for t in ticks if t['phase']==name]
        exact=exact and phase['phase']==name and phase['trace_mbps']==rates and phase['capacity_mbps']==rates[0] and len(actual)==len(rates)
        for i,(tick,rate) in enumerate(zip(actual,rates,strict=True)):
            error=abs(tick['at_ms']-phase['at_ms']-i*1000);worst_tick=max(worst_tick,error)
            exact=exact and tick['sample_index']==i and tick['capacity_mbps']==rate and error<=150
    checks['exact_source_ticks']=exact
    c,u=commands[0],updates[0];ack=c['browser_receive_ms']-c['browser_request_ms'];late=c['browser_request_ms']-(start+24000)
    lo,hi=v.core.mapped_browser_range(u['node_applied_ms'],origin,vertices)
    checks['strict_commands_and_clock_ordering']=(c['sequence']==u['sequence']==1 and c['previous_mbps']==trial['service_sequence_mbps'][0] and
        c['requested_mbps']==trial['service_sequence_mbps'][1] and u['capacity_mbps']==c['readback']['capacity_mbps']==c['requested_mbps'] and
        u['node_applied_ms']==c['readback']['node_applied_ms'] and 0<=ack<=100 and 0<=late<=150 and c['browser_request_ms']-1<=lo<=hi<=c['browser_receive_ms']+1)
    probe=windows[2]['start_ms'];probe_ticks=[t for t in ticks if t['phase']=='block_2'];exposure={}
    for endpoint in (6000,12000):
        totals=[]
        for alpha,beta in vertices:
            series=[(origin+(t['at_ms']-beta)/alpha-probe,t['capacity_mbps']) for t in probe_ticks]
            rate,cursor,total=series[0][1],1000.,0.
            for ms,value in series:
                if ms<=1000:rate=value;continue
                if ms>=endpoint:break
                total+=rate*(ms-cursor);rate,cursor=value,ms
            totals.append((total+rate*(endpoint-cursor))*125)
        exposure[str(endpoint)]=[min(totals),max(totals)]
    return {'passed':all(checks.values()),'checks':checks,'maximum_tick_error_ms':worst_tick,'maximum_ack_ms':ack,
        'maximum_command_lateness_ms':late,'common_service_ack_ms':c['browser_receive_ms'],'common_service_application_bounds_ms':[lo,hi],
        'capacity_exposure_bytes_bounds':exposure}

def session_gate(root,t,item,p):
    row={'trial':t['id'],'capture_status':item['status'],'passed':False,**{k:t[k] for k in ('content_id','prefix','input_order','input_x','block','repetition')}}
    if item['status']!='sealed':row['reason']='failed original; no state interpretation';return row
    d=root/'sessions'/t['id']
    try:
        clock,markers,origin,vertices=clocks(d);sender=v.read(d/'sender_observations.json');points=m.parent.points_for(sender)
        windows=v.read(d/'phase_windows.json')['phase_windows'];assert [w['phase'] for w in windows]==['block_0','block_1','block_2']
        ice=v.read(d/'ice_evidence.json');urls={c.get('url') for peer in ('a','b') for c in ice.get('candidates',{}).get(peer,[])}
        transport=v.frozen.base.transport_checks(root,t['id'],next(iter(urls)) if len(urls)==1 else '')
        cleanup=v.frozen.terminal_cleanup_gate(root,t,markers,p);startup=r.startup_check(d,sender,t)
        readback=bool(sender['decisions']) and not sender['sampling_errors'] and not sender['support_screen']['action_assigned'] and all(
            x['actuator_assignment'] is None and not x['changed'] and x['actuation_readback']['encoder_max_bitrate_bps']==4000000 and x['actuation_readback']['receiver_jitter_buffer_target_ms']==0 for x in sender['decisions'])
        progress=v.read(d/'media_progress.json');media=len(progress)==3 and all(x['frames_encoded']>10 and x['frames_decoded']>10 and math.isfinite(x['mean_encode_s']) for x in progress)
        media=media and all(progress[i][key]-progress[i-1][key]>10 for i in (1,2) for key in ('frames_encoded','frames_decoded'))
        sampled=[x for x in points if windows[1]['start_ms']<=x['ms']<=windows[1]['end_ms']];gaps=[b['ms']-a['ms'] for a,b in zip(sampled,sampled[1:])]
        observer=len(sampled)>=3168 and bool(gaps) and max(gaps)<=250 and all(x['valid'] and x['bwe']>0 for x in sampled)
        polls=[x for x in sender['decisions'] if windows[1]['start_ms']<=x['sample_ms']<=windows[1]['end_ms']]
        timing=all('poll_timing' in x and x['poll_timing']['period_ms']==25 and
            x['poll_timing']['scheduled_ms']<=x['poll_timing']['request_ms']<=x['poll_timing']['response_ms']<=x['sample_ms']<=x['ack_ms'] and
            abs((x['poll_timing']['scheduled_ms']-x['poll_timing']['poll_epoch_ms'])/25-round((x['poll_timing']['scheduled_ms']-x['poll_timing']['poll_epoch_ms'])/25))<=1e-7 for x in polls)
        observer=observer and timing
        replay=fidelity(d,t,v.read(root/t['panel']),origin,vertices,windows)
        row.update(clock=clock,startup=startup,transport_passed=transport['passed'],cleanup_passed=cleanup['passed'],readback_passed=readback,
            media_passed=media,observer_passed=observer,acquisition_timing_passed=timing,maximum_stats_duration_ms=max(x['poll_timing']['stats_duration_ms'] for x in polls),maximum_scheduling_lateness_ms=max(x['poll_timing']['scheduling_lateness_ms'] for x in polls),observer_samples=len(sampled),maximum_observer_gap_ms=max(gaps,default=None),input_fidelity=replay,
            step_phase_start_ms=windows[1]['start_ms'],measurement_step_start_elapsed_ms=windows[1]['start_ms']-sender['measurement_start_ms'])
        row['passed']=all((clock['full']['passed'],clock['beginning']['passed'],startup['passed'],transport['passed'],cleanup['passed'],readback,media,observer,replay['passed']))
    except (AssertionError,ValueError,KeyError,IndexError,StopIteration,ZeroDivisionError) as exc:row['reason']=f'{type(exc).__name__}: {exc}'
    return row

def gate(stage):
    verify();root=ROOT/stage;p,index=v.core.check_capture_integrity(root)
    rows=[session_gate(root,t,i,p) for t,i in zip(p['trials'],index['sessions'],strict=True)];common={}
    if stage=='validation':
        for block in sorted({x['block'] for x in rows}):
            items=[x for x in rows if x['block']==block];available=len(items)==8 and all(x['passed'] for x in items);error=elapsed=None
            if available:
                errors=[]
                for endpoint in ('6000','12000'):
                    bounds=[x['input_fidelity']['capacity_exposure_bytes_bounds'][endpoint] for x in items]
                    errors.append(abs(math.log2(max(b[1] for b in bounds)/min(b[0] for b in bounds))))
                error=max(errors);times=[x['measurement_step_start_elapsed_ms'] for x in items];elapsed=max(times)-min(times)
            common[block]={'passed':bool(available and error<=.01 and elapsed<=250),'maximum_probe_exposure_difference_octaves':error,'step_start_elapsed_spread_ms':elapsed}
    result={'abi':'native_phase_state_m9r_acquisition_v1','stage':stage,'protocol_sha256':v.sha(root/'protocol.json'),
        'capture_index_sha256':v.sha(root/'capture_index.json'),'planned_sessions':len(p['trials']),'qualified_sessions':sum(x['passed'] for x in rows),
        'passed':all(x['passed'] for x in rows) and all(x['passed'] for x in common.values()),'sessions':rows,'common_probe_checks':common,
        'delivery_qoe_action_outcomes_read':False,'controller_fitted':False,'native_common_support_established':False}
    v.write(root/'support_clock_transport_gate.json',result);v.write(root/'mechanism_qualification_gate.json',result)
    v.write(REPO/f'reports/native-phase-state-m9r-{stage}-gate.json',result)
    return {'stage':stage,'planned':len(rows),'qualified':result['qualified_sessions'],'passed':result['passed']}

def capture(stage):
    verify()
    names=SOURCES+[str(CONFIG.relative_to(REPO))]+[f'configs/native_phase_state_m9r_{x}.json' for x in ('instrumentation','validation')]
    for name in names:assert subprocess.check_output(['git','show','HEAD:'+name],cwd=REPO)==(REPO/name).read_bytes(),'commit before capture'
    if stage=='validation':assert v.read(ROOT/'instrumentation/mechanism_qualification_gate.json')['passed'],'qualify machinery first'
    root=ROOT/stage;p=v.read(root/'protocol.json');current,_=v.frozen.base.runtime_provenance(Path(p['preflight_reference']['path']))
    assert current==p['runtime'];v.frozen.v2.set_runtime_env(p);assert v.read(root/'clock_report.json')['passed'];v.core.verify_sources(p)
    sessions=root/'sessions';sessions.mkdir(exist_ok=False)
    index={'abi':'native_clock_action_capture_index_v1','protocol_sha256':v.sha(root/'protocol.json'),'sessions':[]}
    for t in p['trials']:
        child=sessions/t['id'];assert v.sha(root/t['panel'])==t['panel_sha256']
        try:
            proc=subprocess.run(['node',str(RECORDER),str(child),str(root/t['panel']),t['id'],t['condition']],cwd=REPO,env=os.environ.copy(),capture_output=True,text=True,timeout=170)
            status='sealed' if proc.returncode==0 else 'failed';error=None if proc.returncode==0 else f'exit code {proc.returncode}';stdout,stderr=proc.stdout,proc.stderr
        except subprocess.TimeoutExpired as exc:
            status,error='failed','bounded 170-second timeout';stdout=exc.stdout or '';stderr=exc.stderr or ''
            if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
        child.mkdir(parents=True,exist_ok=True);(child/'capture_stdout.log').write_text(stdout);(child/'capture_stderr.log').write_text(stderr)
        seal=v.core.seal_directory(child,'native_action_session' if status=='sealed' else 'native_action_session_failed')
        index['sessions'].append({'trial':t['id'],'status':status,'error':error,'integrity_manifest_sha256':v.sha(child/'integrity.json'),'file_count':seal['file_count']})
        v.core.write_json(root/'capture_index.json',index)
    return {'capture':{'planned':len(p['trials']),'sealed':sum(i['status']=='sealed' for i in index['sessions'])},'gate':gate(stage)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify','capture','gate']);parser.add_argument('--stage',choices=['instrumentation','validation'],default='instrumentation');args=parser.parse_args()
    print(json.dumps(globals()[args.command](args.stage) if args.command in ('capture','gate') else globals()[args.command]()))
