// M10 support-only observability. Receipt clocks are local performance.now().
// No fitted relay clock, receiver presentation feedback or receiver outcomes.
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const finite=x=>typeof x==='number'&&Number.isFinite(x)&&x>=0;
export function counter(row,key){
 const present=!!row&&Object.hasOwn(row,key),raw=present?row[key]:null;
 const valid=present&&finite(raw);
 return {status:!present?'absent':valid?'present':'invalid',value:valid?raw:null,
  raw_value:present?(typeof raw==='number'&&!Number.isFinite(raw)?String(raw):raw):null};
}
export class MechanismObserverM10{
 constructor(){this.native=[];this.relay=[];this.errors=[];this.lastFeedback=null;this.latestRelay=null;this.running=false;}
 start(){
  this.running=true;this.epoch=performance.now();
  this.task=(async()=>{let next=this.epoch;while(this.running){
   while(this.running&&performance.now()<next)await sleep(Math.max(1,next-performance.now()));
   if(!this.running)break;
   const browser_request_ms=performance.now(),sequence=this.relay.length+1;
   try{
    const response=await fetch('/mechanism-snapshot',{method:'POST',headers:{'content-type':'application/json'},
     body:JSON.stringify({sequence,browser_request_ms,scheduled_ms:next})});
    const snapshot=await response.json(),browser_receive_ms=performance.now();
    const item={sequence,scheduled_ms:next,browser_request_ms,browser_receive_ms,snapshot,
     status:response.ok&&snapshot.sequence===sequence?'present':'invalid'};
    this.relay.push(item);if(item.status==='present')this.latestRelay=item;
   }catch(error){this.errors.push({channel:'relay',browser_request_ms,error:String(error)});}
   next=this.epoch+100*(Math.floor((performance.now()-this.epoch)/100)+1);
  }})();
 }
 observe(stats,parameters,poll){
  const available_ms=performance.now(),rows=[...stats.values()];
  const outs=rows.filter(s=>s.type==='outbound-rtp'&&s.kind==='video');
  const out=outs.length===1?outs[0]:null;
  const remotes=out?rows.filter(s=>s.type==='remote-inbound-rtp'&&(s.id===out.remoteId||s.localId===out.id)):[];
  const remote=remotes.length===1?remotes[0]:null;
  const transports=rows.filter(s=>s.type==='transport'&&s.selectedCandidatePairId);
  const ids=[...new Set(transports.map(s=>s.selectedCandidatePairId))];
  const pair=ids.length===1?rows.find(s=>s.type==='candidate-pair'&&s.id===ids[0]):null;
  const outFields={},rtcp={},pairFields={};
  for(const k of ['bytesSent','packetsSent','headerBytesSent','retransmittedBytesSent','framesEncoded',
    'keyFramesEncoded','totalEncodeTime','totalPacketSendDelay','targetBitrate','totalEncodedBytesTarget',
    'frameWidth','frameHeight','framesPerSecond','nackCount','pliCount','firCount'])outFields[k]=counter(out,k);
  // QP/quality, receiver frame/deadline and presentation fields are deliberately absent.
  const reason=out?.qualityLimitationReason;
  outFields.qualityLimitationReason={status:reason===undefined?'absent':['none','cpu','bandwidth','other'].includes(reason)?'present':'invalid',
   value:['none','cpu','bandwidth','other'].includes(reason)?reason:null,raw_value:reason??null};
  for(const k of ['roundTripTime','totalRoundTripTime','roundTripTimeMeasurements','reportsReceived','fractionLost','jitter'])rtcp[k]=counter(remote,k);
  for(const k of ['availableOutgoingBitrate','currentRoundTripTime','totalRoundTripTime','responsesReceived','requestsSent','bytesSent','bytesReceived'])pairFields[k]=counter(pair,k);
  const feedbackKey=rtcp.reportsReceived.status==='present'?'reportsReceived':rtcp.roundTripTimeMeasurements.status==='present'?'roundTripTimeMeasurements':null;
  const value=feedbackKey?rtcp[feedbackKey].value:null,old=this.lastFeedback;
  let feedback={status:'absent',counter_key:feedbackKey,counter_value:value,first_counter_observation_ms:null,
   last_detected_advance_ms:null,advance_detection_interval_ms:null,observed_age_bounds_ms:null,
   true_feedback_generation_age:{status:'not_exposed',value:null},transport_cc_feedback_age:{status:'not_exposed',value:null}};
  if(feedbackKey){
   const same=old&&old.id===remote.id&&old.key===feedbackKey;
   if(!same){this.lastFeedback={id:remote.id,key:feedbackKey,value,at:available_ms,first:available_ms,advance:null,interval:null};}
   else if(value<old.value){this.lastFeedback={id:remote.id,key:feedbackKey,value,at:available_ms,first:available_ms,advance:null,interval:null};feedback.status='counter_reset';}
   else{this.lastFeedback={...old,value,at:available_ms};if(value>old.value){this.lastFeedback.advance=available_ms;this.lastFeedback.interval=[old.at,available_ms];}}
   const now=this.lastFeedback;
   if(feedback.status!=='counter_reset')feedback.status=now.advance===null?'unknown_initial_counter_age':'present';
   Object.assign(feedback,{first_counter_observation_ms:now.first,last_detected_advance_ms:now.advance,
    advance_detection_interval_ms:now.interval,observed_age_bounds_ms:now.interval?[available_ms-now.interval[1],available_ms-now.interval[0]]:null});
  }
  const latest=this.latestRelay;
  this.native.push({abi:'native_mechanism_observation_m10_v1',available_ms,stats_request_ms:poll.request_ms,
   stats_response_ms:poll.response_ms,outbound_count:outs.length,outbound_id:out?.id??null,
   remote_inbound_count:remotes.length,remote_inbound_id:remote?.id??null,remote_local_id:remote?.localId??null,
   selected_pair_count:ids.length,selected_pair_id:pair?.id??null,
   native_timestamps_unmapped:{outbound_ms:out?.timestamp??null,remote_inbound_ms:remote?.timestamp??null,pair_ms:pair?.timestamp??null},
   outbound:outFields,rtcp,pair:pairFields,feedback,
   encoder_cap_bps:counter(parameters?.encodings?.[0],'maxBitrate'),encoder_active:parameters?.encodings?.[0]?.active??null,
   latest_relay_sequence:latest?.sequence??null,latest_relay_receipt_ms:latest?.browser_receive_ms??null,
   relay_receipt_age_ms:latest?available_ms-latest.browser_receive_ms:null,
   online_clock_mapping_used:false,receiver_qoe_fields_read:false});
 }
 async stop(){this.running=false;await this.task;return {abi:'native_mechanism_assay_m10_v1',
  native:this.native,relay:this.relay,errors:this.errors,relay_poll_ms:100,native_poll_ms:25,
  clock_policy:'sender receipt fences only; no fitted clock or mapped native timestamps'};}
}
