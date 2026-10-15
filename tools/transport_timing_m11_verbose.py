"""The one source-qualified, preregistered M11 verbose diagnostic fallback."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import os
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m11_fallback',REPO/'tools/measure_transport_timing_m11.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v
ROOT=m.ROOT/'verbose';CONFIG=REPO/'configs/native_transport_timing_m11_verbose.json'
SOURCES=['tools/transport_timing_m11_verbose.py','docs/NATIVE_TRANSPORT_TIMING_M11_VERBOSE_PLAN.md']

def prepare():
    m.verify();assert not ROOT.exists() and not CONFIG.exists()
    qualification=v.read(m.ROOT/'capability/transport_channel_qualification.json')
    assert not qualification['passed'],'fallback only for failed primary diagnostics'
    original=v.read(m.CONFIG);trial=copy.deepcopy(original['trials'][0]);panel=v.read(m.ROOT/'capability'/trial['panel'])
    tid='m11-timing-v-000-support';pair='m11-verbose-only'
    trial.update(id=tid,pair_id=pair,panel='panels/'+tid+'.json')
    episode=panel['episodes'][0];episode.update(id=tid,m11_verbose_diagnostic=True)
    episode['support_config']['pair_id']=pair
    panel['measurement_recipe']['scientific_role']='M11 one bounded verbose capability fallback; no scientific effect comparison'
    v.write(ROOT/trial['panel'],panel);trial['panel_sha256']=v.sha(ROOT/trial['panel'])
    protocol=copy.deepcopy(original);protocol.update(stage='verbose',trials=[trial],randomized_order=[tid],
        bounded_fallback=True,bounded_fallback_source_hashes={name:v.sha(REPO/name) for name in SOURCES},
        primary_channel_gate_sha256=v.sha(m.ROOT/'capability/transport_channel_qualification.json'))
    protocol['storage']['raw_capture_root']=str(ROOT);v.seal(ROOT,protocol);v.write(CONFIG,protocol)
    return {'prepared':True,'originals':1,'primary_panel_closed':True,'development_opened':False}

def capture():
    m.verify();protocol=v.read(CONFIG)
    assert v.sha(ROOT/'protocol.json')==v.sha(CONFIG)==(ROOT/'protocol.sha256').read_text().split()[0]
    for name,checksum in protocol['bounded_fallback_source_hashes'].items():
        assert v.sha(REPO/name)==checksum and subprocess.check_output(['git','show','HEAD:'+name],cwd=REPO)==(REPO/name).read_bytes()
    assert subprocess.check_output(['git','show','HEAD:'+str(CONFIG.relative_to(REPO))],cwd=REPO)==CONFIG.read_bytes()
    current,_=v.frozen.base.runtime_provenance(Path(protocol['preflight_reference']['path']));assert current==protocol['runtime']
    v.frozen.v2.set_runtime_env(protocol);v.core.verify_sources(protocol);trial=protocol['trials'][0]
    assert v.sha(ROOT/trial['panel'])==trial['panel_sha256'];(ROOT/'sessions').mkdir(exist_ok=False);d=ROOT/'sessions'/trial['id']
    try:
        proc=subprocess.run(['node',str(m.RECORDER),str(d),str(ROOT/trial['panel']),trial['id'],trial['condition']],cwd=REPO,
            env=os.environ.copy(),capture_output=True,text=True,timeout=180)
        status='sealed' if proc.returncode==0 else 'failed';stdout,stderr=proc.stdout,proc.stderr;error=None if proc.returncode==0 else f'exit code{proc.returncode}'
    except subprocess.TimeoutExpired as exc:
        status,error='failed','bounded180s timeout';stdout,stderr=exc.stdout or '',exc.stderr or ''
        if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
        if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
    d.mkdir(exist_ok=True);(d/'capture_stdout.log').write_text(stdout);(d/'capture_stderr.log').write_text(stderr)
    seal=v.core.seal_directory(d,'native_action_session' if status=='sealed' else 'native_action_session_failed')
    v.write(ROOT/'capture_index.json',{'abi':'native_clock_action_capture_index_v1','protocol_sha256':v.sha(ROOT/'protocol.json'),
        'sessions':[{'trial':trial['id'],'status':status,'error':error,'integrity_manifest_sha256':v.sha(d/'integrity.json'),'file_count':seal['file_count']}]})
    return gate()

def gate():
    m.verify();p,index=v.core.check_capture_integrity(ROOT);trial=p['trials'][0];row=m.parent.parent.session_gate(ROOT,trial,index['sessions'][0],p)
    if row['passed']:
        row['mechanism']=m.parent.mechanism_gate(ROOT/'sessions'/trial['id'],row);row['passed'] &= row['mechanism']['passed']
    result={'abi':'native_transport_timing_m11_verbose_acquisition_v1','protocol_sha256':v.sha(ROOT/'protocol.json'),
        'capture_index_sha256':v.sha(ROOT/'capture_index.json'),'planned_sessions':1,'qualified_sessions':int(row['passed']),
        'passed':row['passed'],'sessions':[row],'gate_is_acquisition_only':True,'receiver_outcomes_read':False}
    v.write(ROOT/'support_clock_transport_gate.json',result);v.write(REPO/'reports/native-transport-timing-m11-verbose-acquisition.json',result)
    return {'original':trial['id'],'capture_status':index['sessions'][0]['status'],'technical_passed':row['passed']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','capture','gate']);a=p.parse_args();print(json.dumps(globals()[a.command]()))
