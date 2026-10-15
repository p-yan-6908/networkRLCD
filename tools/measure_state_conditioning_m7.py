"""Preregistered native common-state creation; support variables only, no actions."""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import random
import statistics as st
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location('m7_frozen_m5_dependencies', REPO/'tools/measure_prefix_memory_m5.py')
m5 = importlib.util.module_from_spec(s)
s.loader.exec_module(m5)
r, v = m5.r, m5.v
ROOT = v.CACHE/'native-state-conditioning-m7'
CONFIG = REPO/'configs/native_state_conditioning_m7.json'
ASSETS = REPO/'data/native-m7/sources.json'
FREEZE = REPO/'data/native-m7/prior-freeze-sha256.json'
RECORDER = REPO/'benchmarks/native_m7/state_conditioning_episode_m7.mjs'
SEED = 20261123
PREFIXES = ('ascending_prefix', 'descending_prefix')
TARGETS = (0., .5, 1., 1.5)
SOURCES = ['tools/measure_state_conditioning_m7.py', 'tools/build_state_conditioning_m7.py',
           'tools/prepare_state_conditioning_m7_assets.py', 'benchmarks/native_m7/state_conditioning_episode_m7.mjs',
           'benchmarks/native_m7/state_conditioning_support_m7.mjs', 'docs/NATIVE_STATE_CONDITIONING_M7_PLAN.md',
           'data/native-m7/sources.json', 'data/native-m7/prior-freeze-sha256.json',
           'reports/native-state-conditioning-m7-access-preflight.json', 'reports/native-state-conditioning-m7-runtime-preflight.json']
DESIGN = {'targets_log2_bwe_over_500k':list(TARGETS), 'target_caliper_octaves':.125,
          'conditioning':{'gain':.25, 'max_step_octaves':.125, 'service_bounds_mbps':[.2,5.], 'updates':26,
                          'update_spacing_ms':1000, 'feedback_off_ms':27000, 'duration_ms':32000,
                          'input_history_ms':1000, 'minimum_input_samples':7, 'maximum_input_gap_ms':250,
                          'maximum_command_lateness_ms':150, 'maximum_readback_delay_ms':100},
          'entry_window_ms':[30000,30300], 'history_state_ms':3000, 'minimum_history_samples':27,
          'maximum_recent_log2_drift':.05, 'probe_windows_ms':[[6000,6300],[12000,12300]],
          'eligible_bwe_bounds_bps':[240000,3800000], 'census_samples':11, 'minimum_census_span_ms':900,
          'maximum_sample_gap_ms':250, 'minimum_profile_range_octaves':1., 'minimum_profile_sample_sd_octaves':.35,
          'minimum_common_overlap_octaves':.5, 'maximum_repeat_spread_octaves':.25,
          'maximum_prefix_w_infinity_octaves':.25, 'maximum_actual_census_difference_octaves':.25,
          'maximum_probe_exposure_difference_octaves':.01, 'maximum_entry_elapsed_difference_ms':250,
          'validation_original_repeats_per_history':4, 'minimum_members_per_history':4,
          'all_original_attempts_required':True, 'no_retries_or_optional_stopping':True,
          'no_action_randomization':True, 'no_controllers_or_predictors_fitted':True}


def inventory():
    return {**m5.inventory(), **{name:v.sha(REPO/name) for name in SOURCES}}


def activate():
    v.core.source_inventory, v.core.RECORDER = inventory, RECORDER


def assets_verified():
    assets = v.read(ASSETS)
    assert assets['parent_manifest_sha256'] == v.sha(REPO/'data/native-v13/sources.json')
    v.verify_assets()
    for c in assets['content_sources']:
        assert c['segment_ms'] == [0,60000] and not c['looped']
        assert v.sha(v.CACHE/c['clip_cache_path']) == c['clip_sha256']
    return assets


