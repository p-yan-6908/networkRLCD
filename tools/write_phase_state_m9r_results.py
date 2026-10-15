"""Write M9R results from its preregistered summaries; never select another state."""
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def write():
    s=importlib.util.spec_from_file_location('m9_results_registration',REPO/'tools/measure_phase_state_m9r.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify()
    summary=m.v.read(REPO/'reports/native-phase-state-m9r-summary.json');report=m.v.read(REPO/'reports/native-phase-state-m9r-reporting.json')
    gate=m.v.read(REPO/'reports/native-phase-state-m9r-validation-gate.json');assert gate['passed'] and summary['technical_qualified']
    spec=importlib.util.spec_from_file_location('m9_inherited_gate_veto',REPO/'tools/audit_phase_state_m9r_inherited_gates.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy);inherited=legacy.audit()
    cells=report['cells'];qualified=inherited['qualified_for_next_common_state_validation'];methods=summary['methods'];res=summary['residuals']
    decision={'abi':'native_phase_state_m9r_next_decision_v1','P2_qualified':qualified,'registered_P2_qualified':summary['P2_qualified'],
        'inherited_gates_passed':inherited['inherited_gates_passed'],'compact_state_search_closed_on_M9R':True,
        'M5_causal_history_result_preserved':True,'M8_dynamic_asymmetry_preserved':True,
        'conditioning_duration_derived':False,'old_successor_allocations_opened':False,'actions_or_controller':False,
        'residuals_quantified_before_additional_features':True,
        'matched_four_pair_strata':{'B0':sum(x['B0_full_coverage'] for x in res),'compact':sum(x['compact_full_coverage'] for x in res),'total':len(res)},
        'next_if_qualified':'New untouched phase-state conditioning validation with separately registered measured-family transfer; no old allocation or action session',
        'next_if_unqualified':'Fresh prospective instrumentation study of omitted queue/RTT/encoder histories, selected only after this residual audit; no new feature evaluation on M9R validation',
        'selected_next_step':'fresh phase-state transfer validation' if qualified else 'fresh omitted-history instrumentation design',
        'scope':'This finite rule/matching representation and these reused contents/controlled inputs only; not a proof that every compact observable representation fails'}
    m.v.write(REPO/'reports/native-phase-state-m9r-next-decision.json',decision)
    rows=gate['sessions'];clock=max(x['clock']['full']['max_held_out_width_ms'] for x in rows);begin=max(x['clock']['beginning']['max_held_out_width_ms'] for x in rows)
    def f(x,n=3):return 'unavailable' if x is None else f'{x:.{n}f}'
    lines=['# M9R: prospective phase-aware state and longer-horizon stability','',
        'Scientific registration: `df23517803303e323ae6fee5068967b02bb4b52b`; schedule/clock qualification: `M9R_INSTRUMENTATION_PENDING`.',
        'Eight instrumentation originals and **64/64 validation originals** qualified before state interpretation. No bitrate actions, delivery/QoE analysis or controller fitting occurred.','',
        '## Decision','',
        ('**P2 met every registered state gate.** It supplies a candidate for a new untouched transfer validation, not permission to open either old allocation or fit a controller.' if qualified else
         '**P2 did not qualify for the next common-state validation.** The fixed rule is closed on these validation captures; no alternative state, caliper, count, duration or favorable landmark is substituted.'),
        'M5 remains causal evidence of finite-horizon history effects. M8 remains evidence of asymmetric native dynamics. This result does not establish that history is irrelevant or that no compact representation can ever work.','',
        '## Observation design and horizon','',
        'The longer common-service plateau was prospectively frozen at **64 seconds**, four times the maximum M8 common-rise t90 upper bound rounded up to 16s. This is an observation budget, not a new fixed conditioning duration. No capture-dependent extension was made.',
        'Two reused licensed productions × four fixed wire-service inputs × ascending/descending equal-multiset prefix histories × four independent native originals/history =64. Initial service lasted24s, common service64s; the same original measured-source probe followed. Sender cap4Mbps, native initialization1200kbps, receiver target0. Low input strata fell from1.5Mbps; high strata rose from0.5Mbps. Direction and input stratum are associated by design, so M9R does not independently estimate a new direction effect.',
        'The service plateaus are controlled synthetic inputs. Fresh native originals do not make these reused contents or the measured-source dependencies independent new source evidence. No broad-network or permanent-memory claim is supported.','',
        '## Actual-run machinery','',
        '| Gate | Maximum observed | Limit |','|---|---:|---:|',
        f'| Full held-out clock width | {clock:.3f}ms |50ms|',f'| Beginning held-out clock width | {begin:.3f}ms |50ms|',
        f"| Sender sampling gap | {max(x['maximum_observer_gap_ms'] for x in rows):.3f}ms |250ms|",
        f"| Service acknowledgement | {max(x['input_fidelity']['maximum_ack_ms'] for x in rows):.3f}ms |100ms|",
        f"| Service-command lateness | {max(x['input_fidelity']['maximum_command_lateness_ms'] for x in rows):.3f}ms |0..150ms|",
        f"| Source tick error | {max(x['input_fidelity']['maximum_tick_error_ms'] for x in rows):.3f}ms |150ms|",'',
        'Every actual clock map used128 training and15 held-out exchanges; beginning certificates used35/four. Managed policy, TURN/TCP, media progression, inactive/exact initialization, fixed readback, common-probe exposure, elapsed timing and exact post-cutoff cleanup passed. Complete archive/session checksums were verified before telemetry.','',
        '## Frozen state predictions','',
        'B0 tags an eligible instantaneous BWE. D1 is the unchanged M8 past3s/caliper/drift rule. The single new P2 rule additionally requires a bounded eligible6s trajectory, small3s-versus-previous3s contrast, known service history, and acknowledged response phase beyond the M8 direction-specific t90 envelope (rise16s/fall2s). Features use only past native samples and input acknowledgements. Queue, RTT, delivered throughput, encoder and outcome variables do not enter the state.',
        'For each original the first causal tag on the frozen6..55s grid is binding. Future truth requires the same +/-0.125-octave causal-center caliper and <=0.05 adjacent-second drift through common age63.8s, with >=8s verification. Later grid counts are nested diagnostic measurements and cannot rescue a failed first prediction.','',
        '| Method | Originals tagged /64 | First predictions future-verified | Registered M9R state gates |','|---|---:|---:|---|']
    for key,value in methods.items():lines.append(f"|{key}|{value['first_tags']}|{value['future_verified']}|{'pass' if value['passed'] else 'fail'}|")
    lines+=['','Every method retains the original four-member/history, fixed target caliper, range>=1 octave, sample SD>=0.35, overlap>=0.5, repeat spread/W-infinity<=0.25, census agreement and elapsed gates. Empirical future distributions use all native samples, exact inverse-CDF W-infinity and equal weight per original. No failed/untagged original is removed from the qualification denominator.',
        f"The separately frozen [inherited-gate veto](NATIVE_PHASE_STATE_M9R_INHERITED_GATES.md) also enforces the exact old fixed-target three-second H1 history and6s/12s measured-probe repeatability requirements. It {'passed' if inherited['inherited_gates_passed'] else 'failed'} and cannot rescue a failed M9R prediction. Registered M9R results are unchanged; future-validation qualification requires both decisions.",'',
        '## Later settling and remaining history dependence','',
        'The following onset counts use the frozen D1 rule plus future labels over6..55s; they are descriptive onset estimates, not online state predictions. No verified onset is right-censored after55s, not evidence of permanent nonsettling. At age55s, future labels cover the next8s under identical common service. Each residual is descending minus ascending in subsequent BWE change from its causal current value.','',
        '| Content | Service Mbps | D1 verified onset /8 | P2 first tags / true | Age55 compact pairs /4 | Paired residual range (octaves) | Future W-infinity range |',
        '|---|---:|---:|---:|---:|---|---|']
    for c in cells:
        a=c['late_compact_residual_range'];w=c['late_compact_future_w_infinity'];rr='unestimable' if not a['n'] else f"{f(a['minimum'])}..{f(a['maximum'])}"
        wr='unestimable' if not w['n'] else f"{f(w['minimum'])}..{f(w['maximum'])}"
        lines.append(f"|{c['content']}|{.5*2**c['input_x']:.3f}|{c['D1_future_verified_onsets']}|{c['P2_first_tags']} / {c['P2_first_future_verified']}|{c['late_compact_pairs']}|{rr}|{wr}|")
    lines+=['',f"Across the64 preregistered content/input/landmark strata, B0 had all four matched pairs in **{sum(x['B0_full_coverage'] for x in res)}/64**; compact matching had **{sum(x['compact_full_coverage'] for x in res)}/64**. These repeated landmarks are not independent trials. Complete paired values, dropped counts, individual future-distribution distances and all strata are retained in the summary; cells with fewer than four pairs are under-covered and cannot establish common support.",
        'Compact matching uses only current BWE, recent and longer BWE contrasts, change direction/acknowledged age, and past6/16s controlled-service means. Residual comparisons after matching describe selected contexts; conditioning does not preserve an unconditional randomized prefix estimand. Unconditional history contrasts retain their specific randomized schedule interpretation. Four prepaired values and all16 exact sign assignments are shown separately for each content/input/age: minimum attainable two-sided p is0.125. Polls, repeated ages and reused sources are never used to manufacture precision.',
        'The residual audit is completed before considering additional queue/RTT/encoder history. M9R validation is closed to new state searches. A further representation needs a fresh prospective instrumentation/development panel and an untouched validation, retaining the same support/stability gates.','',
        '## Preservation and next step','',
        'All tracked files at completed M9, including the earlier M8 freeze, are unchanged. M5, M6R, M7/M7R/M7RA, V13 and prior negative results/freezes remain intact. The old M7-family validation panels and M8 successor allocation are unopened/uninstantiated. No heuristic conditioning duration was derived.',
        ('The next justified step is a separate untouched phase-state transfer validation; bitrate actions remain closed.' if qualified else
         'The next justified step is a separate prospective omitted-history instrumentation design, informed by the quantified residuals rather than another post hoc compact-state search or longer fixed wait. Bitrate actions and learned control remain closed.'),
        'All72 original captures, source snapshots, reports and failed state predictions are preserved in a new private archive with an immutable revision, fresh object checks and every member size/SHA-256 verified. Licensed originals/derivatives and raw working copies remain retained; zero evidence files deleted.','',
        '- [Frozen plan](NATIVE_PHASE_STATE_M9R_PLAN.md), [complete registered summary](../reports/native-phase-state-m9r-summary.json), [cell report](../reports/native-phase-state-m9r-reporting.json).',
        '- [Native trajectories](../reports/native-phase-state-m9r-trajectories.png), [conditional residuals](../reports/native-phase-state-m9r-residuals.png).',
        '- [Preservation audit](../reports/native-phase-state-m9r-preservation-audit.json), [archive receipt](storage-receipts/native-phase-state-m9r-20261015-01.json).','']
    path=REPO/'docs/NATIVE_PHASE_STATE_M9R_RESULTS.md';text='\n'.join(lines)
    if path.exists():assert path.read_text()==text
    else:path.write_text(text)
    return {'P2_qualified':qualified,'result_document':str(path.relative_to(REPO)),'next_decision':decision['selected_next_step']}

if __name__=='__main__':print(json.dumps(write()))
