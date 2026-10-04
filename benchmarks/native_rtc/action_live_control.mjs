// Local experimental learned control; immutable fitted weights and original guards.
import {ActionPolicy,CONFIG,CANDIDATES,validateBundle} from './action_policy.mjs';
import {SenderContentEncoder} from './repair5_policy.mjs';
import {explorationCap} from './dense_control.mjs';
export {CONFIG,SenderContentEncoder,explorationCap};
export class RepairPolicy extends ActionPolicy {
 constructor(bundle){if(!bundle)throw Error('sealed fitted action-outcome bundle required for every peer');super(validateBundle(bundle));}
}
export function warmRepair(bundle,iterations=64){
 if(!Number.isSafeInteger(iterations)||iterations<1||iterations>256)throw Error('bounded disposable warmup required');
 const disposable=new RepairPolicy(bundle);
 for(let i=0;i<iterations;i++){const f=Array(16).fill(0);f[0]=.25;f[7]=CANDIDATES[i%CANDIDATES.length]/4e6;f[8]=1;f[9]=1;const now=i*100;disposable.observe({sample_ms:now,features:f,content_features:[.2,.1,1]},i?{source_id:i,capture_request_ms:now-70,received_ms:now-10,presented_fps:30}:null);}
}
