// Verify relay-only TURN/TCP media through the same owned UDP queue used by the action capture.
// The managed Chromium policy is read and fingerprinted, never modified.
import {createServer as httpServer} from 'node:http';
import {createServer as tcpServer,createConnection} from 'node:net';
import {createSocket} from 'node:dgram';
import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,readFile,rm,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {randomBytes,createHash} from 'node:crypto';

const output=process.argv[2],binary=process.env.RLCD_TURN_BINARY;
if(!output||!binary)throw Error('fresh output file and RLCD_TURN_BINARY are required');
const policyPath='/etc/chromium/policies/managed/misc.json';
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const outputPath=path.resolve(output);
await mkdir(path.dirname(outputPath),{recursive:true});
const beforePolicy=await readFile(policyPath);
const policyBefore=JSON.parse(beforePolicy).WebRtcIPHandling;
const binarySha256=hash(await readFile(binary));
const versionRun=spawnSync(binary,['--version'],{encoding:'utf8'});
if(versionRun.status!==0)throw Error('TURN binary version check failed: '+versionRun.stderr);
const libraryDir=process.env.RLCD_TURN_LIBRARY_DIR||path.dirname(binary);
const libraryNames=['libevent_extra-2.1.so.7','libevent_openssl-2.1.so.7','libhiredis.so.1.1.0'];
const libraryHashes={};
for(const name of libraryNames){try{libraryHashes[name]=hash(await readFile(path.join(libraryDir,name)));}catch{libraryHashes[name]=null;}}
const sourceSha256=hash(await readFile(import.meta.filename));
const work=await mkdtemp(path.join(tmpdir(),'n2'));
const profile=path.join(work,'c');
let turn,chrome,ws,site,relaySockets=[];
let chromeError='',relayState=null;

async function reserveTurnPort(){
 for(let attempt=0;attempt<20;attempt++){
  const server=tcpServer();
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const port=server.address().port;
  await new Promise(resolve=>server.close(resolve));
  if(port<49160||port>49260)return port;
 }
 throw Error('could not reserve a TURN control port outside the relay range');
}
async function waitForTcp(port,processRef){
 for(let attempt=0;attempt<100;attempt++){
  if(processRef.exitCode!==null)throw Error('TURN server exited before listening');
  const connected=await new Promise(resolve=>{
   const socket=createConnection({host:'127.0.0.1',port});
   socket.once('connect',()=>{socket.destroy();resolve(true);});
   socket.once('error',()=>{socket.destroy();resolve(false);});
  });
  if(connected)return;
  await wait(50);
 }
 throw Error('TURN/TCP listener did not become ready');
}
function stop(processRef){
 return new Promise(resolve=>{
  if(!processRef||processRef.exitCode!==null)return resolve();
  const timer=setTimeout(()=>{processRef.kill('SIGKILL');resolve();},3000);
  processRef.once('exit',()=>{clearTimeout(timer);resolve();});
  processRef.kill('SIGTERM');
 });
}
const serverConfig={
 capacity_mbps:10,one_way_delay_ms:10,queue_limit_wire_bytes:30000,
 max_packets_per_direction:100
};
const turnPort=await reserveTurnPort();
const username='queue-preflight-'+randomBytes(8).toString('hex');
const credential=randomBytes(24).toString('hex');
const turnUrl='turn:127.0.0.1:'+turnPort+'?transport=tcp';
const turnConfig=path.join(work,'turn.conf');
const turnLog=path.join(work,'turn.log');
await writeFile(turnConfig,[
 'listening-port='+turnPort,'listening-ip=127.0.0.1','relay-ip=127.0.0.1',
 'realm=networkrlcd.local','lt-cred-mech','user='+username+':'+credential,
 'fingerprint','no-tls','no-dtls','no-udp','no-tcp-relay','no-cli','no-daemon',
 'relay-threads=1','min-port=49160','max-port=49260','allow-loopback-peers',
 'denied-peer-ip=0.0.0.0-255.255.255.255','allowed-peer-ip=127.0.0.1',
 'pidfile='+path.join(work,'turn.pid'),'log-file='+turnLog
 ].join('\n')+'\n',{mode:0o600});