def prepare():
    assert not CONFIG.exists() and not ROOT.exists(), 'preserve an existing M7 registration'
    m5.verify()
    assets = assets_verified()
    prior = subprocess.check_output(['git','ls-tree','-r','--name-only','6dc05b5'],cwd=REPO,text=True).splitlines()
    v.write(FREEZE, {'anchor_commit':'6dc05b56ee4d1a657e2514ffc2a7d1d68dc49454',
                    'files':{name:v.sha(REPO/name) for name in prior}})
    mapping = {}
    for family in sorted({p['family_id'] for p in assets['network_profiles']}):
        profiles = sorted((p for p in assets['network_profiles'] if p['family_id']==family),
                          key=lambda p:(p['conditioning_geometric_mean_hint_mbps'],p['profile_id']))
        assert len(profiles)==4
        mapping[family] = [{'target_x':x,'profile':p} for x,p in zip(TARGETS,profiles,strict=True)]
    stages = {}
    for stage in ('feasibility','validation'):
        root, trials, rng = ROOT/stage, [], random.Random(SEED+(stage=='validation'))
        contexts = []
        if stage == 'feasibility':
            profile = next(p for p in assets['network_profiles'] if p['profile_id']=='att_lte_driving_2016-uplink-lower')
            contexts = [(assets['content_sources'][0],profile,x,0) for x in (TARGETS[0],TARGETS[-1])]
        else:
            for rep in range(DESIGN['validation_original_repeats_per_history']):
                block = [(c,item['profile'],item['target_x'],rep) for c in assets['content_sources']
                         for family, items in sorted(mapping.items()) for item in items]
                rng.shuffle(block)
                contexts.extend(block)
        if stage == 'feasibility':
            rng.shuffle(contexts)
        for ci,(content,profile,x,rep) in enumerate(contexts):
            pair = f'm7-{stage[0]}-p{ci:03d}'
            bit = rng.getrandbits(1)
            for slot in (0,1):
                prefix = PREFIXES[slot^bit]
                early = sorted(profile['rates_mbps'][:10], reverse=prefix=='descending_prefix')
                tid = pair+f'-s{slot}-support'
                panel = v.panel_for(tid,content,profile,pair,slot,SEED,True)
                episode = panel['episodes'][0]
                episode.update(support_initial_bwe_kbps=1200, setup_delay_ms=0, conditioning_target_x=x,
                               video_segment=[0,60000], schedule=[[early[0],'block_0',10000,early],
                                 [.5*2**x,'block_1',32000,[.5*2**x]],
                                 [profile['rates_mbps'][10],'block_2',12600,profile['rates_mbps'][10:22]]])
                panel['measurement_recipe'].update(scientific_role='M7 support-only state creation; no action-value/QoE analysis',
                    service_sources='Constructed prefix + synthetic feedback conditioning + original unscaled measured-source probe',
                    state_definition='Fixed BWE target plus past 3-second occupancy and two one-second BWE means',
                    action_ratios=[],instrumentation_version='M7-derived-from-qualified-M4R')
                relative = f'panels/{tid}.json'
                v.write(root/relative,panel)
                trials.append({'id':tid,'condition':'micro','panel':relative,'panel_sha256':v.sha(root/relative),
                    'pair_id':pair,'pair_slot':slot,'repetition':rep,'support_only':True,'content_id':content['content_id'],
                    'prefix':prefix,'setup_delay_ms':0,'target_x':x,'network_family':profile['family_id'],
                    'network_campaign_id':profile['campaign_id'],'network_profile_id':profile['profile_id'],
                    'cell_cluster':content['content_id']+'__'+profile['family_id']+'__'+str(x)})
        p = v.protocol_for(root,trials,'confirmatory' if stage=='validation' else 'development',SEED)
        p.update(abi='native_state_conditioning_m7_protocol_v1',stage='state_creation_'+stage,anchor_commit='6dc05b5',
                 source_hashes=inventory(),design=DESIGN,source_manifest_sha256=v.sha(ASSETS),
                 target_profile_mapping=mapping,randomization={'seed':SEED+(stage=='validation'),
                    'namespace':'networkrlcd-state-conditioning-m7','unit':'prefix order within fresh paired contexts; randomized block order'},
                 scientific_role='Prospective native common-state creation. No state search on M6R. No bitrate actions or fitted predictor.',
                 source_separation=assets['independence']+' '+assets['input_separation'])
        p['trace_replay'].update(phase_duration_ms=[10000,32000,12600],measured_ticks=22,
            source_ticks=22,constructed_prefix_ticks=10,unscaled_measured_probe_ticks=12,
            synthetic_conditioning_initializations=1,synthetic_conditioning_updates=26,tick_tolerance_ms=150)
        p['analysis']={'outcomes_read':False,'fit_or_promote_controller':False,'support_only':True,
                       'future_action_study_requires_separate_registration':True}
        v.seal(root,p)
        path = REPO/f'configs/native_state_conditioning_m7_{stage}.json'
        v.write(path,p)
        stages[stage]={'protocol_sha256':v.sha(root/'protocol.json'),'committed_protocol':str(path.relative_to(REPO)),
                       'planned_sessions':len(trials)}
    v.write(CONFIG,{'abi':'native_state_conditioning_m7_design_v1','design':DESIGN,'stages':stages,
                    'prior_freeze_sha256':v.sha(FREEZE),'sources_sha256':inventory(),
                    'development_and_validation_captures_disjoint':True,'validation_untouched_at_registration':True})
    return verify()


