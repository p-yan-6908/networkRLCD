"""Checksum-only prior preservation and complete external M11 archive preparation."""
from __future__ import annotations
import argparse
import importlib.util
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m11_preserve',REPO/'tools/measure_transport_timing_m11.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v
REGISTRATION='fba94f71da4cc3be308b7ac88476b45935e8319c'

def audit():
    from huggingface_hub import hf_hub_download
    verification=m.verify();archives={}
    prefixes=[('M5','native-prefix-memory-m5-20261014-01'),('M6R','native-history-state-m6r-20261014-01'),
        ('M7','native-state-conditioning-m7-20261015-01'),('M7R','native-state-conditioning-m7r-20261015-01'),
        ('M7RA','native-state-conditioning-m7ra-20261015-01'),('M8','native-bwe-transients-m8-20261015-01'),
        ('M9','native-phase-state-m9-20261015-01'),('M9R','native-phase-state-m9r-20261015-01'),
        ('M10','native-mechanism-observability-m10-20261015-01'),('M10R','native-mechanism-observability-m10r-20261015-01')]
    for label,prefix in prefixes:
        receipt=v.read(REPO/'docs/storage-receipts'/(prefix+'.json'))
        p=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=prefix+'/file-index.json',revision=receipt['revision']))
        assert v.sha(p)==receipt['parts']['file-index.json']['sha256'];files=v.read(p)['files'];root=Path(receipt['raw_capture_root']);total=0
        for name,meta in files.items():
            source=root/name;assert source.stat().st_size==meta['size'] and v.sha(source)==meta['sha256'],(label,name);total+=meta['size']
        archives[label]={'revision':receipt['revision'],'members_unchanged':len(files),'bytes_rehashed':total,'telemetry_decoded':False}
    report={'abi':'native_transport_timing_m11_preservation_v1','verification':verification,'prior_archives':archives,
        'all_prior_tracked_files_unchanged':len(v.read(m.FREEZE)['files']),'closed_panels':m.old_closed(),
        'licensed_originals_verified_by_registration':True,'new_representations_on_old_panels':False,'evidence_deleted':0}
    v.write(REPO/'reports/native-transport-timing-m11-preservation-audit.json',report);return report

def preserve():
    m.verify();root=m.ROOT/'capability';v.core.check_capture_integrity(root)
    qualification=v.read(root/'transport_channel_qualification.json')
    if (m.ROOT/'verbose/capture_index.json').exists():
        v.core.check_capture_integrity(m.ROOT/'verbose');shutil.copytree(m.ROOT/'verbose',root/'verbose_evidence')
    shutil.copytree(m.DISCOVERY,root/'static_source_evidence')
    drafts=v.CACHE/'native-transport-timing-m11-pre-registration-drafts'
    if drafts.exists():shutil.copytree(drafts,root/'pre_registration_drafts')
    names=set(m.inventory())|{'configs/native_transport_timing_m11.json','tools/preserve_transport_timing_m11.py',
        'tools/report_transport_timing_m11.py','tools/transport_timing_m11_verbose.py',
        'tools/archive_transport_timing_m11.py','tools/finalize_transport_timing_m11_storage.py',
        'docs/NATIVE_TRANSPORT_TIMING_M11_RESULTS.md','docs/NATIVE_TRANSPORT_TIMING_M11_VERBOSE_PLAN.md'}
    names|={str(p.relative_to(REPO)) for p in (REPO/'reports').glob('native-transport-timing-m11-*') if p.is_file()}
    if (REPO/'configs/native_transport_timing_m11_verbose.json').exists():names.add('configs/native_transport_timing_m11_verbose.json')
    names={n for n in names if (REPO/n).is_file()}
    for name in sorted(names):
        target=root/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();shutil.copy2(REPO/name,target)
    for p in m.ROOT.glob('*.log'):assert not (root/p.name).exists();shutil.copy2(p,root/p.name)
    bindings={'scientific_registration_commit':REGISTRATION,'source_files':{n:v.sha(root/'provenance'/n) for n in sorted(names)},
        'acquisition_gate_sha256':v.sha(root/'support_clock_transport_gate.json'),'channel_gate_sha256':v.sha(root/'transport_channel_qualification.json'),
        'acquisition_passed':qualification['acquisition_passed'],'required_channels_qualified':qualification['passed'],
        'development_opened':False,'future_BWE_labels_read':False,'receiver_outcomes_read':False,
        'actions_or_controller':False,'evidence_deleted':0,'old_closed_panels':m.old_closed()}
    v.write(root/'archive_bindings.json',bindings)
    return {'archive_root':str(root),'files':sum(p.is_file() for p in root.rglob('*')),'source_snapshots':len(names)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['audit','preserve']);a=p.parse_args();print(json.dumps(globals()[a.command]()))
