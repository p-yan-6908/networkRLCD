"""Derive M9R's denser actual sampler; preserve the complete unestimable M9."""
import ast
import hashlib
import json
import re
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
ANCHOR='26ab4acfd95f2e86cb1979f8e93a1a3369ac2844'

def emit(name,text):
    path=REPO/name;path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():assert path.read_text()==text,'preserve '+name
    else:path.write_text(text)

def build():
    config=json.loads((REPO/'configs/native_phase_state_m9.json').read_text())
    def source(name):
        p=REPO/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==config['source_hashes'][name];return p.read_text()
    def renamed(text):return text.replace('_m9','_m9r').replace('native-m9','native-m9r').replace('state-m9','state-m9r').replace('m9-','m9r-').replace("'m9_'","'m9r_'").replace('M9','M9R')
    text=renamed(source('benchmarks/native_m9/phase_state_episode_m9.mjs'))
    text=text.replace('../native_m9/','../native_m9r/')
    def change(old,new):
        nonlocal text
        assert text.count(old)==1,old;text=text.replace(old,new)
    change("episode.support_config?.support_only!==true)","episode.support_config?.support_only!==true||episode.support_poll_ms!==25)")
    change('let collecting=true;const encoder=', 'const pollEpoch=performance.now();let nextPollMs=pollEpoch;let collecting=true;const encoder=')
    change('const stats=await a.getStats();if(!collecting)break;',
           'const scheduled_ms=nextPollMs;while(collecting&&performance.now()<scheduled_ms)await sleep(Math.max(1,scheduled_ms-performance.now()));if(!collecting)break;const request_ms=performance.now(),stats=await a.getStats(),response_ms=performance.now();if(!collecting)break;const poll_timing={scheduled_ms,request_ms,response_ms,poll_epoch_ms:pollEpoch,period_ms:25,scheduling_lateness_ms:request_ms-scheduled_ms,stats_duration_ms:response_ms-request_ms};')
    change('decisions.push({step_id,observation,policy_input:', 'decisions.push({step_id,observation,poll_timing,policy_input:')
    change('currentDecisionId=step_id;lastApplied=actual;await sleep(OBSERVATION_PROTOCOL.poll_ms);',
           'currentDecisionId=step_id;lastApplied=actual;nextPollMs=pollEpoch+25*(Math.floor((performance.now()-pollEpoch)/25)+1);')
    change('ack_ms:d.ack_ms,policy_input:d.policy_input', 'ack_ms:d.ack_ms,poll_timing:d.poll_timing,policy_input:d.policy_input')
    change('const senderEvidence=result.sender_evidence;',
           "const senderEvidence=result.sender_evidence;senderEvidence.protocol={...senderEvidence.protocol,poll_ms:25,legacy_feature_interval_scale_ms:100,schedule:'anchored absolute deadlines; missed slots skipped, never fabricated'};")
    emit('benchmarks/native_m9r/phase_state_episode_m9r.mjs',text)
    emit('benchmarks/native_m9r/phase_state_support_m9r.mjs',renamed(source('benchmarks/native_m9/phase_state_support_m9.mjs')))
    text=renamed(source('tools/measure_phase_state_m9.py'))
    text=text.replace("ANCHOR='b707226b4fa581458a068fc0cd6249e964468af6'",'ANCHOR='+repr(ANCHOR)).replace('SEED=20261209','SEED=20261210')
    text=text.replace("'native_common_support_established_before_study':False,", "'native_common_support_established_before_study':False,'actual_poll_ms':25,'census_minimum_spacing_ms':90,\n        'instrumentation_originals':8,'native_output_budget_bytes':3000000000,'incremental_external_budget_bytes':10000000000,")
    text=text.replace("'tools/build_phase_state_m9r.py',", "'tools/build_phase_state_m9r.py','docs/NATIVE_PHASE_STATE_M9R_INHERITED_GATES.md',")
    text=text.replace("if stage=='instrumentation':contexts=[(assets['content_sources'][0],0,0.,m.PREFIXES[0]),(assets['content_sources'][1],0,1.5,m.PREFIXES[1])]",
        "if stage=='instrumentation':\n            contexts=[(c,0,x,h) for c in assets['content_sources'] for x in (0.,1.5) for h in m.PREFIXES];rng.shuffle(contexts)")
    text=text.replace('e.update(support_initial_bwe_kbps=1200,','e.update(support_poll_ms=25,support_initial_bwe_kbps=1200,')
    text=text.replace("(2 if stage=='instrumentation' else 64)","(8 if stage=='instrumentation' else 64)")
    text=text.replace("'instrumentation_sessions':2,","'instrumentation_sessions':8,")
    text=text.replace('observer=len(sampled)>=792','observer=len(sampled)>=3168')
    needle="replay=fidelity(d,t,v.read(root/t['panel']),origin,vertices,windows)"
    assert text.count(needle)==1
    text=text.replace(needle,"""polls=[x for x in sender['decisions'] if windows[1]['start_ms']<=x['sample_ms']<=windows[1]['end_ms']]
        timing=all('poll_timing' in x and x['poll_timing']['period_ms']==25 and
            x['poll_timing']['scheduled_ms']<=x['poll_timing']['request_ms']<=x['poll_timing']['response_ms']<=x['sample_ms']<=x['ack_ms'] and
            abs((x['poll_timing']['scheduled_ms']-x['poll_timing']['poll_epoch_ms'])/25-round((x['poll_timing']['scheduled_ms']-x['poll_timing']['poll_epoch_ms'])/25))<=1e-7 for x in polls)
        observer=observer and timing
        replay=fidelity(d,t,v.read(root/t['panel']),origin,vertices,windows)""")
    text=text.replace("media_passed=media,observer_passed=observer,observer_samples=len(sampled)",
        "media_passed=media,observer_passed=observer,acquisition_timing_passed=timing,maximum_stats_duration_ms=max(x['poll_timing']['stats_duration_ms'] for x in polls),maximum_scheduling_lateness_ms=max(x['poll_timing']['scheduling_lateness_ms'] for x in polls),observer_samples=len(sampled)")
    insertion='''def census(points, endpoint):
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

'''
    assert text.count('def clocks(directory):')==1;text=text.replace('def clocks(directory):',insertion+'def clocks(directory):')
    emit('tools/measure_phase_state_m9r.py',text)
    text=renamed(source('tools/analyze_phase_state_m9.py'))
    baseline=(REPO/'tools/analyze_bwe_transients_m8.py').read_text();tree=ast.parse(baseline)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='causal_state')
    body=ast.get_source_segment(baseline,function).replace('def causal_state(', 'def baseline_causal_state(').replace('m.parent.census(', 'm.census(')
    body=re.sub(r'\b(section|xs|valid|drift)\(',r'b.\1(',body)
    text=text.replace('def state_at(points,events,endpoint):',body+'\n\n\ndef state_at(points,events,endpoint):').replace('state=b.causal_state(points,events,endpoint)','state=baseline_causal_state(points,events,endpoint)')
    emit('tools/analyze_phase_state_m9r.py',text)
    # Postprocessing remains separate from the scientific source inventory.
    for old,new in [('report_phase_state_m9.py','report_phase_state_m9r.py'),('audit_phase_state_m9_inherited_gates.py','audit_phase_state_m9r_inherited_gates.py'),
                    ('write_phase_state_m9_results.py','write_phase_state_m9r_results.py'),('preserve_phase_state_m9.py','preserve_phase_state_m9r.py'),
                    ('audit_phase_state_m9.py','audit_phase_state_m9r.py'),('finalize_phase_state_m9_storage.py','finalize_phase_state_m9r_storage.py')]:
        text=renamed((REPO/'tools'/old).read_text()).replace('m.m.parent.census(', 'm.census(')
        text=text.replace('96ada5a290b3807629bf28bf5d74183aff35a9c3','M9R_REGISTRATION_PENDING').replace('f6a0a5f','M9R_INSTRUMENTATION_PENDING').replace('b979441da2a634b226021910636f5bfb57f4a91d','M9R_REGISTRATION_PENDING')
        text=text.replace('Two instrumentation originals','Eight instrumentation originals').replace('All66 original captures','All72 original captures').replace("'instrumentation_originals_included':2","'instrumentation_originals_included':8")
        text=text.replace('All1471 tracked files at completed M8','All tracked files at completed M9, including the earlier M8 freeze,')
        if old=='audit_phase_state_m9.py':text=text.replace("('M8','native-bwe-transients-m8-20261015-01')", "('M8','native-bwe-transients-m8-20261015-01'),('M9','native-phase-state-m9-20261015-01')")
        if old=='finalize_phase_state_m9_storage.py':text=text.replace('3000000000','10000000000')
        emit('tools/'+new,text)
    return {'generated':10,'poll_ms':25,'original_M9_unchanged':True,'original_state_predicates_and_gate_values_unchanged':True}

if __name__=='__main__':print(json.dumps(build()))
