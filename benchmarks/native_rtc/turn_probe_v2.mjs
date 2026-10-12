// Prospective collector v2: stop relay event production before the closing ledger.
// V1 captures, code and registered sources remain unchanged. Same native probe page.
import {createServer} from 'node:http';
import {createServer as createTcpServer} from 'node:net';
import {createSocket} from 'node:dgram';
import {networkInterfaces,tmpdir} from 'node:os';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';
import {randomBytes,createHash} from 'node:crypto';
import path from 'node:path';
const root=process.argv[2],trial=JSON.parse(await readFile(process.argv[3],'utf8'));
if(!root||!process.env.RLCD_TURN_BINARY)throw Error('fresh root, trial and configured TURN binary required');
await mkdir(root,{recursive:false});
const assets=path.dirname(import.meta.filename),work=await mkdtemp(path.join(tmpdir(),'networkrlcd-turn-peer-'));
const reserve=createTcpServer();await new Promise(r=>reserve.listen(0,'127.0.0.1',r));const turnPort=reserve.address().port;await new Promise(r=>reserve.close(r));
const username='local-'+randomBytes(8).toString('hex'),credential=randomBytes(24).toString('hex'),turnConfig=path.join(work,'turn.conf');
await writeFile(turnConfig,[`listening-port=${turnPort}`,'listening-ip=127.0.0.1','relay-ip=127.0.0.1','realm=networkrlcd.local','lt-cred-mech',`user=${username}:${credential}`,'fingerprint','no-tls','no-dtls','no-cli','no-udp','no-tcp-relay','relay-threads=1','min-port=49160','max-port=49260','allow-loopback-peers','denied-peer-ip=0.0.0.0-255.255.255.255','allowed-peer-ip=127.0.0.1',`pidfile=${path.join(work,'turn.pid')}`,`log-file=${path.join(work,'turn.log')}`].join('\n')+'\n',{mode:0o600});
const turn=spawn(process.env.RLCD_TURN_BINARY,['-c',turnConfig],{stdio:['ignore','ignore','ignore']});
const profile=path.join(work,'chrome');
const localIPs=new Set(['127.0.0.1',...Object.values(networkInterfaces()).flat().filter(x=>x?.family==='IPv4').map(x=>x.address)]);
let relaySockets=[],links=[],tick,stopped=false,capacity=5;
const delayMs=25,queueLimit=30000;
const events=[];let nextPacket=0;
function pumpLink(l,now){
 const from=l.last,before=l.queued,oldServed=l.served;let budget=(now-from)*capacity*125;
 l.capacityBytes+=budget;l.last=now;
 while(budget>1e-9&&l.queue.length){
  const p=l.queue[0],used=Math.min(p.remaining,budget);p.remaining-=used;l.queued-=used;l.served+=used;budget-=used;
  if(p.remaining<1e-9){
   l.queue.shift();const complete=now,due=now+delayMs;
   const forward=()=>{if(stopped)return;const wait=due-performance.now();if(wait>0){setTimeout(forward,Math.max(1,wait));return;}
    events.push({kind:'forward',direction:l.direction,packet:p.id,at_ms:performance.now(),serialization_done_ms:complete,wire_bytes:p.wire});
    l.sender.send(p.data,l.destination.port,l.destination.address,err=>{if(err)l.errors++;else{l.forwarded++;l.forwardedWire+=p.wire;}});
   };setTimeout(forward,delayMs);
  }
 }
 if(!l.queue.length)l.queued=0;
 events.push({kind:'service',direction:l.direction,from_ms:from,at_ms:now,capacity_mbps:capacity,budget_wire_bytes:(now-from)*capacity*125,service_wire_bytes:l.served-oldServed,queue_before_wire_bytes:before,queue_after_wire_bytes:l.queued});
}
function ledger(){const now=performance.now();for(const l of links)pumpLink(l,now);const view=l=>({offered_wire_bytes:l.offered,dropped_wire_bytes:l.dropped,served_wire_bytes:l.served,queued_wire_bytes:l.queued,forwarded_wire_bytes:l.forwardedWire,forwarded_packets:l.forwarded,overflow_packets:l.drops,send_errors:l.errors,max_queue_wire_bytes:l.maxQueue,queue_limit_wire_bytes:queueLimit,capacity_integral_wire_bytes:l.capacityBytes,capacity_integral_upper_bound_ok:l.served<=l.capacityBytes+1e-5,conservation_error_bytes:l.offered-l.dropped-l.served-l.queued});return {capacity_mbps:capacity,one_way_propagation_ms:delayMs,ipv4_udp_header_bytes:28,a_to_b:links[0]?view(links[0]):null,b_to_a:links[1]?view(links[1]):null};}
async function startRelay(a,b){
 for(const c of [a,b])if(!localIPs.has(c.address)||!Number.isInteger(c.port)||c.port<1||c.port>65535)throw Error('relay destinations must be owned local IPv4 candidates');
 if(links.length)throw Error('relay already created');const pa=createSocket('udp4'),pb=createSocket('udp4');relaySockets=[pa,pb];
 await Promise.all(relaySockets.map(s=>new Promise((r,j)=>{s.once('error',j);s.bind(0,'127.0.0.1',r);})));
 const make=(sender,destination,direction)=>({sender,destination,direction,last:performance.now(),queue:[],queued:0,offered:0,dropped:0,served:0,capacityBytes:0,forwardedWire:0,forwarded:0,drops:0,errors:0,maxQueue:0,unexpected:0});
 const ab=make(pa,b,'a_to_b'),ba=make(pb,a,'b_to_a');links=[ab,ba];
 const receive=(l,msg,from,expectedPort)=>{
  if(stopped)return;
  if(!localIPs.has(from.address)||from.port!==expectedPort){l.unexpected++;return;}
  const now=performance.now();pumpLink(l,now);const wire=msg.length+28,before=l.queued,id=nextPacket++,drop=before+wire>queueLimit;l.offered+=wire;
  if(drop){l.dropped+=wire;l.drops++;}else{l.queue.push({data:Buffer.from(msg),wire,remaining:wire,id});l.queued+=wire;l.maxQueue=Math.max(l.maxQueue,l.queued);}
  events.push({kind:'offer',direction:l.direction,packet:id,at_ms:now,payload_bytes:msg.length,wire_bytes:wire,dropped:drop,queue_before_wire_bytes:before,queue_after_wire_bytes:l.queued});
 };
 pb.on('message',(msg,from)=>receive(ab,msg,from,a.port));pa.on('message',(msg,from)=>receive(ba,msg,from,b.port));
 tick=setInterval(()=>{const now=performance.now();for(const l of links)pumpLink(l,now);},1);
 return {a_proxy_port:pa.address().port,b_proxy_port:pb.address().port};
}

