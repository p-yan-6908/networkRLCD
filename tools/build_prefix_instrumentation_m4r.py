"""Generate M4R from immutable M4: wait for actual selected-pair readiness."""
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
text = (repo / "benchmarks/native_m4/prefix_instrumentation_episode_m4.mjs").read_text()
old = """ const selectedA=await selectedPair(a),selectedB=await selectedPair(b);
 const transportEvidence={abi:'native_action_turn_tcp_v2_transport_v1',turn_url:nativeConfig.turn_url,
  policy:'relay',candidate_evidence:iceEvidence,selected_a:selectedA,selected_b:selectedB,
  connection_a:a.connectionState,connection_b:b.connectionState};
 await fetch('/transport-evidence',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(transportEvidence)});
 const selectedOk=pair=>['relay','prflx'].includes(pair?.local?.candidateType)&&pair.local.relayProtocol==='tcp'&&pair.local.address==='127.0.0.1'&&pair.remote?.candidateType==='relay'&&pair.remote.address==='127.0.0.1'&&pair.pair?.state==='succeeded'&&pair.pair.nominated===true&&pair.pair.bytesSent>0&&pair.pair.bytesReceived>0;
 if(!selectedOk(selectedA)||!selectedOk(selectedB))throw Error('selected ICE pairs lacked nominated loopback TURN/TCP relay evidence');"""
new = """ const selectedOk=pair=>['relay','prflx'].includes(pair?.local?.candidateType)&&pair.local.relayProtocol==='tcp'&&pair.local.address==='127.0.0.1'&&pair.remote?.candidateType==='relay'&&pair.remote.address==='127.0.0.1'&&pair.pair?.state==='succeeded'&&pair.pair.nominated===true&&pair.pair.bytesSent>0&&pair.pair.bytesReceived>0;
 const readinessStart=performance.now();let selectedA,selectedB,readinessProbes=0;
 do{[selectedA,selectedB]=await Promise.all([selectedPair(a),selectedPair(b)]);readinessProbes++;await fetch('/transport-readiness',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({probe:readinessProbes,browser_ms:performance.now(),elapsed_ms:performance.now()-readinessStart,selected_a:selectedA,selected_b:selectedB,passed:selectedOk(selectedA)&&selectedOk(selectedB)})});if(selectedOk(selectedA)&&selectedOk(selectedB))break;await sleep(25);}while(performance.now()-readinessStart<2000);
 supportStartup.transport_readiness_wait_ms=performance.now()-readinessStart;supportStartup.transport_readiness_probes=readinessProbes;
 const transportEvidence={abi:'native_action_turn_tcp_v2_transport_v1',turn_url:nativeConfig.turn_url,
  policy:'relay',candidate_evidence:iceEvidence,selected_a:selectedA,selected_b:selectedB,
  connection_a:a.connectionState,connection_b:b.connectionState};
 await fetch('/transport-evidence',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(transportEvidence)});
 if(!selectedOk(selectedA)||!selectedOk(selectedB)||supportStartup.transport_readiness_wait_ms>2000)throw Error('unchanged selected-pair readiness did not qualify within 2000 ms; no reconnect or retry');"""
assert text.count(old) == 1
text = text.replace(old, new)
old = " else if(req.url==='/startup-sample')"
new = " else if(req.url==='/transport-readiness'){const body=await readBody(req);await appendFile(root+'/transport_readiness.jsonl',JSON.stringify(body)+'\\n');await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'transport_readiness',...body})+'\\n');res.end('{}');}\n else if(req.url==='/startup-sample')"
assert text.count(old) == 1
text = text.replace(old, new).replace("// M4 startup/clock qualification", "// M4R startup/clock qualification").replace("instrumentation_m4", "instrumentation_m4r")
target = repo / "benchmarks/native_m4r/prefix_instrumentation_episode_m4r.mjs"
target.parent.mkdir(exist_ok=True)
target.write_text(text)
print(target)