def verify():
    config = v.read(CONFIG)
    assert config['design']==DESIGN and config['sources_sha256']==inventory()
    assert config['prior_freeze_sha256']==v.sha(FREEZE)
    for name,checksum in v.read(FREEZE)['files'].items():
        assert v.sha(REPO/name)==checksum, name
    assets_verified()
    for stage,metadata in config['stages'].items():
        root=ROOT/stage
        assert v.sha(root/'protocol.json')==metadata['protocol_sha256']==v.sha(REPO/metadata['committed_protocol'])
        assert (root/'protocol.sha256').read_text().split()[0]==metadata['protocol_sha256']
        p=v.read(root/'protocol.json')
        assert p['source_hashes']==inventory() and p['design']==DESIGN
        assert len(p['trials'])==metadata['planned_sessions']==(4 if stage=='feasibility' else 128)
        assert p['randomized_order']==[t['id'] for t in p['trials']]
        for t in p['trials']:
            assert v.sha(root/t['panel'])==t['panel_sha256'] and t['support_only']
    activate()
    return {'verified':True,'feasibility_sessions':4,'validation_sessions':128,
            'validation_started':(ROOT/'validation/sessions').exists(),'prior_files_unchanged':len(v.read(FREEZE)['files'])}


def points_for(sender):
    return [{'ms':d['sample_ms'],'bwe':d['policy_input']['features'][0]*4000000,
             'valid':d['policy_input']['features'][9]==1} for d in sender['decisions']]


def census(points, endpoint):
    for i,p in enumerate(points):
        tail=points[max(0,i-10):i+1]
        if endpoint<=p['ms']<=endpoint+300 and len(tail)==11 and tail[-1]['ms']-tail[0]['ms']>=900 and all(
            0<b['ms']-a['ms']<=250 for a,b in zip(tail,tail[1:])) and all(q['valid'] and 240000<=q['bwe']<=3800000 for q in tail):
            return {'passed':True,'cutoff_ms':p['ms'],'x':st.mean(math.log2(q['bwe']/500000) for q in tail),
                    'instantaneous_x':math.log2(p['bwe']/500000),'samples':len(tail),'history_span_ms':tail[-1]['ms']-tail[0]['ms']}
    return {'passed':False,'reason':'no eligible fixed-window 11-sample census'}