const routes=new Set(['frame_marker.mjs','source_quality.mjs','dense_actuation.mjs','encoder_response.mjs','actuator_meter.mjs','actuator_control.mjs','sender_observation.mjs','repair3_policy.mjs','native_actuation.mjs']);
const server=createServer(async(req,res)=>{try{
 const name=req.url.slice(1);
 if(routes.has(name)){res.setHeader('Content-Type','text/javascript');res.end(await readFile(path.join(assets,name),'utf8'));}
 else if(req.url==='/config'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({...trial,ice_server:{urls:`turn:127.0.0.1:${turnPort}?transport=tcp`,username,credential}}));}
 else if(req.url==='/relay'){let body='';for await(const data of req)body+=data;const peers=JSON.parse(body);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(await startRelay(peers.a,peers.b)));}
 else if(req.url==='/phase'){let body='';for await(const data of req)body+=data;const next=JSON.parse(body).capacity;if(!Number.isFinite(next)||next<=0||next>4)throw Error('invalid capacity');const now=performance.now();for(const link of links)pumpLink(link,now);events.push({kind:'phase',at_ms:now,capacity_mbps:next});capacity=next;res.end('{}');}
 else{res.setHeader('Content-Type','text/html');res.end(await readFile(path.join(assets,'turn_probe_page.html'),'utf8'));}
 }catch(error){res.statusCode=400;res.end(JSON.stringify({error:String(error)}));}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
