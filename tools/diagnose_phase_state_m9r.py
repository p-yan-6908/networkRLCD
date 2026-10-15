"""Explain registered M9R support failures and residuals; no additional state search."""
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def diagnose():
    s=importlib.util.spec_from_file_location('m9r_closed_diagnostic',REPO/'tools/measure_phase_state_m9r.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify();root=m.ROOT/'validation'
    assert m.v.read(root/'mechanism_qualification_gate.json')['passed'];m.v.core.check_capture_integrity(root)
    summary=m.v.read(root/'phase_state_summary.json');records=m.v.read(root/'phase_state_records.json')
    components={};future={};cells=[];rare=[]
    for content in sorted({r['content_id'] for r in records}):
        for level in m.TARGETS:
            rows=[r for r in records if r['content_id']==content and r['input_x']==level];cc={};fc={}
            for row in rows:
                for item in row['entries'].values():
                    for name,flag in item['state']['P2_components'].items():
                        for counts in (components,cc):
                            p=counts.setdefault(name,{'pass':0,'fail':0});p['pass' if flag else 'fail']+=1
                    for name,flag in item['future']['components'].items():
                        for counts in (future,fc):
                            p=counts.setdefault(name,{'pass':0,'fail':0});p['pass' if flag else 'fail']+=1
                    if item['state']['P2_components']['six_second_frozen_caliper']:
                        rare.append({'id':row['id'],'content':content,'input_x':level,'prefix':row['prefix'],'age_ms':item['age_ms'],
                            'P2_components':item['state']['P2_components'],'recent_drift':item['state']['recent_mean_drift_octaves'],
                            'long_contrast':item['state']['long_drift_octaves']})
            cells.append({'content':content,'input_x':level,'native_originals':8,'nested_grid_measurements':len(rows)*50,
                'P2_components':cc,'future_components':fc})
    covered=[]
    for row in summary['residuals']:
        if not row['compact_full_coverage']:continue
        pairs=row['pairs'];covered.append({'content':row['content'],'input_x':row['input_x'],'age_ms':row['age_ms'],'independent_pairs':4,
            'current_differences_octaves':[p['current_difference_octaves'] for p in pairs],
            'future_mean_differences_octaves':[p['future_mean_difference_octaves'] for p in pairs],
            'future_change_residuals_octaves':[p['future_change_residual_octaves'] for p in pairs],
            'future_w_infinity_octaves':[p['future_w_infinity_octaves'] for p in pairs],
            'future_maximum_one_second_mean_differences_octaves':[p['future_maximum_1s_mean_difference_octaves'] for p in pairs],
            'all_four_future_distributions_within_original_bound':all(p['future_w_infinity_octaves']<=.25 for p in pairs),
            'unconditional_prefix_uncertainty':row['unconditional_prefix_future_mean']})
    label_count=sum(x['future']['passed'] for r in records for x in r['entries'].values())
    result={'abi':'native_phase_state_m9r_registered_component_diagnostic_v1','classification':'qualified acquisition; prospective state-coverage failure',
        'primary_summary_sha256':m.v.sha(root/'phase_state_summary.json'),'state_records_sha256':m.v.sha(root/'phase_state_records.json'),
        'P2_first_tags':summary['methods']['P2']['first_tags'],'P2_positive_predictive_accuracy':None,
        'P2_accuracy_reason':'no positive P2 predictions; support absent, not a zero-percent precision estimate',
        'native_originals':64,'nested_grid_measurements':3200,'nested_measurements_are_independent':False,
        'causal_components':components,'future_components':future,'cells':cells,'six_second_caliper_events':rare,
        'positive_future_stability_labels':label_count,'all_64_D1_onsets_right_censored_after_ms':55000,'observation_horizon_ms':64000,
        'matching_coverage':{'B0_four_pair_strata':sum(r['B0_full_coverage'] for r in summary['residuals']),
            'compact_four_pair_strata':len(covered),'registered_strata':64,
            'covered_strata_all_future_distributions_within_bound':sum(r['all_four_future_distributions_within_original_bound'] for r in covered)},
        'fully_covered_compact_matching_strata':covered,
        'interpretation':'Repeatable moving marginal distributions can occur without frozen future stability. Selected-context residuals do not isolate causal prefix effects or separate within-history native variability.',
        'new_state_or_feature_evaluated':False,'extra_queue_RTT_encoder_features_read':False,'bitrate_actions_or_controller_fitting':False,
        'next_step':'Fresh causal observability/mechanism development; positive support must exist under unchanged gates before any state predictor can qualify. Do not fit additional representations on M9R.'}
    m.v.write(root/'support_failure_diagnostic.json',result);m.v.write(REPO/'reports/native-phase-state-m9r-support-failure-diagnostic.json',result)
    lines=['# M9R: interpretation and registered residual audit','',
        'The frozen M9R analysis is unchanged. This report summarizes its registered components and paired values; it evaluates no additional state, feature, threshold or outcome.','',
        '## Classification','',
        '**Prospective state-coverage failure with qualified acquisition.** All eight instrumentation and64 validation originals passed. Validation maximum actual observation gap99.4ms (limit250), full held-out clock1.385ms and beginning3.269ms (limit50). The sampling repair is qualified on this panel. M9 remains separately frozen and unestimable; its two failed observations are never pooled into M9R.',
        'P2 emitted **zero** eligible first tags. Its positive predictive accuracy is **unestimable**, not0%. B0 tagged64 originals and D1 tagged55; none of those first predictions was future-verified. There were **zero future-stability labels** at any of the3200 registered native-run/grid combinations. These are50 nested measurements per original, not3200 independent replications.',
        'Every original lacked a future-verified D1 settling onset on6..55s. All64 onset records are right-censored at55s, with observation through63.8s. This extends M8’s finite censoring window and does not show permanent nonsettling or permanent memory. There is no selected conditioning duration.','',
        '## Binding constraints','',
        '| Registered P2 component | Passing /3200 nested measurements |','|---|---:|']
    for name,count in components.items():lines.append(f"|{name}|{count['pass']}|")
    lines+=['',
        'All3200 past six-second windows had eligible actual observations. Only **two** met the unchanged current-centered six-second caliper; neither met the complete P2 conjunction. The six-second mean contrast passed315 times and the D1 subrule1070 times. The shortage is observable state support, not missing clock/sample coverage. Extra measurements or another classifier cannot manufacture positive labels in this closed panel.','',
        '## Remaining future variation after causal matching','',
        '**42/64** registered strata had all four BWE-only matched pairs; **13/64** retained all four with the compact vector. The vector uses current BWE, recent/longer contrasts, direction/acknowledged age and past controlled-service means. No queue, RTT or encoder variable was added.',
        'Of the13 fully covered compact strata, **six** kept all four eight-second marginal distributions within the original0.25-octave W-infinity bound. **Seven** failed that bound in at least one pair. Repeatable moving distributions and future stability are different registered requirements: even the six marginal matches left their frozen causal-center stability regions. Neither observation qualifies an action study.',
        'The table retains every fully covered compact stratum. Ranges are across its four prepaired native contexts; repeated landmarks share originals. No pooled population estimate is formed.','',
        '| Content | Input Mbps | Age s | Current prefix difference range | Subsequent-change residual range | Future W-infinity range | All four <=0.25 |',
        '|---|---:|---:|---|---|---|---|']
    def interval(a):return f'{min(a):.3f}..{max(a):.3f}'
    for row in covered:
        lines.append(f"|{row['content']}|{.5*2**row['input_x']:.3f}|{row['age_ms']/1000:g}|{interval(row['current_differences_octaves'])}|{interval(row['future_change_residuals_octaves'])}|{interval(row['future_w_infinity_octaves'])}|{'yes' if row['all_four_future_distributions_within_original_bound'] else 'no'}|")
    lines+=['',
        'For example, at Kampar/1.414Mbps/32s, all four current differences were within about0.020 octave, yet future W-infinity was0.292..0.344, above0.25 in every pair. At Volga/1Mbps/55s, all four pairs met compact matching but subsequent-change residuals were **+0.165..+0.244 octave**, and two future-distribution distances exceeded0.25. Complete paired values remain in the diagnostic JSON.',
        'These selected-context residuals do **not** isolate a causal prefix effect or separate systematic prefix memory from within-history native/run variability. Matching conditions on endogenous observations. Unconditional randomized-prefix comparisons and their four paired values/16 exact sign assignments remain separately reported; minimum attainable two-sided p is0.125. M5’s qualified causal history result remains intact.','',
        '## Consequences and next development design','',
        'The tested compact package provides no prospectively eligible future-stable common state under the frozen contract. It does not establish that history is irrelevant, that all compact states fail, or that no trajectory can be predicted. Some moving marginal distributions were reproducible. Existing calipers, duration, counts, range/SD/overlap, timing and probe gates remain unchanged; action-value estimation and learned control remain closed.',
        'The completed residual audit permits considering additional history information on **fresh development data**. The next useful preparation is a causal-observability/mechanism assay, not another fit to these validation captures. A concrete minimal proposal is eight fresh originals: two contents ×two prefix histories ×two repeats at the1.414Mbps common input where matched contexts diverged. Retain the24s initial/64s common schedule,25ms actual sampler, clock/TURN/readback/cleanup gates and250ms limit.',
        'Record owned relay queue/service-counter snapshots using a request/response acknowledgement fence in the sender clock, linked native RTCP RTT and feedback-counter age, and previous cap/send-rate/encoder behavior from getStats returns. A relay snapshot becomes usable only after its browser receipt; never construct an online feature with a clock fit trained on later markers. Preserve missing/invalid counters explicitly. Receiver quality/deadline outcomes remain unopened. This is an instrumentation proposal, not a registered executable follow-on or a selected representation.',
        'Qualify those channels prospectively before collecting a separate development panel. Any later representation requires fresh untouched confirmation and actual positive stable-context coverage under the existing gates. If that development again has no positive stable labels, do not fit a stability classifier or promote an action study. Queue/RTT/encoder information may explain moving trajectories; it cannot retroactively create stable states in M9R. No new definition, threshold, fixed conditioning wait or favorable late window is selected here.',
        'M9R validation is closed to additional state searches. M8’s successor allocation and all older closed panels remain untouched.','',
        '- [Frozen result](NATIVE_PHASE_STATE_M9R_RESULTS.md), [complete primary summary](../reports/native-phase-state-m9r-summary.json).',
        '- [Registered-component diagnostic and all13 matched strata](../reports/native-phase-state-m9r-support-failure-diagnostic.json).','']
    path=REPO/'docs/NATIVE_PHASE_STATE_M9R_INTERPRETATION.md';assert not path.exists();path.write_text('\n'.join(lines))
    return {'classification':result['classification'],'positive_future_labels':label_count,'P2_first_tags':result['P2_first_tags'],'fully_covered_compact_strata':len(covered),'future_distribution_matches':result['matching_coverage']['covered_strata_all_future_distributions_within_bound'],'new_features_evaluated':False}

if __name__=='__main__':print(json.dumps(diagnose()))
