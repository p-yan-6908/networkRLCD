// Check real Chromium host ICE availability on an owned localhost page.
// No external ICE servers, media outcomes, controller training or frozen-file edits.
import {createServer} from 'node:http';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';

const out=process.argv[2];
if(!out)throw Error('fresh JSON output path required');
const server=createServer((req,res)=>res.end('<!doctype html><canvas id="c" width="16" height="16"></canvas>'));
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
const profile=await mkdtemp(path.join(tmpdir(),'networkrlcd-ice-'));
const flags=['--headless=new','--no-sandbox','--disable-background-networking','--disable-component-update',
 '--no-first-run','--no-default-browser-check','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',
 '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'about:blank'];
const chrome=spawn('/usr/bin/chromium',flags,{stdio:['ignore','ignore','pipe']});
let errors='',ws;
chrome.stderr.on('data',d=>{errors=(errors+d).slice(-4000);});
try{
 let port;
 for(let k=0;k<100;k++){
  try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}
  catch{await new Promise(resolve=>setTimeout(resolve,100));}
 }
 if(!port)throw Error('DevTools unavailable: '+errors);
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(origin),{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 const pending=new Map();let next=0;
 ws.onmessage=event=>{const d=JSON.parse(event.data);if(pending.has(d.id)){const {resolve,reject,timer}=pending.get(d.id);clearTimeout(timer);pending.delete(d.id);d.error?reject(Error(JSON.stringify(d.error))):resolve(d.result);}};
 const call=(method,params)=>new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 let ready=false;
 for(let k=0;k<30;k++){
  const value=await call('Runtime.evaluate',{expression:"Boolean(document.getElementById('c'))",returnByValue:true});
  if(value.result.value){ready=true;break;}
  await new Promise(resolve=>setTimeout(resolve,100));
 }
 if(!ready)throw Error('owned localhost page did not load');
 const modes={};
 for(const grant of [false,true]){
  if(grant)await call('Browser.grantPermissions',{origin,permissions:['videoCapture','audioCapture']});
  const expression=`(async()=>{
   ${grant?"const permissionStream=await navigator.mediaDevices.getUserMedia({video:true});permissionStream.getTracks().forEach(t=>t.stop());":""}
   const canvas=document.getElementById('c'),stream=canvas.captureStream(1),pc=new RTCPeerConnection({iceServers:[]});
   const candidates=[];pc.onicecandidate=e=>{if(e.candidate)candidates.push({type:e.candidate.type,protocol:e.candidate.protocol,address:e.candidate.address,port:e.candidate.port});};
   pc.addTrack(stream.getTracks()[0]);await pc.setLocalDescription(await pc.createOffer());
   for(let k=0;k<50&&pc.iceGatheringState!=='complete';k++)await new Promise(r=>setTimeout(r,100));
   const result={state:pc.iceGatheringState,candidates};pc.close();stream.getTracks().forEach(t=>t.stop());return result;
  })()`;
  const value=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(value.exceptionDetails)throw Error(JSON.stringify(value.exceptionDetails));
  modes[grant?'owned_fake_media_permission':'no_media_permission']=value.result.value;
 }
 const build=await(await fetch('http://127.0.0.1:'+port+'/json/version')).json();
 const result={abi:'native_cloud_ice_preflight_v1',browser:build.Browser,local_only:true,external_ice_servers:[],
  generated_media_only:true,controller_or_qoe_evaluated:false,chrome_flags:flags.filter(x=>!x.startsWith('--user-data-dir=')),modes};
 await writeFile(out,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify(result,null,2));
}finally{
 ws?.close();chrome.kill('SIGTERM');
 await new Promise(resolve=>{if(chrome.exitCode!==null)resolve();else{chrome.once('exit',resolve);setTimeout(()=>{chrome.kill('SIGKILL');resolve();},3000).unref();}});
 await new Promise(resolve=>server.close(resolve));await rm(profile,{recursive:true,force:true});
}
