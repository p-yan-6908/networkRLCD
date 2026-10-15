"""Human-readable tables from registered M8 metrics; no new feature/gate definitions."""
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m8_document_registration',REPO/'tools/measure_bwe_transients_m8.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def number(value,digits=3):return '—' if value is None else f'{value:.{digits}f}'


def latency(item):
    if not item or not item.get('observed'):return 'unconfirmed'
    a,b=item['onset_delay_ms_bounds'];return f'{a/1000:.2f}–{b/1000:.2f}'


def pair(values):return ', '.join(number(x) for x in values)


def write():
    m.verify();summary=m.v.read(REPO/'reports/native-bwe-transients-m8-summary.json')
    tables=m.v.read(REPO/'reports/native-bwe-transients-m8-response-tables.json');selection=summary['selection']
    gate=m.v.read(REPO/'reports/native-bwe-transients-m8-characterization-gate.json');rows=gate['sessions'];assert gate['passed']
    selected=selection['selected_age_ms']
    lines=['# M8: native BWE response to controlled service','',
        'Scientific registration: `cbbafc4f6846d6ad0a5eaf064d09750c7e4d26fa`; long-session instrumentation qualified in `0e5987b`.',
        'The two qualification originals and all **16/16 characterization originals** qualified. '
        'Characterization is two reused content productions × two prefixes × two initial service orders × two fresh repeats. '
        'All results below are support telemetry; there were no bitrate actions or QoE outcomes analyzed.','',
        '## Decision','']
    if selected is None:
        lines+=['**No registered candidate qualified. No conditioning duration or executable successor schedule was derived.** '
            'The new 128-original successor allocation remains untouched and uninstantiated. M7RA’s separate 128-session panel remains closed. '
            'Native reproducible common support is still unestablished; action-value estimation and controller fitting remain closed.','']
    else:
        lines+=[f'The measurement-based development rule selected entry age **{selected/1000:g}s** and constant-service duration '
            f'**{selection["conditioning_duration_ms"]/1000:g}s**. This is a candidate for a separately frozen fresh validation, '
            'not established native common support or authorization for an action/controller study.','']
    lines+=['## Fixed intervention and interpretation','',
        'After the equal-multiset 10s measured-source prefix, four 24s synthetic service plateaus were '
        '`[0.5, 1.5, 0.5, 1.5]` or `[1.5, 1.5, 0.5, 1.5]` Mbps. Service was therefore common high/low/high from 24s onward. '
        'At the first common high plateau, one order stepped up and the other held high at the same content time. '
        'The encoder ceiling stayed 4Mbps, initialization 1200kbps and receiver target zero. A common original measured-source probe followed.','',
        'These are responses of Chromium together with its encoder, content and owned symmetric path. '
        'The known input is wire-service capacity, not controlled encoder output. The measurements do not isolate GCC internals, '
        'queue history or encoder behavior. The no-change control helps distinguish natural estimator drift from a change coincident with a service step. '
        'Synthetic service is not measured-network replication; reused source groups and repeated visits are not independent new evidence.','',
        '## Actual-run instrumentation','',
        'These maxima cover the sixteen characterization originals; the two earlier qualification originals are preserved separately.','',
        '| Check | Maximum observed | Registered limit |','|---|---:|---:|',
        f'| Full clock held-out width | {number(max(x["clock"]["full"]["max_held_out_width_ms"] for x in rows))}ms | 50ms |',
        f'| Beginning clock held-out width | {number(max(x["clock"]["beginning"]["max_held_out_width_ms"] for x in rows))}ms | 50ms |',
        f'| Main sender observation gap | {number(max(x["maximum_observer_gap_ms"] for x in rows))}ms | 250ms |',
        f'| Service acknowledgement | {number(max(x["input_fidelity"]["maximum_ack_ms"] for x in rows))}ms | 100ms |',
        f'| Command lateness | {number(max(x["input_fidelity"]["maximum_command_lateness_ms"] for x in rows))}ms | 0…150ms |',
        f'| Source tick error | {number(max(x["input_fidelity"]["maximum_tick_error_ms"] for x in rows))}ms | 150ms |',
        f'| Common probe exposure difference | {number(max(x["maximum_probe_exposure_difference_octaves"] for x in gate["common_probe_checks"].values()),6)} octave | 0.01 octave |','',
        'Each actual long-session map used 128 fixed training and 15 independent held-out exchanges; beginning certificates used 35/four. '
        'Strict TURN/TCP, managed-policy hashes, inactive/exact startup, fixed readback, native media progression, known service commands '
        'and exact post-cutoff queue cleanup all passed. No failed ICE session was interpreted as a response.','',
        '## Response delay and rise/fall asymmetry','',
        'The following envelopes cover the eight specific native contexts within each content group. They are measurement ranges, '
        'not population intervals; all history/order/repetition cells are retained below.','',
        '| Content | Fall departure onset (s) | Rise departure onset (s) | Fall t50 (s) | Rise t50 (s) | Fall t90 (s) | Rise t90 (s) |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for content in sorted({x['content'] for x in tables['response_rows']}):
        items=[x for x in tables['response_rows'] if x['content']==content]
        def envelope(direction,field):
            values=[v[field] for item in items for v in item[direction] if v.get(field) and v[field].get('observed')]
            if not values:return 'unconfirmed'
            return f'{min(x["onset_delay_ms_bounds"][0] for x in values)/1000:.2f}–{max(x["onset_delay_ms_bounds"][1] for x in values)/1000:.2f}'
        lines.append('| '+content.split('_')[1].capitalize()+' | '+' | '.join(envelope(direction,field) for field in ('departure','t50','t90') for direction in ('fall','rise'))+' |')
    lines+=['',
        'Each entry below contains **both independent repeat values**, in seconds, for the registered input-normalized t50 onset interval. '
        'Intervals include polling and input-clock uncertainty. “Unconfirmed” means the required sustained crossing was not confirmed '
        'inside the finite observation window; it does not establish a latent estimator delay beyond that window. '
        'Common fall/rise transitions are within the same native run. No repeated phase is counted as an independent run.','',
        '| Content | Prefix | Initial service | Fall t50, repeats 0/1 (s) | Rise t50, repeats 0/1 (s) |',
        '|---|---|---|---|---|']
    for row in tables['response_rows']:
        content=row['content'].split('_')[1].capitalize();prefix=row['prefix'].split('_')[0]
        initial='low' if row['input_order'].startswith('step_') else 'high'
        lines.append(f'| {content} | {prefix} | {initial} | '+', '.join(latency(x['t50']) if x['estimable'] else 'unestimable' for x in row['fall'])+' | '+', '.join(latency(x['t50']) if x['estimable'] else 'unestimable' for x in row['rise'])+' |')
    lines+=['','The full tables preserve departure/t10/t50/t90 censoring, t10–t90 intervals and per-native-run rise-minus-fall contrasts. '
        'Input-normalized overshoot is relative to the input-scaled **past** BWE reference, not an assumed equilibrium.','',
        '## Overshoot, late variation and drift','',
        'Values below are the two repeat values in octaves. Late range is the final four-second native BWE range. '
        'Final drift is the latest one-second mean minus the preceding one-second mean; all detailed values remain in the JSON tables.','',
        '| Content | Prefix / initial service | Fall overshoot | Rise overshoot | Fall late range | Rise late range |',
        '|---|---|---|---|---|---|']
    for row in tables['response_rows']:
        content=row['content'].split('_')[1].capitalize();label=row['prefix'].split('_')[0]+'/'+('low' if row['input_order'].startswith('step_') else 'high')
        lines.append(f'| {content} | {label} | '+pair([x['input_normalized_overshoot_octaves'] for x in row['fall']])+' | '+pair([x['input_normalized_overshoot_octaves'] for x in row['rise']])+' | '+pair([x['late_range_octaves'] for x in row['fall']])+' | '+pair([x['late_range_octaves'] for x in row['rise']])+' |')
    lines+=['','## Matched history / hysteresis contrasts','',
        'The following registered contrasts compare **initial service high minus low** while current service is the same high '
        'and content time is matched (first common plateau). Both repeat differences are shown; no pooled population estimate or p-value is inferred. '
        'They are operational history contrasts, not attribution to a particular estimator mechanism.','',
        '| Content | Prefix | Common-high age | Two paired differences (octaves) |','|---|---|---:|---|']
    for x in summary['history_contrasts']:
        if x['kind']=='initial_service_high_minus_low_under_common_later_service' and x['plateau']==1 and x['age_ms'] in (6000,23000):
            lines.append(f'| {x["content"].split("_")[1].capitalize()} | {x["prefix"].split("_")[0]} | {x["age_ms"]/1000:g}s | '+pair(x['paired_repetition_differences_octaves']['values'])+' |')
    lines+=['','Initial ascending/descending-prefix contrasts remain separate in the complete report at all registered common-service ages, '
        'contents and input orders. Two repetitions per cell give empirical ranges, not precise population uncertainty or a convergence/equivalence claim. '
        'M5 remains the qualified causal prefix-history result.','',
        '## Prospective causal settling rule','',
        'B0 used current eligible native BWE as its causal center. D1 additionally required three seconds inside ±0.125 octave, '
        '≥27 eligible samples, gaps ≤250ms, absolute recent mean drift ≤0.05 octave and acknowledged service constant ≥3s. '
        'The state used only past samples and acknowledgements. The initial last-change-direction value is an initialization sentinel; '
        'direction is reported, not a D1 decision threshold. Actual initial input direction remains in the response metrics.','',
        'A true label required at least eight later observed seconds, through plateau +23.8s, inside the **same** causal-center caliper '
        'with the original eligibility and drift bounds. Those later samples were labels only. The 64 occurrences are nested in 16 native runs.','',
        '| Candidate age | B0 tags / verified | D1 tags / verified | D1 false tags | Worst content/service spread | Full calibration-bias range |',
        '|---|---:|---:|---:|---:|---:|']
    for age in m.DESIGN['candidate_ages_ms']:
        q=selection['candidates'][str(age)];spreads=[x['full_spread_octaves'] for x in q['cells'].values()]
        worst=max(spreads) if all(x is not None for x in spreads) else None
        lines.append(f'| {age/1000:g}s | {q["baseline_tags"]} / {q["true_baseline_tags"]} | {q["dynamic_tags"]} / {q["true_dynamic_tags"]} | {q["dynamic_false_tags"]} | {number(worst)} | {number(q["full_bias_spread_octaves"])} |')
    lines+=['',f'**{summary["settling_unverified_occurrences"]}/64** plateau occurrences had no verified D1 settling onset on the registered 3…15s grid. '
        'These onsets are censored at 15s because ≥8s subsequent verification is required; this does not rule out later settling. '
        'Rejecting contexts or being locally flat is insufficient. A selectable age needed all 64 valid future-verified tags, '
        'full retention and ≤0.25-octave repeatability/hysteresis/calibration spread.','']
    diagnostic=m.v.read(REPO/'reports/native-bwe-transients-m8-support-failure-diagnostic.json')['ages']
    if all(q['all_future_component_failures']['future_observable']==q['all_future_component_failures']['original_bwe_bounds']==0 for q in diagnostic.values()):
        lines+=['All future verification windows were observable and stayed within the original BWE eligibility bounds. '
            'At each candidate age, all 64 left their causal ±0.125-octave region during verification. '
            'The fixed future-drift test also failed in '+', '.join(str(diagnostic[str(age)]['all_future_component_failures']['future_drift_at_fixed_seconds'])+'/64 at '+str(age//1000)+'s' for age in m.DESIGN['candidate_ages_ms'])+'. '
            'These are failures of future stability, not missing observations or clock coverage. '
            '[Registered-component diagnostic](../reports/native-bwe-transients-m8-support-failure-diagnostic.json).','']
    lines+=[
        '## Successor design and unchanged gates','']
    decision={'abi':'native_conditioning_after_m8_design_decision_v1','selection_sha256':m.v.sha(REPO/'reports/native-bwe-transients-m8-selection.json'),
        'allocation_sha256':m.v.sha(m.ALLOCATION),'allocated_originals':128,'old_m7ra_panel_untouched':True,
        'selected_age_ms':selected,'conditioning_duration_ms':selection.get('conditioning_duration_ms'),
        'constant_services_mbps':selection.get('constant_services_mbps'),'native_common_support_established':False,
        'controller_fitted':False,'preserved_acceptance_gates':m.v.read(m.ALLOCATION)['preserved_acceptance_gates']}
    if selected is None:
        decision.update(executable_schedule_instantiated=False,native_sessions_started=0)
        lines+=['The preregistered measurement rule did not supply an admissible age/calibration, so **no heuristic duration was substituted**. '
            'The concrete new allocation and conditional derivation remain frozen and untouched, without executable native panels. '
            'Another conditioning recipe or dynamic state would need fresh prospective justification; none is fitted or searched here.','']
    else:
        decision.update(executable_schedule_instantiated=False,native_sessions_started=0)
        lines+=[f'The eligible development schedule uses age {selected/1000:g}s, duration {selection["conditioning_duration_ms"]/1000:g}s '
            f'and constant services {selection["constant_services_mbps"]} Mbps. Its fresh implementation and full native panel must be '
            'separately sealed before any validation run.','']
    lines+=['The successor still requires the original four fixed BWE regions, both content groups and measured-source families, '
        'four original members/history, ±0.125 target membership, sustained history/≤0.05 drift, range≥1 octave, sample SD≥0.35, '
        'overlap≥0.5 and repeatability/W-infinity/census distance≤0.25. No threshold or count was relaxed. '
        'M8 alone establishes neither reproducible native common support nor conditional action value.','',
        '## Evidence and preservation','',
        '- [Frozen plan](NATIVE_BWE_TRANSIENTS_M8_PLAN.md), [summary](../reports/native-bwe-transients-m8-summary.json), '
        '[response tables](../reports/native-bwe-transients-m8-response-tables.json), [selection](../reports/native-bwe-transients-m8-selection.json).',
        '- [All native trajectories](../reports/native-bwe-transients-m8-trajectories.png), [settling tags](../reports/native-bwe-transients-m8-settling.png).',
        '- [Preservation audit](../reports/native-bwe-transients-m8-preservation-audit.json), '
        '[private archive receipt](storage-receipts/native-bwe-transients-m8-20261015-01.json).','',
        'Every original, failed check, source snapshot and successor allocation is retained. The private archive is pinned and '
        'freshly verified object by object and member by member. Raw frame/quality outcomes stay unopened by analysis; licensed originals '
        'and old derivatives remain unchanged. M5, M6R, M7/M7R/M7RA, V13 and all prior freezes are preserved. Zero evidence files deleted.']
    path=REPO/'docs/NATIVE_BWE_TRANSIENTS_M8_RESULTS.md';assert not path.exists();path.write_text('\n'.join(lines)+'\n')
    m.v.write(REPO/'reports/native-bwe-transients-m8-next-design-decision.json',decision)
    return {'document':str(path),'selected_age_ms':selected,'new_untouched_allocation':128}


if __name__=='__main__':print(json.dumps(write()))