def conditioning_check(directory, points, target, phase_start):
    evidence=v.read(directory/'conditioning_evidence.json')
    commands,release=evidence['commands'],evidence['release']
    checks={'all_26_updates':len(commands)==26,'initial_service':evidence['initial']['capacity_mbps']==.5*2**target,
            'release_recorded':release is not None}
    previous=.5*2**target
    max_ack,max_late=0.,0.
    formulas=True
    for i,c in enumerate(commands,1):
        cutoff=c['decision_cutoff_ms']
        expected=[{'sample_ms':p['ms'],'valid':p['valid'],'bwe_bps':p['bwe']} for p in points if cutoff-1000<p['ms']<=cutoff]
        mean=st.mean(math.log2(p['bwe_bps']/500000) for p in expected) if expected else float('inf')
        requested=max(.2,min(5.,previous*2**max(-.125,min(.125,.25*(target-mean)))))
        ack=c['browser_receive_ms']-c['browser_request_ms']
        late=c['browser_request_ms']-(phase_start+i*1000)
        max_ack,max_late=max(max_ack,ack),max(max_late,late)
        formulas = formulas and c['sequence']==i and c['target_x']==target and c['input']==expected and len(expected)>=7 and all(p['valid'] and p['bwe_bps']>0 for p in expected)
        formulas = formulas and all(0<b['sample_ms']-a['sample_ms']<=250 for a,b in zip(expected,expected[1:]))
        formulas = formulas and abs(c['previous_mbps']-previous)<1e-12 and abs(c['requested_mbps']-requested)<1e-12 and abs(c['mean_x']-mean)<1e-12
        formulas = formulas and c['readback']['capacity_mbps']==c['requested_mbps'] and c['readback']['sequence']==i and 0<=ack<=100 and 0<=late<=150
        previous=c['readback']['capacity_mbps']
    checks['causal_inputs_exact_formula_and_readback']=formulas
    checks['feedback_off_on_time']=bool(release and release['feedback_off'] and release['sequence']==27 and 27000<=release['browser_ms']-phase_start<=27150 and release['capacity_mbps']==previous)
    return {'passed':all(checks.values()),'checks':checks,'maximum_ack_ms':max_ack,'maximum_lateness_ms':max_late,
            'last_feedback_update_ms':commands[-1]['browser_receive_ms'] if commands else None,
            'feedback_off_ms':release['browser_ms'] if release else None,'final_service_mbps':previous}


def input_fidelity(directory,panel,origin,vertices,probe_start):
    phases,ticks,initial,updates=[],[],[],[]
    with gzip.open(directory/'events.jsonl.gz','rt') as stream:
        for line in stream:
            e=json.loads(line)
            if e.get('kind')=='phase':phases.append(e)
            elif e.get('kind')=='trace_capacity':ticks.append(e)
            elif e.get('kind')=='conditioning_initial':initial.append(e)
            elif e.get('kind')=='conditioning_service':updates.append(e)
    checks={'phases':len(phases)==3,'source_tick_count':len(ticks)==22,'conditioning_count':len(initial)==1 and len(updates)==26}
    worst=0.
    exact=True
    for phase,schedule in zip(phases,panel['episodes'][0]['schedule'],strict=True):
        _,name,_,rates=schedule
        exact=exact and phase['phase']==name and phase['trace_mbps']==rates and phase['capacity_mbps']==rates[0]
        actual=initial if name=='block_1' else [t for t in ticks if t['phase']==name]
        exact=exact and len(actual)==len(rates)
        for i,(tick,rate) in enumerate(zip(actual,rates,strict=True)):
            error=abs(tick['at_ms']-phase['at_ms']-i*1000);worst=max(worst,error)
            exact=exact and tick['sample_index']==i and tick['capacity_mbps']==rate and error<=150
    checks['exact_unscaled_source_and_timing']=exact
    recorded=v.read(directory/'conditioning_evidence.json')['commands']
    checks['node_service_readbacks_match']=len(recorded)==len(updates) and all(
        u['sequence']==c['sequence'] and u['capacity_mbps']==c['readback']['capacity_mbps'] and
        u['node_applied_ms']==c['readback']['node_applied_ms'] and
        u['previous_mbps']==c['previous_mbps'] for u,c in zip(updates,recorded,strict=True))
    probe_ticks=[t for t in ticks if t['phase']=='block_2']
    exposure={}
    for endpoint in (6000,12000):
        totals=[]
        for alpha,beta in vertices:
            series=[{'ms':origin+(t['at_ms']-beta)/alpha-probe_start,'rate':t['capacity_mbps']} for t in probe_ticks]
            rate,cursor,total=series[0]['rate'],1000.,0.
            for tick in series:
                if tick['ms']<=1000:rate=tick['rate'];continue
                if tick['ms']>=endpoint:break
                total+=rate*(tick['ms']-cursor);rate,cursor=tick['rate'],tick['ms']
            total+=rate*(endpoint-cursor);totals.append(total*125)
        exposure[str(endpoint)]=[min(totals),max(totals)]
    return {'passed':all(checks.values()),'checks':checks,'maximum_tick_error_ms':worst,
            'capacity_exposure_bytes_bounds':exposure,'probe_exposure_starts_relative_ms':1000}


