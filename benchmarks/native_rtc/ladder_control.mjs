// Development pilot only: two rule-based candidates, and fixed levels through the same code path.
// Not the N1 instrument and not a promoted controller.
export {captureLink} from './actuator_control.mjs';
export const ABI='native_ladder_pilot_v1';
// Ratios of the browser's estimate, frozen when a hold begins as in N1.
export const LADDER=Object.freeze([0.25,0.65,0.85,1.05]);
export const HOLD_MS=3000,MAX_EPOCHS=6,FAST_EPOCHS=12,FLOOR_BPS=150000,CEILING_BPS=4000000;
// Mean age of the presentation acknowledgements seen in the last second, in ms: below LOW the rule
// goes one step up, from HIGH one step down, from PANIC or without any acknowledgement to the bottom.
// A fast ladder also cuts to the bottom inside a hold, once GUARD has passed since its last change.
export const LOOKBACK_MS=1000,LOW_MS=104,HIGH_MS=132,PANIC_MS=159,GUARD_MS=1000;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
export function requestedBps(step,bwe){
 if(!Number.isInteger(step)||step<0||step>=LADDER.length||!finite(bwe)||bwe<=0)throw Error('ladder step and positive estimate required');
 return Math.max(FLOOR_BPS,Math.min(CEILING_BPS,Math.round(LADDER[step]*bwe)));
}
export function nextStep(step,age){
 if(age===null||age>=PANIC_MS)return 0;
 if(age>=HIGH_MS)return Math.max(0,step-1);
 if(age<LOW_MS)return Math.min(LADDER.length-1,step+1);
 return step;
}
export class PolicySampler{
 // policy: {kind:'fixed',step,arm} keeps one step; {kind:'ladder',fast,arm} starts at the top and follows the rule.
 constructor(policy){
  const fixed=policy?.kind==='fixed'&&Number.isInteger(policy.step)&&policy.step>=0&&policy.step<LADDER.length;
  const ladder=policy?.kind==='ladder'&&typeof policy.fast==='boolean';
  if(!policy||!(fixed||ladder)||!Number.isInteger(policy.arm)||policy.arm<0)throw Error('pilot policy required');
  this.kind=policy.kind;this.fast=ladder&&policy.fast;this.arm=policy.arm;this.step=fixed?policy.step:LADDER.length-1;
  this.limit=this.fast?FAST_EPOCHS:MAX_EPOCHS;
  this.current=null;this.ack=null;this.lastMs=null;this.seen=[];this.lastSource=null;
 }
 async observe(observation,encoder,meter,link,feedback){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal pilot sample clock');
  this.lastMs=now;
  if(feedback&&feedback.source_id!==this.lastSource){this.lastSource=feedback.source_id;this.seen.push({received_ms:feedback.received_ms,age_ms:feedback.received_ms-feedback.capture_request_ms});}
  this.seen=this.seen.filter(f=>f.received_ms>=now-LOOKBACK_MS);
  let total=0;for(const f of this.seen)total+=f.age_ms;
  const age=this.seen.length?total/this.seen.length:null;
  const epoch=this.current===null?0:this.current.epoch+1,ready=this.current===null||this.ack!==null&&now>=this.ack+HOLD_MS;
  const cut=!ready&&this.fast&&this.ack!==null&&this.step>0&&now>=this.ack+GUARD_MS&&age!==null&&age>=PANIC_MS;
  if((ready||cut)&&epoch<this.limit&&finite(bwe)&&bwe>0){
   const before=this.step;
   if(this.kind==='ladder'&&epoch>0)this.step=cut?0:nextStep(before,age);
   const decision=this.kind==='fixed'?'fixed':epoch===0?'start':cut?'cut':this.step>before?'up':this.step<before?'down':'hold';
   const requested=requestedBps(this.step,bwe);
   this.current={abi:ABI,kind:this.kind,fast:this.fast,epoch,arm:this.arm,step:this.step,ratio:LADDER[this.step],decision,feedback_age_ms:age,feedback_seen:this.seen.length,assignment_ms:now,base_bwe_bps:bwe,requested_bps:requested,clipped:requested!==Math.round(LADDER[this.step]*bwe)};this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){if(this.current===null)return;if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)throw Error('owned pilot cap acknowledgment required');if(this.ack===null)this.ack=now;}
}
