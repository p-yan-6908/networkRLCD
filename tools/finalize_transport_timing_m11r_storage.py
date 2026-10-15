"""Pin a freshly verified M11R diagnostic archive to the actual channel decision."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
PREFIX='native-transport-timing-m11r-20261015-01'
REGISTRATION='86ac6f45ffc96e19bb7320c1a9f3f2d14810133c'
s=importlib.util.spec_from_file_location('m11r_storage',REPO/'tools/measure_transport_timing_m11r.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v

def finalize():
    from huggingface_hub import hf_hub_download
    m.verify();path=REPO/'docs/storage-receipts'/(PREFIX+'.json');receipt=v.read(path)
    assert receipt['remote_fresh_download_verified'] and receipt['archive_and_restored_file_checksums_verified']
    root=Path(receipt['raw_capture_root']);p=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',
        filename=PREFIX+'/file-index.json',revision=receipt['revision'],force_download=True))
    assert v.sha(p)==receipt['parts']['file-index.json']['sha256'];files=v.read(p)['files']
    for name in ('archive_bindings.json','transport_channel_qualification.json','provenance/docs/NATIVE_TRANSPORT_TIMING_M11R_RESULTS.md',
        'provenance/docs/NATIVE_TRANSPORT_TIMING_M11R_PLAN.md','provenance/reports/native-transport-timing-m11r-preservation-audit.json'):
        assert (root/name).stat().st_size==files[name]['size'] and v.sha(root/name)==files[name]['sha256']
    binding=v.read(root/'archive_bindings.json');report=v.read(REPO/'reports/native-transport-timing-m11r-reporting.json')
    receipt.update(abi='native_transport_timing_m11r_archive_receipt_v1',scientific_registration_commit=REGISTRATION,
        gate_is_acquisition_only=True,acquisition_gate_passed=binding['acquisition_passed'],
        required_transport_channels_qualified=binding['required_channels_qualified'],result_classification=report['classification'],
        development_opened=False,future_BWE_labels_read=False,receiver_outcomes_read=False,
        native_common_support_established=False,predictor_or_controller_fitted=False,evidence_deleted=0,
        raw_evidence_retained=True,archive_binding_sha256=v.sha(root/'archive_bindings.json'))
    path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    raw=sum(p.stat().st_size for p in m.ROOT.rglob('*') if p.is_file());stage=v.CACHE/(PREFIX+'-archive')
    staged=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file());fresh=max(x['size'] for x in receipt['parts'].values())
    assert raw<=m.DESIGN['raw_budget_bytes'] and raw+staged+fresh<=m.DESIGN['external_peak_budget_bytes']
    result={'abi':'native_transport_timing_m11r_storage_v1','prefix':PREFIX,'revision':receipt['revision'],
        'files_freshly_verified':receipt['files_verified'],'archive_index_sha256':v.sha(p),'raw_bytes':raw,
        'stage_bytes':staged,'largest_fresh_download_bytes':fresh,'raw_stage_fresh_bound_bytes':raw+staged+fresh,
        'budget_bytes':m.DESIGN['external_peak_budget_bytes'],'within_budget':True,'evidence_deleted':0,
        'raw_and_licensed_originals_retained':True,'bindings':binding}
    v.write(REPO/'reports/native-transport-timing-m11r-storage.json',result)
    return {k:result[k] for k in ('revision','files_freshly_verified','raw_stage_fresh_bound_bytes','within_budget')}
if __name__=='__main__':print(json.dumps(finalize()))
