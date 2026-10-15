// Preregistered metadata-only console route: no peer connections/media/outcomes.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile,rm,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import path from 'node:path';
const root=process.argv[2];if(!root)throw Error('fresh external output required');
await mkdir(root,{recursive:false});
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const policy='/etc/chromium/policies/managed/misc.json',before=await readFile(policy);
if(JSON.parse(before).WebRtcIPHandling!=='disable_non_proxied_udp')throw Error('unexpected managed policy');
const profile=await mkdtemp(path.join(tmpdir(),'m11r-console-'));
const traceFile=path.resolve(root,'startup.pftrace'),chunks=[],observations=[],marks=[];
const flags=['--enable-logging=stderr','--trace-startup=blink.user_timing,disabled-by-default-webrtc,webrtc',
 '--trace-startup-record-mode=trace-to-console','--trace-startup-duration=5',
 '--trace-startup-format=proto','--trace-startup-file='+traceFile];
const chrome=spawn('/usr/bin/chromium',[...flags,'--headless=new','--remote-debugging-port=0',
 '--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--no-first-run',
 '--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','about:blank'],
 {stdio:['ignore','ignore','pipe']});
let bytes=0,ws,next=0;const pending=new Map();
chrome.stderr.on('data',data=>{bytes+=data.length;chunks.push({node_receive_ms:performance.now(),text:data.toString()});
 if(bytes>10000000)chrome.kill('SIGTERM');});
const begin=performance.now();let error=null;
try{
 let port;
 for(let i=0;i<100;i++){try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await wait(25);}}
 if(!port)throw Error('DevTools unavailable');
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const x=JSON.parse(e.data);if(pending.has(x.id)){const f=pending.get(x.id);pending.delete(x.id);clearTimeout(f.timer);x.error?f.reject(Error(JSON.stringify(x.error))):f.resolve(x.result);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('metadata timeout '+method));},3000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 for(const name of ['M11R_CONSOLE_CAUSAL_MARKER_A','M11R_CONSOLE_CAUSAL_MARKER_B']){
  const request_node_ms=performance.now(),result=await call('Runtime.evaluate',{expression:'({mark:performance.mark('+JSON.stringify(name)+').startTime,origin:performance.timeOrigin})',returnByValue:true});
  marks.push({name,request_node_ms,ack_node_ms:performance.now(),result});await wait(500);
 }
 while(performance.now()-begin<6500){
  let size=null;try{size=(await stat(traceFile)).size;}catch{}
  observations.push({node_observation_ms:performance.now(),trace_file_bytes:size,stderr_bytes:bytes});
  if((size??0)+bytes>10000000)throw Error('metadata probe budget exceeded');await wait(25);
 }
}catch(e){error=String(e);}
const liveStop=performance.now(),liveText=chunks.map(x=>x.text).join('');
ws?.close();chrome.kill('SIGTERM');await new Promise(r=>{if(chrome.exitCode!==null)return r();const t=setTimeout(()=>{chrome.kill('SIGKILL');r();},3000);chrome.once('exit',()=>{clearTimeout(t);r();});});
let output=null;try{output=await readFile(traceFile);}catch{}
const result={abi:'native_transport_console_m11r_metadata_probe_v1',flags,begin_node_ms:begin,
 live_stop_node_ms:liveStop,error,marks,observations,stderr_bytes:bytes,
 artificial_markers:marks.map(x=>({name:x.name,live_stderr_contains_marker:liveText.includes(x.name),
  file_contains_marker:output?.includes(Buffer.from(x.name))??false})),
 output_file_bytes:output?.length??null,output_file_sha256:output?createHash('sha256').update(output).digest('hex'):null,
 policy_sha256:createHash('sha256').update(before).digest('hex'),policy_unchanged:before.equals(await readFile(policy)),
 native_sessions_created:0,receiver_outcomes_read:false,transport_channels_qualified:false};
await writeFile(root+'/stderr_chunks.json',JSON.stringify(chunks)+'\n',{flag:'wx'});
await writeFile(root+'/probe.json',JSON.stringify(result,null,2)+'\n',{flag:'wx'});
await rm(profile,{recursive:true,force:true});
console.log(JSON.stringify({error:result.error,markers:result.artificial_markers,output_file_bytes:result.output_file_bytes,
 policy_unchanged:result.policy_unchanged,native_sessions_created:0}));