const result={
 abi:'native_turn_tcp_owned_queue_media_preflight_v1',passed:false,policy_modified:false,
 managed_policy:{path:policyPath,WebRtcIPHandling_before:policyBefore,sha256_before:hash(beforePolicy)},
 turn:{version:(versionRun.stdout||versionRun.stderr).trim(),binary_sha256:binarySha256,
  control_transport:'TCP',relay_transport:'UDP',turn_url:turnUrl,
  library_dir:libraryDir,library_sha256:libraryHashes,
  server_config:{listen_ip:'127.0.0.1',relay_ip:'127.0.0.1',relay_port_range:[49160,49260],
   loopback_peers_only:true,browser_udp_listener_disabled:true,tcp_relay_disabled:true}},
 browser:{binary:'/usr/bin/chromium'},source_sha256:sourceSha256,
 queue_config:serverConfig,ice:{transport_policy:'relay',peer_a_candidates:[],
  peer_b_candidates:[],peer_a_candidate_errors:[],peer_b_candidate_errors:[]},
 connection:{peer_a_state:null,peer_b_state:null,peer_a_selected_pair:null,peer_b_selected_pair:null},
 media:{peer_a_to_peer_b:null,peer_b_to_peer_a:null},
 evaluated_action_or_qoe:false
};
const readBody=async req=>{let text='';for await(const data of req)text+=data;return JSON.parse(text);};
function ledger(){
 if(!relayState)return null;
 const now=performance.now();
 for(const link of relayState.links)pumpLink(link,now);
 const view=link=>({
  offered_wire_bytes:link.offered,dropped_wire_bytes:link.dropped,
  served_wire_bytes:link.served,queued_wire_bytes:link.queued,
  forwarded_wire_bytes:link.forwardedWire,forwarded_packets:link.forwarded,
  overflow_packets:link.drops,send_errors:link.errors,unexpected_sources:link.unexpected,
  max_queue_wire_bytes:link.maxQueue,capacity_integral_wire_bytes:link.capacityBytes,
  capacity_integral_upper_bound_ok:link.served<=link.capacityBytes+1e-5,
  conservation_error_bytes:link.offered-link.dropped-link.served-link.queued
 });
 return {capacity_mbps:serverConfig.capacity_mbps,one_way_delay_ms:serverConfig.one_way_delay_ms,
  a_to_b:view(relayState.links[0]),b_to_a:view(relayState.links[1])};
}
function pumpLink(link,now){
 const before=link.queued,oldServed=link.served;
 let budget=(now-link.last)*serverConfig.capacity_mbps*125;
 link.capacityBytes+=budget;link.last=now;
 while(budget>1e-9&&link.queue.length){
  const packet=link.queue[0],used=Math.min(packet.remaining,budget);
  packet.remaining-=used;link.queued-=used;link.served+=used;budget-=used;
  if(packet.remaining<1e-9){
   link.queue.shift();const due=now+serverConfig.one_way_delay_ms;
   const forward=()=>{
    if(relayState?.stopped)return;
    const remaining=due-performance.now();
    if(remaining>0){setTimeout(forward,Math.max(1,remaining));return;}
    link.events.push({kind:'forward',direction:link.direction,at_ms:performance.now(),wire_bytes:packet.wire});
    link.sender.send(packet.data,link.destination.port,link.destination.address,error=>{
     if(error)link.errors++;else{link.forwarded++;link.forwardedWire+=packet.wire;}
    });
   };
   setTimeout(forward,serverConfig.one_way_delay_ms);
  }
 }
 if(!link.queue.length)link.queued=0;
 link.events.push({kind:'service',direction:link.direction,from_ms:link.previous,at_ms:now,
  capacity_mbps:serverConfig.capacity_mbps,budget_wire_bytes:(now-link.previous)*serverConfig.capacity_mbps*125,
  service_wire_bytes:link.served-oldServed,queue_before_wire_bytes:before,queue_after_wire_bytes:link.queued});
 link.previous=now;
}
async function startRelay(a,b){
 if(!Number.isInteger(a.port)||!Number.isInteger(b.port))throw Error('TURN relay allocation ports are required');
 const pa=createSocket('udp4'),pb=createSocket('udp4');relaySockets=[pa,pb];
 await Promise.all(relaySockets.map(socket=>new Promise((resolve,reject)=>{
  socket.once('error',reject);socket.bind(0,'127.0.0.1',resolve);
 })));
 const make=(sender,destination,expectedPort,direction)=>({
  sender,destination,expectedPort,direction,last:performance.now(),previous:performance.now(),
  queue:[],queued:0,offered:0,dropped:0,served:0,capacityBytes:0,forwardedWire:0,
  forwarded:0,drops:0,errors:0,unexpected:0,maxQueue:0,events:[]
 });
 const ab=make(pa,{address:'127.0.0.1',port:b.port},a.port,'a_to_b');
 const ba=make(pb,{address:'127.0.0.1',port:a.port},b.port,'b_to_a');
 relayState={links:[ab,ba],stopped:false};
 const receive=(link,message,from)=>{
  if(from.address!=='127.0.0.1'||from.port!==link.expectedPort){link.unexpected++;return;}
  const now=performance.now();pumpLink(link,now);const wire=message.length+28,before=link.queued;
  const drop=before+wire>serverConfig.queue_limit_wire_bytes;link.offered+=wire;
  if(drop){link.dropped+=wire;link.drops++;}
  else{link.queue.push({data:Buffer.from(message),wire,remaining:wire});link.queued+=wire;link.maxQueue=Math.max(link.maxQueue,link.queued);}
  link.events.push({kind:'offer',direction:link.direction,at_ms:now,payload_bytes:message.length,
   wire_bytes:wire,dropped:drop,queue_before_wire_bytes:before,queue_after_wire_bytes:link.queued});
 };
 pb.on('message',(message,from)=>receive(ab,message,from));
 pa.on('message',(message,from)=>receive(ba,message,from));
 relayState.tick=setInterval(()=>{const now=performance.now();for(const link of relayState.links)pumpLink(link,now);},1);
 return {a_proxy_port:pa.address().port,b_proxy_port:pb.address().port};
}
site=httpServer(async(req,res)=>{
 try{
  if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><meta charset="utf-8"><body></body>');}
  else if(req.url==='/relay'){
   const data=await readBody(req);const proxies=await startRelay(data.a,data.b);
   res.setHeader('Content-Type','application/json');res.end(JSON.stringify(proxies));
  }else if(req.url==='/ledger'){
   res.setHeader('Content-Type','application/json');res.end(JSON.stringify(ledger()));
  }else{res.statusCode=404;res.end('not found');}
 }catch(error){res.statusCode=400;res.end(JSON.stringify({error:String(error)}));}
});

