"""M7R: exact M7 scientific rules with a monotonic not-before timer guard."""
import argparse
import ast
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]


def put(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():assert path.read_text()==text, 'preserve existing M7R source'
    else:path.write_text(text)


def build(anchor):
    assert len(anchor)==40 and all(c in '0123456789abcdef' for c in anchor)
    parent=json.loads((REPO/'configs/native_state_conditioning_m7.json').read_text())
    import hashlib
    for name in ('tools/measure_state_conditioning_m7.py','benchmarks/native_m7/state_conditioning_episode_m7.mjs','benchmarks/native_m7/state_conditioning_support_m7.mjs'):
        assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==parent['sources_sha256'][name]
    module=(REPO/'benchmarks/native_m7/state_conditioning_support_m7.mjs').read_text()
    old='const until=async elapsed=>{const remaining=start+elapsed-performance.now();if(remaining>0)await sleep(remaining);};'
    new='const until=async elapsed=>{const deadline=start+elapsed;while(performance.now()<deadline)await sleep(Math.max(1,deadline-performance.now()));};'
    assert module.count(old)==1
    module=module.replace(old,new).replace('M7','M7R')
    put(REPO/'benchmarks/native_m7r/state_conditioning_support_m7r.mjs',module)
    recorder=(REPO/'benchmarks/native_m7/state_conditioning_episode_m7.mjs').read_text()
    recorder=recorder.replace('native_m7/','native_m7r/').replace('state_conditioning_support_m7.mjs','state_conditioning_support_m7r.mjs').replace('M7','M7R')
    put(REPO/'benchmarks/native_m7r/state_conditioning_episode_m7r.mjs',recorder)
    text=(REPO/'tools/measure_state_conditioning_m7.py').read_text()
    # Rename identities and pin a new parent; all numeric design/gate logic is copied.
    text=text.replace('state_conditioning_m7','state_conditioning_m7r').replace('native-state-conditioning-m7','native-state-conditioning-m7r').replace('native_m7/','native_m7r/').replace('data/native-m7/','data/native-m7r/').replace('M7','M7R')
    text=text.replace('SEED = 20261123','SEED = 20261125').replace('6dc05b56ee4d1a657e2514ffc2a7d1d68dc49454',anchor).replace('6dc05b5',anchor)
    text=text.replace("pair = f'm7-", "pair = f'm7r-").replace('networkrlcd-state-conditioning-m7\'', 'networkrlcd-state-conditioning-m7r\'')
    text=text.replace("ASSETS = REPO/'data/native-m7r/sources.json'", "ASSETS = REPO/'data/native-m7/sources.json'")
    begin=text.index('SOURCES = ');end=text.index('\nDESIGN = ',begin)
    original=ast.parse((REPO/'tools/measure_state_conditioning_m7.py').read_text())
    old_sources=next(ast.literal_eval(n.value) for n in original.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCES' for t in n.targets))
    sources=old_sources+['tools/build_state_conditioning_m7r.py','tools/measure_state_conditioning_m7r.py',
        'benchmarks/native_m7r/state_conditioning_episode_m7r.mjs','benchmarks/native_m7r/state_conditioning_support_m7r.mjs',
        'data/native-m7r/prior-freeze-sha256.json','docs/NATIVE_STATE_CONDITIONING_M7R_PLAN.md']
    text=text[:begin]+'SOURCES = '+repr(sources)+text[end:]
    put(REPO/'tools/measure_state_conditioning_m7r.py',text)
    return {'parent_result_commit':anchor,'numeric_scientific_rules_unchanged':True,'repair':'monotonic browser deadline rechecked after timer return'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--anchor',required=True)
    print(json.dumps(build(parser.parse_args().anchor)))
