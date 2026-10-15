"""M10R checksum-only prior audit and complete external provenance preservation."""
from __future__ import annotations
import argparse
import importlib.util
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
REGISTRATION='597f3eac529930a329dde9c4b017e7d9217bfe12'
s=importlib.util.spec_from_file_location('m10_preservation',REPO/'tools/measure_mechanism_observability_m10r.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v

def audit():
    from huggingface_hub import hf_hub_download
    verification=m.verify();archives={}
    for label,prefix in [('M5','native-prefix-memory-m5-20261014-01'),('M6R','native-history-state-m6r-20261014-01'),
        ('M7','native-state-conditioning-m7-20261015-01'),('M7R','native-state-conditioning-m7r-20261015-01'),
        ('M7RA','native-state-conditioning-m7ra-20261015-01'),('M8','native-bwe-transients-m8-20261015-01'),
        ('M9','native-phase-state-m9-20261015-01'),('M9R','native-phase-state-m9r-20261015-01'),('M10','native-mechanism-observability-m10-20261015-01')]:
        receipt=v.read(REPO/'docs/storage-receipts'/(prefix+'.json'))
        p=Path(hf_hub_download(receipt['repo_id'],repo_type='dataset',filename=prefix+'/file-index.json',revision=receipt['revision']))
        assert v.sha(p)==receipt['parts']['file-index.json']['sha256'];files=v.read(p)['files'];root=Path(receipt['raw_capture_root']);total=0
        for name,meta in files.items():
            source=root/name;assert source.stat().st_size==meta['size'] and v.sha(source)==meta['sha256'],(label,name);total+=meta['size']
        archives[label]={'revision':receipt['revision'],'members_unchanged':len(files),'bytes_rehashed':total,'telemetry_decoded':False}
    report={'abi':'native_mechanism_observability_m10r_preservation_v1','registration':verification,'prior_archives':archives,
        'all_prior_tracked_files_unchanged':len(v.read(m.FREEZE)['files']),'closed_panels':m.old_closed(),
        'licensed_sources_verified_by_registration':True,'old_validation_representations_searched':False,
        'raw_or_licensed_evidence_deleted':0}
    v.write(REPO/'reports/native-mechanism-observability-m10r-preservation-audit.json',report);return report

def preserve():
    m.verify();opened=[stage for stage in ('instrumentation','development') if (m.ROOT/stage/'capture_index.json').exists()]
    assert opened
    for stage in opened:v.core.check_capture_integrity(m.ROOT/stage)
    stage=opened[-1];root=m.ROOT/stage
    if stage=='development':shutil.copytree(m.ROOT/'instrumentation',root/'instrumentation_evidence')
    names=set(m.inventory())|{str(m.CONFIG.relative_to(REPO)),
        'configs/native_mechanism_observability_m10r_instrumentation.json','configs/native_mechanism_observability_m10r_development.json',
        'tools/preserve_mechanism_observability_m10r.py','tools/report_mechanism_observability_m10r.py',
        'tools/archive_native_v13_run_evidence.py','tools/archive_mechanism_observability_m10r.py','tools/finalize_mechanism_observability_m10r_storage.py',
        'docs/NATIVE_MECHANISM_OBSERVABILITY_M10R_RESULTS.md','docs/NATIVE_MECHANISM_OBSERVABILITY_M10R_QUALIFICATION.md'}
    names|={str(p.relative_to(REPO)) for p in (REPO/'reports').glob('native-mechanism-observability-m10r-*') if p.is_file()}
    names={n for n in names if (REPO/n).is_file()}
    for name in sorted(names):
        target=root/'provenance'/name;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();shutil.copy2(REPO/name,target)
    for p in m.ROOT.glob('*.log'):shutil.copy2(p,root/p.name)
    gate=v.read(root/'mechanism_qualification_gate.json')
    binding={'scientific_registration_commit':REGISTRATION,'instrumentation_qualification_commit':'bebd85eae29ee64446d9ce3ee9d16baa990f8110','last_opened_stage':stage,'gate_is_acquisition_only':True,
        'gate_sha256':v.sha(root/'mechanism_qualification_gate.json'),'acquisition_qualified':gate['passed'],
        'native_common_support_established':False,'old_closed_panels':m.old_closed(),
        'source_files':{n:v.sha(root/'provenance'/n) for n in sorted(names)},
        'actions':False,'controller_fitted':False,'receiver_outcomes_read':False,'evidence_deleted':0}
    if (root/'mechanism_analysis.json').exists():binding.update(analysis_sha256=v.sha(root/'mechanism_analysis.json'),
        records_sha256=v.sha(root/'mechanism_records.json'),positive_future_stability_labels_nested=v.read(root/'mechanism_analysis.json')['positive_future_stationarity_labels_nested'])
    v.write(root/'archive_bindings.json',binding)
    return {'archive_root':str(root),'files':sum(p.is_file() for p in root.rglob('*')),'source_snapshots':len(names),'opened_stages':opened}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['audit','preserve']);a=p.parse_args();print(json.dumps(globals()[a.command]()))
