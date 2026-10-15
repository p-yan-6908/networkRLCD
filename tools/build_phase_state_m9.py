"""Derive the M9 support collector without changing the qualified M8 recorder."""
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
DEST=REPO/'benchmarks/native_m9/phase_state_episode_m9.mjs'

def build():
    name='benchmarks/native_m8/bwe_transients_episode_m8.mjs'
    source=REPO/name
    assert hashlib.sha256(source.read_bytes()).hexdigest()==json.loads((REPO/'configs/native_bwe_transients_m8.json').read_text())['source_hashes'][name]
    text=source.read_text()
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,old
        text=text.replace(old,new)
    text=text.replace('system_id_support_m8.mjs','phase_state_support_m9.mjs').replace('../native_m8/','../native_m9/').replace('runStepPlateausM8','observePhaseStateM9')
    replace('ms!==[10000,96000,12600][i]','ms!==[10000,88000,12600][i]')
    replace("if(!['[0.5,1.5,0.5,1.5]','[1.5,1.5,0.5,1.5]'].includes(JSON.stringify(episode.system_id_sequence_mbps))||episode.video_segment[1]!==130000)throw Error('unregistered M8 sequence/source segment');",
            "if(episode.system_id_sequence_mbps.length!==2||![0,0.5,1,1.5].some(x=>episode.system_id_sequence_mbps[1]===0.5*2**x&&episode.system_id_sequence_mbps[0]===(x<1?1.5:0.5))||episode.video_segment[1]!==130000)throw Error('unregistered M9 sequence/source segment');")
    replace('body.sequence>3','body.sequence>1')
    replace('conditioningSequence!==3','conditioningSequence!==1')
    text=text.replace('M8','M9')
    if DEST.exists():assert DEST.read_text()==text,'preserve existing M9'
    else:DEST.parent.mkdir(parents=True,exist_ok=True);DEST.write_text(text)
    return {'collector':str(DEST.relative_to(REPO)),'qualified_parent_preserved':True}

if __name__=='__main__':print(json.dumps(build()))
