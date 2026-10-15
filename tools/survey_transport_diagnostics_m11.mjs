// Metadata only: fresh browser, no peer/media creation or old panel access.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {tmpdir} from 'node:os';
const out=process.argv[2];if(!out)throw Error('fresh metadata output required');
await mkdir(out,{recursive:false});
const wait=ms=>new Promise(r=>setTimeout(r,ms)),profile=await mkdtemp(path.join(tmpdir(),'m11-meta-'));
const policy='/etc/chromium/policies/managed/misc.json',before=await readFile(policy);
if(JSON.parse(before).WebRtcIPHandling!=='disable_non_proxied_udp')throw Error('unexpected managed policy');
const chrome=spawn('/usr/bin/chromium',['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
 '--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','about:blank'],{stdio:['ignore','ignore','pipe']});
let stderr='';chrome.stderr.on('data',d=>stderr=(stderr+d).slice(-4000));let ws;
try{
 let port;
 for(let i=0;i<100;i++){try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await wait(100);}}
 if(!port)throw Error('DevTools unavailable '+stderr);
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let next=0;const pending=new Map();ws.onmessage=e=>{const x=JSON.parse(e.data);if(pending.has(x.id)){const f=pending.get(x.id);pending.delete(x.id);clearTimeout(f.timer);x.error?f.reject(Error(JSON.stringify(x.error))):f.resolve(x.result);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('metadata timeout '+method));},10000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 const results={};for(const name of ['Browser.getVersion','Tracing.getCategories','Schema.getDomains','Performance.enable','Performance.getMetrics']){
  try{results[name]={status:'ok',result:await call(name)};}catch(e){results[name]={status:'unsupported_or_failed',error:String(e)};}}
 results.javascript=await call('Runtime.evaluate',{expression:'({peer_methods:Object.getOwnPropertyNames(RTCPeerConnection.prototype),chrome_keys:Object.keys(globalThis.chrome??{}),webrtc_logging_private_available:!!globalThis.chrome?.webrtcLoggingPrivate})',returnByValue:true});
 results.policy_before_sha256=createHash('sha256').update(before).digest('hex');results.policy_unchanged=before.equals(await readFile(policy));
 results.native_sessions_created=0;results.receiver_outcomes_read=false;
 await writeFile(out+'/metadata.json',JSON.stringify(results,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({metadata_saved:true,build:results['Browser.getVersion'],webrtc_categories:results['Tracing.getCategories']?.result?.categories?.filter(x=>/webrtc|user_timing/i.test(x)),policy_unchanged:results.policy_unchanged}));
}finally{ws?.close();chrome.kill('SIGTERM');await new Promise(r=>{if(chrome.exitCode!==null)return r();const t=setTimeout(()=>{chrome.kill('SIGKILL');r();},3000);chrome.once('exit',()=>{clearTimeout(t);r();});});await rm(profile,{recursive:true,force:true});}
