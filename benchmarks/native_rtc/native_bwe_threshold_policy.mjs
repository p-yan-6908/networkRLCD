// Fixed sender-only BWE threshold policies for the preregistered V10 native validation.
export const BWE_THRESHOLD_POLICY_PROTOCOL = Object.freeze({
 abi:'native_bwe_threshold_policy_v1',
 state_threshold_bps:500000,
 ratios:Object.freeze({fixed065:0.65,bwe_threshold_low:0.65,bwe_threshold_high:1.05}),
 hold_ms:3000,
 max_epochs:6,
 inputs:'only the current pre-action sender BWE estimate',
});
const finite=value=>typeof value==='number'&&Number.isFinite(value);

export class BweThresholdPolicySampler {
 constructor(behavior){
  if(!['fixed065','bwe_threshold'].includes(behavior))throw Error('registered V10 BWE policy required');
  this.behavior=behavior;this.current=null;this.ack=null;this.lastMs=null;
 }
 async observe(observation){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal V10 sender sample clock');
  this.lastMs=now;
  const epoch=this.current===null?0:this.current.epoch+1;
  const ready=this.current===null||this.ack!==null&&now>=this.ack+BWE_THRESHOLD_POLICY_PROTOCOL.hold_ms;
  if(ready&&epoch<BWE_THRESHOLD_POLICY_PROTOCOL.max_epochs){
   if(!finite(bwe)||bwe<=0)throw Error('V10 action boundary lacks a valid pre-action BWE estimate');
   const stateBin=bwe<BWE_THRESHOLD_POLICY_PROTOCOL.state_threshold_bps?'bwe_lt_500k':'bwe_ge_500k';
   const ratio=this.behavior==='fixed065'?0.65:(bwe>=BWE_THRESHOLD_POLICY_PROTOCOL.state_threshold_bps?1.05:0.65);
   const requested=Math.max(150000,Math.min(4000000,Math.floor(ratio*bwe+0.5)));
   this.current={abi:BWE_THRESHOLD_POLICY_PROTOCOL.abi,policy:this.behavior,epoch,ratio,state_bin:stateBin,
    base_bwe_bps:bwe,requested_bps:requested,assignment_ms:now};
   this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){
  if(this.current===null)return;
  if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)
   throw Error('V10 policy cap did not match native readback');
  if(this.ack===null)this.ack=now;
 }
}
