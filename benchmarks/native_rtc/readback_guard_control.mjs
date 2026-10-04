// Every peer computes the same canonical actor + causal guard on its actual history.
import {ActionPolicy,CONFIG,CANDIDATES,validateBundle} from './action_policy.mjs';
import {readbackGrowthHoldAction,validateReadbackInput,receivePresentationPacket,presentationPacket} from './readback_guard.mjs';
import {SenderContentEncoder,explorationCap} from './action_live_control.mjs';
export {CONFIG,SenderContentEncoder,explorationCap};
export class RepairPolicy extends ActionPolicy {
 constructor(bundle,guarded=false){if(!bundle||typeof guarded!=='boolean')throw Error('fitted bundle and explicit guard mode required');super(validateBundle(bundle));this.guarded=guarded;}
 observe(observation,feedback=null,presentation=null){
  validateReadbackInput(feedback,presentation,observation.sample_ms,this.guarded);
  const canonical=super.observe(observation,feedback),overlay=readbackGrowthHoldAction(canonical,feedback,presentation,observation.sample_ms),applied=this.guarded&&overlay.fallback_growth_hold_applied;
  return {...canonical,encoder_max_bitrate_bps:this.guarded?overlay.encoder_max_bitrate_bps:canonical.encoder_max_bitrate_bps,canonical_decision:canonical,guard_decision:overlay,guard_enabled:this.guarded,guard_applied:applied,effective_action_origin:applied?'readback_fallback_growth_hold':'canonical',modified_fallback_neural_credit:false,modified_fallback_safety_certified:false};
 }
}
export function warmRepair(bundle,iterations=64){
 if(!Number.isSafeInteger(iterations)||iterations<1||iterations>256)throw Error('bounded disposable warmup required');
 const disposable=new RepairPolicy(bundle,true);
 for(let i=0;i<iterations;i++){const f=Array(16).fill(0);f[0]=.25;f[7]=CANDIDATES[i%CANDIDATES.length]/4e6;f[8]=1;f[9]=1;const now=i*100,packet=i?receivePresentationPacket(presentationPacket(i,i,now-40),now-70,now-10,null,true):null;disposable.observe({sample_ms:now,features:f,content_features:[.2,.1,1]},packet?.canonical??null,packet?.presentation??null);}
}
