// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.
import {createServer} from 'node:http';
import {createSocket} from 'node:dgram';
import {networkInterfaces} from 'node:os';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,writeFile,mkdir,rm,copyFile} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';

// Additive public collector. Historical .tools drivers and sealed captures remain untouched.
const root=process.argv[2],panelPath=process.argv[3],episodeId=process.argv[4],conditionId=process.argv[5];
if(!root||!panelPath||!episodeId||!conditionId)throw Error('fresh root, frozen panel, trial and condition required');
const panelText=await readFile(panelPath,'utf8'),panel=JSON.parse(panelText),episode=panel.episodes.find(e=>e.id===episodeId),condition=panel.conditions[conditionId];
if(panel.panel_abi!=='native_reliability_study_v1'||!condition||!['rlcd','bwe','fixed'].includes(condition.controller)||!episode||episode.role!==panel.stage||!['repeatability','calibration','validation','test'].includes(panel.stage)||panel.common_shadow_inference!==true||panel.SOTA_achieved!==false||!Number.isInteger(episode.scene_seed)||episode.scene_seed<0||episode.scene_seed>64500||episode.schedule.length!==3||episode.schedule.some(([c,label,ms])=>!Number.isFinite(c)||c<=0||c>4||!['high','collapse','recovery'].includes(label)||!Number.isInteger(ms)||ms<1000||ms>6000))throw Error('invalid frozen native study trial');
const assetDir=path.dirname(import.meta.filename),controller=condition.controller,nativeMode='min-jitter',allModels={},commonModelHashes={};
for(const [key,entry] of Object.entries(panel.models)){
 if(!/^[a-z][a-z0-9_-]{0,39}$/.test(key))throw Error('unsafe model key');
 const text=await readFile(entry.path,'utf8'),bundle=JSON.parse(text),sha=createHash('sha256').update(text).digest('hex');
 if(sha!==entry.sha256||bundle.risk_cutoff!==0.5||bundle.disagreement_cutoff!==0.2)throw Error('frozen native model/screens changed');
 allModels[key]=bundle;commonModelHashes[key]=sha;
}
const model=allModels[condition.model],modelSha=commonModelHashes[condition.model];
if(!model)throw Error('missing native model');
const collectionConfig={panel_abi:panel.panel_abi,panel_sha256:createHash('sha256').update(panelText).digest('hex'),...episode};
await mkdir(root,{recursive:false});
await copyFile(import.meta.filename,root+'/source_snapshot.mjs');
for(const file of ['frame_marker.mjs','native_actuation.mjs','sender_observation.mjs','source_quality.mjs','bwe_cap_controller.mjs','native_policy.mjs'])await copyFile(path.join(assetDir,file),root+'/'+file);
if(panel.source_kind==='recorded_video_v1'){for(const [name,sha] of Object.entries(panel.extra_source_sha256)){const file=name.startsWith('assets/')?path.join(assetDir,name.split('/')[1]):null;if(file){if(createHash('sha256').update(await readFile(file)).digest('hex')!==sha)throw Error('recorded source implementation changed');await copyFile(file,root+'/'+name.split('/')[1]);}}}
await copyFile(panelPath,root+'/panel_snapshot.json');
for(const [key,entry] of Object.entries(panel.models))await copyFile(entry.path,root+'/model_'+key+'.json');
await copyFile(panel.models[condition.model].path,root+'/model.json');
await writeFile(root+'/all_models.json',JSON.stringify(allModels)+'\n');

