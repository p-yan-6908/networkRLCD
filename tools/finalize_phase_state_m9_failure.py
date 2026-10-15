"""Bind M9's freshly verified archive to its instrumentation-limited scientific stop."""
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
PREFIX='native-phase-state-m9-20261015-01'

def finalize():
    from huggingface_hub import hf_hub_download
    s=importlib.util.spec_from_file_location('m9_failure_finalizer',REPO/'tools/measure_phase_state_m9.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify();root=m.ROOT/'validation'
    path=REPO/'docs/storage-receipts'/(PREFIX+'.json');receipt=m.v.read(path)
    assert receipt['archive_and_restored_file_checksums_verified'] and receipt['remote_fresh_download_verified'] and not receipt['registered_gate_passed']
    downloaded=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=PREFIX+'/file-index.json',revision=receipt['revision'],force_download=True))
    assert m.v.sha(downloaded)==receipt['parts']['file-index.json']['sha256'];files=m.v.read(downloaded)['files']
    for name in ('scientific_stop.json','instrumentation_failure_diagnostic.json','archive_bindings.json','mechanism_qualification_gate.json',
                 'provenance/docs/NATIVE_PHASE_STATE_M9_RESULTS.md','instrumentation_evidence/mechanism_qualification_gate.json'):
        assert (root/name).stat().st_size==files[name]['size'] and m.v.sha(root/name)==files[name]['sha256']
    stop=m.v.read(root/'scientific_stop.json');assert not stop['state_comparison_estimable']
    receipt.update(result_classification='instrumentation-limited; phase-state comparison unestimable',state_outcomes_evaluated=False,
        scientific_stop_sha256=m.v.sha(root/'scientific_stop.json'),native_common_support_established=False)
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    stage=m.v.CACHE/(PREFIX+'-archive');raw=sum(p.stat().st_size for p in m.ROOT.rglob('*') if p.is_file());staged=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file());largest=max(p['size'] for p in receipt['parts'].values())
    assert raw+staged+largest<3000000000
    result={'abi':'native_phase_state_m9_failed_instrumentation_archive_v1','revision':receipt['revision'],'members_verified':receipt['files_verified'],
        'technical_qualified_originals':62,'planned_originals':64,'state_comparison_estimable':False,'future_state_analysis_started':False,
        'raw_stage_and_one_fresh_copy_bytes':raw+staged+largest,'incremental_external_budget_bytes':3000000000,'evidence_deleted':0,
        'scientific_stop_sha256':m.v.sha(root/'scientific_stop.json'),'closed_panels':m.old_closed()}
    m.v.write(REPO/'reports/native-phase-state-m9-archive-bindings.json',result)
    return result

if __name__=='__main__':print(json.dumps(finalize()))
