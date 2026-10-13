// Native browser/Node clock calibration. No media, frame, action, or QoE evidence is collected.
import {createServer} from 'node:http';
import {mkdtemp,readFile,writeFile,rm,copyFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {performance} from 'node:perf_hooks';

const out=process.argv[2];
if(!out)throw Error('fresh output directory required');
const browserRecords=[],nodeRecords=[];
const html=String.raw`<!doctype html><meta charset="utf-8"><script>
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
globalThis.run=async()=>{
 const markers=[];
 for(let i=0;i<120;i++){
  const marker_id='cal-'+String(i).padStart(3,'0'),browser_send_ms=performance.now();
  const response=await fetch('/clock-marker',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({marker_id,browser_send_ms})});
  const body=await response.json(),browser_receive_ms=performance.now();
  markers.push({...body,endpoint:'/clock-marker',browser_send_ms,browser_receive_ms});
  await sleep(500);
 }
 return {time_origin_epoch_ms:performance.timeOrigin,markers};
};
</script>`;
const server=createServer(async(req,res)=>{
 try{
  if(req.url==='/clock-marker'&&req.method==='POST'){
   let text='';for await(const chunk of req)text+=chunk;
   const body=JSON.parse(text),node_receive_ms=performance.now();
   if(typeof body.marker_id!=='string'||!Number.isFinite(body.browser_send_ms))throw Error('malformed marker');
   const node_send_ms=performance.now();
   const record={marker_id:body.marker_id,browser_send_ms:body.browser_send_ms,node_receive_ms,node_phase_ms:null,node_send_ms};
   nodeRecords.push(record);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(record));
  }else{res.setHeader('Content-Type','text/html');res.end(html);}
 }catch(error){res.statusCode=400;res.end(JSON.stringify({error:String(error)}));}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const profile=await mkdtemp(path.join(tmpdir(),'rlcd-clock-cal-'));
const browser=spawn(process.env.RLCD_CHROME||'/usr/bin/chromium',[
 '--headless=new','--no-sandbox','--disable-features=WebRtcHideLocalIpsWithMdns',
 '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
 '--user-data-dir='+profile,'--no-first-run','--no-default-browser-check',
 '--disable-background-networking','--disable-component-update','--disable-sync',
 '--metrics-recording-only','about:blank'
],{stdio:['ignore','ignore','pipe']});
let spawnError,errors='';browser.once('error',error=>spawnError=error);browser.stderr.on('data',data=>{errors=(errors+data).slice(-4000);});
let ws;
try{
 let port;
 for(let i=0;i<120;i++){
  if(spawnError)throw spawnError;
  try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}
  catch{await new Promise(resolve=>setTimeout(resolve,100));}
 }
 if(!port)throw Error('DevTools unavailable: '+errors);
 const url='http://127.0.0.1:'+server.address().port;
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(url),{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP connect timeout')),10000);ws.onopen=()=>{clearTimeout(timer);resolve();};ws.onerror=error=>{clearTimeout(timer);reject(error);};});
 let next=1;const pending=new Map();
 ws.onmessage=event=>{const message=JSON.parse(event.data);if(pending.has(message.id)){const entry=pending.get(message.id);clearTimeout(entry.timer);pending.delete(message.id);message.error?entry.reject(Error(JSON.stringify(message.error))):entry.resolve(message.result);}};
 ws.onclose=()=>{for(const entry of pending.values()){clearTimeout(entry.timer);entry.reject(Error('CDP disconnected'));}pending.clear();};
 const call=(method,params={},timeoutMs=15000)=>new Promise((resolve,reject)=>{const id=next++,timer=setTimeout(()=>{pending.delete(id);reject(Error('bounded CDP timeout: '+method));},timeoutMs);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 let ready=false;for(let i=0;i<40;i++){const state=await call('Runtime.evaluate',{expression:'typeof run',returnByValue:true});if(state.result.value==='function'){ready=true;break;}await new Promise(resolve=>setTimeout(resolve,100));}
 if(!ready)throw Error('calibration page did not initialize');
 const result=await call('Runtime.evaluate',{expression:'run()',awaitPromise:true,returnByValue:true},85000);
 if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));
 const browserEvidence=result.result.value;
 if(browserEvidence.markers.length!==120||nodeRecords.length!==120)throw Error('incomplete calibration marker series');
 const versions=await(await fetch('http://127.0.0.1:'+port+'/json/version')).json();
 await (await import('node:fs/promises')).mkdir(out,{recursive:false});
 await copyFile(import.meta.filename,path.join(out,'source_snapshot.mjs'));
 await writeFile(path.join(out,'clock_markers_browser.json'),JSON.stringify(browserEvidence,null,2)+'\n');
 await writeFile(path.join(out,'clock_markers_node.json'),JSON.stringify(nodeRecords,null,2)+'\n');
 await writeFile(path.join(out,'runtime.json'),JSON.stringify({abi:'native_clock_marker_calibration_v1',started_node_time_origin_epoch_ms:performance.timeOrigin,browser:versions.Browser,protocol_version:versions['Protocol-Version'],marker_count:nodeRecords.length,interval_ms:500},null,2)+'\n');
 console.log(JSON.stringify({abi:'native_clock_marker_calibration_v1',browser:versions.Browser,marker_count:nodeRecords.length,elapsed_ms:nodeRecords.at(-1).node_send_ms-nodeRecords[0].node_receive_ms}));
}finally{
 ws?.close();browser.kill('SIGTERM');await new Promise(resolve=>{if(!browser.pid||browser.exitCode!==null)resolve();else{browser.once('exit',resolve);setTimeout(()=>{browser.kill('SIGKILL');resolve();},3000).unref();}});
 server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
