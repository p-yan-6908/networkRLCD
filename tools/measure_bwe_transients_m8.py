"""M8 preregistered native service-response identification, support telemetry only."""
from __future__ import annotations
import argparse
import gzip
import importlib.util
import json
import math
import os
import random
import statistics as st
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m8_qualified_dependencies',REPO/'tools/measure_state_conditioning_m7ra.py')
parent=importlib.util.module_from_spec(s);s.loader.exec_module(parent)
v,r=parent.v,parent.r
ROOT=v.CACHE/'native-bwe-transients-m8'
CONFIG=REPO/'configs/native_bwe_transients_m8.json'
ASSETS=REPO/'data/native-m8/sources.json'
FREEZE=REPO/'data/native-m8/prior-freeze-sha256.json'
ALLOCATION=REPO/'data/native-m8/next-validation-allocation.json'
RECORDER=REPO/'benchmarks/native_m8/bwe_transients_episode_m8.mjs'
ANCHOR='81be2db9cd1a35a710ce3da6efd604d2badf50e6'
SEED=20261131
ORDERS={'step_hold_fall_rise':[.5,1.5,.5,1.5], 'hold_hold_fall_rise':[1.5,1.5,.5,1.5]}
PREFIXES=parent.PREFIXES
DESIGN={'plateau_ms':24000,'plateaus':4,'step_duration_ms':96000,'measurement_phases_ms':[10000,96000,12600],
        'orders':ORDERS,'service_levels_mbps':[.5,1.5],'candidate_ages_ms':[6000,9000,12000,15000],
        'diagnostic_age_grid_ms':[1000,2000,4000,6000,9000,12000,15000,18000,21000,23000],
        'settling_age_grid_ms':list(range(3000,15001,1000)),'future_ends_at_plateau_ms':23800,
        'minimum_future_verification_ms':8000,'target_caliper_octaves':.125,'recent_ms':3000,'recent_minimum_samples':27,
        'recent_drift_limit_octaves':.05,'eligible_bwe_bounds_bps':[240000,3800000],
        'census_samples':11,'census_span_ms':900,'maximum_sample_gap_ms':250,
        'command_lateness_ms':[0,150],'command_ack_ms':100,'maximum_repeat_spread_octaves':.25,
        'maximum_prefix_w_infinity_octaves':.25,'minimum_profile_range_octaves':1.,
        'minimum_profile_sample_sd_octaves':.35,'minimum_common_overlap_octaves':.5,'next_members_per_history':4,
        'rise_fall_departure_octaves':.05,'input_normalized_fractions':[.1,.5,.9],
        'maximum_common_probe_exposure_difference_octaves':.01,'maximum_paired_elapsed_difference_ms':250,
        'new_clock_brackets_ms':[12000,24000,36000,48000,60000,72000,84000,90000],
        'full_clock_train':128,'full_clock_holdout':15,'beginning_clock_train':35,'beginning_clock_holdout':4,
        'next_schedule_rule':'earliest all-occurrence verified age + 8000ms future verification + 1000ms decision/clock guard',
        'calibration_rule':'median causal current-BWE minus log2(known service/0.5Mbps), only if full bias spread <=0.25 octave',
        'all_originals_required':True,'retries':0,'bitrate_actions':False,'outcomes_read':False,'controller_fitting':False}
SOURCES=['tools/measure_bwe_transients_m8.py','tools/analyze_bwe_transients_m8.py','tools/build_bwe_transients_m8.py',
         'tools/prepare_bwe_transients_m8_assets.py','benchmarks/native_m8/bwe_transients_episode_m8.mjs',
         'benchmarks/native_m8/system_id_support_m8.mjs','docs/NATIVE_BWE_TRANSIENTS_M8_PLAN.md',
         'data/native-m8/sources.json','data/native-m8/prior-freeze-sha256.json','data/native-m8/next-validation-allocation.json',
         'reports/native-bwe-transients-m8-preflight.json']


def inventory():return {**parent.inventory(),**{name:v.sha(REPO/name) for name in SOURCES}}


def activate():v.core.source_inventory=inventory


