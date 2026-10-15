"""Stage complete M8 evidence for immutable private archival; no telemetry decoding."""
import importlib.util
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]


def preserve():
    s=importlib.util.spec_from_file_location('m8_preservation_registration',REPO/'tools/measure_bwe_transients_m8.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify()
    root=m.ROOT/'characterization'
    m.v.core.check_capture_integrity(root);m.v.core.check_capture_integrity(m.ROOT/'instrumentation')
    assert m.v.read(root/'mechanism_qualification_gate.json')['passed']
    summary=m.v.read(root/'system_id_summary.json')
    names=set(m.inventory())|{str(m.CONFIG.relative_to(REPO)),str(m.ALLOCATION.relative_to(REPO)),
        'configs/native_bwe_transients_m8_characterization.json','configs/native_bwe_transients_m8_instrumentation.json',
        'tools/audit_bwe_transients_m8.py','tools/report_bwe_transients_m8.py','tools/preserve_bwe_transients_m8.py',
        'tools/write_bwe_transients_m8_results.py','reports/native-bwe-transients-m8-next-design-decision.json',
        'reports/native-bwe-transients-m8-summary.json','reports/native-bwe-transients-m8-selection.json',
        'reports/native-bwe-transients-m8-preservation-audit.json','reports/native-bwe-transients-m8-reporting.json',
        'reports/native-bwe-transients-m8-trajectories.png','reports/native-bwe-transients-m8-settling.png',
        'reports/native-bwe-transients-m8-response-tables.json',
        'reports/native-bwe-transients-m8-support-failure-diagnostic.json',
        'docs/NATIVE_BWE_TRANSIENTS_M8_RESULTS.md'}
    for name in sorted(names):
        target=root/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists()
        shutil.copy2(REPO/name,target)
    shutil.copytree(m.ROOT/'instrumentation',root/'instrumentation_evidence')
    for stage in ('instrumentation','characterization'):
        for suffix in ('capture.log','worker.json'):
            name=stage+'-'+suffix;shutil.copy2(m.ROOT/name,root/name)
    m.v.write(root/'archive_bindings.json',{'scientific_registration_commit':'cbbafc4f6846d6ad0a5eaf064d09750c7e4d26fa',
        'acquisition_only_gate_sha256':m.v.sha(root/'mechanism_qualification_gate.json'),
        'settling_selection_sha256':m.v.sha(root/'settling_selection.json'),'system_id_summary_sha256':m.v.sha(root/'system_id_summary.json'),
        'instrumentation_gate_sha256':m.v.sha(root/'instrumentation_evidence/mechanism_qualification_gate.json'),
        'candidate_qualified_for_successor':summary['selection']['eligible'],'native_common_support_established':False,
        'old_m7ra_panel_opened':False,'untouched_successor_allocation':128,
        'source_files':{name:m.v.sha(root/'provenance'/name) for name in sorted(names)},'raw_or_licensed_files_deleted':0})
    return {'completed_stage':'characterization','files':len([p for p in root.rglob('*') if p.is_file()]),
            'source_snapshots':len(names),'instrumentation_originals_included':2}


if __name__=='__main__':print(json.dumps(preserve()))