try{
 if(policyBefore!=='disable_non_proxied_udp')throw Error('managed Chromium policy differs from the registered transport condition');
 turn=spawn(binary,['-c',turnConfig],{stdio:['ignore','ignore','ignore']});
 await waitForTcp(turnPort,turn);
 await new Promise((resolve,reject)=>{site.once('error',reject);site.listen(0,'127.0.0.1',resolve);});
 const origin='http://127.0.0.1:'+site.address().port;
 chrome=spawn('/usr/bin/chromium',[
  '--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
  '--user-data-dir='+profile,'--no-first-run','--no-default-browser-check',
  '--disable-background-networking','--disable-component-update','--disable-sync',
  '--metrics-recording-only','--autoplay-policy=no-user-gesture-required','about:blank'
 ],{stdio:['ignore','ignore','pipe']});
 chrome.stderr.on('data',data=>{chromeError=(chromeError+data).slice(-5000);});
 let port;
 for(let attempt=0;attempt<120;attempt++){
  try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}
  catch{if(chrome.exitCode!==null)throw Error('Chromium exited before DevTools was ready: '+chromeError);await wait(100);}
 }
 if(!port)throw Error('Chromium DevTools unavailable: '+chromeError);
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(origin),{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP connection timed out')),10000);ws.onopen=()=>{clearTimeout(timer);resolve();};ws.onerror=error=>{clearTimeout(timer);reject(error);};});
 let next=0;const pending=new Map();
 ws.onmessage=event=>{const message=JSON.parse(event.data);if(pending.has(message.id)){const item=pending.get(message.id);clearTimeout(item.timer);pending.delete(message.id);message.error?item.reject(Error(JSON.stringify(message.error))):item.resolve(message.result);}};
 ws.onclose=()=>{for(const item of pending.values()){clearTimeout(item.timer);item.reject(Error('CDP disconnected'));}pending.clear();};
 const call=(method,params={},timeoutMs=20000)=>new Promise((resolve,reject)=>{
  const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timed out: '+method));},timeoutMs);
  pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));
 });
 const iceServer={urls:turnUrl,username,credential};
 const expression=[
  '(async()=>{',
  'const iceServer='+JSON.stringify(iceServer)+';',
  'const config={iceTransportPolicy:"relay",iceServers:[iceServer]};',
  'const errorsA=[],errorsB=[],candidatesA=[],candidatesB=[];',
  'const makeSource=seed=>{const canvas=document.createElement("canvas");canvas.width=320;canvas.height=180;const ctx=canvas.getContext("2d");let n=0;const draw=()=>{n++;ctx.fillStyle="rgb("+((n*17+seed)%255)+","+((n*37+seed)%255)+","+((n*59+seed)%255)+")";ctx.fillRect(0,0,320,180);ctx.fillStyle="white";ctx.font="20px monospace";ctx.fillText("TURN queue "+seed+" "+n,8,30);};draw();const timer=setInterval(draw,1000/30);return {canvas,stream:canvas.captureStream(30),stop:()=>clearInterval(timer)};};',
  'const sourceA=makeSource(31),sourceB=makeSource(97),pcA=new RTCPeerConnection(config),pcB=new RTCPeerConnection(config);',
  'const videoA=document.createElement("video"),videoB=document.createElement("video");for(const video of [videoA,videoB]){video.autoplay=true;video.muted=true;video.playsInline=true;video.width=320;video.height=180;document.body.append(video);}',
  'pcA.addTrack(sourceA.stream.getVideoTracks()[0],sourceA.stream);pcB.addTrack(sourceB.stream.getVideoTracks()[0],sourceB.stream);',
  'pcA.ontrack=event=>{videoA.srcObject=event.streams[0];videoA.play().catch(()=>{});};pcB.ontrack=event=>{videoB.srcObject=event.streams[0];videoB.play().catch(()=>{});};',
  'const recordCandidate=c=>({candidate:c.candidate,sdpMid:c.sdpMid,sdpMLineIndex:c.sdpMLineIndex,type:c.type,protocol:c.protocol,address:c.address,port:c.port,relayProtocol:c.relayProtocol,url:c.url});',
  'pcA.onicecandidate=event=>{if(event.candidate)candidatesA.push(recordCandidate(event.candidate));};pcB.onicecandidate=event=>{if(event.candidate)candidatesB.push(recordCandidate(event.candidate));};',
  'pcA.onicecandidateerror=event=>errorsA.push({code:event.errorCode,text:event.errorText,url:event.url});pcB.onicecandidateerror=event=>errorsB.push({code:event.errorCode,text:event.errorText,url:event.url});',
  'const gather=pc=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error("ICE gathering timed out")),20000);if(pc.iceGatheringState==="complete"){clearTimeout(timer);resolve();}else pc.addEventListener("icegatheringstatechange",()=>{if(pc.iceGatheringState==="complete"){clearTimeout(timer);resolve();}});});',
  'const strip=sdp=>sdp.split("\\r\\n").filter(line=>!line.startsWith("a=candidate:")&&line!=="a=end-of-candidates").join("\\r\\n");',
  'const onlyRelay=rows=>rows.length>0&&rows.every(row=>row.type==="relay"&&row.protocol==="udp"&&row.relayProtocol==="tcp"&&row.address==="127.0.0.1"&&row.url===iceServer.urls);',
  'const record=c=>({type:c.type,protocol:c.protocol,address:c.address,port:c.port,relayProtocol:c.relayProtocol,url:c.url,candidate:c.candidate});',
  'const rewrite=(c,port)=>{const words=c.candidate.split(" ");words[4]="127.0.0.1";words[5]=String(port);return {candidate:words.join(" "),sdpMid:c.sdpMid,sdpMLineIndex:c.sdpMLineIndex};};',
  'const candidateRowsA=candidatesA,candidateRowsB=candidatesB;',
  'const offer=await pcA.createOffer();await pcA.setLocalDescription(offer);await gather(pcA);',
  'await pcB.setRemoteDescription({type:"offer",sdp:strip(pcA.localDescription.sdp)});const answer=await pcB.createAnswer();await pcB.setLocalDescription(answer);await gather(pcB);',
  'await pcA.setRemoteDescription({type:"answer",sdp:strip(pcB.localDescription.sdp)});',
  'if(!onlyRelay(candidateRowsA)||!onlyRelay(candidateRowsB)||errorsA.length||errorsB.length)throw Error("relay-only TURN/TCP candidate qualification failed");',
  'const ca=candidatesA.find(c=>c.type==="relay"&&c.relayProtocol==="tcp"),cb=candidatesB.find(c=>c.type==="relay"&&c.relayProtocol==="tcp");',
  'const relayResponse=await fetch("/relay",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({a:{address:ca.address,port:ca.port},b:{address:cb.address,port:cb.port}})});const proxies=await relayResponse.json();if(!relayResponse.ok||proxies.error)throw Error("owned queue setup failed: "+JSON.stringify(proxies));',
  'await pcB.addIceCandidate(rewrite(ca,proxies.a_proxy_port));await pcA.addIceCandidate(rewrite(cb,proxies.b_proxy_port));',
  'const deadline=Date.now()+30000;while(Date.now()<deadline){if(pcA.connectionState==="connected"&&pcB.connectionState==="connected")break;if(["failed","closed"].includes(pcA.connectionState)||["failed","closed"].includes(pcB.connectionState))break;await new Promise(resolve=>setTimeout(resolve,100));}',
  'if(pcA.connectionState!=="connected"||pcB.connectionState!=="connected")throw Error("queue-backed TURN peers did not connect: "+pcA.connectionState+"/"+pcB.connectionState);',
  'const readStats=async pc=>{const rows=[...(await pc.getStats()).values()];const sum=(type)=>rows.filter(row=>row.type===type&&row.kind==="video").reduce((a,row)=>({bytes:a.bytes+(type==="outbound-rtp"?(row.bytesSent||0):(row.bytesReceived||0)),packets:a.packets+(type==="outbound-rtp"?(row.packetsSent||0):(row.packetsReceived||0)),frames:a.frames+(type==="outbound-rtp"?(row.framesEncoded||0):(row.framesDecoded||0))}),{bytes:0,packets:0,frames:0});const transport=rows.find(row=>row.type==="transport"&&row.selectedCandidatePairId),pair=rows.find(row=>row.id===transport?.selectedCandidatePairId)||rows.find(row=>row.type==="candidate-pair"&&row.nominated&&row.state==="succeeded"),local=rows.find(row=>row.id===pair?.localCandidateId),remote=rows.find(row=>row.id===pair?.remoteCandidateId);return {outbound:sum("outbound-rtp"),inbound:sum("inbound-rtp"),selected_pair:pair?{state:pair.state,nominated:pair.nominated,bytesSent:pair.bytesSent,bytesReceived:pair.bytesReceived}:null,local_candidate:local?{candidateType:local.candidateType,protocol:local.protocol,relayProtocol:local.relayProtocol,address:local.address}:null,remote_candidate:remote?{candidateType:remote.candidateType,protocol:remote.protocol,relayProtocol:remote.relayProtocol,address:remote.address,port:remote.port}:null};};',
  'let statsA,statsB;for(let i=0;i<100;i++){await new Promise(resolve=>setTimeout(resolve,200));statsA=await readStats(pcA);statsB=await readStats(pcB);if(statsA.outbound.frames>10&&statsA.inbound.frames>10&&statsB.outbound.frames>10&&statsB.inbound.frames>10)break;}',
  'const queue=await(await fetch("/ledger")).json();const result={gathering:{a_state:pcA.iceGatheringState,b_state:pcB.iceGatheringState,a_candidates:candidateRowsA.map(({candidate,...row})=>row),b_candidates:candidateRowsB.map(({candidate,...row})=>row),a_errors:errorsA,b_errors:errorsB},connection:{a_state:pcA.connectionState,b_state:pcB.connectionState,a_stats:statsA,b_stats:statsB,proxy_ports:proxies},queue:queue};',
  'sourceA.stop();sourceB.stop();for(const stream of [sourceA.stream,sourceB.stream])stream.getTracks().forEach(track=>track.stop());pcA.close();pcB.close();return result;',
  '})()'
 ].join('\n');
 const evaluated=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},90000);
 if(evaluated.exceptionDetails)throw Error(JSON.stringify(evaluated.exceptionDetails));
 const pageResult=evaluated.result.value;
 result.ice.peer_a_candidates=pageResult.gathering.a_candidates;
 result.ice.peer_b_candidates=pageResult.gathering.b_candidates;
 result.ice.peer_a_candidate_errors=pageResult.gathering.a_errors;
 result.ice.peer_b_candidate_errors=pageResult.gathering.b_errors;
 result.connection={peer_a_state:pageResult.connection.a_state,peer_b_state:pageResult.connection.b_state,
  peer_a_selected_pair:pageResult.connection.a_stats.selected_pair,peer_b_selected_pair:pageResult.connection.b_stats.selected_pair,
  peer_a_local_candidate:pageResult.connection.a_stats.local_candidate,peer_a_remote_candidate:pageResult.connection.a_stats.remote_candidate,
  peer_b_local_candidate:pageResult.connection.b_stats.local_candidate,peer_b_remote_candidate:pageResult.connection.b_stats.remote_candidate,
  proxy_ports:pageResult.connection.proxy_ports};
 result.media={peer_a_to_peer_b:{sender:pageResult.connection.a_stats.outbound,receiver:pageResult.connection.b_stats.inbound},
  peer_b_to_peer_a:{sender:pageResult.connection.b_stats.outbound,receiver:pageResult.connection.a_stats.inbound}};
 result.queue=pageResult.queue;
 result.browser.version=(await(await fetch('http://127.0.0.1:'+port+'/json/version')).json()).Browser;
 result.browser.sha256=hash(await readFile('/usr/bin/chromium'));
 const onlyRelay=rows=>rows.length>0&&rows.every(row=>row.type==='relay'&&row.relayProtocol==='tcp'&&row.protocol==='udp'&&row.address==='127.0.0.1'&&row.url===turnUrl);
 const selectedOk=pair=>pair?.state==='succeeded'&&pair.nominated===true&&pair.bytesSent>0&&pair.bytesReceived>0;
 const directionOk=direction=>direction?.sender?.bytes>0&&direction?.sender?.packets>10&&direction?.sender?.frames>10&&direction?.receiver?.bytes>0&&direction?.receiver?.packets>10&&direction?.receiver?.frames>10;
 const linkOk=link=>link?.forwarded_packets>=serverConfig.max_packets_per_direction&&link.unexpected_sources===0&&link.send_errors===0&&link.overflow_packets===0&&link.capacity_integral_upper_bound_ok===true&&Math.abs(link.conservation_error_bytes)<=1e-6;
 result.managed_policy.WebRtcIPHandling_after=JSON.parse((await readFile(policyPath)).toString()).WebRtcIPHandling;
 result.managed_policy.sha256_after=hash(await readFile(policyPath));
 result.managed_policy.unchanged=result.managed_policy.sha256_before===result.managed_policy.sha256_after;
 result.acceptance={both_gathering_complete:pageResult.gathering.a_state==='complete'&&pageResult.gathering.b_state==='complete',
  relay_only_turn_tcp_candidates_on_both_peers:onlyRelay(result.ice.peer_a_candidates)&&onlyRelay(result.ice.peer_b_candidates),
  no_ice_candidate_errors:result.ice.peer_a_candidate_errors.length===0&&result.ice.peer_b_candidate_errors.length===0,
  connected_with_nominated_pairs:pageResult.connection.a_state==='connected'&&pageResult.connection.b_state==='connected'&&selectedOk(result.connection.peer_a_selected_pair)&&selectedOk(result.connection.peer_b_selected_pair),
  bidirectional_media:directionOk(result.media.peer_a_to_peer_b)&&directionOk(result.media.peer_b_to_peer_a),
  bidirectional_owned_queue_forwarding:linkOk(result.queue.a_to_b)&&linkOk(result.queue.b_to_a),
  policy_unchanged:result.managed_policy.unchanged&&result.managed_policy.WebRtcIPHandling_after==='disable_non_proxied_udp'};
 result.passed=Object.values(result.acceptance).every(Boolean);
}catch(error){
 result.error={name:error?.name??'Error',message:String(error?.message??error),chrome_stderr_tail:chromeError.slice(-1500)};
}finally{
 ws?.close();await stop(chrome);await stop(turn);
 if(relayState){relayState.stopped=true;clearInterval(relayState.tick);}
 for(const socket of relaySockets)try{socket.close();}catch{}
 if(site){site.closeAllConnections();await new Promise(resolve=>site.close(resolve));}
 try{
  const after=await readFile(policyPath);
  result.managed_policy.WebRtcIPHandling_after=JSON.parse(after).WebRtcIPHandling;
  result.managed_policy.sha256_after=hash(after);
  result.managed_policy.unchanged=result.managed_policy.sha256_before===result.managed_policy.sha256_after;
 }catch{}
 try{if(relayState)result.queue=ledger();}catch{}
 if(!result.passed){try{result.turn.log_tail=(await readFile(turnLog,'utf8')).slice(-6000).replaceAll(username,'[redacted-user]').replaceAll(credential,'[redacted-credential]');}catch{}}
 await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
const outputBytes=Buffer.from(JSON.stringify(result,null,2)+'\n');
await writeFile(outputPath,outputBytes,{flag:'wx',mode:0o600});
console.log(JSON.stringify({abi:result.abi,passed:result.passed,output:outputPath,sha256:hash(outputBytes),
 acceptance:result.acceptance??null,error:result.error?.message??null}));
if(!result.passed)process.exitCode=1;
