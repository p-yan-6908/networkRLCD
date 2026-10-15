// M8 fixed network-service conditioning, derived from the frozen M4R collector.
// Derived from unchanged V13; all native clock/transport/support/cleanup limits retained.
// The Node UDP queue appears peer-reflexive locally after the relay candidate is rewritten to its owned socket.
import {createServer} from 'node:http';
import {createServer as tcpServer,createConnection} from 'node:net';
import {createSocket} from 'node:dgram';
import {networkInterfaces} from 'node:os';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,writeFile,appendFile,mkdir,rm,copyFile} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash,randomBytes} from 'node:crypto';
import {verifiedMovie} from '../native_rtc/repair_http.mjs';
// Support only: fixed encoder cap, causal BWE feedback changes owned network service.
const root=process.argv[2],panelPath=process.argv[3],episodeId=process.argv[4],conditionId=process.argv[5];
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const turnBinary=process.env.RLCD_TURN_BINARY;
if(!root||!panelPath||!episodeId||!conditionId||!turnBinary)throw Error('fresh root, frozen panel, trial, condition and RLCD_TURN_BINARY required');
const panelText=await readFile(panelPath,'utf8'),panel=JSON.parse(panelText),episode=panel.episodes.find(e=>e.id===episodeId),condition=panel.conditions[conditionId];
const micro=condition?.controller==='micro'&&condition.behavior==='ratio-randomized'&&condition.level===null;
if(panel.panel_abi!=='native_clock_action_probe_v1'||panel.source_kind!=='recorded_video_v1'||panel.repair_model!==null||!micro||!episode||episode.role!==panel.stage||panel.stage!=='discovery'||panel.common_shadow_inference!==true||panel.SOTA_achieved!==false||!Number.isInteger(episode.content_index)||episode.content_index<0||episode.content_index>3||!Number.isInteger(episode.action_randomization_seed)||episode.action_randomization_seed<0||episode.action_randomization_seed>0xffffffff||episode.schedule.length!==3||episode.schedule.some(([c,label,ms,trace],i)=>!Number.isFinite(c)||c<0||c>10||!['block_0','block_1','block_2'].includes(label)||!Number.isInteger(ms)||ms<1000||ms!==[10000,96000,12600][i]||!Array.isArray(trace)||trace.length!==[10,1,12][i]||trace.some(value=>!Number.isFinite(value)||value<0||value>10)))throw Error('invalid frozen M8 support-only conditioning trial');
const initialBweKbps=episode.support_initial_bwe_kbps;
if(initialBweKbps!==1200||episode.support_config?.support_only!==true)throw Error('M8 requires exact initialization and support-only capture');
if(!['[0.5,1.5,0.5,1.5]','[1.5,1.5,0.5,1.5]'].includes(JSON.stringify(episode.system_id_sequence_mbps))||episode.video_segment[1]!==130000)throw Error('unregistered M8 sequence/source segment');
const assetDir=path.resolve(path.dirname(import.meta.filename),'../native_rtc'),controller=condition.controller,nativeMode='min-jitter',allModels={},commonModelHashes={};
const model={risk_cutoff:0.5,disagreement_cutoff:0.2},modelSha=null,repairBundle=null,repairSha=null;
const movieServer=await verifiedMovie(panel.video_source.path,panel.video_source.sha256);
const collectionConfig={panel_abi:panel.panel_abi,panel_sha256:createHash('sha256').update(panelText).digest('hex'),...episode};
await mkdir(root,{recursive:false});
await copyFile(import.meta.filename,root+'/source_snapshot.mjs');
for(const file of ['native_bwe_hold_control.mjs','frame_marker.mjs','native_actuation.mjs','sender_observation.mjs','source_quality.mjs','bwe_cap_controller.mjs','native_policy.mjs','range_control.mjs','actuator_control.mjs','actuator_meter.mjs','encoder_response.mjs','dense_control.mjs','excitation_control.mjs','dense_actuation.mjs','streamed_actuator_video.mjs','fixed_encoder5.mjs','repair5_policy.mjs','repair3_policy.mjs','streamed_video5.mjs','streamed_video.mjs','recorded_video.mjs'])await copyFile(path.join(assetDir,file),root+'/'+file);
await copyFile(path.join(assetDir,'../native_v13/native_continuous_support_v13.mjs'),root+'/native_continuous_support_v13.mjs');
await copyFile(path.join(assetDir,'../native_m8/system_id_support_m8.mjs'),root+'/system_id_support_m8.mjs');
await copyFile(panelPath,root+'/panel_snapshot.json');
await writeFile(root+'/all_models.json','{}\n');
await writeFile(root+'/repair_model.json','null\n');

const work=await mkdtemp(path.join(tmpdir(),'n2'));
const profile=path.join(work,'c');
const turnConfigPath=path.join(work,'turn.conf'),turnLogPath=path.join(work,'turn.log');
const turnPidPath=path.join(work,'turn.pid');
const turnPort=await (async()=>{for(let attempt=0;attempt<20;attempt++){const server=tcpServer();await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});const port=server.address().port;await new Promise(resolve=>server.close(resolve));if(port<49160||port>49260)return port;}throw Error('could not reserve a TCP TURN port outside the relay range');})();
const turnUsername='action-'+randomBytes(8).toString('hex'),turnCredential=randomBytes(24).toString('hex');
const turnUrl=`turn:127.0.0.1:${turnPort}?transport=tcp`;
const policyPath='/etc/chromium/policies/managed/misc.json';
const policyBytesBefore=await readFile(policyPath),policyBefore=JSON.parse(policyBytesBefore).WebRtcIPHandling;
const turnBinarySha256=createHash('sha256').update(await readFile(turnBinary)).digest('hex');
const turnLibraryDir=process.env.RLCD_TURN_LIBRARY_DIR||path.dirname(turnBinary);
const turnRuntime={abi:'native_action_turn_tcp_runtime_v1',binary_sha256:turnBinarySha256,
 turn_version:'4.6.1',control_transport:'TCP',relay_transport:'UDP',turn_url:turnUrl,
 server_config:{listen_ip:'127.0.0.1',relay_ip:'127.0.0.1',relay_port_range:[49160,49260],
  browser_udp_listener_disabled:true,tcp_relay_disabled:true,loopback_peers_only:true},
 browser_policy:{path:policyPath,WebRtcIPHandling:policyBefore,
  sha256_before:createHash('sha256').update(policyBytesBefore).digest('hex'),modified:false}};
if(policyBefore!=='disable_non_proxied_udp')throw Error('managed Chromium WebRtcIPHandling policy differs from the registered transport condition');
await writeFile(turnConfigPath,[`listening-port=${turnPort}`,'listening-ip=127.0.0.1','relay-ip=127.0.0.1',
 'realm=networkrlcd.local','lt-cred-mech',`user=${turnUsername}:${turnCredential}`,'fingerprint',
 'no-tls','no-dtls','no-udp','no-tcp-relay','no-cli','no-daemon','relay-threads=1',
 'min-port=49160','max-port=49260','allow-loopback-peers',
 'denied-peer-ip=0.0.0.0-255.255.255.255','allowed-peer-ip=127.0.0.1',
 `pidfile=${turnPidPath}`,`log-file=${turnLogPath}`].join('\n')+'\n',{mode:0o600});
