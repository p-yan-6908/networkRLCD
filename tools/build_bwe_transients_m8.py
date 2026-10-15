"""Derive M8 collector from the frozen qualified M7RA recorder without editing it."""
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
DEST=REPO/'benchmarks/native_m8/bwe_transients_episode_m8.mjs'


def build():
    name='benchmarks/native_m7r/state_conditioning_episode_m7r.mjs'
    text=(REPO/name).read_text()
    assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==json.loads((REPO/'configs/native_state_conditioning_m7ra.json').read_text())['sources_sha256'][name]
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,old[:100]
        text=text.replace(old,new)
    text=text.replace('state_conditioning_support_m7r.mjs','system_id_support_m8.mjs').replace('../native_m7r/','../native_m8/').replace('conditionServiceM7R','runStepPlateausM8')
    replace('ms!==[10000,32000,12600][i]','ms!==[10000,96000,12600][i]')
    replace("if(![0,0.5,1,1.5].includes(episode.conditioning_target_x)||episode.video_segment[1]!==60000)throw Error('unregistered M7R target/source segment');", "if(!['[0.5,1.5,0.5,1.5]','[1.5,1.5,0.5,1.5]'].includes(JSON.stringify(episode.system_id_sequence_mbps))||episode.video_segment[1]!==130000)throw Error('unregistered M8 sequence/source segment');")
    replace("await runStepPlateausM8(decisions,phaseStart,nativeConfig.conditioning_target_x)","await runStepPlateausM8(phaseStart,nativeConfig.system_id_sequence_mbps,clockBracket)")
    replace('conditioning_target_x:episode.conditioning_target_x','system_id_sequence_mbps:episode.system_id_sequence_mbps')
    begin=text.index(" else if(req.url==='/condition-service'){");end=text.index(" else if(req.url==='/ledger'){",begin)
    text=text[:begin]+""" else if(req.url==='/system-service'){
  const body=await readBody(req),now=performance.now();
  if(currentServicePhase!=='block_1'||conditioningRelease||body.sequence!==conditioningSequence+1||body.sequence>3||body.requested_mbps!==episode.system_id_sequence_mbps[body.sequence]||Math.abs(body.previous_mbps-capacity)>1e-12)throw Error('invalid M8 service intervention');
  for(const l of links)pumpLink(l,now);const previous_mbps=capacity;capacity=body.requested_mbps;conditioningSequence=body.sequence;
  const readback={sequence:body.sequence,capacity_mbps:capacity,previous_mbps,node_applied_ms:now};events.push({kind:'system_id_service',at_ms:now,...readback,browser_request_ms:body.browser_request_ms});
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(readback));
 }
 else if(req.url==='/system-service-browser'){const body=await readBody(req);conditioningBrowser.push(body);await appendFile(root+'/system_id_stream.jsonl',JSON.stringify({kind:'browser',...body})+'\\n');res.end('{}');}
 else if(req.url==='/system-id-complete'){const body=await readBody(req);if(currentServicePhase!=='block_1'||conditioningRelease||conditioningSequence!==3||JSON.stringify(body.service_sequence_mbps)!==JSON.stringify(episode.system_id_sequence_mbps))throw Error('invalid M8 completion');conditioningRelease=body;await appendFile(root+'/system_id_stream.jsonl',JSON.stringify({kind:'completion',...body,node_persist_ms:performance.now()})+'\\n');res.end('{}');}
"""+text[end:]
    text=text.replace("'conditioning_initial'","'system_id_initial'")
    replace("'conditioning_evidence.json'","'system_id_evidence.json'")
    replace('{initial:conditioningInitial,commands:conditioningBrowser,release:conditioningRelease}', '{initial:conditioningInitial,commands:conditioningBrowser,completion:conditioningRelease}')
    replace('synthetic feedback conditioning','synthetic fixed step/plateau service')
    text=text.replace('M7R','M8')
    if DEST.exists():assert DEST.read_text()==text,'preserve existing M8 source'
    else:DEST.parent.mkdir(parents=True,exist_ok=True);DEST.write_text(text)
    return {'collector':str(DEST.relative_to(REPO)),'frozen_parent_unchanged':True}


if __name__=='__main__':print(json.dumps(build()))