def assets_verified():
    assets=v.read(ASSETS);v.verify_assets()
    for c in assets['content_sources']:
        assert c['segment_ms']==[0,130000] and not c['looped']
        assert v.sha(v.CACHE/c['clip_cache_path'])==c['clip_sha256']
    return assets


def prepare_next_allocation(assets):
    rng=random.Random(SEED+2);trials=[]
    for rep in range(4):
        contexts=[(c,p,x) for c in assets['content_sources'] for family in sorted({p['family_id'] for p in assets['network_profiles']})
                  for x,p in zip(parent.TARGETS,sorted([p for p in assets['network_profiles'] if p['family_id']==family],key=lambda p:(p['conditioning_geometric_mean_hint_mbps'],p['profile_id'])),strict=True)]
        rng.shuffle(contexts)
        for c,p,x in contexts:
            pair=f'm9-from-m8-p{len(trials)//2:03d}';bit=rng.getrandbits(1)
            for slot in (0,1):trials.append({'id':pair+f'-s{slot}-support','pair_id':pair,'pair_slot':slot,'repetition':rep,
                'content_id':c['content_id'],'network_profile_id':p['profile_id'],'network_family':p['family_id'],
                'target_x':x,'prefix':PREFIXES[slot^bit],'support_only':True})
    assert len(trials)==128
    v.write(ALLOCATION,{'abi':'native_conditioning_after_m8_untouched_allocation_v1','source_manifest_sha256':v.sha(ASSETS),
        'seed':SEED+2,'trials':trials,'old_m7ra_128_panel_excluded':True,'no_native_session_started':True,
        'schedule_not_instantiated_until_m8_rule_qualifies':True,
        'preserved_acceptance_gates':{k:parent.DESIGN[k] for k in ('targets_log2_bwe_over_500k','target_caliper_octaves',
            'history_state_ms','minimum_history_samples','maximum_recent_log2_drift','eligible_bwe_bounds_bps',
            'census_samples','minimum_census_span_ms','maximum_sample_gap_ms','minimum_profile_range_octaves',
            'minimum_profile_sample_sd_octaves','minimum_common_overlap_octaves','maximum_repeat_spread_octaves',
            'maximum_prefix_w_infinity_octaves','maximum_actual_census_difference_octaves','minimum_members_per_history',
            'maximum_probe_exposure_difference_octaves','maximum_entry_elapsed_difference_ms','all_original_attempts_required')},
        'derivation':{'ages_ms':DESIGN['candidate_ages_ms'],'constant_service_mbps':'0.5 * 2**target_x / 2**selected_log2_bias',
                      'entry_ms':'selected_age_ms','conditioning_duration_ms':'selected_age_ms + 9000',
                      'service_bounds_mbps':[.2,5],'probe_ms':[6000,12000],'all_128_originals_required':True}})