await writeFile(root+'/turn_runtime.json',JSON.stringify(turnRuntime,null,2)+'\n',{flag:'wx'});
const turnServer=spawn(turnBinary,['-c',turnConfigPath],{stdio:['ignore','ignore','ignore']});
for(let attempt=0;attempt<100;attempt++){
 if(turnServer.exitCode!==null)throw Error('TURN/TCP server exited before listening');
 const ready=await new Promise(resolve=>{const socket=createConnection({host:'127.0.0.1',port:turnPort});socket.once('connect',()=>{socket.destroy();resolve(true);});socket.once('error',()=>{socket.destroy();resolve(false);});});
 if(ready)break;
 if(attempt===99)throw Error('TURN/TCP server did not become ready');
 await new Promise(resolve=>setTimeout(resolve,50));
}
const localIPs=new Set(['127.0.0.1',...Object.values(networkInterfaces()).flat().filter(x=>x?.family==='IPv4').map(x=>x.address)]);
let relaySockets=[],links=[],tick,stopped=false,capacity=5,traceTimers=[];
const delayMs=25,queueLimit=30000;
const events=[];let nextPacket=0;
function pumpLink(l,now){
 const from=l.last,before=l.queued,oldServed=l.served;let budget=(now-from)*capacity*125;
 l.capacityBytes+=budget;l.last=now;
 while(budget>1e-9&&l.queue.length){
  const p=l.queue[0],used=Math.min(p.remaining,budget);p.remaining-=used;l.queued-=used;l.served+=used;budget-=used;
  if(p.remaining<1e-9){
   l.queue.shift();l.servedPackets++;const complete=now,due=now+delayMs;
   const forward=()=>{if(stopped)return;const wait=due-performance.now();if(wait>0){setTimeout(forward,Math.max(1,wait));return;}
    events.push({kind:'forward',direction:l.direction,packet:p.id,at_ms:performance.now(),serialization_done_ms:complete,wire_bytes:p.wire});
    l.sender.send(p.data,l.destination.port,l.destination.address,err=>{if(err)l.errors++;else{l.forwarded++;l.forwardedWire+=p.wire;}});
   };setTimeout(forward,delayMs);
  }
 }
 if(!l.queue.length)l.queued=0;
 events.push({kind:'service',direction:l.direction,from_ms:from,at_ms:now,capacity_mbps:capacity,budget_wire_bytes:(now-from)*capacity*125,service_wire_bytes:l.served-oldServed,queue_before_wire_bytes:before,queue_after_wire_bytes:l.queued});
}
function ledger(){const now=performance.now();for(const l of links)pumpLink(l,now);const view=l=>({offered_packets:l.offeredPackets,offered_wire_bytes:l.offered,dropped_wire_bytes:l.dropped,served_packets:l.servedPackets,served_wire_bytes:l.served,queued_wire_bytes:l.queued,forwarded_wire_bytes:l.forwardedWire,forwarded_packets:l.forwarded,overflow_packets:l.drops,send_errors:l.errors,max_queue_wire_bytes:l.maxQueue,queue_limit_wire_bytes:queueLimit,capacity_integral_wire_bytes:l.capacityBytes,capacity_integral_upper_bound_ok:l.served<=l.capacityBytes+1e-5,conservation_error_bytes:l.offered-l.dropped-l.served-l.queued});return {capacity_mbps:capacity,one_way_propagation_ms:delayMs,ipv4_udp_header_bytes:28,a_to_b:links[0]?view(links[0]):null,b_to_a:links[1]?view(links[1]):null};}
async function startRelay(a,b){
 for(const c of [a,b])if(!localIPs.has(c.address)||!Number.isInteger(c.port)||c.port<1||c.port>65535)throw Error('relay destinations must be owned local IPv4 candidates');
 if(links.length)throw Error('relay already created');const pa=createSocket('udp4'),pb=createSocket('udp4');relaySockets=[pa,pb];
 await Promise.all(relaySockets.map(s=>new Promise((r,j)=>{s.once('error',j);s.bind(0,'127.0.0.1',r);})));
 const make=(sender,destination,direction)=>({sender,destination,direction,last:performance.now(),queue:[],queued:0,offeredPackets:0,offered:0,dropped:0,servedPackets:0,served:0,capacityBytes:0,forwardedWire:0,forwarded:0,drops:0,errors:0,maxQueue:0,unexpected:0});
 const ab=make(pa,b,'a_to_b'),ba=make(pb,a,'b_to_a');ab.expectedPort=a.port;ba.expectedPort=b.port;links=[ab,ba];
 const receive=(l,msg,from,expectedPort)=>{
  if(!localIPs.has(from.address)||from.port!==expectedPort){l.unexpected++;return;}
  const now=performance.now();pumpLink(l,now);const wire=msg.length+28,before=l.queued,id=nextPacket++,drop=before+wire>queueLimit;l.offeredPackets++;l.offered+=wire;
  if(drop){l.dropped+=wire;l.drops++;}else{l.queue.push({data:Buffer.from(msg),wire,remaining:wire,id});l.queued+=wire;l.maxQueue=Math.max(l.maxQueue,l.queued);}
  events.push({kind:'offer',direction:l.direction,packet:id,at_ms:now,payload_bytes:msg.length,wire_bytes:wire,dropped:drop,queue_before_wire_bytes:before,queue_after_wire_bytes:l.queued});
 };
 pb.on('message',(msg,from)=>receive(ab,msg,from,a.port));pa.on('message',(msg,from)=>receive(ba,msg,from,b.port));
 tick=setInterval(()=>{const now=performance.now();for(const l of links)pumpLink(l,now);},1);
 return {a_proxy_port:pa.address().port,b_proxy_port:pb.address().port};
}
await writeFile(root+'/instrument_stream.jsonl','',{flag:'wx'});
const html=String.raw`<!doctype html><meta charset="utf-8"><canvas id="c" width="640" height="360"></canvas><video id="v" autoplay muted playsinline></video><script type="module">
import {FRAME_PROTOCOL,writeFrameMarker,readFrameMarker} from '/frame-marker.mjs';
import {runStepPlateausM8} from '/system_id_support_m8.mjs';
import {applyNativeAction} from '/dense_actuation.mjs';
import {captureEncoderResponse} from '/encoder_response.mjs';
import {LevelSampler,captureLink} from '/range_control.mjs';
import {BweCapHoldSampler} from '/native_bwe_hold_control.mjs';
import {SupportQualifiedRatioSampler, SUPPORT_PROTOCOL} from '/native_continuous_support_v13.mjs';
import {installEncodedMeter} from '/actuator_meter.mjs';
import {OBSERVATION_PROTOCOL,selectSenderSource,SenderObservationEncoder} from '/sender_observation.mjs';
import {QUALITY_PROTOCOL} from '/source_quality.mjs';
import {BWE_CAP_PROTOCOL,chooseBweCapAction} from '/bwe_cap_controller.mjs';
import {NativePolicyController} from '/native_policy.mjs';
import {RepairPolicy,SenderContentEncoder,CONFIG as REPAIR_CONFIG,warmRepair,explorationCap} from '/excitation_control.mjs';
const recorded=await import('/recorded_video.mjs'),fixedEncoder=await import('/fixed_encoder5.mjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const clockMarkers=[],phaseWindows=[],markerPosts=[];let markerSequence=0;
async function markerRequest(endpoint,extra={}){const marker_id='m'+String(++markerSequence).padStart(4,'0'),browser_send_ms=performance.now();const response=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...extra,marker_id,browser_send_ms})});const body=await response.json(),browser_receive_ms=performance.now();if(!response.ok||body.marker_id!==marker_id)throw Error('clock marker exchange failed: '+JSON.stringify(body));const record={...body,endpoint,browser_send_ms,browser_receive_ms};clockMarkers.push(record);markerPosts.push(fetch('/browser-marker',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(record)}).then(r=>{if(!r.ok)throw Error('browser marker evidence persistence failed');}));return record;}

const extraClock=[],startupTimeline=[],startupPosts=[];let extraSequence=0,startupTimer=null,startupBusy=false,startupStopMs=null,mediaActive=false,startupStage='created';
async function extraMarker(role,label){const marker_id='x'+String(++extraSequence).padStart(4,'0'),browser_send_ms=performance.now();const response=await fetch('/instrument-clock',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({marker_id,browser_send_ms,role,label})});const body=await response.json(),browser_receive_ms=performance.now();if(!response.ok||body.marker_id!==marker_id)throw Error('instrument clock exchange failed');const record={...body,browser_receive_ms,role,label};extraClock.push(record);await fetch('/instrument-browser',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(record)});return record;}
async function clockTrain(label){for(let i=0;i<4;i++)await extraMarker('train',label);}
async function clockBracket(label){await clockTrain(label+'_before');await extraMarker('holdout',label);await clockTrain(label+'_after');}
async function startupSnapshot(pc,sender,label){const request_ms=performance.now();let stats=[],error=null;try{stats=[...(await pc.getStats()).values()];}catch(e){error=String(e);}const response_ms=performance.now();const transports=stats.filter(s=>s.type==='transport'&&s.selectedCandidatePairId),ids=[...new Set(transports.map(s=>s.selectedCandidatePairId))];const pair=ids.length===1?stats.find(s=>s.id===ids[0]&&s.type==='candidate-pair'):null,primaries=stats.filter(s=>s.type==='outbound-rtp'&&s.kind==='video'),out=primaries.length===1?primaries[0]:null;const parameters=sender?.getParameters(),encoding=parameters?.encodings?.[0];const record={label,stage:startupStage,request_ms,response_ms,connection_state:pc.connectionState,ice_connection_state:pc.iceConnectionState,media_active:mediaActive,encoder_active_readback:encoding?.active??null,encoder_cap_bps:encoding?.maxBitrate??null,selected_pair_count:ids.length,selected_pair_id:pair?.id??null,selected_pair_state:pair?.state??null,selected_pair_nominated:pair?.nominated??null,native_stats_timestamp_ms:pair?.timestamp??null,bwe_bps:pair?.availableOutgoingBitrate??null,outbound_count:primaries.length,frames_encoded:out?.framesEncoded??null,bytes_sent:out?.bytesSent??null,packets_sent:out?.packetsSent??null,error};startupTimeline.push(record);startupPosts.push(fetch('/startup-sample',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(record)}).then(r=>{if(!r.ok)throw Error('startup sample persistence failed');}));return record;}

globalThis.run=async function(){
 const nativeConfig=await(await fetch('/native-mode')).json();
 await clockBracket('session_open');
 const pcConfig={iceTransportPolicy:'relay',iceServers:[nativeConfig.ice_server]};
 const modelBundles={},repairBundle=null;
 const actors={},repairActor={observe:()=>({encoder_max_bitrate_bps:4000000,receiver_jitter_buffer_target_ms:0}),acknowledge(){}};
 const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');let n=0,currentPhase='pre_connection';
 const movie=await recorded.loadRecordedVideo(nativeConfig),sourceReferences=new Map();
 if(!movie)throw Error('registered independently sourced video did not load');
 const sources=[],observations=[],sourceTimes=new Map(),contentEncoder=new SenderContentEncoder();let readErrors=0,observing=true,callbackHandle;
let currentDecisionId=null,actionInFlight=false,lastApplied=null;
 const stream=canvas.captureStream(0),capture=stream.getVideoTracks()[0],a=new RTCPeerConnection({...pcConfig,encodedInsertableStreams:true}),b=new RTCPeerConnection(pcConfig);
 if(typeof capture.requestFrame!=='function')throw Error('manual canvas capture unsupported');
const feedbackTx=a.createDataChannel('presentation-ack-v2',{ordered:false,maxRetransmits:0}),feedbackEvents=[],feedbackSends=[];let feedbackChannel=null,latestFeedback=null,lastFeedbackSent=-Infinity,lastFeedbackReceived=null,feedbackIgnored=0;
b.ondatachannel=e=>{if(e.channel.label!=='presentation-ack-v2')throw Error('unexpected feedback channel');feedbackChannel=e.channel;};
feedbackTx.onmessage=e=>{try{const p=JSON.parse(e.data),received=performance.now();if(Object.keys(p).sort().join()!=='presented_frames,source_id'||!Number.isInteger(p.source_id)||!Number.isInteger(p.presented_frames)||p.presented_frames<1||!sourceTimes.has(p.source_id)||latestFeedback&&p.source_id<=latestFeedback.source_id){feedbackIgnored++;return;}const fps=lastFeedbackReceived?1000*(p.presented_frames-lastFeedbackReceived.presented_frames)/(received-lastFeedbackReceived.received_ms):0;if(fps<0||!Number.isFinite(fps)){feedbackIgnored++;return;}latestFeedback={source_id:p.source_id,capture_request_ms:sourceTimes.get(p.source_id),received_ms:received,presented_fps:fps};feedbackEvents.push({...latestFeedback,presented_frames:p.presented_frames});lastFeedbackReceived={...p,received_ms:received};}catch{feedbackIgnored++;}};
 const draw=()=>{n++;const sourceReference=movie.draw(ctx);sourceReferences.set(n,sourceReference.reference_rgb);writeFrameMarker(ctx,n);const born=performance.now();contentEncoder.observe(sourceReference.reference_rgb,born);sourceTimes.set(n,born);sources.push({source_id:n,capture_request_ms:born,phase:currentPhase,decision_id:currentDecisionId,action_transition_inflight:actionInFlight,encoder_cap_bps:lastApplied?.encoder_max_bitrate_bps??null,receiver_target_ms:lastApplied?.receiver_jitter_buffer_target_ms??null});capture.requestFrame();};draw();
 let timer=null;let receiverTrack=false;const video=document.getElementById('v');
 const readback=document.createElement('canvas');readback.width=640;readback.height=360;const readctx=readback.getContext('2d',{willReadFrequently:true});
 const reference=document.createElement('canvas');reference.width=640;reference.height=360;const refctx=reference.getContext('2d',{willReadFrequently:true});
if(typeof video.requestVideoFrameCallback!=='function')throw Error('native frame callback unsupported');
 const inspect=(callbackTime,meta)=>{if(!observing)return;try{readctx.drawImage(video,0,0,640,360);const marker=readFrameMarker(readctx),readTime=performance.now(),known=marker.source_id!==null&&sourceTimes.has(marker.source_id);let quality=null;if(known){const q=recorded.pairRecordedQuality(readctx,sourceReferences.get(marker.source_id));quality={rgb_mse:q.rgb_mse,psnr_db:q.psnr_db,exact_match:q.exact_match};}observations.push({...marker,known_source:known,quality,callback_ms:callbackTime,readback_ms:readTime,expected_display_ms:meta.expectedDisplayTime,presented_frames:meta.presentedFrames,media_time:meta.mediaTime,video_width:video.videoWidth,video_height:video.videoHeight});if(known&&feedbackChannel?.readyState==='open'&&feedbackChannel.bufferedAmount<1024&&readTime-lastFeedbackSent>=100){feedbackChannel.send(JSON.stringify({source_id:marker.source_id,presented_frames:meta.presentedFrames}));feedbackSends.push({source_id:marker.source_id,presented_frames:meta.presentedFrames,sent_ms:performance.now()});lastFeedbackSent=readTime;}}catch(error){readErrors++;observations.push({read_error:String(error),callback_ms:callbackTime,readback_ms:performance.now()});}callbackHandle=video.requestVideoFrameCallback(inspect);};
 b.ontrack=e=>{receiverTrack=true;video.srcObject=e.streams[0];video.play();callbackHandle=video.requestVideoFrameCallback(inspect);};
 const candidatesA=[],candidatesB=[],candidateErrorsA=[],candidateErrorsB=[];
 a.onicecandidate=e=>{if(e.candidate)candidatesA.push(e.candidate);};
 b.onicecandidate=e=>{if(e.candidate)candidatesB.push(e.candidate);};
 a.onicecandidateerror=e=>candidateErrorsA.push({code:e.errorCode,text:e.errorText,url:e.url});
 b.onicecandidateerror=e=>candidateErrorsB.push({code:e.errorCode,text:e.errorText,url:e.url});
 const strip=s=>s.split('\r\n').filter(l=>!l.startsWith('a=candidate:')&&!l.startsWith('a=end-of-candidates')).join('\r\n');
 const supportStartup={abi:'native_prefix_instrumentation_m4r_startup_v1',requested_initial_bwe_bps:nativeConfig.support_initial_bwe_kbps*1000,preconnection_encoder_cap_bps:4000000,negotiation_start_ms:performance.now()};
 const withStartBitrate=sdp=>{const lines=sdp.split('\r\n'),vp8=lines.find(line=>/^a=rtpmap:[0-9]+ VP8\/90000$/i.test(line));if(!vp8)throw Error('VP8 SDP start target unavailable');const pt=vp8.split(':')[1].split(' ')[0],prefix='a=fmtp:'+pt+' ',index=lines.findIndex(line=>line.startsWith(prefix));const value='x-google-start-bitrate='+nativeConfig.support_initial_bwe_kbps;if(index>=0){const params=lines[index].slice(prefix.length).split(';').map(x=>x.trim()).filter(x=>x&&!x.startsWith('x-google-start-bitrate='));lines[index]=prefix+[...params,value].join(';');}else lines.splice(lines.indexOf(vp8)+1,0,prefix+value);return lines.join('\r\n');};
 const sender=a.addTransceiver(stream.getVideoTracks()[0],{direction:'sendonly',streams:[stream],sendEncodings:[{active:false,maxBitrate:4000000}]}).sender;
 await clockBracket('pre_sdp');
 startupStage='before_sdp';await startupSnapshot(a,sender,'before_sdp');
 startupTimer=setInterval(async()=>{if(startupBusy)return;if(startupStopMs!==null&&performance.now()>=startupStopMs){clearInterval(startupTimer);startupTimer=null;return;}startupBusy=true;try{await startupSnapshot(a,sender,'poll');}finally{startupBusy=false;}},25);
const encodedMeter=installEncodedMeter(sender),instrument=nativeConfig.controller==='micro'?new SupportQualifiedRatioSampler(nativeConfig.action_randomization_seed,nativeConfig.trial_id,nativeConfig.support_config):nativeConfig.controller==='bwe'?new BweCapHoldSampler():new LevelSampler(nativeConfig.level);
 const caps=RTCRtpSender.getCapabilities('video').codecs;
 const vp8=caps.filter(c=>c.mimeType.toLowerCase()==='video/vp8');if(vp8.length)a.getTransceivers()[0].setCodecPreferences(vp8);
 startupStage='negotiating';supportStartup.sdp_call_ms=performance.now();
 const offer=await a.createOffer();await a.setLocalDescription({type:'offer',sdp:withStartBitrate(offer.sdp)});await b.setRemoteDescription({type:'offer',sdp:strip(a.localDescription.sdp)});
 const answer=await b.createAnswer();await b.setLocalDescription({type:'answer',sdp:withStartBitrate(answer.sdp)});await a.setRemoteDescription({type:'answer',sdp:strip(b.localDescription.sdp)});
 supportStartup.local_start_parameter=Number(a.localDescription.sdp.match(/x-google-start-bitrate=([0-9]+)/)?.[1]);supportStartup.remote_start_parameter=Number(a.remoteDescription.sdp.match(/x-google-start-bitrate=([0-9]+)/)?.[1]);
const initialParameters=sender.getParameters();initialParameters.encodings[0].maxBitrate=4000000;await sender.setParameters(initialParameters);supportStartup.preconnection_cap_readback_bps=sender.getParameters().encodings[0].maxBitrate;
 for(let i=0;i<120&&(a.iceGatheringState!=='complete'||b.iceGatheringState!=='complete');i++)await sleep(100);
 const candidateRecord=c=>({type:c.type,protocol:c.protocol,address:c.address,port:c.port,relayProtocol:c.relayProtocol,url:c.url});
 const candidateLists={a:candidatesA.map(candidateRecord),b:candidatesB.map(candidateRecord)};
 const iceEvidence={abi:'native_action_turn_tcp_v2_ice_v1',turn_url:nativeConfig.turn_url,
  ice_transport_policy:'relay',gathering_state_a:a.iceGatheringState,gathering_state_b:b.iceGatheringState,
  candidates:candidateLists,candidate_errors:{a:candidateErrorsA,b:candidateErrorsB}};
 await fetch('/ice-evidence',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(iceEvidence)});
 if(a.iceGatheringState!=='complete'||b.iceGatheringState!=='complete')throw Error('TURN/TCP ICE gathering did not complete on both peers');
 const onlyRelay=cs=>cs.length>0&&cs.every(c=>c.type==='relay'&&c.relayProtocol==='tcp'&&c.protocol==='udp'&&c.address==='127.0.0.1'&&c.url===nativeConfig.turn_url);
 if(!onlyRelay(candidatesA)||!onlyRelay(candidatesB)||candidateErrorsA.length||candidateErrorsB.length)throw Error('TURN/TCP relay-only candidate qualification failed');
 const pick=cs=>cs.find(c=>c.type==='relay'&&c.protocol==='udp'&&c.relayProtocol==='tcp'&&c.address==='127.0.0.1'&&c.url===nativeConfig.turn_url);
 const ca=pick(candidatesA),cb=pick(candidatesB);if(!ca||!cb)throw Error('authenticated TURN/TCP relay candidate missing; no direct-UDP fallback');
 startupStage='gathered';await startupSnapshot(a,sender,'gathered');
 supportStartup.ice_gathering_complete_ms=performance.now();
 const relay=await(await fetch('/relay',{method:'POST',body:JSON.stringify({a:{address:ca.address,port:ca.port},b:{address:cb.address,port:cb.port}})})).json();if(relay.error)throw Error(relay.error);supportStartup.relay_created_ms=performance.now();
 const rewrite=(c,port)=>{const words=c.candidate.split(' ');words[4]='127.0.0.1';words[5]=String(port);return {candidate:words.join(' '),sdpMid:c.sdpMid,sdpMLineIndex:c.sdpMLineIndex};};
 await b.addIceCandidate(rewrite(ca,relay.a_proxy_port));await a.addIceCandidate(rewrite(cb,relay.b_proxy_port));
 for(let i=0;i<120&&(a.connectionState!=='connected'||b.connectionState!=='connected');i++)await sleep(100);
 if(a.connectionState!=='connected'||b.connectionState!=='connected')throw Error('TURN-backed native RTC did not connect: '+a.connectionState+'/'+b.connectionState);
 const selectedPair=async pc=>{const rows=[...(await pc.getStats()).values()],transport=rows.find(x=>x.type==='transport'&&x.selectedCandidatePairId),pair=rows.find(x=>x.id===transport?.selectedCandidatePairId)??rows.find(x=>x.type==='candidate-pair'&&x.nominated&&x.state==='succeeded'),local=rows.find(x=>x.id===pair?.localCandidateId),remote=rows.find(x=>x.id===pair?.remoteCandidateId);return {pair:pair?{state:pair.state,nominated:pair.nominated,bytesSent:pair.bytesSent,bytesReceived:pair.bytesReceived}:null,local:local?{candidateType:local.candidateType,protocol:local.protocol,relayProtocol:local.relayProtocol,address:local.address}:null,remote:remote?{candidateType:remote.candidateType,protocol:remote.protocol,relayProtocol:remote.relayProtocol,address:remote.address}:null};};
 const selectedOk=pair=>['relay','prflx'].includes(pair?.local?.candidateType)&&pair.local.relayProtocol==='tcp'&&pair.local.address==='127.0.0.1'&&pair.remote?.candidateType==='relay'&&pair.remote.address==='127.0.0.1'&&pair.pair?.state==='succeeded'&&pair.pair.nominated===true&&pair.pair.bytesSent>0&&pair.pair.bytesReceived>0;
 const readinessStart=performance.now();let selectedA,selectedB,readinessProbes=0;
 do{[selectedA,selectedB]=await Promise.all([selectedPair(a),selectedPair(b)]);readinessProbes++;await fetch('/transport-readiness',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({probe:readinessProbes,browser_ms:performance.now(),elapsed_ms:performance.now()-readinessStart,selected_a:selectedA,selected_b:selectedB,passed:selectedOk(selectedA)&&selectedOk(selectedB)})});if(selectedOk(selectedA)&&selectedOk(selectedB))break;await sleep(25);}while(performance.now()-readinessStart<2000);
 supportStartup.transport_readiness_wait_ms=performance.now()-readinessStart;supportStartup.transport_readiness_probes=readinessProbes;
 const transportEvidence={abi:'native_action_turn_tcp_v2_transport_v1',turn_url:nativeConfig.turn_url,
  policy:'relay',candidate_evidence:iceEvidence,selected_a:selectedA,selected_b:selectedB,
  connection_a:a.connectionState,connection_b:b.connectionState};
 await fetch('/transport-evidence',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(transportEvidence)});
 if(!selectedOk(selectedA)||!selectedOk(selectedB)||supportStartup.transport_readiness_wait_ms>2000)throw Error('unchanged selected-pair readiness did not qualify within 2000 ms; no reconnect or retry');
 supportStartup.connection_qualified_ms=performance.now();
 startupStage='connected_inactive';await startupSnapshot(a,sender,'connected_inactive');
 const setupDelay=nativeConfig.setup_delay_ms;if(![0,750].includes(setupDelay))throw Error('unregistered setup delay');supportStartup.setup_delay_ms=setupDelay;supportStartup.delay_start_ms=performance.now();await sleep(setupDelay);supportStartup.delay_end_ms=performance.now();
 await clockBracket('ready_inactive');
 supportStartup.pre_activation=await startupSnapshot(a,sender,'inactive_ready');
 if(supportStartup.pre_activation.encoder_active_readback!==false||supportStartup.pre_activation.encoder_cap_bps!==4000000||![null,0].includes(supportStartup.pre_activation.frames_encoded)||![null,0].includes(supportStartup.pre_activation.bytes_sent))throw Error('media advanced during inactive startup');
 const snapshots=[];let lastTx=0,lastRx=0,last=performance.now();
 const receiver=b.getReceivers().find(r=>r.track.kind==='video');
 const actuation=await applyNativeAction(sender,receiver,{encoder_max_bitrate_bps:4000000,receiver_jitter_buffer_target_ms:0});
lastApplied=actuation;
if(movie)await movie.start();
 const encoderRecipe=await fixedEncoder.configureFixedEncoder(sender);
 const activeParameters=sender.getParameters();activeParameters.encodings[0].active=true;await sender.setParameters(activeParameters);mediaActive=true;startupStage='active';draw();timer=setInterval(draw,1000/30);
 const activationStart=performance.now();let init;do{init=await startupSnapshot(a,sender,'initialization');if(Number.isFinite(init.bwe_bps)&&init.bwe_bps>0&&Math.abs(init.bwe_bps-1200000)>1)throw Error('first observed active native BWE differs from registered initialization');if(Number.isFinite(init.bwe_bps)&&init.bwe_bps>0&&init.outbound_count===1)break;await sleep(5);}while(performance.now()-activationStart<100);
 supportStartup.initial_native_sample_ms=init.response_ms;supportStartup.initial_native_source={bwe_bps:init.bwe_bps,frames_encoded:init.frames_encoded,bytes_sent:init.bytes_sent,packets_sent:init.packets_sent};supportStartup.initial_pair_id=init.selected_pair_id;supportStartup.initial_encoder_active=init.encoder_active_readback;supportStartup.initialization_latency_ms=init.response_ms-activationStart;supportStartup.initialization_success=init.selected_pair_count===1&&init.selected_pair_state==='succeeded'&&init.selected_pair_nominated===true&&Number.isFinite(init.bwe_bps)&&Math.abs(init.bwe_bps-1200000)<=1&&init.outbound_count===1&&init.encoder_active_readback===true&&init.encoder_cap_bps===4000000&&supportStartup.initialization_latency_ms<=100;
 if(!supportStartup.initialization_success)throw Error('native initialization unobservable within 100 ms; no fallback or retry');
 const measurementStart=performance.now();instrument.start(measurementStart);startupStopMs=measurementStart+1500;supportStartup.activation_readback=sender.getParameters().encodings[0].active;await startupSnapshot(a,sender,'measurement_start');
await markerRequest('/clock-marker');
let collecting=true;const encoder=new SenderObservationEncoder(),decisions=[],samplingErrors=[];
const sampleTask=(async()=>{try{while(collecting){const stats=await a.getStats();if(!collecting)break;const own={encoder_max_bitrate_bps:sender.getParameters().encodings[0].maxBitrate,receiver_jitter_buffer_target_ms:actuation.native_jitter_target_supported?receiver.jitterBufferTarget:null};const observation=encoder.observe(selectSenderSource(stats,own),performance.now());const encoder_response=captureEncoderResponse(stats,observation.raw_source,observation.sample_ms,performance.timeOrigin);observation.content_features=contentEncoder.snapshot(observation.sample_ms);const instrumentStart=performance.now(),encoded_snapshot=encodedMeter.snapshot(observation.sample_ms),instrument_link=captureLink(stats,observation.raw_source),policyInput={observation_abi:observation.observation_abi,feature_names:observation.feature_names,features:observation.features},actuator_assignment=await instrument.observe(observation,encoder_response,encoded_snapshot,instrument_link,policyInput),instrument_compute_ms=performance.now()-instrumentStart;const commonStart=performance.now(),all_policy_decisions={},model_inference_ms={};for(const [key,actor] of Object.entries(actors)){const before=performance.now();all_policy_decisions[key]=actor.observe(policyInput);model_inference_ms[key]=performance.now()-before;}const feedback_input=latestFeedback?{...latestFeedback}:null,repairStart=performance.now(),repair_decision=repairActor.observe(observation,feedback_input),repair_inference_ms=performance.now()-repairStart;const policyDecision=all_policy_decisions[nativeConfig.active_model],inference_ms=model_inference_ms[nativeConfig.active_model];const proposed=nativeConfig.controller==='repair'?{encoder_max_bitrate_bps:repair_decision.encoder_max_bitrate_bps,receiver_jitter_buffer_target_ms:0}:nativeConfig.controller==='explore'?{encoder_max_bitrate_bps:(actuator_assignment?.requested_bps??4000000),receiver_jitter_buffer_target_ms:0}:nativeConfig.controller==='bwe'?{encoder_max_bitrate_bps:(actuator_assignment?.requested_bps??4000000),receiver_jitter_buffer_target_ms:0}:nativeConfig.controller==='micro'?{encoder_max_bitrate_bps:(actuator_assignment?.requested_bps??4000000),receiver_jitter_buffer_target_ms:0}:nativeConfig.controller==='rlcd'?{encoder_max_bitrate_bps:policyDecision.encoder_max_bitrate_bps,receiver_jitter_buffer_target_ms:policyDecision.receiver_jitter_buffer_target_ms}:nativeConfig.controller==='gcc'?{encoder_max_bitrate_bps:REPAIR_CONFIG.gcc_ceiling_bps,receiver_jitter_buffer_target_ms:0}:chooseBweCapAction(policyInput);const total_inference_ms=performance.now()-commonStart+instrument_compute_ms;let actual=lastApplied;const changed=proposed.encoder_max_bitrate_bps!==own.encoder_max_bitrate_bps||proposed.receiver_jitter_buffer_target_ms!==own.receiver_jitter_buffer_target_ms;if(changed){actionInFlight=true;try{actual=await applyNativeAction(sender,receiver,proposed);}finally{actionInFlight=false;}}const step_id=decisions.length,ack_ms=performance.now();if(changed)repairActor.acknowledge(actual.encoder_max_bitrate_bps,ack_ms);instrument.acknowledge(ack_ms,actual.encoder_max_bitrate_bps);decisions.push({step_id,observation,policy_input:policyInput,encoder_response,encoded_snapshot,instrument_link,actuator_assignment,instrument_compute_ms,feedback_input,repair_decision,repair_inference_ms,policy_decision:policyDecision,inference_ms,all_policy_decisions,model_inference_ms,total_inference_ms,proposed_action:proposed,actuation_readback:actual,changed,ack_ms});currentDecisionId=step_id;lastApplied=actual;await sleep(OBSERVATION_PROTOCOL.poll_ms);}}catch(error){samplingErrors.push(String(error));collecting=false;}})();
 await markerRequest('/clock-marker');
 let phaseIndex=0;
 for(const [capacity,label,duration,trace_mbps] of nativeConfig.schedule){
  if(phaseIndex===1||phaseIndex===2)await markerRequest('/clock-marker');
  await clockTrain(label+'_before');
  const phaseMarker=await markerRequest('/phase',{capacity,phase:label,trace_mbps});currentPhase=label;
  await clockTrain(label+'_after');
  await markerRequest('/clock-marker');
  const phaseStart=performance.now();if(label==='block_2'){await sleep(duration/2);await clockTrain('midpoint_before');await markerRequest('/clock-marker');await clockTrain('midpoint_after');const remaining=duration-(performance.now()-phaseStart);if(remaining>0)await sleep(remaining);}else if(label==='block_1')await runStepPlateausM8(phaseStart,nativeConfig.system_id_sequence_mbps,clockBracket);else await sleep(duration);const phaseEnd=performance.now();phaseWindows.push({phase:label,marker_id:phaseMarker.marker_id,start_ms:phaseStart,end_ms:phaseEnd,capacity_mbps:capacity,capacity_sequence_mbps:trace_mbps});
  const tx=[...(await a.getStats()).values()],rx=[...(await b.getStats()).values()];
  const sent=tx.find(x=>x.type==='outbound-rtp'&&x.kind==='video'),received=rx.find(x=>x.type==='inbound-rtp'&&x.kind==='video');
  const transport=tx.find(x=>x.type==='transport'&&x.selectedCandidatePairId);const pair=tx.find(x=>x.id===transport?.selectedCandidatePairId)??tx.find(x=>x.type==='candidate-pair'&&x.nominated&&x.state==='succeeded');
  const remote=tx.find(x=>x.id===pair?.remoteCandidateId),codec=tx.find(x=>x.id===sent.codecId),now=performance.now();
  const network=await(await fetch('/ledger')).json();
  snapshots.push({phase:label,capacity_mbps:capacity,encoder_cap_bps:sender.getParameters().encodings[0].maxBitrate,interval_ms:now-last,sent_mbps:(sent.bytesSent-lastTx)*8/(now-last)/1000,received_mbps:(received.bytesReceived-lastRx)*8/(now-last)/1000,
    frames_encoded:sent.framesEncoded,frames_decoded:received.framesDecoded,packets_lost:received.packetsLost,jitter_s:received.jitter,
    codec:codec.mimeType,available_outgoing_bitrate_bps:pair?.availableOutgoingBitrate??null,rtt_s:pair?.currentRoundTripTime??null,remote_candidate_address:remote?.address??remote?.ip??null,
    mean_encode_s:sent.totalEncodeTime/sent.framesEncoded,mean_native_jitter_buffer_s:received.jitterBufferEmittedCount?received.jitterBufferDelay/received.jitterBufferEmittedCount:null,mean_native_jitter_buffer_target_s:received.jitterBufferEmittedCount?received.jitterBufferTargetDelay/received.jitterBufferEmittedCount:null,freeze_count:received.freezeCount??null,freeze_duration_s:received.totalFreezesDuration??null,remote_candidate_type:remote?.candidateType??null,network});
  lastTx=sent.bytesSent;lastRx=received.bytesReceived;last=now;phaseIndex++;
 }
 const cutoff=performance.now();clearInterval(timer);observing=false;if(callbackHandle!==undefined)video.cancelVideoFrameCallback(callbackHandle);
 collecting=false;await sampleTask;
if(samplingErrors.length||decisions.length<30)throw Error('unqualified sender collection: '+JSON.stringify(samplingErrors));
 const connectionAtCutoff=a.connectionState,transportCcNegotiated=a.localDescription.sdp.includes('transport-cc');
 if(movie)movie.stop();stream.getTracks().forEach(t=>t.stop());a.close();b.close();
 await markerRequest('/clock-marker',{terminal_drain_start:true,measurement_cutoff_browser_ms:cutoff});
 await Promise.all(markerPosts);if(startupTimer)clearInterval(startupTimer);await Promise.all(startupPosts);
const frameEvidence={protocol:FRAME_PROTOCOL,quality_protocol:recorded.VIDEO_QUALITY_PROTOCOL,content_id:nativeConfig.content_id,network_family:nativeConfig.network_family,network_profile_id:nativeConfig.network_profile_id,time_origin_epoch_ms:performance.timeOrigin,measurement_start_ms:measurementStart,measurement_cutoff_ms:cutoff,sources,observations,read_errors:readErrors,clock_markers:clockMarkers,phase_windows:phaseWindows};
supportStartup.measurement_start_ms=measurementStart;
const senderEvidence={instrumentation_m4r:{extra_clock:extraClock,startup_timeline:startupTimeline},support_startup:supportStartup,support_screen:instrument.evidence(),encoded_meter:encodedMeter.evidence(measurementStart,cutoff),encoder_recipe:encoderRecipe,protocol:OBSERVATION_PROTOCOL,controller:{controller:nativeConfig.controller,behavior:nativeConfig.behavior??null,repair_model_sha256:nativeConfig.repair_model_sha256,repair_config:REPAIR_CONFIG},measurement_start_ms:measurementStart,measurement_cutoff_ms:cutoff,decisions,sampling_errors:samplingErrors,learned_policy:['rlcd','repair'].includes(nativeConfig.controller),feedback_protocol:{channel:'presentation-ack-v2',ordered:false,max_retransmits:0,min_send_interval_ms:100},feedback_events:feedbackEvents,feedback_sends:feedbackSends,feedback_ignored:feedbackIgnored,measurement_recipe:nativeConfig.measurement_recipe,model_sha256:nativeConfig.model_sha256,common_shadow_inference:true,common_models_sha256:nativeConfig.common_models_sha256};
 const result={encoder_recipe:encoderRecipe,native_rtc:true,local_loopback_only:true,userspace_relay_only:true,source:'independently sourced licensed recorded video; rights and attribution in the pinned content manifest',browser_user_agent:navigator.userAgent,connection:connectionAtCutoff,
   turn_tcp_backed:true,turn_url:nativeConfig.turn_url,ice_candidate_evidence:iceEvidence,transport_evidence:transportEvidence,
   transport_cc_negotiated:transportCcNegotiated,receiver_track_present:receiverTrack,snapshots,frame_evidence:frameEvidence,sender_evidence:senderEvidence,native_actuation:{mode:nativeConfig.mode,...actuation},native_controller:nativeConfig.controller,collection_config:nativeConfig.collection_config,
   limitations:['M8 separates a constructed equal-integral prefix, synthetic fixed step/plateau service, and an original measured-source probe, replayed as symmetric service. This is not an end-to-end live network or packet replay.','Source clips retain their pinned content licenses (V13: pinned CC BY 3.0/4.0); source pixels are used only transiently for paired RGB quality and are not saved in the capture evidence.','Scalar encoder maxBitrate changes are not FEC/codec-mode actuation.','Pixel-ID application deadlines and sampled RGB PSNR are proxies, not physical capture/scan-out or human QoE.']};
 return result;
}
</script>`;
const moduleRoutes=new Set(['/system_id_support_m8.mjs','/native_continuous_support_v13.mjs','/native_continuous_support_v13.mjs','/native_bwe_hold_control.mjs','/range_control.mjs','/actuator_control.mjs','/actuator_meter.mjs','/encoder_response.mjs','/dense_control.mjs','/excitation_control.mjs','/dense_actuation.mjs','/streamed_actuator_video.mjs','/fixed_encoder5.mjs','/repair5_policy.mjs','/repair3_policy.mjs','/streamed_video5.mjs','/streamed_video.mjs','/recorded_video.mjs','/native_actuation.mjs','/sender_observation.mjs','/source_quality.mjs','/bwe_cap_controller.mjs','/native_policy.mjs']);
let postedIceEvidence=null,postedTransportEvidence=null,postedBrowserMarkers=[],terminalDrainState=null;const instrumentNode=[],instrumentBrowser=[],startupSamples=[],conditioningBrowser=[];let conditioningRelease=null,conditioningInitial=null,conditioningSequence=0,currentServicePhase=null;
const readBody=async req=>{let text='';for await(const data of req)text+=data;return JSON.parse(text);};
const server=createServer(async(req,res)=>{try{
 if(req.url==='/instrument-clock'){const body=await readBody(req),node_receive_ms=performance.now();if(!['train','holdout'].includes(body.role)||!Number.isFinite(body.browser_send_ms)||typeof body.marker_id!=='string')throw Error('invalid instrument marker');const marker={...body,node_receive_ms,node_send_ms:performance.now()};instrumentNode.push(marker);await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'clock_node',...marker})+'\n');res.setHeader('Content-Type','application/json');res.end(JSON.stringify(marker));}
 else if(req.url==='/instrument-browser'){const body=await readBody(req);instrumentBrowser.push(body);await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'clock_browser',...body})+'\n');res.end('{}');}
 else if(req.url==='/transport-readiness'){const body=await readBody(req);await appendFile(root+'/transport_readiness.jsonl',JSON.stringify(body)+'\n');await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'transport_readiness',...body})+'\n');res.end('{}');}
 else if(req.url==='/startup-sample'){const body=await readBody(req);startupSamples.push(body);await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'startup',...body,node_persist_ms:performance.now()})+'\n');res.end('{}');}
 else if(moduleRoutes.has(req.url)){res.setHeader('Content-Type','text/javascript');res.end(await readFile(root+req.url,'utf8'));}
 else if(req.url==='/recorded-video.mp4'&&panel.source_kind==='recorded_video_v1'){await movieServer.serve(req,res);}
 else if(req.url==='/repair-model.json'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(repairBundle));}
 else if(req.url==='/all-models.json'){res.setHeader('Content-Type','application/json');res.end(await readFile(root+'/all_models.json','utf8'));}
 else if(req.url==='/model.json'){res.setHeader('Content-Type','application/json');res.end(await readFile(root+'/model.json','utf8'));}
 else if(req.url==='/native-mode'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({mode:nativeMode,controller,active_model:condition.model,model_sha256:modelSha,common_models_sha256:commonModelHashes,risk_cutoff:model.risk_cutoff,disagreement_cutoff:model.disagreement_cutoff,content_index:episode.content_index,content_id:episode.content_id,network_family:episode.network_family,network_profile_id:episode.network_profile_id,trial_id:episode.id,action_randomization_seed:episode.action_randomization_seed,support_config:episode.support_config,setup_delay_ms:episode.setup_delay_ms,system_id_sequence_mbps:episode.system_id_sequence_mbps,support_initial_bwe_kbps:initialBweKbps,source_kind:panel.source_kind,video_segment:episode.video_segment??null,video_sha256:panel.video_source?.sha256??null,repair_model_sha256:repairSha,behavior:condition.behavior??null,level:condition.level,exploration_seed:episode.exploration_seed,measurement_recipe:panel.measurement_recipe,schedule:episode.schedule,collection_config:collectionConfig,turn_url:turnUrl,ice_server:{urls:turnUrl,username:turnUsername,credential:turnCredential}}));}
 else if(req.url==='/native-actuation.mjs'){res.setHeader('Content-Type','text/javascript');res.end(await readFile(root+'/native_actuation.mjs','utf8'));}
 else if(req.url==='/frame-marker.mjs'){res.setHeader('Content-Type','text/javascript');res.end(await readFile(root+'/frame_marker.mjs','utf8'));}
 else if(req.url==='/ice-evidence'){postedIceEvidence=await readBody(req);res.setHeader('Content-Type','application/json');res.end('{"ok":true}');}
 else if(req.url==='/transport-evidence'){postedTransportEvidence=await readBody(req);res.setHeader('Content-Type','application/json');res.end('{"ok":true}');}
 else if(req.url==='/browser-marker'){postedBrowserMarkers.push(await readBody(req));res.setHeader('Content-Type','application/json');res.end('{"ok":true}');}
 else if(req.url==='/relay'){const data=await readBody(req);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(await startRelay(data.a,data.b)));}
 else if(req.url==='/phase'||req.url==='/clock-marker'){const body=await readBody(req),node_receive_ms=performance.now();if(typeof body.marker_id!=='string'||!Number.isFinite(body.browser_send_ms))throw Error('malformed clock marker');let node_phase_ms=null;if(req.url==='/phase'){const trace=body.trace_mbps;if(!Array.isArray(trace)||trace.length!==({block_0:10,block_1:1,block_2:12}[body.phase])||trace.some(value=>!Number.isFinite(value)||value<0||value>10)||body.capacity!==trace[0])throw Error('invalid frozen M8 source/service block');currentServicePhase=body.phase;for(const timer of traceTimers)clearTimeout(timer);traceTimers=[];const applyRate=(sampleIndex)=>{if(stopped)return;const now=performance.now();for(const l of links)pumpLink(l,now);capacity=trace[sampleIndex];events.push({kind:body.phase==='block_1'?'system_id_initial':'trace_capacity',phase:body.phase,sample_index:sampleIndex,at_ms:now,capacity_mbps:capacity});if(body.phase==='block_1')conditioningInitial={at_ms:now,capacity_mbps:capacity};};applyRate(0);node_phase_ms=performance.now();events.push({kind:'phase',marker_id:body.marker_id,browser_send_ms:body.browser_send_ms,at_ms:node_phase_ms,capacity_mbps:body.capacity,phase:body.phase,trace_mbps:trace});for(let sampleIndex=1;sampleIndex<trace.length;sampleIndex++)traceTimers.push(setTimeout(()=>applyRate(sampleIndex),sampleIndex*1000));}else if(body.terminal_drain_start===true){if(terminalDrainState||body.marker_id!=='m0012'||!Number.isFinite(body.measurement_cutoff_browser_ms)||body.browser_send_ms<=body.measurement_cutoff_browser_ms)throw Error('invalid post-measurement terminal-drain marker');for(const timer of traceTimers)clearTimeout(timer);traceTimers=[];const pre_cleanup_ledger=ledger(),measured_final_capacity_mbps=capacity;const start_event_index=events.length,service_start_node_ms=performance.now();capacity=10;events.push({kind:'terminal_drain_start',at_ms:node_receive_ms,service_start_node_ms,browser_measurement_cutoff_ms:body.measurement_cutoff_browser_ms,browser_send_ms:body.browser_send_ms,marker_id:body.marker_id,measured_final_capacity_mbps,cleanup_service_rate_mbps:10});terminalDrainState={abi:'native_action_terminal_queue_drain_v1',marker_id:body.marker_id,browser_measurement_cutoff_ms:body.measurement_cutoff_browser_ms,browser_send_ms:body.browser_send_ms,node_receive_ms,service_start_node_ms,measured_final_capacity_mbps,cleanup_service_rate_mbps:10,start_event_index,pre_cleanup_ledger};}const node_send_ms=performance.now(),marker={marker_id:body.marker_id,browser_send_ms:body.browser_send_ms,node_receive_ms,node_phase_ms,node_send_ms};events.push({kind:'clock_marker',endpoint:req.url,...marker,phase:body.phase??null,capacity_mbps:body.capacity??null});res.setHeader('Content-Type','application/json');res.end(JSON.stringify(marker));}
 else if(req.url==='/system-service'){
  const body=await readBody(req),now=performance.now();
  if(currentServicePhase!=='block_1'||conditioningRelease||body.sequence!==conditioningSequence+1||body.sequence>3||body.requested_mbps!==episode.system_id_sequence_mbps[body.sequence]||Math.abs(body.previous_mbps-capacity)>1e-12)throw Error('invalid M8 service intervention');
  for(const l of links)pumpLink(l,now);const previous_mbps=capacity;capacity=body.requested_mbps;conditioningSequence=body.sequence;
  const readback={sequence:body.sequence,capacity_mbps:capacity,previous_mbps,node_applied_ms:now};events.push({kind:'system_id_service',at_ms:now,...readback,browser_request_ms:body.browser_request_ms});
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(readback));
 }
 else if(req.url==='/system-service-browser'){const body=await readBody(req);conditioningBrowser.push(body);await appendFile(root+'/system_id_stream.jsonl',JSON.stringify({kind:'browser',...body})+'\n');res.end('{}');}
 else if(req.url==='/system-id-complete'){const body=await readBody(req);if(currentServicePhase!=='block_1'||conditioningRelease||conditioningSequence!==3||JSON.stringify(body.service_sequence_mbps)!==JSON.stringify(episode.system_id_sequence_mbps))throw Error('invalid M8 completion');conditioningRelease=body;await appendFile(root+'/system_id_stream.jsonl',JSON.stringify({kind:'completion',...body,node_persist_ms:performance.now()})+'\n');res.end('{}');}
 else if(req.url==='/ledger'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(ledger()));}
 else{res.setHeader('Content-Type','text/html');res.end(html);}
}catch(error){res.statusCode=400;res.end(JSON.stringify({error:String(error)}));}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const url='http://127.0.0.1:'+server.address().port;
const chrome=spawn(process.env.RLCD_CHROME||(process.platform==='darwin'?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':'google-chrome'),['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--metrics-recording-only','--autoplay-policy=no-user-gesture-required','about:blank'],{stdio:['ignore','ignore','pipe']});
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
 if(!terminalDrainState)throw Error('post-measurement terminal-drain marker was not received');
 for(let i=0;i<200;i++){
  ledger();
  if(links.every(l=>l.queued===0&&l.servedPackets===l.forwarded))break;
  await wait(10);
 }
 if(links.some(l=>l.queued!==0||l.servedPackets!==l.forwarded))throw Error('terminal cleanup failed the unchanged exact served/forwarded queue check');
 const cleanupAfter=ledger(),cleanupCompleteNodeMs=performance.now(),cleanupBefore=terminalDrainState.pre_cleanup_ledger;
 const terminalCleanup={abi:'native_action_terminal_queue_drain_v1',...terminalDrainState,
  complete_node_ms:cleanupCompleteNodeMs,elapsed_ms:cleanupCompleteNodeMs-terminalDrainState.service_start_node_ms,
  complete_event_index:events.length,post_cleanup_ledger:cleanupAfter,
  outcomes_read:false,cleanup_rate_in_treatment_trace:false};
 events.push({kind:'terminal_drain_complete',at_ms:cleanupCompleteNodeMs,elapsed_ms:terminalCleanup.elapsed_ms});
 if(!postedIceEvidence||!postedTransportEvidence)throw Error('TURN candidate and selected-pair evidence was not persisted');
 await writeFile(root+'/ice_evidence.json',JSON.stringify(postedIceEvidence,null,2)+'\n',{flag:'wx'});
 await writeFile(root+'/transport_evidence.json',JSON.stringify(postedTransportEvidence,null,2)+'\n',{flag:'wx'});
 const senderEvidence=result.sender_evidence;delete result.sender_evidence;await writeFile(root+'/instrumentation_m4r.json',JSON.stringify(senderEvidence.instrumentation_m4r)+'\n',{flag:'wx'});delete senderEvidence.instrumentation_m4r;await writeFile(root+'/support_startup.json',JSON.stringify({...senderEvidence.support_startup,first_measured_bwe_bps:senderEvidence.decisions[0].observation.raw_source.bwe_bps},null,2)+'\n',{flag:'wx'});senderEvidence.decisions=senderEvidence.decisions.map(d=>({step_id:d.step_id,sample_ms:d.observation.sample_ms,ack_ms:d.ack_ms,policy_input:d.policy_input,actuator_assignment:d.actuator_assignment,proposed_action:d.proposed_action,actuation_readback:d.actuation_readback,changed:d.changed}));await writeFile(root+'/sender_observations.json',JSON.stringify(senderEvidence)+String.fromCharCode(10));result.native_observation_protocol=senderEvidence.protocol;result.sender_decisions=senderEvidence.decisions.length;result.learned_policy_loaded=senderEvidence.learned_policy;result.repair_model_sha256=repairSha;result.measurement_recipe=panel.measurement_recipe;result.frozen_native_model_sha256=modelSha;result.common_shadow_inference=true;
const frameEvidence=result.frame_evidence;delete result.frame_evidence;
 await writeFile(root+'/phase_windows.json',JSON.stringify({measurement_start_ms:frameEvidence.measurement_start_ms,measurement_cutoff_ms:frameEvidence.measurement_cutoff_ms,phase_windows:frameEvidence.phase_windows})+'\n',{flag:'wx'});
 await writeFile(root+'/media_progress.json',JSON.stringify(result.snapshots.map(s=>({phase:s.phase,frames_encoded:s.frames_encoded,frames_decoded:s.frames_decoded,mean_encode_s:s.mean_encode_s})))+'\n',{flag:'wx'});
 await writeFile(root+'/frame_events.json',JSON.stringify(frameEvidence)+String.fromCharCode(10));
 await writeFile(root+'/clock_markers_browser.json',JSON.stringify({markers:frameEvidence.clock_markers},null,2)+'\n',{flag:'wx'});
 await writeFile(root+'/clock_markers_node.json',JSON.stringify(events.filter(event=>event.kind==='clock_marker'),null,2)+'\n',{flag:'wx'});
 result.frame_protocol=frameEvidence.protocol;result.source_frame_requests=frameEvidence.sources.length;result.receiver_frame_readbacks=frameEvidence.observations.length;
 const build=await(await fetch('http://127.0.0.1:'+port+'/json/version')).json();
 result.browser_build=build.Browser;result.protocol_version=build['Protocol-Version'];
 result.relay=cleanupBefore;
 result.relay_after_terminal_cleanup=cleanupAfter;
 result.terminal_queue_cleanup=terminalCleanup;
 await writeFile(root+'/terminal_drain.json',JSON.stringify(terminalCleanup,null,2)+'\n',{flag:'wx'});
 await writeFile(root+'/queue_evidence.json',JSON.stringify({abi:'native_action_turn_tcp_v7_queue_evidence_v1',relay:cleanupAfter,
  pre_cleanup_relay:cleanupBefore,terminal_cleanup:terminalCleanup,
  accepted_source_ports:{a_to_b:links[0]?.expectedPort??null,b_to_a:links[1]?.expectedPort??null},
  unexpected_sources:{a_to_b:links[0]?.unexpected??null,b_to_a:links[1]?.unexpected??null}},null,2)+'\n',{flag:'wx'});
 if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');
 result.raw_event_count=events.length;
 const raw=gzipSync(events.map(e=>JSON.stringify(e)).join(String.fromCharCode(10))+String.fromCharCode(10));
 await writeFile(root+'/events.jsonl.gz',raw);
 if(!result.snapshots.every(s=>s.remote_candidate_address==='127.0.0.1'&&s.remote_candidate_type==='relay')||cleanupAfter.a_to_b.forwarded_packets<100||cleanupAfter.b_to_a.forwarded_packets<100)throw Error('media bypassed the selected TURN relay or did not progress through the owned queue');
 const queueDirections=[cleanupAfter.a_to_b,cleanupAfter.b_to_a];
 if(queueDirections.some(link=>!link.capacity_integral_upper_bound_ok||Math.abs(link.conservation_error_bytes)>1e-6||link.send_errors!==0))throw Error('queue ledger failed its service or byte-conservation check');
 if(!result.native_rtc||result.connection!=='connected'||!result.snapshots.every(s=>s.frames_decoded>10&&s.frames_encoded>10&&Number.isFinite(s.mean_encode_s)))throw Error('native media stats not valid');
 await writeFile(root+'/summary.json',JSON.stringify(result,null,2)+'\n');
 if(process.env.RLCD_TECHNICAL_SMOKE!=='1')console.log(JSON.stringify(result));
}finally{
 ws?.close();
 const stopProcess=async child=>{if(!child||child.exitCode!==null)return;await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},3000);child.once('exit',()=>{clearTimeout(timer);resolve();});child.kill('SIGTERM');});};
 await stopProcess(chrome);await stopProcess(turnServer);
 stopped=true;if(tick)clearInterval(tick);for(const s of relaySockets)s.close();
 const policyBytesAfter=await readFile(policyPath).catch(()=>Buffer.alloc(0));
 const policyAfter=policyBytesAfter.length?JSON.parse(policyBytesAfter).WebRtcIPHandling:null;
 const policyCheck={abi:'native_action_turn_tcp_policy_check_v1',WebRtcIPHandling_before:policyBefore,
  WebRtcIPHandling_after:policyAfter,sha256_before:createHash('sha256').update(policyBytesBefore).digest('hex'),
  sha256_after:createHash('sha256').update(policyBytesAfter).digest('hex'),
  unchanged:policyBytesAfter.length>0&&createHash('sha256').update(policyBytesBefore).digest('hex')===createHash('sha256').update(policyBytesAfter).digest('hex'),
  modified_by_runner:false};
 try{await readFile(root+'/policy_check.json');}catch{await writeFile(root+'/policy_check.json',JSON.stringify(policyCheck,null,2)+'\n',{flag:'wx'});}
 if(postedIceEvidence)await writeFile(root+'/ice_evidence.json',JSON.stringify(postedIceEvidence,null,2)+'\n').catch(()=>{});
 if(postedTransportEvidence)await writeFile(root+'/transport_evidence.json',JSON.stringify(postedTransportEvidence,null,2)+'\n').catch(()=>{});
 const writeMissing=async(name,bytes)=>{try{await readFile(root+'/'+name);}catch{await writeFile(root+'/'+name,bytes,{flag:'wx'}).catch(()=>{});}};
 if(links.length)await writeMissing('queue_evidence.json',JSON.stringify({abi:'native_action_turn_tcp_v7_queue_evidence_v1',relay:ledger(),
  accepted_source_ports:{a_to_b:links[0]?.expectedPort??null,b_to_a:links[1]?.expectedPort??null},
  unexpected_sources:{a_to_b:links[0]?.unexpected??null,b_to_a:links[1]?.unexpected??null}},null,2)+'\n');
 if(events.length)await writeMissing('events.jsonl.gz',gzipSync(events.map(event=>JSON.stringify(event)).join(String.fromCharCode(10))+String.fromCharCode(10)));
 await writeMissing('clock_markers_node.json',JSON.stringify(events.filter(event=>event.kind==='clock_marker'),null,2)+'\n');
 if(postedBrowserMarkers.length)await writeMissing('clock_markers_browser.json',JSON.stringify({markers:postedBrowserMarkers},null,2)+'\n');
 await writeMissing('system_id_evidence.json',JSON.stringify({initial:conditioningInitial,commands:conditioningBrowser,completion:conditioningRelease})+'\n');
 await writeMissing('instrument_clock_node.json',JSON.stringify(instrumentNode)+'\n');await writeMissing('instrument_clock_browser.json',JSON.stringify(instrumentBrowser)+'\n');await writeMissing('startup_samples.json',JSON.stringify(startupSamples)+'\n');
 const rawTurnLog=await readFile(turnLogPath,'utf8').catch(()=> '');
 await writeFile(root+'/turn_server_log.txt',rawTurnLog.replaceAll(turnUsername,'[redacted-user]').replaceAll(turnCredential,'[redacted-credential]')).catch(()=>{});
 server.closeAllConnections();await new Promise(r=>server.close(r));for(const timer of traceTimers)clearTimeout(timer);await movieServer.close();await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
