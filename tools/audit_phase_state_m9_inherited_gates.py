"""Enforce inherited H1/probe gates as a veto; never rescue a failed M9 rule."""
import importlib.util
import json
import math
import statistics as st
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def audit():
    s=importlib.util.spec_from_file_location('m9_legacy_gate_registration',REPO/'tools/measure_phase_state_m9.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify();root=m.ROOT/'validation'
    assert m.v.read(root/'mechanism_qualification_gate.json')['passed']
    p,index=m.v.core.check_capture_integrity(root)
    summary=m.v.read(root/'phase_state_summary.json');records=m.v.read(root/'phase_state_records.json');lookup={x['id']:x for x in records};rows=[]
    for t in p['trials']:
        d=root/'sessions'/t['id'];points=m.m.parent.points_for(m.v.read(d/'sender_observations.json'))
        record=lookup[t['id']];age=record['first_tags_ms']['P2'];entry=record['entries'][str(age)] if age is not None else None
        checks={'frozen_first_P2_tag':entry is not None};maximum=None
        if entry is not None:
            cutoff=entry['state']['cutoff_ms'];recent=[x for x in points if cutoff-3000<x['ms']<=cutoff]
            last=[x for x in recent if cutoff-1000<x['ms']<=cutoff];before=[x for x in recent if cutoff-2000<x['ms']<=cutoff-1000]
            valid=all(x['valid'] and 240000<=x['bwe']<=3800000 for x in recent)
            values=[math.log2(x['bwe']/500000) for x in recent] if valid else []
            maximum=max(abs(x-t['target_x']) for x in values) if values else None
            drift=st.mean(math.log2(x['bwe']/500000) for x in last)-st.mean(math.log2(x['bwe']/500000) for x in before) if valid and last and before else None
            checks.update(original_recent_count=len(recent)>=27 and len(last)>=7 and len(before)>=7,
                original_eligibility=valid,original_gap=bool(recent) and all(0<b['ms']-a['ms']<=250 for a,b in zip(recent,recent[1:])),
                original_fixed_target_history=maximum is not None and maximum<=.125+1e-12,
                original_recent_drift=drift is not None and abs(drift)<=.05,
                known_constant_service=entry['state']['known_service_age_ms']>=3000)
        probe=m.v.read(d/'phase_windows.json')['phase_windows'][2]['start_ms']
        windows={str(ms):m.m.parent.census(points,probe+ms) for ms in (6000,12000)}
        rows.append({'id':t['id'],'content_id':t['content_id'],'input_x':t['input_x'],'prefix':t['prefix'],'repetition':t['repetition'],
            'first_P2_age_ms':age,'entry_checks':checks,'entry_passed':all(checks.values()),'maximum_past_three_second_target_distance_octaves':maximum,'probe_censuses':windows})
    cells=[]
    for content in sorted({x['content_id'] for x in rows}):
        for level in m.TARGETS:
            members=[x for x in rows if x['content_id']==content and x['input_x']==level];states={}
            for endpoint in ('6000','12000'):
                arms=[[x['probe_censuses'][endpoint]['x'] for x in members if x['prefix']==h and x['probe_censuses'][endpoint]['passed']] for h in m.m.PREFIXES]
                valid=all(len(a)==4 for a in arms);values=[x for a in arms for x in a]
                spread=max(values)-min(values) if values else None
                winf=max(abs(a-b) for a,b in zip(*[sorted(a) for a in arms],strict=True)) if valid else None
                distance=max(abs(x-st.mean(values)) for x in values) if values else None
                states[endpoint]={'four_censuses_per_history':valid,'repeat_spread_octaves':spread,'prefix_w_infinity_octaves':winf,
                    'maximum_actual_census_distance_octaves':distance,'passed':bool(valid and spread<=.25+1e-12 and winf<=.25+1e-12 and distance<=.25+1e-12)}
            counts={h:sum(x['entry_passed'] and x['prefix']==h for x in members) for h in m.m.PREFIXES}
            cells.append({'content':content,'input_x':level,'originals':len(members),'fixed_target_H1_counts':counts,
                'probe_states':states,'passed':len(members)==8 and all(n==4 for n in counts.values()) and all(x['passed'] for x in states.values())})
    legacy=all(x['entry_passed'] for x in rows) and all(x['passed'] for x in cells)
    result={'abi':'native_phase_state_m9_inherited_gate_veto_v1','primary_P2_qualified':summary['P2_qualified'],
        'inherited_gates_passed':legacy,'qualified_for_next_common_state_validation':summary['P2_qualified'] and legacy,
        'registered_M9_results_modified':False,'can_rescue_a_failed_rule':False,'new_state_representation':False,
        'source_H1_definition_sha256':m.v.sha(REPO/'tools/measure_state_conditioning_m7ra.py'),
        'clarification_sha256':m.v.sha(REPO/'docs/NATIVE_PHASE_STATE_M9_INHERITED_GATES.md'),
        'primary_summary_sha256':m.v.sha(root/'phase_state_summary.json'),'state_records_sha256':m.v.sha(root/'phase_state_records.json'),
        'sessions':rows,'cells':cells,'actions':False,'controller_fitted':False}
    m.v.write(root/'inherited_gate_audit.json',result);m.v.write(REPO/'reports/native-phase-state-m9-inherited-gates.json',result)
    return result

if __name__=='__main__':
    r=audit();print(json.dumps({k:r[k] for k in ('primary_P2_qualified','inherited_gates_passed','qualified_for_next_common_state_validation')}))
