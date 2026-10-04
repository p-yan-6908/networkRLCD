// Sender-only, causal features. Receiver pixels/relay capacity/queues are labels, not inputs.
export const NATIVE_OBSERVATION_ABI='native_sender_stats_v1';
export const FEATURE_NAMES=Object.freeze(['bwe_mbps','rtcp_rtt_ms','rtcp_rtt_observed_age_ms','rtp_payload_send_mbps','encoder_fps','encode_ms_per_frame','packet_send_delay_ms','encoder_cap_mbps','receiver_zero_target','bwe_valid','rtcp_rtt_valid','rtcp_rtt_age_known','byte_interval_valid','encode_interval_valid','packet_delay_valid','interval_s']);
export const FEATURE_SCALES=Object.freeze([4,150,1000,4,30,1000/30,150,4,1,1,1,1,1,1,1,0.1]);
export const FEATURE_LIMITS=Object.freeze([2.5,20,60,2.5,2,30,100,1,1,1,1,1,1,1,1,100]);
export const RAW_KEYS=Object.freeze(['stream_key','bwe_bps','rtcp_rtt_s','rtcp_rtt_measurements','bytes_sent','frames_encoded','total_encode_s','packets_sent','total_packet_send_delay_s','encoder_cap_bps','receiver_target_ms']);
export const OBSERVATION_PROTOCOL=Object.freeze({abi:NATIVE_OBSERVATION_ABI,dimension:16,feature_names:FEATURE_NAMES,feature_scales:FEATURE_SCALES,feature_limits:FEATURE_LIMITS,poll_ms:100,max_interval_ms:1000,default_history_steps:4,rtt_source:'linked remote-inbound-rtp; not STUN RTT',rtt_age_semantics:'time since observing counter advancement, not exact feedback arrival age',excluded_inputs:Object.freeze(['relay_capacity','relay_queue','scenario','future_trace','receiver_pixels','frame_deadline_labels','absolute_episode_time'])});
const nonnegative=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
const counter=v=>nonnegative(v)&&Number.isInteger(v);
const clean=v=>nonnegative(v)?v:null;
export function validateNativeObservationManifest(m){if(!m||m.native_observation_abi!==NATIVE_OBSERVATION_ABI||m.observation_dim!==16||!Number.isInteger(m.history_steps)||m.history_steps<1||m.history_steps>16||m.input_dim!==16*m.history_steps||JSON.stringify(m.feature_names)!==JSON.stringify(FEATURE_NAMES))throw Error('native sender observation/history ABI required; legacy feature meaning is incompatible');return true;}
export function selectSenderSource(stats,ownAction){
 const values=Array.isArray(stats)?stats:[...stats.values()];
 const primaries=values.filter(s=>s.type==='outbound-rtp'&&s.kind==='video'&&values.some(c=>c.id===s.codecId&&c.type==='codec'&&c.mimeType?.toLowerCase()==='video/vp8'));
 if(primaries.length!==1)throw Error('exactly one VP8 sender stream required');
 const s=primaries[0],transport=values.find(t=>t.id===s.transportId&&t.type==='transport');
 let pair=values.find(p=>p.id===transport?.selectedCandidatePairId&&p.type==='candidate-pair');
 if(!pair){const active=values.filter(p=>p.type==='candidate-pair'&&p.nominated&&p.state==='succeeded');if(active.length>1)throw Error('ambiguous selected transport');pair=active[0];}
 const remotes=values.filter(r=>r.type==='remote-inbound-rtp'&&(r.id===s.remoteId||r.localId===s.id));
 if(remotes.length>1)throw Error('ambiguous RTCP linkage');
 const r=remotes[0];
 const cap=ownAction.encoder_max_bitrate_bps,target=ownAction.receiver_jitter_buffer_target_ms;
 if(!nonnegative(cap)||cap<=0||(target!==null&&target!==0))throw Error('actual supported action readbacks required');
 return {stream_key:String(s.id)+':'+String(s.ssrc??''),bwe_bps:clean(pair?.availableOutgoingBitrate),rtcp_rtt_s:clean(r?.roundTripTime),rtcp_rtt_measurements:counter(r?.roundTripTimeMeasurements)?r.roundTripTimeMeasurements:null,
         bytes_sent:clean(s.bytesSent),frames_encoded:counter(s.framesEncoded)?s.framesEncoded:null,total_encode_s:clean(s.totalEncodeTime),packets_sent:counter(s.packetsSent)?s.packetsSent:null,total_packet_send_delay_s:clean(s.totalPacketSendDelay),encoder_cap_bps:cap,receiver_target_ms:target};
}
export class SenderObservationEncoder{
 constructor(){this.previous=null;this.rttCounter=null;this.rttObservedAt=null;}
 observe(source,now){
  if(typeof now!=='number'||!Number.isFinite(now)||now<0)throw Error('monotonic sender clock required');
  if(Object.keys(source).length!==RAW_KEYS.length||RAW_KEYS.some(k=>!Object.hasOwn(source,k)))throw Error('exact sender-only raw schema required; no oracle/receiver fields');
  if(typeof source.stream_key!=='string'||!source.stream_key||!nonnegative(source.encoder_cap_bps)||source.encoder_cap_bps<=0||(source.receiver_target_ms!==null&&source.receiver_target_ms!==0))throw Error('invalid sender stream/action readback');
  for(const key of RAW_KEYS.filter(k=>!['stream_key','receiver_target_ms'].includes(k))){if(source[key]!==null&&!nonnegative(source[key]))throw Error('invalid raw numeric field');}
  if(source.rtcp_rtt_measurements!==null&&!counter(source.rtcp_rtt_measurements))throw Error('integer RTCP counter required');
  let prior=this.previous;
  if(prior&&now<prior.now)throw Error('sender clock moved backward');
  if(prior&&prior.raw.stream_key!==source.stream_key){prior=null;this.rttCounter=null;this.rttObservedAt=null;}
  const dt=prior?now-prior.now:0,validInterval=!!prior&&dt>0&&dt<=OBSERVATION_PROTOCOL.max_interval_ms;
  const delta=(key)=>validInterval&&nonnegative(source[key])&&nonnegative(prior.raw[key])&&source[key]>=prior.raw[key]?source[key]-prior.raw[key]:null;
  const byteDelta=delta('bytes_sent'),frameDelta=delta('frames_encoded'),encodeDelta=delta('total_encode_s'),packetDelta=delta('packets_sent'),sendDelayDelta=delta('total_packet_send_delay_s');
  const bweValid=nonnegative(source.bwe_bps)&&source.bwe_bps>0;
  const rttValid=nonnegative(source.rtcp_rtt_s)&&(source.rtcp_rtt_measurements===null||source.rtcp_rtt_measurements>0);
  if(counter(source.rtcp_rtt_measurements)){
   if(this.rttCounter!==null&&source.rtcp_rtt_measurements>this.rttCounter&&rttValid)this.rttObservedAt=now;
   else if(this.rttCounter!==null&&source.rtcp_rtt_measurements<this.rttCounter)this.rttObservedAt=null;
   this.rttCounter=source.rtcp_rtt_measurements;
  }else{this.rttCounter=null;this.rttObservedAt=null;}
  const ageKnown=rttValid&&this.rttObservedAt!==null;
  const encodeValid=frameDelta!==null&&frameDelta>0&&encodeDelta!==null;
  const delayValid=packetDelta!==null&&packetDelta>0&&sendDelayDelta!==null;
  const unscaled=[bweValid?source.bwe_bps/1e6:0,rttValid?source.rtcp_rtt_s*1000:0,ageKnown?now-this.rttObservedAt:0,byteDelta!==null?byteDelta*8/(dt*1000):0,frameDelta!==null?frameDelta*1000/dt:0,encodeValid?encodeDelta*1000/frameDelta:0,delayValid?sendDelayDelta*1000/packetDelta:0,source.encoder_cap_bps/1e6,source.receiver_target_ms===0?1:0,
                  +bweValid,+rttValid,+ageKnown,+(byteDelta!==null),+encodeValid,+delayValid,dt/1000];
  const features=unscaled.map((x,i)=>Math.min(FEATURE_LIMITS[i],Math.max(0,x/FEATURE_SCALES[i])));
  if(!features.every(Number.isFinite))throw Error('nonfinite observation');
  const raw=Object.fromEntries(RAW_KEYS.map(k=>[k,source[k]]));this.previous={now,raw};
  return {observation_abi:NATIVE_OBSERVATION_ABI,sample_ms:now,interval_ms:dt,raw_source:raw,features,feature_names:FEATURE_NAMES,rtt_age_known:ageKnown};
 }
}