def prepare():
    assert not CONFIG.exists() and not ROOT.exists(),'preserve existing M8'
    parent.verify();assets=assets_verified()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',ANCHOR],cwd=REPO,text=True).splitlines()
    v.write(FREEZE,{'anchor_commit':ANCHOR,'files':{name:v.sha(REPO/name) for name in names}})
    prepare_next_allocation(assets)
    profile=next(p for p in assets['network_profiles'] if p['profile_id']=='att_lte_driving_2016-uplink-lower')
    stages={}
    for stage in ('instrumentation','characterization'):
        root,trials=ROOT/stage,[];rng=random.Random(SEED+(stage=='characterization'))
        if stage=='instrumentation':
            contexts=[(assets['content_sources'][0],0,'step_hold_fall_rise',PREFIXES[0]),
                      (assets['content_sources'][0],0,'hold_hold_fall_rise',PREFIXES[1])]
        else:
            contexts=[]
            for rep in range(2):
                for c in rng.sample(assets['content_sources'],2):
                    block=[(c,rep,order,prefix) for order in ORDERS for prefix in PREFIXES]
                    rng.shuffle(block);contexts.extend(block)
        for index,(c,rep,order,prefix) in enumerate(contexts):
            tid=f'm8-{stage[0]}-{index:03d}-support';pair=f'm8-{stage[0]}-{c["content_id"]}-r{rep}'
            early=sorted(profile['rates_mbps'][:10],reverse=prefix==PREFIXES[1]);sequence=ORDERS[order]
            panel=v.panel_for(tid,c,profile,pair,index%2,SEED,True);e=panel['episodes'][0]
            e.update(support_initial_bwe_kbps=1200,setup_delay_ms=0,system_id_sequence_mbps=sequence,
                video_segment=[0,130000],episode_timeout_s=150,
                schedule=[[early[0],'block_0',10000,early],[sequence[0],'block_1',96000,[sequence[0]]],
                          [profile['rates_mbps'][10],'block_2',12600,profile['rates_mbps'][10:22]]])
            panel['episode_timeout_s']=150
            panel['measurement_recipe'].update(scientific_role='M8 fixed service-response identification; no bitrate actions or outcome analysis',
                service_sources=assets['input_separation'],action_ratios=[],instrumentation_version='M8')
            relative=f'panels/{tid}.json';v.write(root/relative,panel)
            trials.append({'id':tid,'condition':'micro','panel':relative,'panel_sha256':v.sha(root/relative),
                'pair_id':pair,'pair_slot':index%2,'repetition':rep,'content_id':c['content_id'],'prefix':prefix,
                'input_order':order,'service_sequence_mbps':sequence,'setup_delay_ms':0,'support_only':True,
                'network_family':profile['family_id'],'network_profile_id':profile['profile_id'],
                'block':c['content_id']+'__'+str(rep),'cell_cluster':c['content_id']+'__'+prefix+'__'+order})
        p=v.protocol_for(root,trials,'development',SEED)
        p.update(abi='native_bwe_transients_m8_protocol_v1',stage=stage,anchor_commit=ANCHOR,design=DESIGN,source_hashes=inventory(),
                 source_manifest_sha256=v.sha(ASSETS),scientific_role='Support-only system identification; repeated phases stay nested within fresh native runs',
                 source_separation=assets['independence']+' '+assets['input_separation'],
                 randomization={'seed':SEED+(stage=='characterization'),'namespace':'networkrlcd-service-transients-m8',
                    'unit':'randomized 2x2 history/input-order factorial within each content/repetition block'},
                 analysis={'outcomes_read':False,'fit_or_promote_controller':False,'controller_fitting':False},
                 capture_timeout_seconds=170)
        p['trace_replay'].update(phase_duration_ms=[10000,96000,12600],measured_ticks=22,source_ticks=22,
                                synthetic_service_settings=4,tick_tolerance_ms=150)
        v.seal(root,p);config=REPO/f'configs/native_bwe_transients_m8_{stage}.json';v.write(config,p)
        stages[stage]={'protocol_sha256':v.sha(root/'protocol.json'),'committed_protocol':str(config.relative_to(REPO)),'sessions':len(trials)}
    v.write(CONFIG,{'abi':'native_bwe_transients_m8_design_v1','stages':stages,'design':DESIGN,'source_hashes':inventory(),
        'prior_freeze_sha256':v.sha(FREEZE),'next_allocation_sha256':v.sha(ALLOCATION),'characterization_untouched':True,
        'no_action_stage':True})
    return verify()


