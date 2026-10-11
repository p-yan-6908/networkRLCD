// Development pilot only: one rule-based candidate that widens its margin after a drop, and fixed
// levels through the same code path. Not the N1 instrument and not a promoted controller.
export {captureLink} from './actuator_control.mjs';
export const ABI='native_margin_pilot_v1';
// Ratios of the browser's estimate, frozen when a hold begins as in N1.
export const LADDER=Object.freeze([0.25,0.65,0.85,1.05]);
export const SAFE=0,CRUISE=1,HIGH=2,START=3;
export const HOLD_MS=3000,MAX_EPOCHS=40,FLOOR_BPS=150000,CEILING_BPS=4000000;
// The signal is the mean age of the presentation acknowledgements seen in the last second, in ms,
// with the marks of the controller pilot. The rule holds the top for its first hold and then cruises
// at 0.65. CALM_HOLDS holds in a row under LOW take it up to 0.85; from HIGH it comes back to 0.65.
// From PANIC, or without any acknowledgement when a hold begins, it goes to 0.25: at once if GUARD has
// passed since its last change. It stays there until MEMORY has passed since lateness was last seen.
// Every further drop it sees doubles the memory, up to MEMORY_MAX.
export const LOOKBACK_MS=1000,LOW_MS=104,HIGH_MS=132,PANIC_MS=159,GUARD_MS=1000;
export const CALM_HOLDS=2,MEMORY_MS=30000,MEMORY_MAX_MS=120000;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
export function requestedBps(step,bwe){
 if(!Number.isInteger(step)||step<0||step>=LADDER.length||!finite(bwe)||bwe<=0)throw Error('ladder step and positive estimate required');
 return Math.max(FLOOR_BPS,Math.min(CEILING_BPS,Math.round(LADDER[step]*bwe)));
}
export class PolicySampler{
 // policy: {kind:'fixed',step,arm} keeps one step; {kind:'margin',arm} follows the rule.
 constructor(policy){
  const fixed=policy?.kind==='fixed'&&Number.isInteger(policy.step)&&policy.step>=0&&policy.step<LADDER.length;
  if(!policy||!(fixed||policy.kind==='margin')||!Number.isInteger(policy.arm)||policy.arm<0)throw Error('pilot policy required');
  this.kind=policy.kind;this.arm=policy.arm;this.step=fixed?policy.step:START;
  this.drops=0;this.memory=MEMORY_MS;this.lastLate=null;this.calm=0;
  this.current=null;this.ack=null;this.lastMs=null;this.seen=[];this.lastSource=null;
 }
 async observe(observation,encoder,meter,link,feedback){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal pilot sample clock');
  this.lastMs=now;
  if(feedback&&feedback.source_id!==this.lastSource){this.lastSource=feedback.source_id;this.seen.push({received_ms:feedback.received_ms,age_ms:feedback.received_ms-feedback.capture_request_ms});}
  this.seen=this.seen.filter(f=>f.received_ms>=now-LOOKBACK_MS);
  let total=0;for(const f of this.seen)total+=f.age_ms;
  const age=this.seen.length?total/this.seen.length:null,late=age!==null&&age>=PANIC_MS,rule=this.kind==='margin';
  if(rule&&late&&this.step===SAFE&&this.lastLate!==null)this.lastLate=now;   // lateness seen at the bottom keeps the memory running
  const epoch=this.current===null?0:this.current.epoch+1,ready=this.current===null||this.ack!==null&&now>=this.ack+HOLD_MS;
  const cut=!ready&&rule&&this.ack!==null&&this.step>SAFE&&now>=this.ack+GUARD_MS&&late;
  if((ready||cut)&&epoch<MAX_EPOCHS&&finite(bwe)&&bwe>0){
   const before=this.step;let decision=rule?'start':'fixed';
   if(rule&&epoch>0){
    if(cut||late||age===null){
     if(before>SAFE){this.drops+=1;this.memory=Math.min(MEMORY_MAX_MS,MEMORY_MS*2**(this.drops-1));}
     this.step=SAFE;this.lastLate=now;this.calm=0;decision=cut?'cut':before>SAFE?'drop':'hold';
    }else if(before===SAFE){
     if(now-this.lastLate<this.memory)decision='hold';else{this.step=CRUISE;this.calm=0;decision='return';}
    }else if(before===START){this.step=CRUISE;this.calm=0;decision='cruise';
    }else if(before===CRUISE){
     this.calm=age<LOW_MS?this.calm+1:0;
     if(this.calm>=CALM_HOLDS){this.step=HIGH;this.calm=0;decision='up';}else decision='hold';
    }else if(age>=HIGH_MS){this.step=CRUISE;this.calm=0;decision='down';
    }else decision='hold';
   }
   const requested=requestedBps(this.step,bwe);
   this.current={abi:ABI,kind:this.kind,epoch,arm:this.arm,step:this.step,ratio:LADDER[this.step],decision,feedback_age_ms:age,feedback_seen:this.seen.length,drops:this.drops,memory_ms:this.memory,last_late_ms:this.lastLate,assignment_ms:now,base_bwe_bps:bwe,requested_bps:requested,clipped:requested!==Math.round(LADDER[this.step]*bwe)};this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){if(this.current===null)return;if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)throw Error('owned pilot cap acknowledgment required');if(this.ack===null)this.ack=now;}
}