def session_gate(root,trial,item):
    row={'trial':trial['id'],'capture_status':item['status'],'technical_passed':False,'passed':False,
         **{k:trial[k] for k in ('content_id','prefix','target_x','pair_id','repetition','network_family','network_profile_id','cell_cluster')}}
    if item['status']!='sealed':
        row['reason']='failed capture; retained original, no treatment interpretation'
        return row
    directory=root/'sessions'/trial['id']
    try:
        clock,markers,origin,vertices=r.clocks(directory)
        sender=v.read(directory/'sender_observations.json');points=points_for(sender)
        phases=v.read(directory/'phase_windows.json')['phase_windows']
        assert [p['phase'] for p in phases]==['block_0','block_1','block_2']
        cstart,probe=phases[1]['start_ms'],phases[2]['start_ms']
        ice=v.read(directory/'ice_evidence.json')
        urls={c.get('url') for peer in ('a','b') for c in ice.get('candidates',{}).get(peer,[])}
        transport=v.frozen.base.transport_checks(root,trial['id'],next(iter(urls)) if len(urls)==1 else '')
        cleanup=v.frozen.terminal_cleanup_gate(root,trial,markers,v.read(root/'protocol.json'))
        startup=r.startup_check(directory,sender,trial)
        readback=not sender['support_screen']['action_assigned'] and bool(sender['decisions']) and not sender['sampling_errors'] and all(
            d['actuator_assignment'] is None and not d['changed'] and d['actuation_readback']['encoder_max_bitrate_bps']==4000000 and d['actuation_readback']['receiver_jitter_buffer_target_ms']==0 for d in sender['decisions'])
        progress=v.read(directory/'media_progress.json')
        media=len(progress)==3 and all(x['frames_encoded']>10 and x['frames_decoded']>10 and math.isfinite(x['mean_encode_s']) for x in progress)
        media=media and all(progress[i][k]-progress[i-1][k]>10 for i in (1,2) for k in ('frames_encoded','frames_decoded'))
        cond=conditioning_check(directory,points,trial['target_x'],cstart)
        fidelity=input_fidelity(directory,v.read(root/trial['panel']),origin,vertices,probe)
        technical=all((clock['full']['passed'],clock['beginning']['passed'],transport['passed'],cleanup['passed'],startup['passed'],readback,media,cond['passed'],fidelity['passed']))
        entry=census(points,cstart+30000)
        baseline,history=False,False
        if entry['passed']:
            cutoff=entry['cutoff_ms'];recent=[p for p in points if cutoff-3000<p['ms']<=cutoff]
            last=[p for p in recent if cutoff-1000<p['ms']<=cutoff]
            before=[p for p in recent if cutoff-2000<p['ms']<=cutoff-1000]
            recent_valid=all(p['valid'] and 240000<=p['bwe']<=3800000 for p in recent)
            xs=[math.log2(p['bwe']/500000) for p in recent] if recent_valid else []
            drift=st.mean(math.log2(p['bwe']/500000) for p in last)-st.mean(math.log2(p['bwe']/500000) for p in before) if recent_valid and last and before else None
            baseline=abs(entry['instantaneous_x']-trial['target_x'])<=.125+1e-12
            history=bool(baseline and len(recent)>=27 and len(last)>=7 and len(before)>=7 and recent_valid and
                         all(0<b['ms']-a['ms']<=250 for a,b in zip(recent,recent[1:])) and
                         max(abs(x-trial['target_x']) for x in xs)<=.125+1e-12 and abs(drift)<=.05 and
                         cond['feedback_off_ms'] is not None and cond['feedback_off_ms']<=cutoff-3000)
            entry.update(baseline_member=baseline,history_member=history,recent_n=len(recent),recent_min_x=min(xs) if xs else None,
                         recent_max_x=max(xs) if xs else None,recent_drift_x=drift,
                         feedback_off_before_cutoff_ms=cutoff-cond['feedback_off_ms'] if cond['feedback_off_ms'] else None,
                         measurement_elapsed_ms=cutoff-sender['measurement_start_ms'])
        row.update(technical_passed=technical,clock=clock,startup=startup,transport_passed=transport['passed'],
                   cleanup_passed=cleanup['passed'],readback_passed=readback,media_passed=media,conditioning=cond,
                   fidelity=fidelity,entry=entry,baseline_member=baseline,history_member=history,
                   probe_windows={str(t):census(points,probe+t) for t in (6000,12000)})
        row['passed']=technical and entry['passed'] and history and all(w['passed'] for w in row['probe_windows'].values())
    except (AssertionError,ValueError,KeyError,IndexError,StopIteration,ZeroDivisionError) as exc:
        row['reason']=f'{type(exc).__name__}: {exc}'
    return row


