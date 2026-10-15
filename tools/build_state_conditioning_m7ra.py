"""Preserve M7R; create a fresh registration with the exact existing recorder path."""
import ast
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
ANCHOR='dd2c17de8e07836f42c06170d50323a14250974d'


def build():
    parent=json.loads((REPO/'configs/native_state_conditioning_m7r.json').read_text())
    source='tools/measure_state_conditioning_m7r.py'
    assert hashlib.sha256((REPO/source).read_bytes()).hexdigest()==parent['sources_sha256'][source]
    text=(REPO/source).read_text()
    old_ast=ast.parse(text)
    old_sources=next(ast.literal_eval(n.value) for n in old_ast.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCES' for t in n.targets))
    text=text.replace('native-state-conditioning-m7r','native-state-conditioning-m7ra').replace('state_conditioning_m7r','state_conditioning_m7ra').replace('data/native-m7r/','data/native-m7ra/')
    old="RECORDER = REPO/'benchmarks/native_m7r/state_conditioning_episode_m7.mjs'"
    new="RECORDER = REPO/'benchmarks/native_m7r/state_conditioning_episode_m7r.mjs'"
    assert text.count(old)==1
    text=text.replace(old,new).replace('M7R','M7RA').replace('SEED = 20261125','SEED = 20261127')
    text=text.replace('85fd656a39cd7deb9582fdc3bac953beecd78cc0',ANCHOR).replace("f'm7r-","f'm7ra-").replace("networkrlcd-state-conditioning-m7r'","networkrlcd-state-conditioning-m7ra'")
    begin=text.index('SOURCES = ');end=text.index('\nDESIGN = ',begin)
    sources=old_sources+['tools/build_state_conditioning_m7ra.py','tools/measure_state_conditioning_m7ra.py',
        'docs/NATIVE_STATE_CONDITIONING_M7RA_PLAN.md','data/native-m7ra/prior-freeze-sha256.json']
    text=text[:begin]+'SOURCES = '+repr(sources)+text[end:]
    text=text.replace('def verify():\n', "def verify():\n    assert RECORDER.is_file(), 'registered recorder path must exist before launch'\n    assert v.sha(RECORDER)==inventory()[str(RECORDER.relative_to(REPO))]\n")
    def design(tree):
        return ast.dump(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DESIGN' for t in n.targets)))
    assert design(old_ast)==design(ast.parse(text))
    path=REPO/'tools/measure_state_conditioning_m7ra.py'
    if path.exists():assert path.read_text()==text
    else:path.write_text(text)
    recorder=REPO/'benchmarks/native_m7r/state_conditioning_episode_m7r.mjs'
    assert recorder.is_file() and hashlib.sha256(recorder.read_bytes()).hexdigest()==parent['sources_sha256'][str(recorder.relative_to(REPO))]
    return {'collector_path_verified':str(recorder),'numeric_design_unchanged':True,'new_parent':ANCHOR}


if __name__=='__main__':
    print(json.dumps(build()))