def verify():
    assert RECORDER.is_file() and (REPO/'benchmarks/native_m8/system_id_support_m8.mjs').is_file()
    config=v.read(CONFIG);assert config['design']==DESIGN and config['source_hashes']==inventory()
    assert config['prior_freeze_sha256']==v.sha(FREEZE) and config['next_allocation_sha256']==v.sha(ALLOCATION)
    for name,checksum in v.read(FREEZE)['files'].items():assert v.sha(REPO/name)==checksum,name
    assets_verified()
    for stage,meta in config['stages'].items():
        root=ROOT/stage;p=v.read(root/'protocol.json')
        assert v.sha(root/'protocol.json')==v.sha(REPO/meta['committed_protocol'])==meta['protocol_sha256']==(root/'protocol.sha256').read_text().split()[0]
        assert p['source_hashes']==inventory() and p['design']==DESIGN and len(p['trials'])==meta['sessions']==(2 if stage=='instrumentation' else 16)
        assert p['randomized_order']==[t['id'] for t in p['trials']]
        for t in p['trials']:
            assert v.sha(root/t['panel'])==t['panel_sha256']
            panel=v.read(root/t['panel']);assert v.sha(Path(panel['video_source']['path']))==panel['video_source']['sha256']
            assert panel['episode_timeout_s']==150 and t['support_only'] and t['service_sequence_mbps']==ORDERS[t['input_order']]
    assert not (parent.ROOT/'validation/sessions').exists(),'M7RA validation must stay untouched'
    activate()
    return {'verified':True,'instrumentation_sessions':2,'characterization_sessions':16,'next_untouched_allocation':128,
            'prior_files_unchanged':len(v.read(FREEZE)['files']),'controller_fitted':False}


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
    start_held=[original[2]]+[x for x in extra if x['role']=='holdout' and not x['label'].startswith('m8_')]
    assert (len(start_train),len(start_held))==(35,4)
    check=lambda a,b:v.core.validate_markers(a+b,list(range(len(a))),list(range(len(a),len(a)+len(b))))
    full,beginning=check(train,held),check(start_train,start_held)
    origin,vertices=v.core.feasible_polygon(train)
    return {'full':full,'beginning':beginning,'training_ids':[x['marker_id'] for x in train],'holdout_ids':[x['marker_id'] for x in held]},original,origin,vertices


def fidelity(directory,trial,panel,origin,vertices,phase_windows):
    phases,ticks,initial,updates=[],[],[],[]
    with gzip.open(directory/'events.jsonl.gz','rt') as stream:
        for line in stream:
            e=json.loads(line);kind=e.get('kind')
            if kind=='phase':phases.append(e)
            elif kind=='trace_capacity':ticks.append(e)
            elif kind=='system_id_initial':initial.append(e)
            elif kind=='system_id_service':updates.append(e)
    evidence=v.read(directory/'system_id_evidence.json');commands=evidence['commands'];done=evidence['completion']
    start=phase_windows[1]['start_ms'];checks={'inventory':len(phases)==3 and len(ticks)==22 and len(initial)==1 and len(updates)==len(commands)==3,
        'initial_setting':initial[0]['capacity_mbps']==trial['service_sequence_mbps'][0] and evidence['initial']['at_ms']==initial[0]['at_ms'],
        'completion':done is not None and done['browser_start_ms']==start and 96000<=done['browser_end_ms']-start<=96250 and
            96000<=phase_windows[1]['end_ms']-start<=96250 and done['service_sequence_mbps']==trial['service_sequence_mbps']}
    worst_tick,worst_ack,worst_late=0.,0.,0.;exact=True;command_ok=True;mapped=[]
    for phase,schedule in zip(phases,panel['episodes'][0]['schedule'],strict=True):
        _,name,_,rates=schedule;actual=initial if name=='block_1' else [t for t in ticks if t['phase']==name]
        exact=exact and phase['phase']==name and phase['trace_mbps']==rates and phase['capacity_mbps']==rates[0] and len(actual)==len(rates)
        for i,(tick,rate) in enumerate(zip(actual,rates,strict=True)):
            error=abs(tick['at_ms']-phase['at_ms']-i*1000);worst_tick=max(worst_tick,error)
            exact=exact and tick['sample_index']==i and tick['capacity_mbps']==rate and error<=150
    checks['exact_source_ticks']=exact
    for i,(c,u) in enumerate(zip(commands,updates,strict=True),1):
        ack=c['browser_receive_ms']-c['browser_request_ms'];late=c['browser_request_ms']-(start+i*24000)
        worst_ack,worst_late=max(worst_ack,ack),max(worst_late,late)
        lo,hi=v.core.mapped_browser_range(u['node_applied_ms'],origin,vertices)
        command_ok=command_ok and c['sequence']==u['sequence']==i and c['previous_mbps']==trial['service_sequence_mbps'][i-1] and c['requested_mbps']==trial['service_sequence_mbps'][i]
        command_ok=command_ok and u['capacity_mbps']==c['readback']['capacity_mbps']==c['requested_mbps'] and u['node_applied_ms']==c['readback']['node_applied_ms'] and 0<=ack<=100 and 0<=late<=150
        command_ok=command_ok and c['browser_request_ms']-1<=lo<=hi<=c['browser_receive_ms']+1
        mapped.append({'plateau':i,'browser_applied_ms_bounds':[lo,hi],'browser_ack_ms':c['browser_receive_ms'],'true_step':c['previous_mbps']!=c['requested_mbps']})
    checks['strict_commands_and_clock_ordering']=command_ok
    initial_bounds=v.core.mapped_browser_range(initial[0]['at_ms'],origin,vertices)
    mapped.insert(0,{'plateau':0,'browser_applied_ms_bounds':initial_bounds,'browser_ack_ms':start,'true_step':True})
    probe=phase_windows[2]['start_ms'];probe_ticks=[t for t in ticks if t['phase']=='block_2'];exposure={}
    for endpoint in (6000,12000):
        totals=[]
        for alpha,beta in vertices:
            series=[(origin+(t['at_ms']-beta)/alpha-probe,t['capacity_mbps']) for t in probe_ticks]
            rate,cursor,total=series[0][1],1000.,0.
            for ms,value in series:
                if ms<=1000:rate=value;continue
                if ms>=endpoint:break
                total+=rate*(ms-cursor);rate,cursor=value,ms
            total+=rate*(endpoint-cursor);totals.append(total*125)
        exposure[str(endpoint)]=[min(totals),max(totals)]
    return {'passed':all(checks.values()),'checks':checks,'maximum_tick_error_ms':worst_tick,'maximum_ack_ms':worst_ack,
            'maximum_command_lateness_ms':worst_late,'service_events':mapped,'capacity_exposure_bytes_bounds':exposure}


