// Continuous measured BWE after common conditioning; a randomized action assay.
// No 500 kbps state membership is required, and no controller is learned.
export const SUPPORT_PROTOCOL=Object.freeze({abi:'native_continuous_support_v13',baseline_cap_bps:4000000,
 eligible_bwe_bounds_bps:Object.freeze([240000,3800000]),decision_open_ms:18000,decision_close_ms:18300,
 history_samples:11,minimum_history_span_ms:900,maximum_sample_gap_ms:250,
 ratios:Object.freeze([0.65,1.05]),hold_ms:3000,endpoint_window_ms:Object.freeze([1800,2600]),state_reference_bps:500000});
const finite=v=>typeof v==='number'&&Number.isFinite(v);
export function supportCheck(history,elapsed){
 const p=SUPPORT_PROTOCOL,tail=history.slice(-p.history_samples),span=tail.length?tail.at(-1).sample_ms-tail[0].sample_ms:0;
 const gap=tail.length>1?Math.max(...tail.slice(1).map((x,i)=>x.sample_ms-tail[i].sample_ms)):Infinity;
 const passed=elapsed>=p.decision_open_ms&&elapsed<=p.decision_close_ms&&tail.length===p.history_samples&&span>=p.minimum_history_span_ms&&gap<=p.maximum_sample_gap_ms&&
  tail.every(x=>finite(x.bwe_bps)&&x.bwe_bps>=p.eligible_bwe_bounds_bps[0]&&x.bwe_bps<=p.eligible_bwe_bounds_bps[1]);
 const x=passed?tail.reduce((sum,x)=>sum+Math.log2(x.bwe_bps/p.state_reference_bps),0)/tail.length:null;
 return {passed,elapsed_ms:elapsed,history_samples:tail.length,span_ms:span,max_gap_ms:gap,
  bwe_history_bps:tail.map(x=>x.bwe_bps),sample_history_ms:tail.map(x=>x.sample_ms),continuous_log2_bwe:x,
  geometric_mean_bwe_bps:x===null?null:p.state_reference_bps*2**x};
}
export class SupportQualifiedRatioSampler{
 constructor(seed,trialId,config){
  if(!Number.isInteger(seed)||seed<0||seed>0xffffffff||!trialId||!config||![0,1].includes(config.pair_slot)||typeof config.pair_id!=='string'||!config.pair_id)
   throw Error('registered continuous support and paired randomization required');
  this.seed=seed;this.trialId=trialId;this.config=structuredClone(config);this.history=[];this.startMs=null;this.lastMs=null;this.current=null;this.qualification=null;this.ack=null;
 }
 start(now){if(!finite(now)||this.startMs!==null)throw Error('single sender origin required');this.startMs=now;}
 async observe(observation){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(this.startMs===null||!finite(now)||now<this.startMs||this.lastMs!==null&&now<=this.lastMs)throw Error('strict sender support clock required');
  this.lastMs=now;
  if(this.current!==null)return structuredClone(this.current);
  if(this.qualification!==null&&this.config.support_only)return null;
  this.history.push({sample_ms:now,bwe_bps:bwe});this.history=this.history.slice(-SUPPORT_PROTOCOL.history_samples);
  const check=supportCheck(this.history,now-this.startMs);if(!check.passed)return null;
  this.qualification=check;if(this.config.support_only)return null;
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`networkrlcd-native-v13:${this.seed}:${this.config.pair_id}`));
  const draw=new DataView(bytes).getUint32(0,false),arm=(draw&1)^this.config.pair_slot,ratio=SUPPORT_PROTOCOL.ratios[arm],requested=Math.floor(ratio*bwe+0.5);
  if(requested<150000||requested>4000000)throw Error('action contrast would be clipped');
  this.current={abi:SUPPORT_PROTOCOL.abi,epoch:0,arm,ratio,propensity:0.5,propensity_scope:'marginal over the pair-order draw',
   conditional_propensity_given_prior_pair_slot:this.config.pair_slot?1:0.5,randomization_seed:this.seed,trial_id:this.trialId,
   pair_id:this.config.pair_id,pair_slot:this.config.pair_slot,draw_uint32:draw,base_bwe_bps:bwe,state_bin:'continuous_bwe',
   continuous_log2_bwe:check.continuous_log2_bwe,requested_bps:requested,assignment_ms:now,support_qualification:check};
  return structuredClone(this.current);
 }
 acknowledge(now,applied){
  if(this.current===null){if(applied!==SUPPORT_PROTOCOL.baseline_cap_bps)throw Error('common ceiling changed');return;}
  if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)throw Error('randomized cap readback mismatch');
  if(this.ack===null)this.ack=now;
 }
 evidence(){return {protocol:SUPPORT_PROTOCOL,config:this.config,qualification:this.qualification,action_assigned:this.current!==null,ack_ms:this.ack,
  final_check:supportCheck(this.history,this.lastMs-this.startMs)};}
}
