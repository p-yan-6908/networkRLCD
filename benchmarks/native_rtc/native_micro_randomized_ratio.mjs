// Micro-randomized native BWE-ratio action sampler; no fitted policy.
export const MICRO_RATIO_PROTOCOL=Object.freeze({
 abi:'native_micro_randomized_ratio_v1',
 ratios:Object.freeze([0.65,1.05]),
 propensity:0.5,
 state_threshold_bps:500000,
 hold_ms:3000,
 max_epochs:6,
 randomization:'SHA256 first uint32 big-endian; low bit selects ratio; keyed by seed, trial ID, epoch',
});
const finite=value=>typeof value==='number'&&Number.isFinite(value);

async function drawFor(seed,trialId,epoch){
 const input=`networkrlcd-native-v9:${seed}:${trialId}:${epoch}`;
 const bytes=new TextEncoder().encode(input),digest=await crypto.subtle.digest('SHA-256',bytes);
 return new DataView(digest).getUint32(0,false);
}

export class MicroRandomizedRatioSampler{
 constructor(seed,trialId){
  if(!Number.isInteger(seed)||seed<0||seed>0xffffffff||typeof trialId!=='string'||!trialId)
   throw Error('registered V9 action randomization seed and trial ID required');
  this.seed=seed;this.trialId=trialId;this.current=null;this.ack=null;this.lastMs=null;
 }
 async observe(observation){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal V9 sender sample clock');
  this.lastMs=now;
  const epoch=this.current===null?0:this.current.epoch+1;
  const ready=this.current===null||this.ack!==null&&now>=this.ack+MICRO_RATIO_PROTOCOL.hold_ms;
  if(ready&&epoch<MICRO_RATIO_PROTOCOL.max_epochs){
   if(!finite(bwe)||bwe<=0)throw Error('V9 action boundary lacks a valid pre-action BWE estimate');
   const draw=await drawFor(this.seed,this.trialId,epoch),arm=draw&1,ratio=MICRO_RATIO_PROTOCOL.ratios[arm];
   const requested=Math.max(150000,Math.min(4000000,Math.floor(ratio*bwe+0.5)));
   this.current={abi:MICRO_RATIO_PROTOCOL.abi,epoch,arm,ratio,propensity:MICRO_RATIO_PROTOCOL.propensity,
    randomization_seed:this.seed,trial_id:this.trialId,draw_uint32:draw,
    base_bwe_bps:bwe,state_bin:bwe<MICRO_RATIO_PROTOCOL.state_threshold_bps?'bwe_lt_500k':'bwe_ge_500k',
    requested_bps:requested,assignment_ms:now};
   this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){
  if(this.current===null)return;
  if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)
   throw Error('V9 randomized action did not match native cap readback');
  if(this.ack===null)this.ack=now;
 }
}