def session_gate(root,t,item,p):
    row={'trial':t['id'],'capture_status':item['status'],'passed':False,**{k:t[k] for k in ('content_id','prefix','input_order','block','repetition')}}
    if item['status']!='sealed':row['reason']='failed original; no response interpretation';return row
    d=root/'sessions'/t['id']
    try:
        clock,markers,origin,vertices=clocks(d);sender=v.read(d/'sender_observations.json');points=parent.points_for(sender)
        windows=v.read(d/'phase_windows.json')['phase_windows'];assert [w['phase'] for w in windows]==['block_0','block_1','block_2']
        ice=v.read(d/'ice_evidence.json');urls={c.get('url') for peer in ('a','b') for c in ice.get('candidates',{}).get(peer,[])}
        transport=v.frozen.base.transport_checks(root,t['id'],next(iter(urls)) if len(urls)==1 else '')
        cleanup=v.frozen.terminal_cleanup_gate(root,t,markers,p);startup=r.startup_check(d,sender,t)
        readback=bool(sender['decisions']) and not sender['sampling_errors'] and not sender['support_screen']['action_assigned'] and all(
            x['actuator_assignment'] is None and not x['changed'] and x['actuation_readback']['encoder_max_bitrate_bps']==4000000 and x['actuation_readback']['receiver_jitter_buffer_target_ms']==0 for x in sender['decisions'])
        progress=v.read(d/'media_progress.json');media=len(progress)==3 and all(x['frames_encoded']>10 and x['frames_decoded']>10 and math.isfinite(x['mean_encode_s']) for x in progress)
        media=media and all(progress[i][key]-progress[i-1][key]>10 for i in (1,2) for key in ('frames_encoded','frames_decoded'))
        sampled=[x for x in points if windows[1]['start_ms']<=x['ms']<=windows[1]['end_ms']]
        gaps=[b['ms']-a['ms'] for a,b in zip(sampled,sampled[1:])]
        observer=len(sampled)>=900 and bool(gaps) and max(gaps)<=250 and all(x['valid'] and x['bwe']>0 for x in sampled)
        replay=fidelity(d,t,v.read(root/t['panel']),origin,vertices,windows)
        row.update(clock=clock,startup=startup,transport_passed=transport['passed'],cleanup_passed=cleanup['passed'],readback_passed=readback,
                   media_passed=media,observer_passed=observer,observer_samples=len(sampled),maximum_observer_gap_ms=max(gaps,default=None),
                   input_fidelity=replay,step_phase_start_ms=windows[1]['start_ms'],measurement_step_start_elapsed_ms=windows[1]['start_ms']-sender['measurement_start_ms'])
        row['passed']=all((clock['full']['passed'],clock['beginning']['passed'],startup['passed'],transport['passed'],cleanup['passed'],readback,media,observer,replay['passed']))
    except (AssertionError,ValueError,KeyError,IndexError,StopIteration,ZeroDivisionError) as exc:row['reason']=f'{type(exc).__name__}: {exc}'
    return row


