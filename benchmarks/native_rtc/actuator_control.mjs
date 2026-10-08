// Diagnostic IID instrument only; never a learned/controller action ABI.
export const ABI='native_actuator_instrument_v1';
export const RATIOS=Object.freeze([0.65,0.85,1.05]);
export const HOLD_MS=3000,MAX_EPOCHS=6;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const status=(v,fraction=false)=>({status:v===null||v===undefined?'absent':finite(v)&&v>=0&&(!fraction||v<=1)?'present':'invalid',value:finite(v)&&v>=0&&(!fraction||v<=1)?v:null});
export async function assignedArm(seed,epoch){
 if(!Number.isInteger(seed)||seed<0||seed>0xffffffff||!Number.isInteger(epoch)||epoch<0)throw Error('bounded instrument seed/epoch required');
 for(let attempt=0;attempt<100;attempt++){
  const bytes=new TextEncoder().encode(`${ABI}:${seed}:${epoch}:${attempt}`);
  const digest=await crypto.subtle.digest('SHA-256',bytes),draw=new DataView(digest).getUint32(0,false);
  if(draw<0xffffffff)return draw%3;
 }
 throw Error('instrument hash rejection exhausted');
}
export function captureLink(stats,source){
 const values=[...stats.values()],s=values.find(x=>String(x.id)+':'+String(x.ssrc??'')===source.stream_key);
 const candidates=values.filter(x=>x.type==='remote-inbound-rtp'&&(x.id===s?.remoteId||x.localId===s?.id));
 if(candidates.length>1)throw Error('ambiguous instrument RTCP source');
 const r=candidates[0];
 return {loss_fraction:status(r?.fractionLost,true),jitter_ms:status(finite(r?.jitter)?r.jitter*1000:null)};
}
export class InstrumentSampler{
 constructor(seed){this.seed=seed;this.current=null;this.ack=null;this.lastMs=null;this.previous=null;this.lastRtt=null;}
 async observe(observation,encoder,meter,link){
  const now=observation.sample_ms,raw=observation.raw_source,bwe=raw.bwe_bps,rtt=raw.rtcp_rtt_s,fields=encoder.fields,previous=this.previous;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal instrument sample clock');
  this.lastMs=now;
  let qp=null,size=null,actual=null,send=null;
  if(previous&&raw.stream_key===previous.observation.raw_source.stream_key){
   const dt=now-previous.observation.sample_ms,old=previous.encoder.fields,f=fields.framesEncoded.value,of=old.framesEncoded.value;
   const df=finite(f)&&finite(of)?f-of:null;
   if(dt>0&&dt<=1000){
    const before=previous.observation.raw_source.bytes_sent;
    if(finite(raw.bytes_sent)&&finite(before)&&raw.bytes_sent>=before)send=(raw.bytes_sent-before)*8000/dt;
    if(meter.status===previous.meter.status&&meter.status==='active'){
     const delta=meter.total_bytes-previous.meter.total_bytes,count=meter.total_frames-previous.meter.total_frames;
     if(delta>=0){actual=delta*8000/dt;if(count>0)size=delta/count;}
    }
    if(finite(df)&&df>0){const q=fields.qpSum.value,oq=old.qpSum.value;if(finite(q)&&finite(oq)&&q>=oq)qp=(q-oq)/df;}
   }
  }
  const trend=finite(rtt)&&finite(this.lastRtt)?(rtt-this.lastRtt)*1000:null;if(finite(rtt))this.lastRtt=rtt;
  const context={bwe_bps:status(bwe),rtt_ms:status(finite(rtt)?rtt*1000:null),rtt_trend_ms:{status:finite(trend)?'present':'absent',value:trend},loss_fraction:link.loss_fraction,jitter_ms:link.jitter_ms,previous_requested_bps:status(raw.encoder_cap_bps),encoder_target_bps:structuredClone(fields.targetBitrate),actual_encoder_bps:status(actual),actual_send_bps:status(send),qp:status(qp),mean_encoded_frame_bytes:status(size),complexity:structuredClone(observation.content_features),previous_action:this.current?.arm??null,rtt_age_known:Boolean(observation.features[11])};
  this.previous=structuredClone({observation,encoder,meter});
  const epoch=this.current===null?0:this.current.epoch+1,ready=this.current===null||this.ack!==null&&now>=this.ack+HOLD_MS;
  if(ready&&epoch<MAX_EPOCHS&&finite(bwe)&&bwe>0){
   const arm=await assignedArm(this.seed,epoch),caps=RATIOS.map(r=>Math.max(150000,Math.min(4000000,Math.round(r*bwe))));
   this.current={abi:ABI,seed:this.seed,epoch,arm,ratio:RATIOS[arm],assignment_ms:now,base_bwe_bps:bwe,requested_bps:caps[arm],candidates_bps:caps,clipped_or_aliased:new Set(caps).size!==3,propensity:1/3,propensities:[1/3,1/3,1/3],state:context};this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){if(this.current===null)return;if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)throw Error('owned instrument cap acknowledgment required');if(this.ack===null)this.ack=now;}
}
