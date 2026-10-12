// Probe the browser-supported proxied route: authenticated localhost TURN/TCP.
// Leaves Chromium policy intact and restricts the TURN server to loopback peers.
import {createServer} from 'node:http';
import {createServer as tcpServer} from 'node:net';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {randomBytes} from 'node:crypto';

const out=process.argv[2],binary=process.env.RLCD_TURN_BINARY;
if(!out||!binary)throw Error('fresh output and configured TURN binary required');
const work=await mkdtemp(path.join(tmpdir(),'networkrlcd-turn-'));
const reserve=tcpServer();await new Promise(r=>reserve.listen(0,'127.0.0.1',r));
const turnPort=reserve.address().port;await new Promise(r=>reserve.close(r));
const username='local-'+randomBytes(8).toString('hex'),credential=randomBytes(24).toString('hex');
const turnConfig=path.join(work,'turn.conf');
await writeFile(turnConfig,[`listening-port=${turnPort}`,'listening-ip=127.0.0.1','relay-ip=127.0.0.1',
 'realm=networkrlcd.local','lt-cred-mech',`user=${username}:${credential}`,'fingerprint','no-tls','no-dtls',
 'no-cli','no-udp','no-tcp-relay','relay-threads=1','min-port=49160','max-port=49260','allow-loopback-peers',
 'denied-peer-ip=0.0.0.0-255.255.255.255','allowed-peer-ip=127.0.0.1',
 `pidfile=${path.join(work,'turn.pid')}`,`log-file=${path.join(work,'turn.log')}`].join('\n')+'\n',{mode:0o600});
const turn=spawn(binary,['-c',turnConfig],{stdio:['ignore','ignore','ignore']});
const server=createServer((req,res)=>res.end('<!doctype html><canvas id="c" width="16" height="16"></canvas>'));
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin='http://127.0.0.1:'+server.address().port;
const profile=path.join(work,'chrome');
const flags=['--headless=new','--no-sandbox','--disable-background-networking','--disable-component-update',
 '--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
 '--user-data-dir='+profile,'about:blank'];
const chrome=spawn('/usr/bin/chromium',flags,{stdio:['ignore','ignore','pipe']});
let ws,errors='';chrome.stderr.on('data',d=>{errors=(errors+d).slice(-4000);});
try{
 let port;
 for(let k=0;k<100;k++){
  try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}
  catch{await new Promise(r=>setTimeout(r,100));}
 }
 if(!port)throw Error('DevTools unavailable: '+errors);
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(origin),{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let next=0;const pending=new Map();
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(pending.has(d.id)){const {r,j,timer}=pending.get(d.id);clearTimeout(timer);pending.delete(d.id);d.error?j(Error(JSON.stringify(d.error))):r(d.result);}};
 const call=(method,params)=>new Promise((r,j)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);j(Error('CDP timeout'));},15000);pending.set(id,{r,j,timer});ws.send(JSON.stringify({id,method,params}));});
 let ready=false;
 for(let k=0;k<30;k++){
  const value=await call('Runtime.evaluate',{expression:"Boolean(document.getElementById('c'))",returnByValue:true});
  if(value.result.value){ready=true;break;}await new Promise(r=>setTimeout(r,100));
 }
 if(!ready)throw Error('owned page did not load');
 const iceServer={urls:`turn:127.0.0.1:${turnPort}?transport=tcp`,username,credential};
 const expression=`(async()=>{
  const stream=document.getElementById('c').captureStream(1),pc=new RTCPeerConnection({iceTransportPolicy:'relay',iceServers:[${JSON.stringify(iceServer)}]});
  const candidates=[],errors=[];
  pc.onicecandidate=e=>{if(e.candidate)candidates.push({type:e.candidate.type,protocol:e.candidate.protocol,address:e.candidate.address,port:e.candidate.port,relayProtocol:e.candidate.relayProtocol,url:e.candidate.url});};
  pc.onicecandidateerror=e=>errors.push({code:e.errorCode,text:e.errorText,url:e.url});
  pc.addTrack(stream.getTracks()[0]);await pc.setLocalDescription(await pc.createOffer());
  for(let k=0;k<100&&pc.iceGatheringState!=='complete';k++)await new Promise(r=>setTimeout(r,100));
  const value={state:pc.iceGatheringState,candidates,errors};pc.close();stream.getTracks().forEach(t=>t.stop());return value;
 })()`;
 const value=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
 if(value.exceptionDetails)throw Error(JSON.stringify(value.exceptionDetails));
 const build=await(await fetch('http://127.0.0.1:'+port+'/json/version')).json();
 const result={abi:'native_local_turn_tcp_preflight_v1',browser:build.Browser,policy_modified:false,
  owned_loopback_only:true,authenticated_turn_tcp:true,controller_or_qoe_evaluated:false,
  turn_version:'4.6.1',ice:value.result.value};
 await writeFile(out,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result,null,2));
}finally{
 ws?.close();
 for(const process of [chrome,turn]){
  process.kill('SIGTERM');await new Promise(r=>{if(process.exitCode!==null)r();else{process.once('exit',r);setTimeout(()=>{process.kill('SIGKILL');r();},3000).unref();}});
 }
 await new Promise(r=>server.close(r));await rm(work,{recursive:true,force:true});
}