def gate(stage):
    verify();root=ROOT/stage;p,index=v.core.check_capture_integrity(root)
    rows=[session_gate(root,t,i,p) for t,i in zip(p['trials'],index['sessions'],strict=True)]
    common={}
    if stage=='characterization':
        for block in sorted({x['block'] for x in rows}):
            items=[x for x in rows if x['block']==block];available=len(items)==4 and all(x['passed'] for x in items)
            error=None;elapsed=None
            if available:
                errors=[]
                for endpoint in ('6000','12000'):
                    bounds=[x['input_fidelity']['capacity_exposure_bytes_bounds'][endpoint] for x in items]
                    errors.append(abs(math.log2(max(b[1] for b in bounds)/min(b[0] for b in bounds))))
                error=max(errors);times=[x['measurement_step_start_elapsed_ms'] for x in items];elapsed=max(times)-min(times)
            common[block]={'passed':bool(available and error<=.01 and elapsed<=250),'maximum_probe_exposure_difference_octaves':error,'step_start_elapsed_spread_ms':elapsed}
    result={'abi':'native_bwe_transients_m8_acquisition_v1','stage':stage,'protocol_sha256':v.sha(root/'protocol.json'),
            'capture_index_sha256':v.sha(root/'capture_index.json'),'planned_sessions':len(p['trials']),'qualified_sessions':sum(x['passed'] for x in rows),
            'passed':all(x['passed'] for x in rows) and all(x['passed'] for x in common.values()),'sessions':rows,'common_probe_checks':common,
            'delivery_qoe_action_outcomes_read':False,'controller_fitted':False,'native_common_support_established':False}
    v.write(root/'support_clock_transport_gate.json',result);v.write(root/'mechanism_qualification_gate.json',result)
    v.write(REPO/f'reports/native-bwe-transients-m8-{stage}-gate.json',result)
    return {'stage':stage,'planned':len(rows),'qualified':result['qualified_sessions'],'passed':result['passed']}


def capture(stage):
    verify()
    for name in SOURCES+[str(CONFIG.relative_to(REPO))]+[f'configs/native_bwe_transients_m8_{x}.json' for x in ('instrumentation','characterization')]:
        assert subprocess.check_output(['git','show','HEAD:'+name],cwd=REPO)==(REPO/name).read_bytes(),'commit before capture'
    if stage=='characterization':assert v.read(ROOT/'instrumentation/mechanism_qualification_gate.json')['passed'],'instrumentation must qualify first'
    root=ROOT/stage;p=v.read(root/'protocol.json');current,_=v.frozen.base.runtime_provenance(Path(p['preflight_reference']['path']))
    assert current==p['runtime'];v.frozen.v2.set_runtime_env(p)
    assert v.read(root/'clock_report.json')['passed'];v.core.verify_sources(p)
    sessions=root/'sessions';sessions.mkdir(exist_ok=False)
    index={'abi':'native_clock_action_capture_index_v1','protocol_sha256':v.sha(root/'protocol.json'),'sessions':[]}
    for t in p['trials']:
        child=sessions/t['id'];assert v.sha(root/t['panel'])==t['panel_sha256']
        command=['node',str(RECORDER),str(child),str(root/t['panel']),t['id'],t['condition']]
        try:
            proc=subprocess.run(command,cwd=REPO,env=os.environ.copy(),capture_output=True,text=True,timeout=170)
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify','capture','gate']);parser.add_argument('--stage',choices=['instrumentation','characterization'],default='instrumentation');args=parser.parse_args()
    print(json.dumps(globals()[args.command](args.stage) if args.command in ('capture','gate') else globals()[args.command]()))
