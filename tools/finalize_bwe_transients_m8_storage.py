"""Bind the verified private M8 archive to scientific results and storage limits."""
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
CACHE=Path.home()/'.cache/networkrlcd'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    assert not path.exists(),'preserve completed verification artifact'
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def finalize():
    from huggingface_hub import hf_hub_download
    receipt_path=REPO/'docs/storage-receipts/native-bwe-transients-m8-20261015-01.json'
    receipt=json.loads(receipt_path.read_text());assert receipt['private'] and receipt['remote_fresh_download_verified']
    proof_path=REPO/'reports/native-bwe-transients-m8-archive-bindings.json'
    storage_path=REPO/'reports/native-bwe-transients-m8-storage.json'
    assert not proof_path.exists() and not storage_path.exists()
    root=Path(receipt['raw_capture_root']);stage=CACHE/'native-bwe-transients-m8-archive-20261015-01'
    inventory=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=receipt['prefix']+'/file-index.json',
                  revision=receipt['revision'],local_dir=stage/'receipt-check',force_download=True))
    assert sha(inventory)==receipt['parts']['file-index.json']['sha256']
    files=json.loads(inventory.read_text())['files'];assert len(files)==receipt['files_verified']
    bindings=json.loads((root/'archive_bindings.json').read_text())
    checks={'protocol.json':REPO/'configs/native_bwe_transients_m8_characterization.json',
        'mechanism_qualification_gate.json':REPO/'reports/native-bwe-transients-m8-characterization-gate.json',
        'system_id_summary.json':REPO/'reports/native-bwe-transients-m8-summary.json',
        'settling_selection.json':REPO/'reports/native-bwe-transients-m8-selection.json',
        'instrumentation_evidence/mechanism_qualification_gate.json':REPO/'reports/native-bwe-transients-m8-instrumentation-gate.json',
        'provenance/data/native-m8/next-validation-allocation.json':REPO/'data/native-m8/next-validation-allocation.json',
        'provenance/docs/NATIVE_BWE_TRANSIENTS_M8_RESULTS.md':REPO/'docs/NATIVE_BWE_TRANSIENTS_M8_RESULTS.md',
        'provenance/reports/native-bwe-transients-m8-next-design-decision.json':REPO/'reports/native-bwe-transients-m8-next-design-decision.json',
        'provenance/reports/native-bwe-transients-m8-support-failure-diagnostic.json':REPO/'reports/native-bwe-transients-m8-support-failure-diagnostic.json',
        'provenance/reports/native-bwe-transients-m8-preservation-audit.json':REPO/'reports/native-bwe-transients-m8-preservation-audit.json'}
    for name,path in checks.items():assert files[name]['sha256']==sha(path),name
    assert files['archive_bindings.json']['sha256']==sha(root/'archive_bindings.json')
    for name,checksum in bindings['source_files'].items():
        assert files['provenance/'+name]['sha256']==checksum==sha(REPO/name),name
    summary=json.loads(checks['system_id_summary.json'].read_text());selection=summary['selection']
    allocation=json.loads(checks['provenance/data/native-m8/next-validation-allocation.json'].read_text())
    assert len(allocation['trials'])==128 and len({t['id'] for t in allocation['trials']})==128
    assert not(CACHE/'native-state-conditioning-m7ra/validation/sessions').exists()
    assert summary['new_next_allocation_native_sessions_started']==0 and not summary['controller_fitted'] and not summary['action_value_estimated']
    proof={'abi':'native_bwe_transients_m8_fresh_scientific_bindings_v1','revision':receipt['revision'],
        'archive_members_verified':len(files),'fresh_inventory_sha256':sha(inventory),
        'scientific_bindings':{name:files[name]['sha256'] for name in checks},'source_snapshot_bindings_verified':len(bindings['source_files']),
        'instrumentation_originals':2,'characterization_originals':16,'system_identification_estimable':True,
        'settling_selection_eligible':selection['eligible'],'selected_age_ms':selection['selected_age_ms'],
        'old_m7ra_panel_untouched':True,'new_successor_allocation_untouched':128,'executable_successor_schedule_instantiated':False,
        'native_common_support_established':False,'action_value_estimated':False,'controller_fitted':False}
    write(proof_path,proof)
    receipt.update(generic_gate_scope='Acquisition qualification only. The separate settling selection is false and no successor schedule is instantiated.',
        system_identification_estimable=True,prospective_settling_selection_passed=selection['eligible'],
        selected_age_ms=selection['selected_age_ms'],derived_conditioning_duration_ms=selection.get('conditioning_duration_ms'),
        native_common_support_established=False,old_m7ra_128_panel_untouched=True,new_successor_allocation_untouched=128,
        successor_executable_schedule_instantiated=False,instrumentation_originals=2,characterization_originals=16,
        nested_plateau_occurrences=64,verified_settling_onsets_on_registered_grid=64-summary['settling_unverified_occurrences'],
        system_id_summary_sha256=sha(checks['system_id_summary.json']),settling_selection_sha256=sha(checks['settling_selection.json']),
        archive_bindings_sha256=sha(root/'archive_bindings.json'),fresh_scientific_binding_proof_sha256=sha(proof_path),
        storage_binding_helper_sha256=sha(Path(__file__).resolve()),additional_bindings_verified_against_freshly_restored_inventory=True,
        action_value_estimated=False,controller_fitted=False)
    receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    roots=sorted(p for p in CACHE.glob('native-bwe-transients-m8*') if p.is_dir())
    sizes={str(p):sum(f.stat().st_size for f in p.rglob('*') if f.is_file() and not f.is_symlink()) for p in roots}
    retained=sum(sizes.values());fresh=sum(x['size'] for x in receipt['parts'].values());upper=retained+fresh
    assert upper<3000000000
    write(storage_path,{'abi':'native_bwe_transients_m8_storage_bound_v1','incremental_roots_bytes':sizes,
        'current_retained_bytes':retained,'conservative_peak_including_fresh_verification_bytes':upper,
        'incremental_budget_bytes':3000000000,'within_budget':True,'licensed_originals_and_old_derivatives_retained':True,
        'raw_or_licensed_evidence_deleted':0,'private_archive_revision':receipt['revision']})
    return {'revision':receipt['revision'],'members_verified':len(files),'source_bindings_verified':len(bindings['source_files']),
            'settling_qualified':selection['eligible'],'conservative_peak_bytes':upper,'budget_bytes':3000000000}


if __name__=='__main__':print(json.dumps(finalize()))