const flags=['--headless=new','--no-sandbox','--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--autoplay-policy=no-user-gesture-required','about:blank'];
const chrome=spawn('/usr/bin/chromium',flags,{stdio:['ignore','ignore','pipe']});let errors='',ws;chrome.stderr.on('data',d=>{errors=(errors+d).slice(-4000);});
try{
 let port;for(let k=0;k<100;k++){try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await new Promise(r=>setTimeout(r,100));}}
 if(!port)throw Error('DevTools unavailable: '+errors);
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(origin),{method:'PUT'})).json();ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let next=0;const pending=new Map();ws.onmessage=e=>{const d=JSON.parse(e.data);if(pending.has(d.id)){const {r,j,timer}=pending.get(d.id);clearTimeout(timer);pending.delete(d.id);d.error?j(Error(JSON.stringify(d.error))):r(d.result);}};
 const call=(method,params,timeout=15000)=>new Promise((r,j)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);j(Error('bounded CDP timeout'));},timeout);pending.set(id,{r,j,timer});ws.send(JSON.stringify({id,method,params}));});
 let ready=false;for(let k=0;k<60;k++){const value=await call('Runtime.evaluate',{expression:'typeof run',returnByValue:true});if(value.result.value==='function'){ready=true;break;}await new Promise(r=>setTimeout(r,100));}
 if(!ready)throw Error('native probe page failed to initialize');
 const value=await call('Runtime.evaluate',{expression:'run()',awaitPromise:true,returnByValue:true},90000);if(value.exceptionDetails)throw Error(JSON.stringify(value.exceptionDetails));
 const result=value.result.value;
 const build=await(await fetch('http://127.0.0.1:'+port+'/json/version')).json();
 stopped=true;if(tick){clearInterval(tick);tick=undefined;}for(const socket of relaySockets)socket.close();relaySockets=[];
 result.relay=ledger();result.node_time_origin_epoch_ms=performance.timeOrigin;result.browser_build=build.Browser;
 if(result.connection!=='connected'||!result.transport_cc_negotiated||!result.snapshots.every(s=>s.remote_candidate_address==='127.0.0.1'&&s.frames_decoded>10)||links.some(l=>l.unexpected)||!result.relay.a_to_b.capacity_integral_upper_bound_ok||!result.relay.b_to_a.capacity_integral_upper_bound_ok)throw Error('native path/progress/capacity qualification failed');
 const text=JSON.stringify(result)+'\n';await writeFile(root+'/peer.json',text,{flag:'wx'});
 const raw=gzipSync(events.map(e=>JSON.stringify(e)).join('\n')+'\n');await writeFile(root+'/events.jsonl.gz',raw,{flag:'wx'});
 const snapshot={trial,peer_sha256:createHash('sha256').update(text).digest('hex'),events_sha256:createHash('sha256').update(raw).digest('hex'),browser:result.browser_build,controller_promoted:false,native_counterfactuals:false,policy_modified:false,complete:true};await writeFile(root+'/manifest.json',JSON.stringify(snapshot,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({trial:trial.id,samples:result.decisions.length,encoded_frames:result.encoded_meter.events.length,requests:result.sources.length,readbacks:result.observations.length,browser:result.browser_build}));
}finally{
 ws?.close();stopped=true;if(tick)clearInterval(tick);for(const socket of relaySockets)socket.close();server.closeAllConnections();await new Promise(r=>server.close(r));
 for(const process of [chrome,turn]){process.kill('SIGTERM');await new Promise(r=>{if(process.exitCode!==null)r();else{process.once('exit',r);setTimeout(()=>{process.kill('SIGKILL');r();},3000).unref();}});}
 await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
