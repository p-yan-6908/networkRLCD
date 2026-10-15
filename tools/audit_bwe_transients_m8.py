"""Checksum-only M8 preservation/storage audit; never project old telemetry."""
import importlib.util
import json
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]


def audit():
    from huggingface_hub import hf_hub_download
    s=importlib.util.spec_from_file_location('audit_m8_registration',REPO/'tools/measure_bwe_transients_m8.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);verification=m.verify();archives={}
    for label,name in [('M5','native-prefix-memory-m5-20261014-01'),('M6R','native-history-state-m6r-20261014-01'),
        ('M7','native-state-conditioning-m7-20261015-01'),('M7R','native-state-conditioning-m7r-20261015-01'),('M7RA','native-state-conditioning-m7ra-20261015-01')]:
        receipt=m.v.read(REPO/'docs/storage-receipts'/(name+'.json'))
        path=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=receipt['prefix']+'/file-index.json',revision=receipt['revision']))
        assert m.v.sha(path)==receipt['parts']['file-index.json']['sha256'];files=m.v.read(path)['files'];root=Path(receipt['raw_capture_root']);total=0
        for relative,meta in files.items():
            file=root/relative;assert file.stat().st_size==meta['size'] and m.v.sha(file)==meta['sha256'],(label,relative);total+=meta['size']
        archives[label]={'revision':receipt['revision'],'members_unchanged':len(files),'bytes_rehashed':total,'telemetry_decoded':False}
    committed=subprocess.check_output(['git','ls-tree','-r','--name-only','0e5987b'],cwd=REPO,text=True).splitlines()
    for name in committed:assert subprocess.check_output(['git','show','0e5987b:'+name],cwd=REPO)==(REPO/name).read_bytes(),name
    assert not(m.parent.ROOT/'validation/sessions').exists()
    result={'abi':'native_bwe_transients_m8_preservation_audit_v1','registration':verification,'all_preregistration_tracked_files_unchanged':len(committed),
        'prior_archives':archives,'old_m7ra_128_sessions_untouched':True,'next_allocation_sha256':m.v.sha(m.ALLOCATION),
        'next_allocation_originals':128,'new_states_tested_on_prior_validation':False,'raw_or_licensed_evidence_deleted':0,
        'licensed_originals_and_old_derivatives_unchanged':True}
    m.v.write(REPO/'reports/native-bwe-transients-m8-preservation-audit.json',result)
    return result


if __name__=='__main__':print(json.dumps(audit()))
