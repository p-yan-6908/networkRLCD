"""IF1 frozen design verification and one resource-admission audit; no native run."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
CACHE=Path('/home/agent/.cache/networkrlcd')
ROOT=CACHE/'native-instrumented-fixture-if1'
DISCOVERY=CACHE/'native-instrumented-fixture-if1-discovery'
ANCHOR='14d411530b0f5d6cc06a1493ec33a5a6f1ce50bc'
CONFIG=REPO/'configs/native_instrumented_fixture_if1.json'
FREEZE=REPO/'data/native-if1/prior-freeze-sha256.json'
CHROMIUM='73c14f6228d7cd537c855007e8f88678969cc0eb'
WEBRTC='3a8b0c76e6b7bf0e72141047f82eb2c3f4862c8d'
SOURCES=['tools/instrumented_fixture_if1.py','docs/NATIVE_INSTRUMENTED_FIXTURE_IF1_PLAN.md',
 'docs/NATIVE_RESEARCH_DECISION_IF1.md','instrumentation/if1/BUILD_REQUEST.md',
 'instrumentation/if1/args.gn','instrumentation/if1/hook-map.json',
 'instrumentation/if1/transport-control.schema.json','data/native-if1/source-survey.json',
 'data/native-if1/qualification-allocation.json','data/native-if1/prior-freeze-sha256.json',
 'data/native-if1/CHROMIUM_LICENSE','data/native-if1/WEBRTC_LICENSE',
 'reports/native-instrumented-fixture-if1-runtime.json',
 'reports/native-instrumented-fixture-if1-prior-audit.json']

def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(4<<20),b''):h.update(block)
    return h.hexdigest()
def write(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
def inventory():return {name:sha(REPO/name) for name in SOURCES}
def legacy():
    s=importlib.util.spec_from_file_location('if1_prior_immutable_m11r',REPO/'tools/measure_transport_timing_m11r.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def closed():
    return {**legacy().old_closed(),'IF1_native_technical_unopened':not (ROOT/'technical').exists(),
        'IF1_native_observability_unopened':not (ROOT/'observability').exists(),
        'IF1_support_uninstantiated':not (ROOT/'support').exists()}

def design():
    inherited=read(REPO/'configs/native_phase_state_m9r.json')['design']['unchanged_state_gates']
    return {
      'question':'New fixture causal transport observability before fresh native common support',
      'fixture':'IF1 instrumented Chromium; no managed-fixture state reuse',
      'build_bounds':{'official_pinned_minimum_free_bytes':100_000_000_000,
        'minimum_free_bytes':130_000_000_000,'minimum_memory_limit_bytes':16*2**30,
        'minimum_effective_cpu_cores':4,'maximum_incremental_external_bytes':120_000_000_000,
        'maximum_production_files':28,'maximum_handwritten_changed_lines':2000,
        'maximum_engineer_hours':8,'maximum_build_wall_hours':6,
        'maximum_initial_build_and_compiler_repair_cycles':2,'maximum_admission_audits':1},
      'current_static_bounds':{'maximum_raw_bytes':10_000_000,'maximum_raw_stage_fresh_bytes':20_000_000},
      'capture_bounds':{'maximum_raw_bytes':2_000_000_000,'maximum_raw_stage_fresh_bytes':6_000_000_000,
        'minimum_runtime_free_bytes':8_000_000_000,'retries':0,'replacement_originals':0},
      'identity':{'required':['run_id','process_generation','pc_id','transport_id','controller_id','pacer_id',
          'registry_sequence','producer_sequence','SSRC_assignment_generation'],
        'direct_JS_PC_to_native_binding':True,'maximum_cross_attribution':0,'maximum_reused_opaque_ids':0,
        'registry_available_at_decision_required':True,'native_aggregate_scope_preserved':True,
        'pointer_thread_filename_or_correlation_identity_allowed':False},
      'timing':{'native_clock':'Linux_CLOCK_MONOTONIC','native_stamp_unit':'integer_microseconds',
        'sender_clock':'performance.now actual receipt','maximum_past_anchor_age_ms':1500,
        'clock_poll_ms':1000,'diagnostic_poll_ms':50,'pacer_state_poll_ms':50,
        'maximum_clock_interval_width_ms':50,'maximum_snapshot_ack_ms':100,
        'maximum_event_freshness_ms':250,'minimum_fresh_event_fraction_each_family_each_original':.9,
        'maximum_TCC_delivery_blackout_ms':1000,'late_pre_cutoff_events_stay_in_denominator':True,
        'events_future_clock_registry_or_parse_information_allowed':False,'feature_cutoff':'actual_sender_receipt'},
      'completeness':{'maximum_dropped_records':0,'maximum_unexplained_count_gaps':0,
        'maximum_silent_overwrites':0,'ring_records_per_PC':8192,'maximum_record_bytes':512,
        'minimum_TCC_events_each_original':10,'minimum_delay_or_loss_update_invocations':10,
        'minimum_probe_created':1,'minimum_probe_terminal':1,
        'minimum_main_pacer_snapshots':1584,'nominal_main_pacer_snapshots':1760,
        'maximum_pacer_snapshot_gap_ms':250,'required_channels':['transport_feedback','estimator_update','probe_lifecycle','pacer_state'],
        'required_TCC_fields':['packet_token','authenticated_ingress_native_us','parse_native_us',
            'dispatch_native_us','controller_consumption_native_us','parse_status','adapter_status',
            'sender_ssrc','media_ssrc','base_sequence','feedback_packet_count','packet_status_count'],
        'required_estimator_fields':['estimator_version','update_sequence','invocation_native_us','completion_native_us',
            'logical_at_time_us','before_bps','after_bps','state_changed','detector_state','trigger','parent_feedback_id'],
        'required_probe_fields':['cluster_id','controller_phase','prober_phase','transition','target_bps',
            'required_packets','required_bytes','sent_packets','sent_bytes','result_status'],
        'required_pacer_fields':['queued_bytes','queued_packets','queue_state_last_updated_us','oldest_enqueue_native_us',
            'media_debt_bytes','padding_debt_bytes','configured_pacing_bps','adjusted_media_bps','padding_bps',
            'paused','congested','prober_phase','last_process_native_us','last_send_native_us'],
        'credit_semantics':'Pinned implementation has native media/padding debt; separate positive credit is not_applicable',
        'missing_invalid_inactive_unassigned_statuses_explicit':True},
      'noninterference':{'native_hot_hook_p99_max_us':50,'native_hot_hook_absolute_max_us':1000,
        'scripted_same_input_clock_algorithm_output_parity_required':True,
        'blocking_or_IO_on_hot_path_allowed':False,'diagnostic_read_mutates_budget_or_scheduling':False,
        'algorithm_field_trial_or_managed_policy_change_allowed':False,
        'independent_native_BWE_equality_assumed':False},
      'technical':{'fresh_originals':4,'additional_short_native_identity_controls':2,
        'fresh_TURN_TCP_bidirectional_media_preflight':True,'managed_policy':'disable_non_proxied_udp',
        'codec':'VP8','encoder_cap_bps':4_000_000,'jitter_target_ms':0,'initial_BWE_bps':1_200_000,
        'maximum_initialization_ms':100,'actual_native_poll_ms':25,'main_ms':88000,
        'minimum_main_native_observations':3168,'maximum_native_gap_ms':250,
        'maximum_scheduling_lateness_ms':150,'maximum_command_ack_ms':100,
        'maximum_replay_tick_error_ms':150,'maximum_cleanup_ms':2000,
        'beginning_clock_training':35,'beginning_clock_heldout':4,'full_clock_training':128,
        'full_clock_heldout':15,'minimum_heldout_clock_coverage':1.0,'maximum_clock_width_ms':50,
        'all_originals_required':True,'receiver_QoE_analysis':False},
      'observability':{'fresh_originals':8,'contents':2,'histories':2,'repeats_each_condition':2,
        'phase_durations_ms':[10000,88000,12600],'initial_service_ms':24000,'common_service_ms':64000,
        'service_mbps':[.5,.5*2**1.5],'all_originals_required':True,
        'randomized_bitrate_actions':False,'future_BWE_labels':False},
      'future_support':{'reserved_originals':64,'contents':2,'histories':2,'service_levels':4,'repeats':4,
        'complete_separate_protocol_required':True,'representation_search_allowed':False,
        'minimum_future_window_ms':8000,'unchanged_support_gates':inherited,'instantiated':False},
      'closed':{'old_panel_search':False,'conditioning_extension':False,'predictor_fit':False,
        'action_value_study':False,'controller_fit_or_promotion':False,'receiver_outcomes':False,
        'inherited_native_common_support_claim':False,'scientific_failure_inferred_from_build_resources':False}}

def prepare():
    assert not ROOT.exists() and not CONFIG.exists(),'preserve original IF1 evidence'
    legacy().verify()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',ANCHOR],cwd=REPO,text=True).splitlines()
    write(FREEZE,{'anchor_commit':ANCHOR,'files':{n:sha(REPO/n) for n in names},'closed':closed()})
    source=read(REPO/'data/native-if1/source-survey.json')
    assert source['chromium_commit']==CHROMIUM and source['webrtc_commit']==WEBRTC
    assert WEBRTC in (DISCOVERY/'chromium__DEPS').read_text()
    assert 'At least 100GB of free disk space' in (DISCOVERY/'chromium__docs__linux__build_instructions.md').read_text()
    p={'abi':'native_instrumented_fixture_if1_registered_design_v1','anchor_commit':ANCHOR,
       'pins':{k:source[k] for k in ('chromium_commit','webrtc_commit','depot_tools_commit','clang_package')},
       'design':design(),'source_hashes':inventory(),'prior_freeze_sha256':sha(FREEZE),
       'qualification_allocation_sha256':sha(REPO/'data/native-if1/qualification-allocation.json'),
       'Cxx_patch_implemented':False,'binary_built':False,'native_acquisition_run':False,
       'support_panel_uninstantiated':True,'development_data_collected':False}
    write(CONFIG,p);write(ROOT/'protocol.json',p);(ROOT/'protocol.sha256').write_text(sha(CONFIG)+'  protocol.json\n')
    return verify()

def verify():
    p=read(CONFIG);assert p['design']==design() and p['source_hashes']==inventory()
    assert sha(CONFIG)==sha(ROOT/'protocol.json')==(ROOT/'protocol.sha256').read_text().split()[0]
    f=read(FREEZE);assert sha(FREEZE)==p['prior_freeze_sha256']
    for n,h in f['files'].items():assert sha(REPO/n)==h,n
    assert closed()==f['closed'];legacy().verify()
    for n,meta in read(REPO/'data/native-if1/source-survey.json')['files'].items():
        file=DISCOVERY/n;assert file.stat().st_size==meta['size'] and sha(file)==meta['sha256'],n
    assert sha(REPO/'data/native-if1/qualification-allocation.json')==p['qualification_allocation_sha256']
    return {'verified':True,'prior_tracked_files_unchanged':len(f['files']),'source_files_verified':len(read(REPO/'data/native-if1/source-survey.json')['files']),
        'old_panels_unchanged':True,'native_capture_run':False,'support_panel_uninstantiated':True}

def resources():
    memory_limit=None
    path=Path('/sys/fs/cgroup/memory.max')
    if path.exists() and path.read_text().strip()!='max':memory_limit=int(path.read_text())
    if memory_limit is None:
        memory_limit=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:'))
    effective=float(os.cpu_count() or 1);cpu=Path('/sys/fs/cgroup/cpu.max')
    if cpu.exists():
        quota,period=cpu.read_text().split()
        if quota!='max':effective=min(effective,int(quota)/int(period))
    return {'filesystem':dict(zip(('total','used','free'),shutil.disk_usage(CACHE))),
        'memory_limit_bytes':memory_limit,'effective_cpu_cores':effective,
        'build_tools':{x:shutil.which(x) for x in ('gclient','gn','ninja','clang++','g++','docker')}}

def feasibility():
    verify();out=ROOT/'build-admission.json';assert not out.exists(),'one frozen admission audit; preserve it'
    for n in SOURCES+[str(CONFIG.relative_to(REPO))]:
        assert subprocess.check_output(['git','show','HEAD:'+n],cwd=REPO)==(REPO/n).read_bytes(),'commit before formal audit'
    r=resources();b=design()['build_bounds'];local={
      'published_minimum_free_disk':r['filesystem']['free']>=b['official_pinned_minimum_free_bytes'],
      'bounded_peak_and_reserve':r['filesystem']['free']>=b['minimum_free_bytes'],
      'memory_limit':r['memory_limit_bytes']>=b['minimum_memory_limit_bytes'],
      'effective_cpu':r['effective_cpu_cores']>=b['minimum_effective_cpu_cores']}
    metadata=read(REPO/'reports/native-instrumented-fixture-if1-runtime.json')
    remote=metadata['remote_build_metadata'];docker=metadata['docker']
    # A reachable GitHub test workflow or same-host Docker daemon is not a
    # resource-attested builder and is never silently dispatched/provisioned.
    alternate={'docker_additional_resource_attestation':False,'remote_builder_resource_attestation':False,
        'provenance_verified_IF1_binary_available':False}
    admitted=all(local.values()) or any(alternate.values())
    result={'abi':'native_instrumented_fixture_if1_build_admission_v1','at_utc':datetime.now(timezone.utc).isoformat(),
      'protocol_sha256':sha(CONFIG),'resources':r,'local_admission_checks':local,'alternate_admission_checks':alternate,
      'docker_same_host_metadata':docker,'remote_build_metadata':remote,'admitted':admitted,
      'classification':'build admitted; implementation still unqualified' if admitted else 'resource/access admission limit; IF1 not built',
      'published_minimum_disk_shortfall_bytes':max(0,b['official_pinned_minimum_free_bytes']-r['filesystem']['free']),
      'filesystem_total_below_published_minimum':r['filesystem']['total']<b['official_pinned_minimum_free_bytes'],
      'source_hook_presence_is_only_static':True,'Cxx_patch_implemented':False,'compiler_invocations':0,
      'full_source_checkouts':0,'native_sessions':0,'observability_qualified':False,'common_support_qualified':False,
      'support_panel_instantiated':False,'old_panel_search':False,'receiver_outcomes_read':False,
      'predictor_or_controller_fitted':False,'actions_opened':False,
      'experimental_limit':'Fine-grained native conditional action value remains unestablished under the available bounded fixture effort; no empirical claim that native hooks are impossible.',
      'next_research_question':'Partially observed / uncertainty-aware policy-sequence value with a separately preregistered permitted fixture and fresh data',
      'closed':closed()}
    write(out,result);write(REPO/'reports/native-instrumented-fixture-if1-build-admission.json',result)
    return {k:result[k] for k in ('classification','admitted','compiler_invocations','native_sessions','observability_qualified','actions_opened')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','verify','feasibility'))
    args=parser.parse_args();print(json.dumps(globals()[args.command]()))