def summarize_groups(rows):
    groups=defaultdict(list)
    for row in rows:groups[row['cell_cluster']].append(row)
    result={}
    for key,members in sorted(groups.items()):
        states={}
        for endpoint in ('entry','6000','12000'):
            vals=[];arms=[]
            for prefix in PREFIXES:
                arm=[]
                for row in members:
                    if row['prefix']!=prefix:continue
                    w=row.get('entry',{}) if endpoint=='entry' else row.get('probe_windows',{}).get(endpoint,{})
                    if w.get('passed'):arm.append(w['x'])
                arms.append(sorted(arm));vals+=arm
            valid=len(vals)==len(members) and len(arms[0])==len(arms[1]) and bool(arms[0])
            spread=max(vals)-min(vals) if vals else None
            winf=max(abs(a-b) for a,b in zip(*arms,strict=True)) if valid else None
            mean=st.mean(vals) if vals else None
            max_census_distance=max(abs(x-mean) for x in vals) if vals else None
            states[endpoint]={'all_originals_observable':valid,'prefix_values':dict(zip(PREFIXES,arms,strict=True)),
                'full_repeat_spread_octaves':spread,'prefix_w_infinity_octaves':winf,
                'census_mean_x':mean,'maximum_actual_census_difference_octaves':max_census_distance,
                'passed':bool(valid and spread<=.25+1e-12 and winf<=.25+1e-12 and max_census_distance<=.25+1e-12)}
        count={p:sum(x.get('history_member',False) and x['technical_passed'] and x['prefix']==p for x in members) for p in PREFIXES}
        result[key]={'originals':len(members),'history_counts':count,'baseline_counts':{p:sum(x.get('baseline_member',False) and x['technical_passed'] and x['prefix']==p for x in members) for p in PREFIXES},
                     'states':states,'all_originals_passed':all(x['passed'] for x in members)}
    return result


