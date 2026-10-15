"""Archive IF1 static design/admission evidence, with a fresh complete verification."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('if1_preservation',REPO/'tools/instrumented_fixture_if1.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
PREFIX='native-instrumented-fixture-if1-20261015-01'
REGISTRATION='361c4bbe7c8e752b34ffec510e7130e21d77a0fe'
DATASET='p-yan/networkrlcd-results-archive'
STAGE=m.CACHE/(PREFIX+'-archive')
RECEIPT=REPO/'docs/storage-receipts'/(PREFIX+'.json')

def preserve():
    m.verify();root=m.ROOT;decision=m.read(root/'build-admission.json')
    assert not decision['admitted'] and decision['compiler_invocations']==decision['native_sessions']==0
    assert decision['protocol_sha256']==m.sha(m.CONFIG)
    shutil.copytree(m.DISCOVERY,root/'static_source_evidence')
    names=set(m.SOURCES)|{'configs/native_instrumented_fixture_if1.json',
        'tools/preserve_instrumented_fixture_if1.py','docs/NATIVE_INSTRUMENTED_FIXTURE_IF1_RESULT.md',
        'reports/native-instrumented-fixture-if1-build-admission.json'}
    for name in sorted(names):
        target=root/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists();shutil.copy2(REPO/name,target)
    binding={'scientific_registration_commit':REGISTRATION,'protocol_sha256':m.sha(root/'protocol.json'),
        'admission_sha256':m.sha(root/'build-admission.json'),'source_files':{n:m.sha(root/'provenance'/n) for n in sorted(names)},
        'classification':decision['classification'],'compiler_invocations':0,'native_contexts':0,
        'Cxx_interface_implemented':False,'native_channels_qualified':False,'native_common_support':False,
        'closed_panels':m.closed(),'old_telemetry_decoded':False,'receiver_outcomes_opened':False,
        'new_predictor_actions_or_controller':False,'evidence_deleted':0}
    m.write(root/'archive-bindings.json',binding)
    return {'files':sum(p.is_file() for p in root.rglob('*')),'new_native_contexts':0,'source_snapshots':len(names)}

def archive():
    from huggingface_hub import CommitOperationAdd,HfApi,hf_hub_download
    m.verify();root=m.ROOT;assert not RECEIPT.exists() and not STAGE.exists(),'fresh namespace and stage required'
    binding=m.read(root/'archive-bindings.json');assert not binding['native_channels_qualified'] and binding['native_contexts']==0
    for name,checksum in binding['source_files'].items():assert m.sha(root/'provenance'/name)==checksum
    assert binding['admission_sha256']==m.sha(root/'build-admission.json')
    paths=sorted(p for p in root.rglob('*') if p.is_file());assert not any(p.is_symlink() for p in root.rglob('*'))
    files={str(p.relative_to(root)):{'size':p.stat().st_size,'sha256':m.sha(p)} for p in paths}
    raw=sum(p.stat().st_size for p in paths)+sum(p.stat().st_size for p in m.DISCOVERY.rglob('*') if p.is_file())
    bounds=m.design()['current_static_bounds'];assert raw<=bounds['maximum_raw_bytes']
    STAGE.mkdir();part=STAGE/'evidence.tar.part-000'
    with tarfile.open(part,'w',format=tarfile.PAX_FORMAT) as tar:
        for name,meta in files.items():
            assert m.sha(root/name)==meta['sha256'];tar.add(root/name,arcname=root.name+'/'+name,recursive=False)
            assert m.sha(root/name)==meta['sha256']
    m.write(STAGE/'file-index.json',{'abi':'native_if1_static_archive_inventory_v1','member_root':root.name,'files':files})
    (STAGE/'SHA256SUMS').write_text(m.sha(part)+'  '+part.name+'\n')
    (STAGE/'RESTORE.md').write_text(
        'Static source, design and build-admission evidence only. No instrumented browser or native session exists. '
        'Fetch at the pinned receipt revision, verify every object SHA/size, then every tar member against file-index.json. '
        'Restore only into a fresh external directory. Preserve prior freezes. Original licensed media is absent.\n')
    parts={p.name:{'size':p.stat().st_size,'sha256':m.sha(p)} for p in sorted(STAGE.iterdir()) if p.is_file()}
    staged=sum(x['size'] for x in parts.values());fresh=sum(x['size'] for x in parts.values())
    assert raw+staged+fresh<=bounds['maximum_raw_stage_fresh_bytes']
    api=HfApi();info=api.dataset_info(DATASET);assert info.private
    assert not any(e.path==PREFIX for e in api.list_repo_tree(DATASET,repo_type='dataset',recursive=False))
    result=api.create_commit(DATASET,repo_type='dataset',parent_commit=info.sha,
        operations=[CommitOperationAdd(path_in_repo=PREFIX+'/'+n,path_or_fileobj=str(STAGE/n)) for n in parts],
        commit_message='Preserve IF1 registered instrumented-fixture design and resource admission limit')
    revision=result.oid;m.write(STAGE/'upload-commit.json',{'repo_id':DATASET,'prefix':PREFIX,'revision':revision})
    with tempfile.TemporaryDirectory(dir=STAGE) as temporary:
        downloaded={}
        for name,meta in parts.items():
            p=Path(hf_hub_download(DATASET,repo_type='dataset',filename=PREFIX+'/'+name,revision=revision,
                local_dir=temporary,force_download=True))
            assert p.stat().st_size==meta['size'] and m.sha(p)==meta['sha256'];downloaded[name]=p
        with tarfile.open(downloaded[part.name],'r') as tar:
            seen=set()
            for member in tar.getmembers():
                name=str(Path(member.name).relative_to(root.name));meta=files[name]
                assert member.isfile() and member.size==meta['size'] and name not in seen
                assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==meta['sha256'];seen.add(name)
            assert seen==set(files)
        # Rehash the temporary downloaded candidates immediately before cleanup.
        for name,p in downloaded.items():assert m.sha(p)==parts[name]['sha256']
    receipt={'abi':'native_if1_static_design_archive_receipt_v1','repo_id':DATASET,'private':True,
        'prefix':PREFIX,'revision':revision,'scientific_registration_commit':REGISTRATION,
        'parts':parts,'members_freshly_size_sha256_verified':len(files),'objects_freshly_verified':len(parts),
        'remote_fresh_download_verified':True,'all_members_verified':True,'raw_evidence_retained':True,
        'evidence_deleted':0,'raw_root':str(root),'protocol_sha256':m.sha(root/'protocol.json'),
        'admission_sha256':m.sha(root/'build-admission.json'),'archive_binding_sha256':m.sha(root/'archive-bindings.json'),
        'classification':binding['classification'],'fixture_built':False,'native_contexts':0,
        'native_channels_qualified':False,'receiver_outcomes_read':False,'controller_or_action_study':False,
        'prior_tracked_files_unchanged':len(m.read(m.FREEZE)['files']),
        'local_static_raw_bytes_including_reference_copy':raw,'stage_bytes':staged,
        'fresh_download_bytes':fresh,'raw_stage_fresh_peak_bound_bytes':raw+staged+fresh,
        'raw_stage_fresh_budget_bytes':bounds['maximum_raw_stage_fresh_bytes'],'archive_helper_sha256':m.sha(Path(__file__))}
    m.write(RECEIPT,receipt)
    m.write(REPO/'reports/native-instrumented-fixture-if1-storage.json',receipt)
    return {'revision':revision,'members_verified':len(files),'objects_verified':len(parts),
        'raw_stage_fresh_bytes':raw+staged+fresh,'evidence_deleted':0}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('preserve','archive'))
    args=parser.parse_args();print(json.dumps(globals()[args.command]()))
