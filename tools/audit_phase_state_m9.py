"""Checksum-only preservation audit; no new projections of previous validation data."""
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def audit():
    from huggingface_hub import hf_hub_download
    s=importlib.util.spec_from_file_location('m9_audit_registration',REPO/'tools/measure_phase_state_m9.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);verification=m.verify();archives={}
    for label,name in [('M5','native-prefix-memory-m5-20261014-01'),('M6R','native-history-state-m6r-20261014-01'),
        ('M7','native-state-conditioning-m7-20261015-01'),('M7R','native-state-conditioning-m7r-20261015-01'),
        ('M7RA','native-state-conditioning-m7ra-20261015-01'),('M8','native-bwe-transients-m8-20261015-01')]:
        receipt=m.v.read(REPO/'docs/storage-receipts'/(name+'.json'))
        path=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=receipt['prefix']+'/file-index.json',revision=receipt['revision']))
        assert m.v.sha(path)==receipt['parts']['file-index.json']['sha256'];files=m.v.read(path)['files'];root=Path(receipt['raw_capture_root']);total=0
        for relative,meta in files.items():
            file=root/relative;assert file.stat().st_size==meta['size'] and m.v.sha(file)==meta['sha256'],(label,relative);total+=meta['size']
        archives[label]={'revision':receipt['revision'],'members_unchanged':len(files),'bytes_rehashed':total,'telemetry_decoded':False}
    result={'abi':'native_phase_state_m9_preservation_audit_v1','registration':verification,'prior_archives':archives,
        'all_M8_result_tracked_files_unchanged':len(m.v.read(m.FREEZE)['files']),'closed_panels':m.old_closed(),
        'new_states_tested_on_prior_validation':False,'raw_or_licensed_evidence_deleted':0,'licensed_originals_and_old_derivatives_unchanged':True}
    m.v.write(REPO/'reports/native-phase-state-m9-preservation-audit.json',result)
    return result

if __name__=='__main__':print(json.dumps(audit()))