def gate(stage):
    verify();root=ROOT/stage
    p,index=v.core.check_capture_integrity(root)
    rows=[session_gate(root,t,i) for t,i in zip(p['trials'],index['sessions'],strict=True)]
    technical=all(x['technical_passed'] for x in rows)
    base={'abi':'native_state_conditioning_m7_acquisition_v1','stage':p['stage'],'protocol_sha256':v.sha(root/'protocol.json'),
          'capture_index_sha256':v.sha(root/'capture_index.json'),'planned_sessions':len(p['trials']),
          'qualified_sessions':sum(x['technical_passed'] for x in rows),'passed':technical,'sessions':rows,
          'delivery_qoe_action_outcomes_read':False,'predictors_fitted':False,'controller_fitted':False}
    v.write(root/'support_clock_transport_gate.json',base)
    groups=summarize_groups(rows)
    pairs=defaultdict(list)
    for row in rows:pairs[row['pair_id']].append(row)
    fidelity={}
    for pair,members in pairs.items():
        details={}
        for endpoint in ('6000','12000'):
            available=len(members)==2 and all(x['technical_passed'] for x in members)
            error=None
            if available:
                a,b=[x['fidelity']['capacity_exposure_bytes_bounds'][endpoint] for x in members]
                error=max(abs(math.log2(a[0]/b[1])),abs(math.log2(a[1]/b[0])))
            details[endpoint]={'passed':bool(available and error<=.01),'maximum_log2_exposure_difference':error}
        elapsed=[x.get('entry',{}).get('measurement_elapsed_ms') for x in members]
        timing=all(x is not None for x in elapsed) and max(elapsed)-min(elapsed)<=250
        fidelity[pair]={'passed':all(x['passed'] for x in details.values()) and timing,'probe':details,
                        'entry_elapsed_difference_ms':max(elapsed)-min(elapsed) if all(x is not None for x in elapsed) else None}
    panel={}
    if stage=='validation':
        for content,family in sorted({(x['content_id'],x['network_family']) for x in rows}):
            means=[]
            for target in TARGETS:
                selected=[x for x in rows if x['content_id']==content and x['network_family']==family and x['target_x']==target]
                valid=len(selected)==8 and all(x['passed'] for x in selected)
                means.append(st.mean(x['entry']['x'] for x in selected) if valid else None)
            available=all(x is not None for x in means)
            span=max(means)-min(means) if available else None;sd=st.stdev(means) if available else None
            panel[content+'__'+family]={'target_census_means':means,'range_octaves':span,'sample_sd_octaves':sd,
                'passed':bool(available and span>=1. and sd>=.35),'interval':[min(means),max(means)] if available else None}
    overlap=None
    if panel and all(x['interval'] is not None for x in panel.values()):
        overlap=min(x['interval'][1] for x in panel.values())-max(x['interval'][0] for x in panel.values())
    memberships=all(x['passed'] for x in rows) and all(min(g['history_counts'].values())>=(1 if stage=='feasibility' else 4) for g in groups.values())
    repeatability=all(w['passed'] for g in groups.values() for w in g['states'].values())
    panel_pass=stage=='feasibility' or (len(panel)==4 and all(x['passed'] for x in panel.values()) and overlap is not None and overlap>=.5)
    result={**base,'abi':'native_state_conditioning_m7_qualification_v1','base_gate_sha256':v.sha(root/'support_clock_transport_gate.json'),
            'technical_passed':technical,'state_membership_passed':memberships,'repeatability_passed':repeatability,
            'pair_fidelity':fidelity,'groups':groups,'panel_gates':panel,'common_overlap_octaves':overlap,
            'range_sd_overlap_passed':panel_pass,'registered_minimum_history_count':1 if stage=='feasibility' else 4,
            'passed':technical and memberships and repeatability and all(x['passed'] for x in fidelity.values()) and panel_pass,
            'native_common_support_established':False,'future_action_stage_enabled':False,
            'scope':'Feasibility gate only' if stage=='feasibility' else 'Two reused contents/two measured-source bundles within one program, synthetic conditioning; no broad network generalization'}
    result['native_common_support_established']=stage=='validation' and result['passed']
    v.write(root/'mechanism_qualification_gate.json',result)
    v.write(REPO/f'reports/native-state-conditioning-m7-{stage}-gate.json',result)
    return {'stage':stage,'planned':len(rows),'technical_qualified':base['qualified_sessions'],
            'history_members':sum(x.get('history_member',False) and x['technical_passed'] for x in rows),
            'passed':result['passed'],'native_common_support_established':result['native_common_support_established']}


def capture(stage):
    verify()
    for name in SOURCES+[str(CONFIG.relative_to(REPO))]+[f'configs/native_state_conditioning_m7_{x}.json' for x in ('feasibility','validation')]:
        assert subprocess.check_output(['git','show','HEAD:'+name],cwd=REPO)==(REPO/name).read_bytes(), 'commit before capture'
    if stage=='validation':
        assert v.read(ROOT/'feasibility/mechanism_qualification_gate.json')['passed'], 'feasibility failed; validation must remain untouched'
    root=ROOT/stage;p=v.read(root/'protocol.json')
    current,_=v.frozen.base.runtime_provenance(Path(p['preflight_reference']['path']))
    assert current==p['runtime']
    v.frozen.v2.set_runtime_env(p)
    result=v.core.capture(root)
    return {'capture':result,'qualification':gate(stage)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','verify','capture','gate'])
    parser.add_argument('--stage',choices=['feasibility','validation'],default='feasibility')
    args=parser.parse_args()
    print(json.dumps(globals()[args.command](args.stage) if args.command in ('capture','gate') else globals()[args.command]()))
