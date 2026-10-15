"""Bind the freshly verified M9 archive to its scientific decisions and storage audit."""
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
PREFIX='native-phase-state-m9-20261015-01'

def finalize():
    from huggingface_hub import hf_hub_download
    s=importlib.util.spec_from_file_location('m9_final_storage',REPO/'tools/measure_phase_state_m9.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify();root=m.ROOT/'validation'
    path=REPO/'docs/storage-receipts'/(PREFIX+'.json');receipt=m.v.read(path)
    assert receipt['archive_and_restored_file_checksums_verified'] and receipt['remote_fresh_download_verified']
    downloaded=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=PREFIX+'/file-index.json',revision=receipt['revision'],force_download=True))
    assert m.v.sha(downloaded)==receipt['parts']['file-index.json']['sha256'];index=m.v.read(downloaded)['files']
    for name in ('archive_bindings.json','phase_state_summary.json','phase_state_records.json','inherited_gate_audit.json','mechanism_qualification_gate.json',
        'instrumentation_evidence/mechanism_qualification_gate.json','provenance/docs/NATIVE_PHASE_STATE_M9_PLAN.md',
        'provenance/docs/NATIVE_PHASE_STATE_M9_RESULTS.md','provenance/reports/native-phase-state-m9-preservation-audit.json'):
        assert (root/name).stat().st_size==index[name]['size'] and m.v.sha(root/name)==index[name]['sha256']
    binding=m.v.read(root/'archive_bindings.json')
    report={'abi':'native_phase_state_m9_science_archive_binding_v1','revision':receipt['revision'],'prefix':PREFIX,
        'archive_members_verified':receipt['files_verified'],'raw_bytes_retained':True,'files_deleted':0,
        'actual_raw_gate_is_acquisition_only':True,'P2_qualified':binding['P2_qualified'],
        'science_bindings':binding,'archive_index_sha256':m.v.sha(downloaded)}
    m.v.write(REPO/'reports/native-phase-state-m9-archive-bindings.json',report)
    # The archive helper cannot label its generic acquisition gate as the state decision.
    # Add explicit scientific fields while retaining the original verified object metadata.
    receipt.update(scientific_gate='inherited_gate_audit.json: qualified_for_next_common_state_validation',
        scientific_gate_passed=binding['P2_qualified'],acquisition_gate_passed=receipt['registered_gate_passed'],
        registered_M9_P2_gate_passed=binding['registered_P2_qualified'],inherited_gate_audit_sha256=binding['inherited_gate_audit_sha256'],
        scientific_summary_sha256=binding['phase_state_summary_sha256'],old_closed_panels=binding['old_closed_panels'])
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    stage=m.v.CACHE/(PREFIX+'-archive')
    raw=sum(p.stat().st_size for p in m.ROOT.rglob('*') if p.is_file())
    staged=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
    largest=max(x['size'] for x in receipt['parts'].values())
    assert raw+staged+largest<3000000000,'incremental raw/staging/fresh-copy bound'
    storage={'abi':'native_phase_state_m9_storage_v1','raw_and_instrumentation_bytes':raw,'archive_staging_bytes':staged,
        'largest_fresh_download_bytes':largest,'raw_stage_and_fresh_copy_upper_bound_bytes':raw+staged+largest,
        'incremental_external_budget_bytes':3000000000,'within_budget':True,'files_deleted':0}
    m.v.write(REPO/'reports/native-phase-state-m9-storage.json',storage)
    return {'archive_revision':receipt['revision'],'members_verified':receipt['files_verified'],'P2_qualified':binding['P2_qualified'],'storage_bound_bytes':raw+staged+largest}

if __name__=='__main__':print(json.dumps(finalize()))
