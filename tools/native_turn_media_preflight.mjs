// Prove policy-compatible TURN/TCP candidate gathering and bidirectional media.
// The managed Chromium policy is read and fingerprinted, never modified.
import {createServer as httpServer} from 'node:http';
import {createServer as tcpServer,createConnection} from 'node:net';
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
const packagePath=process.env.RLCD_TURN_PACKAGE||null;
const packageSha256=packagePath?hash(await readFile(packagePath)):null;
const sourceSha256=hash(await readFile(import.meta.filename));
const work=await mkdtemp(path.join(tmpdir(),'n2'));
const profile=path.join(work,'c');
let turn,chrome,ws,site;
let chromeError='';

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
const turnPort=await reserveTurnPort();
const username='preflight-'+randomBytes(8).toString('hex');
const credential=randomBytes(24).toString('hex');
const turnConfig=path.join(work,'turn.conf');
const turnLog=path.join(work,'turn.log');
await writeFile(turnConfig,[
 `listening-port=${turnPort}`,'listening-ip=127.0.0.1','relay-ip=127.0.0.1',
 'realm=networkrlcd.local','lt-cred-mech',`user=${username}:${credential}`,
 'fingerprint','no-tls','no-dtls','no-udp','no-tcp-relay','no-cli','no-daemon',
 'relay-threads=1','min-port=49160','max-port=49260','allow-loopback-peers',
 'denied-peer-ip=0.0.0.0-255.255.255.255','allowed-peer-ip=127.0.0.1',
 `pidfile=${path.join(work,'turn.pid')}`,`log-file=${turnLog}`
 ].join('\n')+'\n',{mode:0o600});

const result={
 abi:'native_turn_tcp_media_preflight_v1',passed:false,policy_modified:false,
 managed_policy:{path:policyPath,WebRtcIPHandling_before:policyBefore,sha256_before:hash(beforePolicy)},
 turn:{version:(versionRun.stdout||versionRun.stderr).trim(),binary_sha256:binarySha256,
  package_sha256:packageSha256,library_dir:libraryDir,library_sha256:libraryHashes,
  control_transport:'TCP',server_config:{listen_ip:'127.0.0.1',relay_ip:'127.0.0.1',
   relay_transport:'UDP',relay_port_range:[49160,49260],loopback_peers_only:true,
   browser_udp_listener_disabled:true,tcp_relay_disabled:true}},
 browser:{binary:'/usr/bin/chromium'},source_sha256:sourceSha256,
 ice:{transport_policy:'relay',turn_url:`turn:127.0.0.1:${turnPort}?transport=tcp`,
  peer_a_candidates:[],peer_b_candidates:[],peer_a_candidate_errors:[],peer_b_candidate_errors:[]},
 media:{connection_state:null,peer_a_to_peer_b:null,peer_b_to_peer_a:null},
 evaluated_action_or_qoe:false
};

