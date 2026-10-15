"""Copy completed M9R provenance into its external archive tree without decoding outcomes."""
import importlib.util
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def preserve():
    s=importlib.util.spec_from_file_location('m9_preservation_registration',REPO/'tools/measure_phase_state_m9r.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify();root=m.ROOT/'validation'
    for stage in ('instrumentation','validation'):m.v.core.check_capture_integrity(m.ROOT/stage)
    summary=m.v.read(root/'phase_state_summary.json');assert summary['technical_qualified']
    names=set(m.inventory())|{str(m.CONFIG.relative_to(REPO)),'configs/native_phase_state_m9r_instrumentation.json',
        'configs/native_phase_state_m9r_validation.json','tools/report_phase_state_m9r.py','tools/audit_phase_state_m9r.py',
        'tools/preserve_phase_state_m9r.py','tools/write_phase_state_m9r_results.py','tools/finalize_phase_state_m9r_storage.py',
        'tools/audit_phase_state_m9r_inherited_gates.py','docs/NATIVE_PHASE_STATE_M9R_INHERITED_GATES.md',
        'reports/native-phase-state-m9r-inherited-gates.json',
        'tools/diagnose_phase_state_m9r.py','docs/NATIVE_PHASE_STATE_M9R_INTERPRETATION.md',
        'reports/native-phase-state-m9r-support-failure-diagnostic.json',
        'reports/native-phase-state-m9r-summary.json','reports/native-phase-state-m9r-reporting.json',
        'reports/native-phase-state-m9r-trajectories.png','reports/native-phase-state-m9r-residuals.png',
        'reports/native-phase-state-m9r-preservation-audit.json','reports/native-phase-state-m9r-next-decision.json',
        'reports/native-phase-state-m9r-instrumentation-gate.json','reports/native-phase-state-m9r-validation-gate.json',
        'docs/NATIVE_PHASE_STATE_M9R_RESULTS.md'}
    names|={str(p.relative_to(REPO)) for p in (REPO/'reports').glob('native-phase-state-m9r-runtime-refresh-*.json')}
    for name in sorted(names):
        target=root/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists()
        shutil.copy2(REPO/name,target)
    shutil.copytree(m.ROOT/'instrumentation',root/'instrumentation_evidence')
    for stage in ('instrumentation','validation'):
        for suffix in ('capture.log','worker.json'):shutil.copy2(m.ROOT/(stage+'-'+suffix),root/(stage+'-'+suffix))
    for name in ('postprocessing.log','postprocessing-worker.json','analysis-complete.json'):
        shutil.copy2(m.ROOT/name,root/name)
    inherited=m.v.read(root/'inherited_gate_audit.json')
    bindings={'scientific_registration_commit':'df23517803303e323ae6fee5068967b02bb4b52b',
        'inherited_gate_compatibility_commit':'df23517803303e323ae6fee5068967b02bb4b52b',
        'acquisition_only_gate_sha256':m.v.sha(root/'mechanism_qualification_gate.json'),
        'phase_state_summary_sha256':m.v.sha(root/'phase_state_summary.json'),'phase_state_records_sha256':m.v.sha(root/'phase_state_records.json'),
        'instrumentation_gate_sha256':m.v.sha(root/'instrumentation_evidence/mechanism_qualification_gate.json'),
        'registered_P2_qualified':summary['P2_qualified'],'inherited_gate_audit_sha256':m.v.sha(root/'inherited_gate_audit.json'),
        'P2_qualified':inherited['qualified_for_next_common_state_validation'],'native_common_support_established':inherited['qualified_for_next_common_state_validation'],
        'old_closed_panels':m.old_closed(),'actions_or_controller':False,'outcomes_read':False,
        'source_files':{name:m.v.sha(root/'provenance'/name) for name in sorted(names)},'raw_or_licensed_files_deleted':0}
    m.v.write(root/'archive_bindings.json',bindings)
    return {'completed_stage':'validation','files':len([p for p in root.rglob('*') if p.is_file()]),'source_snapshots':len(names),'instrumentation_originals_included':8}

if __name__=='__main__':print(json.dumps(preserve()))
