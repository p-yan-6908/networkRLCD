"""Checksum-only preservation audit. Never decode previous telemetry or outcomes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]


def audit():
    from huggingface_hub import hf_hub_download
    s=importlib.util.spec_from_file_location('audit_m7_registration',REPO/'tools/measure_state_conditioning_m7ra.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    verified=m.verify()
    previous={}
    for label,name in [('M5','native-prefix-memory-m5-20261014-01'),('M6R','native-history-state-m6r-20261014-01'),('M7','native-state-conditioning-m7-20261015-01'),('M7R','native-state-conditioning-m7r-20261015-01')]:
        receipt=m.v.read(REPO/'docs/storage-receipts'/(name+'.json'))
        inventory=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=receipt['prefix']+'/file-index.json',revision=receipt['revision']))
        assert m.v.sha(inventory)==receipt['parts']['file-index.json']['sha256']
        files=m.v.read(inventory)['files'];root=Path(receipt['raw_capture_root'])
        total=0
        for relative,meta in files.items():
            path=root/relative
            assert path.stat().st_size==meta['size'] and m.v.sha(path)==meta['sha256'], f'{label}: {relative}'
            total+=meta['size']
        previous[label]={'revision':receipt['revision'],'files_unchanged':len(files),'bytes_rehashed':total,
                         'checksum_only':True,'telemetry_fields_decoded':False}
    path=m.ROOT/'validation'
    validation={'started':(path/'sessions').exists(),'capture_index_exists':(path/'capture_index.json').exists(),
                'panels':len(list((path/'panels').glob('*.json'))),'protocol_sha256':m.v.sha(path/'protocol.json')}
    if not validation['started']:
        assert not validation['capture_index_exists'] and validation['panels']==128
    result={'abi':'native_state_conditioning_m7ra_preservation_audit_v1','registration':verified,
            'prior_archives':previous,'validation':validation,'prior_files_unchanged':verified['prior_files_unchanged'],
            'm6r_validation_new_state_features_computed':False,'prior_outcomes_read':False,'prior_frozen_files_modified':0,
            'licensed_originals_and_old_clips_unchanged':True,'files_deleted':0}
    m.v.write(REPO/'reports/native-state-conditioning-m7ra-preservation-audit.json',result)
    return result


if __name__=='__main__':
    print(json.dumps(audit()))