try{
 turn=spawn(binary,['-c',turnConfig],{stdio:['ignore','ignore','ignore']});
 await waitForTcp(turnPort,turn);
 site=httpServer((req,res)=>{
  if(req.url==='/')res.end('<!doctype html><meta charset="utf-8"><body></body>');
  else{res.statusCode=404;res.end('not found');}
 });
 await new Promise((resolve,reject)=>{site.once('error',reject);site.listen(0,'127.0.0.1',resolve);});
 const origin='http://127.0.0.1:'+site.address().port;
 chrome=spawn('/usr/bin/chromium',[
  '--headless=new','--no-sandbox','--disable-background-networking','--disable-component-update',
  '--no-first-run','--no-default-browser-check','--remote-debugging-port=0',
  '--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,
  '--autoplay-policy=no-user-gesture-required','about:blank'
 ],{stdio:['ignore','ignore','pipe']});
 chrome.stderr.on('data',data=>{chromeError=(chromeError+data).slice(-5000);});
 let port;
 for(let attempt=0;attempt<120;attempt++){
  try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}
  catch{if(chrome.exitCode!==null)throw Error('Chromium exited before DevTools was ready: '+chromeError);await wait(100);}
 }
 if(!port)throw Error('Chromium DevTools unavailable: '+chromeError);
 const target=await(await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(origin)}`,{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP connection timed out')),10000);ws.onopen=()=>{clearTimeout(timer);resolve();};ws.onerror=error=>{clearTimeout(timer);reject(error);};});
 let next=0;const pending=new Map();
 ws.onmessage=event=>{const message=JSON.parse(event.data);if(pending.has(message.id)){const item=pending.get(message.id);clearTimeout(item.timer);pending.delete(message.id);message.error?item.reject(Error(JSON.stringify(message.error))):item.resolve(message.result);}};
 ws.onclose=()=>{for(const item of pending.values()){clearTimeout(item.timer);item.reject(Error('CDP disconnected'));}pending.clear();};
 const call=(method,params={},timeoutMs=20000)=>new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timed out: '+method));},timeoutMs);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 let ready=false;
 for(let attempt=0;attempt<50;attempt++){
  const state=await call('Runtime.evaluate',{expression:'document.readyState',returnByValue:true});
  if(state.result.value==='complete'){ready=true;break;}await wait(100);
 }
 if(!ready)throw Error('owned preflight page did not load');
 const iceServer={urls:result.ice.turn_url,username,credential};
 const expression=`(async()=>{
  const iceServer=${JSON.stringify(iceServer)};
  const config={iceTransportPolicy:'relay',iceServers:[iceServer]};
  const errorsA=[],errorsB=[],candidatesA=[],candidatesB=[];
  const makeSource=(seed)=>{const canvas=document.createElement('canvas');canvas.width=320;canvas.height=180;
   const ctx=canvas.getContext('2d');let n=0;const draw=()=>{n++;ctx.fillStyle='rgb('+((n*17+seed)%255)+','+((n*37+seed)%255)+','+((n*59+seed)%255)+')';ctx.fillRect(0,0,320,180);ctx.fillStyle='white';ctx.font='20px monospace';ctx.fillText('TURN '+seed+' '+n,8,30);};draw();const timer=setInterval(draw,1000/30);return {canvas,stream:canvas.captureStream(30),stop:()=>clearInterval(timer)};};
  const sourceA=makeSource(31),sourceB=makeSource(97),pcA=new RTCPeerConnection(config),pcB=new RTCPeerConnection(config);
  const videoA=document.createElement('video'),videoB=document.createElement('video');
  for(const video of [videoA,videoB]){video.autoplay=true;video.muted=true;video.playsInline=true;video.width=320;video.height=180;document.body.append(video);}
  pcA.addTrack(sourceA.stream.getVideoTracks()[0],sourceA.stream);pcB.addTrack(sourceB.stream.getVideoTracks()[0],sourceB.stream);
  pcA.ontrack=event=>{videoA.srcObject=event.streams[0];videoA.play().catch(()=>{});};
  pcB.ontrack=event=>{videoB.srcObject=event.streams[0];videoB.play().catch(()=>{});};
  pcA.onicecandidate=event=>{if(event.candidate)candidatesA.push({type:event.candidate.type,protocol:event.candidate.protocol,address:event.candidate.address,port:event.candidate.port,relayProtocol:event.candidate.relayProtocol,url:event.candidate.url});};
  pcB.onicecandidate=event=>{if(event.candidate)candidatesB.push({type:event.candidate.type,protocol:event.candidate.protocol,address:event.candidate.address,port:event.candidate.port,relayProtocol:event.candidate.relayProtocol,url:event.candidate.url});};
  pcA.onicecandidateerror=event=>errorsA.push({code:event.errorCode,text:event.errorText,url:event.url});
  pcB.onicecandidateerror=event=>errorsB.push({code:event.errorCode,text:event.errorText,url:event.url});
  const gather=pc=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('ICE gathering timed out')),20000);if(pc.iceGatheringState==='complete'){clearTimeout(timer);resolve();}else pc.addEventListener('icegatheringstatechange',()=>{if(pc.iceGatheringState==='complete'){clearTimeout(timer);resolve();}},{once:false});});
  const offer=await pcA.createOffer();await pcA.setLocalDescription(offer);await gather(pcA);
  await pcB.setRemoteDescription(pcA.localDescription);const answer=await pcB.createAnswer();await pcB.setLocalDescription(answer);await gather(pcB);await pcA.setRemoteDescription(pcB.localDescription);
  const waitConnected=async()=>{const end=Date.now()+30000;while(Date.now()<end){if(pcA.connectionState==='connected'&&pcB.connectionState==='connected')return;if(['failed','closed'].includes(pcA.connectionState)||['failed','closed'].includes(pcB.connectionState))break;await new Promise(r=>setTimeout(r,100));}throw Error('TURN relay-only peers did not connect: '+pcA.connectionState+'/'+pcB.connectionState);};
  await waitConnected();
  const selected=async pc=>{const stats=await pc.getStats(),rows=[...stats.values()],transport=rows.find(row=>row.type==='transport'&&row.selectedCandidatePairId),pair=rows.find(row=>row.id===(transport?.selectedCandidatePairId))??rows.find(row=>row.type==='candidate-pair'&&row.nominated&&row.state==='succeeded');const local=rows.find(row=>row.id===pair?.localCandidateId),remote=rows.find(row=>row.id===pair?.remoteCandidateId);return {pair:pair?{state:pair.state,nominated:pair.nominated,bytesSent:pair.bytesSent,bytesReceived:pair.bytesReceived}:null,local:local?{candidateType:local.candidateType,protocol:local.protocol,relayProtocol:local.relayProtocol,address:local.address}:null,remote:remote?{candidateType:remote.candidateType,protocol:remote.protocol,relayProtocol:remote.relayProtocol,address:remote.address}:null};};
  let statsA,statsB;for(let i=0;i<100;i++){await new Promise(r=>setTimeout(r,200));const allA=[...(await pcA.getStats()).values()],allB=[...(await pcB.getStats()).values()];const inA=allA.filter(row=>row.type==='inbound-rtp'&&row.kind==='video'),inB=allB.filter(row=>row.type==='inbound-rtp'&&row.kind==='video'),outA=allA.filter(row=>row.type==='outbound-rtp'&&row.kind==='video'),outB=allB.filter(row=>row.type==='outbound-rtp'&&row.kind==='video');statsA={inbound:inA.reduce((a,x)=>({bytes:a.bytes+(x.bytesReceived||0),frames:a.frames+(x.framesDecoded||0),packets:a.packets+(x.packetsReceived||0)}),{bytes:0,frames:0,packets:0}),outbound:outA.reduce((a,x)=>({bytes:a.bytes+(x.bytesSent||0),frames:a.frames+(x.framesEncoded||0),packets:a.packets+(x.packetsSent||0)}),{bytes:0,frames:0,packets:0})};statsB={inbound:inB.reduce((a,x)=>({bytes:a.bytes+(x.bytesReceived||0),frames:a.frames+(x.framesDecoded||0),packets:a.packets+(x.packetsReceived||0)}),{bytes:0,frames:0,packets:0}),outbound:outB.reduce((a,x)=>({bytes:a.bytes+(x.bytesSent||0),frames:a.frames+(x.framesEncoded||0),packets:a.packets+(x.packetsSent||0)}),{bytes:0,frames:0,packets:0})};if(statsA.inbound.frames>=30&&statsB.inbound.frames>=30&&statsA.outbound.bytes>0&&statsB.outbound.bytes>0)break;}
  const result={gathering:{a_state:pcA.iceGatheringState,b_state:pcB.iceGatheringState,a_candidates:candidatesA,b_candidates:candidatesB,a_errors:errorsA,b_errors:errorsB},connection:{a_state:pcA.connectionState,b_state:pcB.connectionState,a_selected_pair:await selected(pcA),b_selected_pair:await selected(pcB)},media:{a_to_b:{sender:statsA.outbound,receiver:statsB.inbound},b_to_a:{sender:statsB.outbound,receiver:statsA.inbound}}};
  sourceA.stop();sourceB.stop();pcA.close();pcB.close();return result;
 })()`;
 const evaluated=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},60000);
 if(evaluated.exceptionDetails)throw Error(JSON.stringify(evaluated.exceptionDetails));
 const pageResult=evaluated.result.value;
 result.ice.peer_a_candidates=pageResult.gathering.a_candidates;result.ice.peer_b_candidates=pageResult.gathering.b_candidates;
 result.ice.peer_a_candidate_errors=pageResult.gathering.a_errors;result.ice.peer_b_candidate_errors=pageResult.gathering.b_errors;
 result.media.connection_state={peer_a:pageResult.connection.a_state,peer_b:pageResult.connection.b_state,
  peer_a_selected_pair:pageResult.connection.a_selected_pair,peer_b_selected_pair:pageResult.connection.b_selected_pair};
 result.media.peer_a_to_peer_b=pageResult.media.a_to_b;result.media.peer_b_to_peer_a=pageResult.media.b_to_a;
 const build=await(await fetch(`http://127.0.0.1:${port}/json/version`)).json();
 result.browser.version=build.Browser;result.browser.sha256=hash(await readFile('/usr/bin/chromium'));
 result.browser.launch_flags_used_to_change_webrtc_policy=false;
 result.turn.listener_ready=true;
 const onlyRelay=candidates=>candidates.length>0&&candidates.every(candidate=>candidate.type==='relay'&&candidate.relayProtocol==='tcp'&&candidate.address==='127.0.0.1');
 const relaySelected=pair=>pair?.local?.candidateType==='relay'&&pair?.local?.relayProtocol==='tcp'&&pair?.remote?.candidateType==='relay';
 const directionOk=direction=>direction?.sender?.bytes>0&&direction?.sender?.packets>0&&direction?.receiver?.bytes>0&&direction?.receiver?.packets>0&&direction?.sender?.frames>10&&direction?.receiver?.frames>10;
 const afterPolicy=await readFile(policyPath);
 result.managed_policy.WebRtcIPHandling_after=JSON.parse(afterPolicy).WebRtcIPHandling;
 result.managed_policy.sha256_after=hash(afterPolicy);
 result.managed_policy.unchanged=hash(beforePolicy)===hash(afterPolicy);
 result.acceptance={both_gathering_complete:pageResult.gathering.a_state==='complete'&&pageResult.gathering.b_state==='complete',
  relay_only_candidates_on_both_peers:onlyRelay(result.ice.peer_a_candidates)&&onlyRelay(result.ice.peer_b_candidates),
  turn_tcp_selected_for_both_local_candidates:relaySelected(pageResult.connection.a_selected_pair)&&relaySelected(pageResult.connection.b_selected_pair),
  connected_both_peers:pageResult.connection.a_state==='connected'&&pageResult.connection.b_state==='connected',
  bidirectional_media:directionOk(pageResult.media.a_to_b)&&directionOk(pageResult.media.b_to_a),
  managed_policy_unchanged:hash(beforePolicy)===hash(afterPolicy)&&result.managed_policy.WebRtcIPHandling_after==='disable_non_proxied_udp'};
 result.passed=Object.values(result.acceptance).every(Boolean);
}catch(error){
 result.error={name:error?.name??'Error',message:String(error?.message??error),chrome_stderr_tail:chromeError.slice(-1500)};
}finally{
 if(!result.passed){try{result.turn.log_tail=(await readFile(turnLog,'utf8')).slice(-6000).replaceAll(username,'[redacted-user]').replaceAll(credential,'[redacted-credential]');}catch{}}
 ws?.close();await stop(chrome);await stop(turn);
 if(site){site.closeAllConnections();await new Promise(resolve=>site.close(resolve));}
 await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
const outputBytes=Buffer.from(JSON.stringify(result,null,2)+'\n');
await writeFile(outputPath,outputBytes,{flag:'wx',mode:0o600});
console.log(JSON.stringify({abi:result.abi,passed:result.passed,output:outputPath,sha256:hash(outputBytes),acceptance:result.acceptance??null,error:result.error?.message??null}));
if(!result.passed)process.exitCode=1;
