"""Bind fresh verified M10 archive to acquisition, scientific scope and retention."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
PREFIX='native-mechanism-observability-m10-20261015-01'
REGISTRATION='03aac061347fb9c9c44b69a8f8f900e27720c60e'
s=importlib.util.spec_from_file_location('m10_storage',REPO/'tools/measure_mechanism_observability_m10.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v

def finalize():
    from huggingface_hub import hf_hub_download
    m.verify();path=REPO/'docs/storage-receipts'/(PREFIX+'.json');receipt=v.read(path)
    assert receipt['remote_fresh_download_verified'] and receipt['archive_and_restored_file_checksums_verified']
    root=Path(receipt['raw_capture_root']);download=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',
        filename=PREFIX+'/file-index.json',revision=receipt['revision'],force_download=True))
    assert v.sha(download)==receipt['parts']['file-index.json']['sha256'];files=v.read(download)['files']
    required=['archive_bindings.json','mechanism_qualification_gate.json','provenance/docs/NATIVE_MECHANISM_OBSERVABILITY_M10_PLAN.md',
        'provenance/docs/NATIVE_MECHANISM_OBSERVABILITY_M10_RESULTS.md','provenance/reports/native-mechanism-observability-m10-preservation-audit.json']
    if (root/'mechanism_analysis.json').exists():required+=['mechanism_analysis.json','mechanism_records.json',
        'instrumentation_evidence/mechanism_qualification_gate.json']
    for name in required:assert (root/name).stat().st_size==files[name]['size'] and v.sha(root/name)==files[name]['sha256']
    binding=v.read(root/'archive_bindings.json');report=v.read(REPO/'reports/native-mechanism-observability-m10-reporting.json')
    receipt.update(abi='native_mechanism_observability_m10_archive_receipt_v1',scientific_registration_commit=REGISTRATION,
        gate_is_acquisition_only=True,acquisition_gate_passed=binding['acquisition_qualified'],
        native_common_support_established=False,scientific_common_support_gate_passed=False,
        result_classification=report['classification'],fit_predictor=False,controller_fitted=False,receiver_outcomes_read=False,
        evidence_deleted=0,raw_evidence_retained=True,old_closed_panels=binding['old_closed_panels'],
        archive_binding_sha256=v.sha(root/'archive_bindings.json'))
    if 'analysis_sha256' in binding:receipt.update(analysis_sha256=binding['analysis_sha256'],
        positive_future_stability_labels_nested=binding['positive_future_stability_labels_nested'])
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    raw=sum(p.stat().st_size for p in m.ROOT.rglob('*') if p.is_file())
    stage=v.CACHE/(PREFIX+'-archive');staged=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
    fresh=max(x['size'] for x in receipt['parts'].values());assert raw<=m.DESIGN['raw_budget_bytes']
    assert raw+staged+fresh<=m.DESIGN['incremental_external_budget_bytes']
    result={'abi':'native_mechanism_observability_m10_verified_storage_v1','revision':receipt['revision'],
        'prefix':PREFIX,'members_freshly_verified':receipt['files_verified'],'archive_index_sha256':v.sha(download),
        'raw_bytes':raw,'staging_bytes':staged,'largest_fresh_download_bytes':fresh,
        'raw_stage_fresh_upper_bound_bytes':raw+staged+fresh,'budget_bytes':m.DESIGN['incremental_external_budget_bytes'],
        'within_budget':True,'files_deleted':0,'raw_retained':True,'licensed_sources_retained':True,
        'binding':binding}
    v.write(REPO/'reports/native-mechanism-observability-m10-storage.json',result)
    return {k:result[k] for k in ('revision','members_freshly_verified','raw_stage_fresh_upper_bound_bytes','within_budget')}

if __name__=='__main__':print(json.dumps(finalize()))
