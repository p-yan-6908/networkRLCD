"""Preserve M9's strict technical stop; never run its gated state analysis."""
import importlib.util
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def preserve():
    s=importlib.util.spec_from_file_location('m9_failure_preservation',REPO/'tools/measure_phase_state_m9.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify();root=m.ROOT/'validation'
    for stage in ('instrumentation','validation'):m.v.core.check_capture_integrity(m.ROOT/stage)
    gate=m.v.read(root/'mechanism_qualification_gate.json');diagnostic=m.v.read(root/'instrumentation_failure_diagnostic.json')
    assert not gate['passed'] and gate['qualified_sessions']==62
    assert not(root/'phase_state_records.json').exists() and not(root/'phase_state_summary.json').exists()
    stop={'abi':'native_phase_state_m9_scientific_stop_v1','technical_gate_passed':False,'state_comparison_estimable':False,
        'classification':'instrumentation-limited; not evidence for or against phase-aware state sufficiency',
        'planned_originals':64,'sealed_originals':64,'technically_qualified_originals':62,
        'future_state_predictions_or_residuals_evaluated':False,'fixed_gates_relaxed':False,'failed_originals_replaced':False,
        'old_successor_allocations_opened':False,'bitrate_actions_or_controller_fitting':False,
        'protocol_sha256':m.v.sha(root/'protocol.json'),'gate_sha256':m.v.sha(root/'mechanism_qualification_gate.json'),
        'diagnostic_sha256':m.v.sha(root/'instrumentation_failure_diagnostic.json'),'closed_panels':m.old_closed(),
        'next_step':'Prospectively qualify denser actual observation timing, then use a fresh phase-state panel; preserve all time-domain gates and state rules'}
    m.v.write(root/'scientific_stop.json',stop);m.v.write(REPO/'reports/native-phase-state-m9-scientific-stop.json',stop)
    text='''# M9: instrumentation-limited phase-state validation

Scientific registration: `96ada5a290b3807629bf28bf5d74183aff35a9c3`.
The two instrumentation originals qualified. All **64/64** validation originals
sealed, but only **62/64** met the registered technical gate. The scientific
comparison is **unestimable**. No phase-state prediction, later-settling label,
conditional residual, bitrate action effect or controller was evaluated.

## Exact failure

| Original | Content / prefix | Current service | Main-phase gap | Limit |
|---|---|---:|---:|---:|
| m9-phase-v-020 | Volga / ascending |0.5Mbps|301.2ms|250ms|
| m9-phase-v-026 | Kampar / descending |0.5Mbps|296.8ms|250ms|

Each original had one excessive gap and no invalid/nonpositive BWE samples. The
gaps occurred at main-phase86.880..87.181s and55.143..55.440s, respectively.
Counts were856 and858 samples (registered minimum792). The gap criterion alone
failed. No sample was interpolated, omitted, replaced or accepted at a wider gap.

All64 passed full and beginning clocks, exact native1200kbps initialization,
TURN/TCP, unchanged managed-policy hashes, fixed4Mbps cap/jitter0 readback,
media progression, exact service commands/source replay and terminal cleanup.
Maximum full held-out width was1.468ms; beginning3.021ms, both below50ms.
The common-probe group gate correctly also failed the two blocks containing
unqualified originals. A sealed capture is not a qualified scientific original.

## Frozen design and scientific limit

The64s common-service horizon remains the prospectively frozen4×16s M8 rise-t90
envelope. B0, D1 and the single P2 rule, first-tag selection, future calipers,
drift, coverage, range/SD/overlap and repeatability requirements are unchanged.
The explicit inherited H1/probe veto is preserved. Neither the original phase
comparison nor a revised state is tested on these captures. M9 supplies only
instrumentation development evidence; it does not show that phase information
is irrelevant, that later settling is absent or that a compact state fails.

The source sampler waits100ms after its preceding processing/getStats cycle.
The saved metadata identifies long observation intervals but lacks a separate
getStats-request timestamp or main-thread scheduling delay. It therefore cannot
attribute these gaps to garbage collection, getStats, rendering or host pauses.
Their excess above the nominal100ms period is201.2ms/196.8ms. This motivates a
prospective denser actual-observation/anchored-scheduling qualification, with
request/response/deadline timing recorded. It does not motivate relaxing250ms,
carrying values forward, changing state thresholds or a longer conditioning wait.

## Preservation and next step

All66 originals and technical failures are retained. All1471 tracked files at
completed M8 and9076 members of the six prior pinned evidence archives were
rehashed unchanged. Both old successor allocations remain untouched. M5's causal
history result, M8's asymmetry and every prior frozen negative result remain intact.

Preregister an instrumentation-only sampler qualification, keeping the same media,
inputs, clock/TURN/readback/cleanup gates,250ms actual-observation limit and64s
common-service observation horizon. Any state-validation successor must have new
original IDs, remain untouched until that qualification passes, and retain the
same state predicates and coverage/repeatability gates. Bitrate actions and
learned control remain closed. Do not estimate residual history effects from M9.

- [Frozen plan](NATIVE_PHASE_STATE_M9_PLAN.md), [inherited-gate clarification](NATIVE_PHASE_STATE_M9_INHERITED_GATES.md).
- [Exact instrumentation diagnostic](../reports/native-phase-state-m9-instrumentation-failure.json), [technical gate](../reports/native-phase-state-m9-validation-gate.json).
- [Preservation audit](../reports/native-phase-state-m9-preservation-audit.json), [private archive receipt](storage-receipts/native-phase-state-m9-20261015-01.json).
'''
    path=REPO/'docs/NATIVE_PHASE_STATE_M9_RESULTS.md';assert not path.exists();path.write_text(text)
    names=set(m.inventory())|{str(m.CONFIG.relative_to(REPO)),'configs/native_phase_state_m9_instrumentation.json','configs/native_phase_state_m9_validation.json',
        'docs/NATIVE_PHASE_STATE_M9_RESULTS.md','docs/NATIVE_PHASE_STATE_M9_INHERITED_GATES.md',
        'reports/native-phase-state-m9-instrumentation-gate.json','reports/native-phase-state-m9-validation-gate.json',
        'reports/native-phase-state-m9-preservation-audit.json','reports/native-phase-state-m9-instrumentation-failure.json',
        'reports/native-phase-state-m9-scientific-stop.json','tools/preserve_phase_state_m9_failure.py'}
    names|={str(p.relative_to(REPO)) for p in (REPO/'tools').glob('*phase_state_m9*.py')}
    names|={str(p.relative_to(REPO)) for p in (REPO/'reports').glob('native-phase-state-m9-runtime-refresh-*.json')}
    for name in sorted(names):
        target=root/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();shutil.copy2(REPO/name,target)
    shutil.copytree(m.ROOT/'instrumentation',root/'instrumentation_evidence')
    for stage in ('instrumentation','validation'):
        for suffix in ('capture.log','worker.json'):shutil.copy2(m.ROOT/(stage+'-'+suffix),root/(stage+'-'+suffix))
    for name in ('postprocessing.log','postprocessing-worker.json','preservation-audit.log'):shutil.copy2(m.ROOT/name,root/name)
    m.v.write(root/'archive_bindings.json',{'scientific_registration_commit':'96ada5a290b3807629bf28bf5d74183aff35a9c3',
        'scientific_stop_sha256':m.v.sha(root/'scientific_stop.json'),'state_comparison_estimable':False,
        'technical_gate_sha256':m.v.sha(root/'mechanism_qualification_gate.json'),'native_common_support_established':False,
        'future_state_outcomes_evaluated':False,'old_closed_panels':m.old_closed(),'source_files':{n:m.v.sha(root/'provenance'/n) for n in sorted(names)},'evidence_deleted':0})
    return {'scientific_comparison':'unestimable','source_snapshots':len(names),'originals':66,'new_state_analysis':False}

if __name__=='__main__':print(json.dumps(preserve()))