const profile=await mkdtemp(path.join(tmpdir(),'rlcd-native-rtc-'));
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
  if(!localIPs.has(from.address)||from.port!==expectedPort){l.unexpected++;return;}
  const now=performance.now();pumpLink(l,now);const wire=msg.length+28,before=l.queued,id=nextPacket++,drop=before+wire>queueLimit;l.offered+=wire;
  if(drop){l.dropped+=wire;l.drops++;}else{l.queue.push({data:Buffer.from(msg),wire,remaining:wire,id});l.queued+=wire;l.maxQueue=Math.max(l.maxQueue,l.queued);}
  events.push({kind:'offer',direction:l.direction,packet:id,at_ms:now,payload_bytes:msg.length,wire_bytes:wire,dropped:drop,queue_before_wire_bytes:before,queue_after_wire_bytes:l.queued});
 };
 pb.on('message',(msg,from)=>receive(ab,msg,from,a.port));pa.on('message',(msg,from)=>receive(ba,msg,from,b.port));
 tick=setInterval(()=>{const now=performance.now();for(const l of links)pumpLink(l,now);},1);
 return {a_proxy_port:pa.address().port,b_proxy_port:pb.address().port};
}
const html=String.raw`<!doctype html><meta charset="utf-8"><canvas id="c" width="640" height="360"></canvas><video id="v" autoplay muted playsinline></video><script type="module">
import {FRAME_PROTOCOL,writeFrameMarker,readFrameMarker} from '/frame-marker.mjs';
import {applyNativeAction} from '/native-actuation.mjs';
import {OBSERVATION_PROTOCOL,selectSenderSource,SenderObservationEncoder} from '/sender_observation.mjs';
import {QUALITY_PROTOCOL,drawSourceScene,samplePairedQuality} from '/source_quality.mjs';
import {BWE_CAP_PROTOCOL,chooseBweCapAction} from '/bwe_cap_controller.mjs';
import {NativePolicyController} from '/native_policy.mjs';
const recordedModule=await(await fetch('/native-mode')).json();const recorded=recordedModule.source_kind==='recorded_video_v1'?await import('/recorded_video.mjs'):null;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
globalThis.run=async function(){
 const nativeConfig=await(await fetch('/native-mode')).json();
 const modelBundles=await(await fetch('/all-models.json')).json(),actors=Object.fromEntries(Object.entries(modelBundles).map(([key,bundle])=>[key,new NativePolicyController(bundle)]));
 const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');let n=0,currentPhase='pre_connection';
 const movie=recorded?await recorded.loadRecordedVideo(nativeConfig):null,sourceReferences=new Map();
 const sources=[],observations=[],sourceTimes=new Map();let readErrors=0,observing=true,callbackHandle;
let currentDecisionId=null,actionInFlight=false,lastApplied=null;
 const stream=canvas.captureStream(0),capture=stream.getVideoTracks()[0],a=new RTCPeerConnection(),b=new RTCPeerConnection();
 if(typeof capture.requestFrame!=='function')throw Error('manual canvas capture unsupported');
 const draw=()=>{n++;let sourceReference={};if(movie){sourceReference=movie.draw(ctx);sourceReferences.set(n,sourceReference.reference_rgb);}else drawSourceScene(ctx,n+nativeConfig.scene_seed);writeFrameMarker(ctx,n);const born=performance.now();sourceTimes.set(n,born);sources.push({source_id:n,capture_request_ms:born,...sourceReference,phase:currentPhase,decision_id:currentDecisionId,action_transition_inflight:actionInFlight,encoder_cap_bps:lastApplied?.encoder_max_bitrate_bps??null,receiver_target_ms:lastApplied?.receiver_jitter_buffer_target_ms??null});capture.requestFrame();};draw();
 const timer=setInterval(draw,1000/30);let receiverTrack=false;const video=document.getElementById('v');
 const readback=document.createElement('canvas');readback.width=640;readback.height=360;const readctx=readback.getContext('2d',{willReadFrequently:true});
 const reference=document.createElement('canvas');reference.width=640;reference.height=360;const refctx=reference.getContext('2d',{willReadFrequently:true});
if(typeof video.requestVideoFrameCallback!=='function')throw Error('native frame callback unsupported');
 const inspect=(callbackTime,meta)=>{if(!observing)return;try{readctx.drawImage(video,0,0,640,360);const marker=readFrameMarker(readctx),readTime=performance.now(),known=marker.source_id!==null&&sourceTimes.has(marker.source_id);let quality=null;if(known){if(movie)quality=recorded.pairRecordedQuality(readctx,sourceReferences.get(marker.source_id));else{drawSourceScene(refctx,marker.source_id+nativeConfig.scene_seed);quality=samplePairedQuality(readctx,refctx);}}observations.push({...marker,known_source:known,quality,callback_ms:callbackTime,readback_ms:readTime,expected_display_ms:meta.expectedDisplayTime,presented_frames:meta.presentedFrames,media_time:meta.mediaTime,video_width:video.videoWidth,video_height:video.videoHeight});}catch(error){readErrors++;observations.push({read_error:String(error),callback_ms:callbackTime,readback_ms:performance.now()});}callbackHandle=video.requestVideoFrameCallback(inspect);};
 b.ontrack=e=>{receiverTrack=true;video.srcObject=e.streams[0];video.play();callbackHandle=video.requestVideoFrameCallback(inspect);};
 const candidatesA=[],candidatesB=[];
 a.onicecandidate=e=>{if(e.candidate)candidatesA.push(e.candidate);};
 b.onicecandidate=e=>{if(e.candidate)candidatesB.push(e.candidate);};
 const strip=s=>s.split('\r\n').filter(l=>!l.startsWith('a=candidate:')&&!l.startsWith('a=end-of-candidates')).join('\r\n');
 const sender=a.addTrack(stream.getVideoTracks()[0],stream);
 const caps=RTCRtpSender.getCapabilities('video').codecs;
 const vp8=caps.filter(c=>c.mimeType.toLowerCase()==='video/vp8');if(vp8.length)a.getTransceivers()[0].setCodecPreferences(vp8);
 await a.setLocalDescription(await a.createOffer());await b.setRemoteDescription({type:'offer',sdp:strip(a.localDescription.sdp)});
 await b.setLocalDescription(await b.createAnswer());await a.setRemoteDescription({type:'answer',sdp:strip(b.localDescription.sdp)});
 for(let i=0;i<60&&(a.iceGatheringState!=='complete'||b.iceGatheringState!=='complete');i++)await sleep(100);
 const pick=cs=>cs.find(c=>c.protocol==='udp'&&c.type==='host'&&/^\d+\.\d+\.\d+\.\d+$/.test(c.address));
 const ca=pick(candidatesA),cb=pick(candidatesB);if(!ca||!cb)throw Error('no local IPv4 ICE candidates; do not bypass relay');
 const relay=await(await fetch('/relay',{method:'POST',body:JSON.stringify({a:{address:ca.address,port:ca.port},b:{address:cb.address,port:cb.port}})})).json();if(relay.error)throw Error(relay.error);
 const rewrite=(c,port)=>{const words=c.candidate.split(' ');words[4]='127.0.0.1';words[5]=String(port);return {candidate:words.join(' '),sdpMid:c.sdpMid,sdpMLineIndex:c.sdpMLineIndex};};
 await b.addIceCandidate(rewrite(ca,relay.a_proxy_port));await a.addIceCandidate(rewrite(cb,relay.b_proxy_port));
 for(let i=0;i<80&&a.connectionState!=='connected';i++)await sleep(100);
 if(a.connectionState!=='connected')throw Error('native RTC did not connect: '+a.connectionState);
 const snapshots=[];let lastTx=0,lastRx=0,last=performance.now();
 if(movie)await movie.start();
 const measurementStart=performance.now();
 const receiver=b.getReceivers().find(r=>r.track.kind==='video');
 const actuation=await applyNativeAction(sender,receiver,{encoder_max_bitrate_bps:4000000,receiver_jitter_buffer_target_ms:nativeConfig.mode==='min-jitter'?0:null});
lastApplied=actuation;
let collecting=true;const encoder=new SenderObservationEncoder(),decisions=[],samplingErrors=[];
const sampleTask=(async()=>{try{while(collecting){const stats=await a.getStats();if(!collecting)break;const own={encoder_max_bitrate_bps:sender.getParameters().encodings[0].maxBitrate,receiver_jitter_buffer_target_ms:actuation.native_jitter_target_supported?receiver.jitterBufferTarget:null};const observation=encoder.observe(selectSenderSource(stats,own),performance.now());const policyInput={observation_abi:observation.observation_abi,feature_names:observation.feature_names,features:observation.features};const commonStart=performance.now(),all_policy_decisions={},model_inference_ms={};for(const [key,actor] of Object.entries(actors)){const before=performance.now();all_policy_decisions[key]=actor.observe(policyInput);model_inference_ms[key]=performance.now()-before;}const total_inference_ms=performance.now()-commonStart,policyDecision=all_policy_decisions[nativeConfig.active_model],inference_ms=model_inference_ms[nativeConfig.active_model];const proposed=nativeConfig.controller==='rlcd'?{encoder_max_bitrate_bps:policyDecision.encoder_max_bitrate_bps,receiver_jitter_buffer_target_ms:policyDecision.receiver_jitter_buffer_target_ms}:nativeConfig.controller==='bwe'?chooseBweCapAction(policyInput):own;let actual=lastApplied;const changed=proposed.encoder_max_bitrate_bps!==own.encoder_max_bitrate_bps||proposed.receiver_jitter_buffer_target_ms!==own.receiver_jitter_buffer_target_ms;if(changed){actionInFlight=true;try{actual=await applyNativeAction(sender,receiver,proposed);}finally{actionInFlight=false;}}const step_id=decisions.length,ack_ms=performance.now();decisions.push({step_id,observation,policy_decision:policyDecision,inference_ms,all_policy_decisions,model_inference_ms,total_inference_ms,proposed_action:proposed,actuation_readback:actual,changed,ack_ms});currentDecisionId=step_id;lastApplied=actual;await sleep(OBSERVATION_PROTOCOL.poll_ms);}}catch(error){samplingErrors.push(String(error));collecting=false;}})();
 for(const [capacity,label,duration] of nativeConfig.schedule){
  await fetch('/phase',{method:'POST',body:JSON.stringify({capacity})});currentPhase=label;await sleep(duration);
  const tx=[...(await a.getStats()).values()],rx=[...(await b.getStats()).values()];
  const sent=tx.find(x=>x.type==='outbound-rtp'&&x.kind==='video'),received=rx.find(x=>x.type==='inbound-rtp'&&x.kind==='video');
  const transport=tx.find(x=>x.type==='transport'&&x.selectedCandidatePairId);const pair=tx.find(x=>x.id===transport?.selectedCandidatePairId)??tx.find(x=>x.type==='candidate-pair'&&x.nominated&&x.state==='succeeded');
  const remote=tx.find(x=>x.id===pair?.remoteCandidateId),codec=tx.find(x=>x.id===sent.codecId),now=performance.now();
  const network=await(await fetch('/ledger')).json();
  snapshots.push({phase:label,capacity_mbps:capacity,encoder_cap_bps:sender.getParameters().encodings[0].maxBitrate,interval_ms:now-last,sent_mbps:(sent.bytesSent-lastTx)*8/(now-last)/1000,received_mbps:(received.bytesReceived-lastRx)*8/(now-last)/1000,
    frames_encoded:sent.framesEncoded,frames_decoded:received.framesDecoded,packets_lost:received.packetsLost,jitter_s:received.jitter,
    codec:codec.mimeType,available_outgoing_bitrate_bps:pair?.availableOutgoingBitrate??null,rtt_s:pair?.currentRoundTripTime??null,remote_candidate_address:remote?.address??remote?.ip??null,
    mean_encode_s:sent.totalEncodeTime/sent.framesEncoded,mean_native_jitter_buffer_s:received.jitterBufferEmittedCount?received.jitterBufferDelay/received.jitterBufferEmittedCount:null,mean_native_jitter_buffer_target_s:received.jitterBufferEmittedCount?received.jitterBufferTargetDelay/received.jitterBufferEmittedCount:null,freeze_count:received.freezeCount??null,freeze_duration_s:received.totalFreezesDuration??null,network});
  lastTx=sent.bytesSent;lastRx=received.bytesReceived;last=now;
 }
 const cutoff=performance.now();clearInterval(timer);observing=false;if(callbackHandle!==undefined)video.cancelVideoFrameCallback(callbackHandle);
 collecting=false;await sampleTask;
if(samplingErrors.length||decisions.length<30)throw Error('unqualified sender collection: '+JSON.stringify(samplingErrors));
const frameEvidence={protocol:FRAME_PROTOCOL,quality_protocol:movie?recorded.VIDEO_QUALITY_PROTOCOL:QUALITY_PROTOCOL,...(movie?{video_source:{sha256:movie.sha256,segment:movie.segment,geometry:'center_crop_fill_640x360'}}:{}),scene_seed:nativeConfig.scene_seed,time_origin_epoch_ms:performance.timeOrigin,measurement_start_ms:measurementStart,measurement_cutoff_ms:cutoff,sources,observations,read_errors:readErrors};
const senderEvidence={protocol:OBSERVATION_PROTOCOL,controller:nativeConfig.controller==='rlcd'?{controller:'native_rlcd_cql_v1',model_sha256:nativeConfig.model_sha256,risk_cutoff:nativeConfig.risk_cutoff,disagreement_cutoff:nativeConfig.disagreement_cutoff}:nativeConfig.controller==='bwe'?BWE_CAP_PROTOCOL:{controller:'native_fixed_cap_v1',cap_bps:4000000},measurement_start_ms:measurementStart,measurement_cutoff_ms:cutoff,decisions,sampling_errors:samplingErrors,learned_policy:nativeConfig.controller==='rlcd',model_sha256:nativeConfig.model_sha256,common_shadow_inference:true,common_models_sha256:nativeConfig.common_models_sha256};
 const result={native_rtc:true,local_loopback_only:true,userspace_relay_only:true,source:movie?'recorded live-action/VFX movie (not a representative corpus)':'generated canvas pattern',browser_user_agent:navigator.userAgent,connection:a.connectionState,
   transport_cc_negotiated:a.localDescription.sdp.includes('transport-cc'),receiver_track_present:receiverTrack,snapshots,frame_evidence:frameEvidence,sender_evidence:senderEvidence,native_actuation:{mode:nativeConfig.mode,...actuation},native_controller:nativeConfig.controller,collection_config:nativeConfig.collection_config,
   limitations:['Userspace datagram relay is not kernel netem, an Internet path or representative content.','Role-declared repeated native synthetic peers; no representative measured-link, published learned-peer, deployment or SOTA evidence.','Scalar encoder maxBitrate changes are not FEC/codec-mode actuation.','Pixel-ID application deadlines and sampled synthetic RGB PSNR are not physical capture/scan-out, human QoE or SOTA evidence.']};
 if(movie)movie.stop();
 stream.getTracks().forEach(t=>t.stop());a.close();b.close();return result;
}
</script>`;
const moduleRoutes=new Set(['/recorded_video.mjs','/native_actuation.mjs','/sender_observation.mjs','/source_quality.mjs','/bwe_cap_controller.mjs','/native_policy.mjs']);
const server=createServer(async(req,res)=>{try{if(moduleRoutes.has(req.url)){res.setHeader('Content-Type','text/javascript');res.end(await readFile(root+req.url,'utf8'));}else if(req.url==='/recorded-video.mp4'&&panel.source_kind==='recorded_video_v1'){res.setHeader('Content-Type','video/mp4');createReadStream(path.join(root,'../recorded-video.mp4')).pipe(res);}else if(req.url==='/all-models.json'){res.setHeader('Content-Type','application/json');res.end(await readFile(root+'/all_models.json','utf8'));}else if(req.url==='/model.json'){res.setHeader('Content-Type','application/json');res.end(await readFile(root+'/model.json','utf8'));}else if(req.url==='/native-mode'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({mode:nativeMode,controller,active_model:condition.model,model_sha256:modelSha,common_models_sha256:commonModelHashes,risk_cutoff:model.risk_cutoff,disagreement_cutoff:model.disagreement_cutoff,scene_seed:episode.scene_seed,source_kind:panel.source_kind,video_segment:episode.video_segment??null,video_sha256:panel.video_source?.sha256??null,schedule:episode.schedule,collection_config:collectionConfig}));}else if(req.url==='/native-actuation.mjs'){res.setHeader('Content-Type','text/javascript');res.end(await readFile(root+'/native_actuation.mjs','utf8'));}else if(req.url==='/frame-marker.mjs'){res.setHeader('Content-Type','text/javascript');res.end(await readFile(root+'/frame_marker.mjs','utf8'));}else if(req.url==='/relay'){let text='';for await(const data of req)text+=data;const data=JSON.parse(text);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(await startRelay(data.a,data.b)));}else if(req.url==='/phase'){let text='';for await(const data of req)text+=data;const next=JSON.parse(text).capacity;if(!Number.isFinite(next)||next<=0||next>10)throw Error('invalid capacity');const now=performance.now();for(const l of links)pumpLink(l,now);events.push({kind:'phase',at_ms:now,capacity_mbps:next});capacity=next;res.end('{}');}else if(req.url==='/ledger'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(ledger()));}else{res.setHeader('Content-Type','text/html');res.end(html);}}catch(error){res.statusCode=400;res.end(JSON.stringify({error:String(error)}));}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const url='http://127.0.0.1:'+server.address().port;
const chrome=spawn(process.env.RLCD_CHROME||(process.platform==='darwin'?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':'google-chrome'),['--headless=new','--disable-features=WebRtcHideLocalIpsWithMdns','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--metrics-recording-only','--autoplay-policy=no-user-gesture-required','about:blank'],{stdio:['ignore','ignore','pipe']});
let spawnError;chrome.once('error',error=>{spawnError=error;});let errors='';chrome.stderr.on('data',d=>{errors=(errors+d).slice(-4000);});
let ws;
try{
 let port;
 for(let i=0;i<100;i++){if(spawnError)throw spawnError;try{port=Number((await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await new Promise(r=>setTimeout(r,100));}}
 if(!port)throw Error('DevTools unavailable '+errors);
 const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(url),{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{const timeout=setTimeout(()=>j(Error('CDP connect timeout')),10000);ws.onopen=()=>{clearTimeout(timeout);r();};ws.onerror=error=>{clearTimeout(timeout);j(error);};});
 let next=1;const pending=new Map();ws.onmessage=e=>{const d=JSON.parse(e.data);if(pending.has(d.id)){const {resolve,reject,timer}=pending.get(d.id);clearTimeout(timer);pending.delete(d.id);d.error?reject(Error(JSON.stringify(d.error))):resolve(d.result);}};
 ws.onclose=()=>{for(const {reject,timer} of pending.values()){clearTimeout(timer);reject(Error('CDP disconnected'));}pending.clear();};
 const call=(method,params={},timeoutMs=15000)=>new Promise((resolve,reject)=>{const id=next++,timer=setTimeout(()=>{pending.delete(id);reject(Error('bounded CDP timeout: '+method));},timeoutMs);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
 let pageReady=false;for(let i=0;i<30;i++){const state=await call('Runtime.evaluate',{expression:'typeof run',returnByValue:true});if(state.result.value==='function'){pageReady=true;break;}await new Promise(r=>setTimeout(r,100));}if(!pageReady)throw Error('frame marker module did not initialize');
 const answer=await call('Runtime.evaluate',{expression:'run()',awaitPromise:true,returnByValue:true},panel.episode_timeout_s*1000);
 if(answer.exceptionDetails)throw Error(JSON.stringify(answer.exceptionDetails));
 const result=answer.result.value;
 const senderEvidence=result.sender_evidence;delete result.sender_evidence;await writeFile(root+'/sender_observations.json',JSON.stringify(senderEvidence)+String.fromCharCode(10));result.native_observation_protocol=senderEvidence.protocol;result.sender_decisions=senderEvidence.decisions.length;result.learned_policy_loaded=senderEvidence.learned_policy;result.frozen_native_model_sha256=modelSha;result.common_shadow_inference=true;
const frameEvidence=result.frame_evidence;delete result.frame_evidence;
 await writeFile(root+'/frame_events.json',JSON.stringify(frameEvidence)+String.fromCharCode(10));
 result.frame_protocol=frameEvidence.protocol;result.source_frame_requests=frameEvidence.sources.length;result.receiver_frame_readbacks=frameEvidence.observations.length;
 const build=await(await fetch('http://127.0.0.1:'+port+'/json/version')).json();
 result.browser_build=build.Browser;result.protocol_version=build['Protocol-Version'];
 result.relay=ledger();
 if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');
 result.raw_event_count=events.length;
 const raw=gzipSync(events.map(e=>JSON.stringify(e)).join(String.fromCharCode(10))+String.fromCharCode(10));
 await writeFile(root+'/events.jsonl.gz',raw);
 if(!result.snapshots.every(s=>s.remote_candidate_address==='127.0.0.1')||result.relay.a_to_b.forwarded_packets<100)throw Error('media bypassed relay or did not progress');
 if(!result.relay.a_to_b.capacity_integral_upper_bound_ok||!result.relay.b_to_a.capacity_integral_upper_bound_ok)throw Error('service exceeded capacity integral');
 if(!result.native_rtc||result.connection!=='connected'||!result.snapshots.every(s=>s.frames_decoded>10&&s.frames_encoded>10&&Number.isFinite(s.mean_encode_s)))throw Error('native media stats not valid');
 await writeFile(root+'/summary.json',JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result));
}finally{
 ws?.close();chrome.kill('SIGTERM');await new Promise(r=>{if(!chrome.pid||chrome.exitCode!==null)r();else{chrome.once('exit',r);setTimeout(()=>{chrome.kill('SIGKILL');r();},3000).unref();}});
 stopped=true;if(tick)clearInterval(tick);for(const s of relaySockets)s.close();
 server.closeAllConnections();await new Promise(r=>server.close(r));await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
