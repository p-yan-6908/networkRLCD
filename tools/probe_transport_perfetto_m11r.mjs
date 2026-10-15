// One preregistered supported-file export probe, zero native peer/media contexts.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {tmpdir} from 'node:os';
const root=path.resolve(process.argv[2]??'');if(!process.argv[2])throw Error('fresh external output required');
await mkdir(root,{recursive:false});
const wait=ms=>new Promise(r=>setTimeout(r,ms)),cat=xs=>Buffer.concat(xs);
const vi=n=>{n=BigInt(n);const a=[];do{let b=Number(n&127n);n>>=7n;a.push(n?b|128:b);}while(n);return Buffer.from(a);};
const num=(f,n)=>cat([vi(f*8),vi(n)]),blob=(f,b)=>{b=Buffer.from(b);return cat([vi(f*8+2),vi(b.length),b]);};
const traceFile=root+'/live.pftrace',configPath=root+'/config.pb';
const track=cat([blob(1,'*'),...['blink.user_timing','webrtc','disabled-by-default-webrtc'].map(x=>blob(2,x)),num(5,1)]);
const config=cat([blob(1,cat([num(1,1024),num(4,1)])),blob(2,blob(1,cat([blob(1,'track_event'),blob(113,track)]))),
 num(3,6000),num(8,1),blob(29,traceFile),num(9,100),num(13,100),num(10,10000000)]);
await writeFile(configPath,config,{flag:'wx'});
const policy='/etc/chromium/policies/managed/misc.json',before=await readFile(policy);
if(JSON.parse(before).WebRtcIPHandling!=='disable_non_proxied_udp')throw Error('unexpected managed policy');
const profile=await mkdtemp(path.join(tmpdir(),'m11r-perfetto-'));
const flags=['--enable-logging=stderr','--trace-perfetto-config-file='+configPath];
const chunks=[],marks=[],observations=[],first=new Map();let bytes=0,error=null,ws,next=0,running=true;
const pending=new Map(),begin=performance.now();
const chrome=spawn('/usr/bin/chromium',[...flags,'--headless=new','--remote-debugging-port=0',
 '--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check',
 '--disable-background-networking','--disable-component-update','--disable-sync','about:blank'],
 {cwd:root,stdio:['ignore','ignore','pipe']});
chrome.stderr.on('data',data=>{bytes+=data.length;chunks.push({node_receive_ms:performance.now(),text:data.toString()});
 if(bytes>10000000)chrome.kill('SIGTERM');});
const names=['M11R_PERFETTO_CAUSAL_MARKER_A','M11R_PERFETTO_CAUSAL_MARKER_B'];
const tailTask=(async()=>{while(running){let out=null;try{out=await readFile(traceFile);}catch{}
 const now=performance.now();observations.push({node_available_ms:now,file_bytes:out?.length??null});
 if(out){for(const name of names)if(!first.has(name)&&out.includes(Buffer.from(name)))first.set(name,now);
  if(out.length+bytes>10000000){error='metadata budget exceeded';chrome.kill('SIGTERM');break;}}
 await wait(25);
}})();
try{
 let port;for(let i=0;i<100;i++){try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await wait(25);}}
 if(!port)throw Error('DevTools unavailable');
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const x=JSON.parse(e.data);if(pending.has(x.id)){const f=pending.get(x.id);pending.delete(x.id);clearTimeout(f.timer);x.error?f.reject(Error(JSON.stringify(x.error))):f.resolve(x.result);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('metadata timeout '+method));},3000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 await wait(500);
 for(const name of names){const request_node_ms=performance.now(),result=await call('Runtime.evaluate',{
  expression:'({mark:performance.mark('+JSON.stringify(name)+').startTime,origin:performance.timeOrigin})',returnByValue:true});
  marks.push({name,request_node_ms,ack_node_ms:performance.now(),result});await wait(500);}
 while(performance.now()-begin<8000)await wait(25);
}catch(e){error=String(e);}
running=false;await tailTask;const liveStop=performance.now();
ws?.close();chrome.kill('SIGTERM');await new Promise(r=>{if(chrome.exitCode!==null||chrome.signalCode!==null)return r();const t=setTimeout(()=>{chrome.kill('SIGKILL');r();},3000);chrome.once('exit',()=>{clearTimeout(t);r();});});
let output=null;try{output=await readFile(traceFile);}catch{}
const result={abi:'native_transport_perfetto_m11r_metadata_probe_v1',flags,begin_node_ms:begin,live_stop_node_ms:liveStop,error,
 marks,observations,artificial_markers:names.map(name=>{const mark=marks.find(x=>x.name===name),available=first.get(name)??null;
  return {name,first_visible_node_ms:available,delay_from_request_upper_ms:available!==null&&mark?available-mark.request_node_ms:null,
   delay_from_ack_lower_ms:available!==null&&mark?available-mark.ack_node_ms:null,file_contains_marker:output?.includes(Buffer.from(name))??false};}),
 output_file_bytes:output?.length??null,output_file_sha256:output?createHash('sha256').update(output).digest('hex'):null,
 config_sha256:createHash('sha256').update(config).digest('hex'),process_exit_code:chrome.exitCode,process_signal_code:chrome.signalCode,
 policy_sha256:createHash('sha256').update(before).digest('hex'),policy_unchanged:before.equals(await readFile(policy)),
 native_sessions_created:0,receiver_outcomes_read:false,transport_channels_qualified:false};
await writeFile(root+'/stderr_chunks.json',JSON.stringify(chunks)+'\n',{flag:'wx'});
await writeFile(root+'/probe.json',JSON.stringify(result,null,2)+'\n',{flag:'wx'});
await rm(profile,{recursive:true,force:true});
console.log(JSON.stringify({error:result.error,markers:result.artificial_markers,output_file_bytes:result.output_file_bytes,
 process_exit_code:result.process_exit_code,process_signal_code:result.process_signal_code,policy_unchanged:result.policy_unchanged,native_sessions_created:0}));
