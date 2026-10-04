// Preregistered train-only cap exploration; not learned or safety-qualified.
import {RepairPolicy,CONFIG,SenderContentEncoder,warmRepair} from './dense_control.mjs';
export {RepairPolicy,CONFIG,SenderContentEncoder,warmRepair};
export const CAPS=Object.freeze([300000,450000,900000]);
export const BEHAVIORS=Object.freeze(['random-hold-a','random-hold-b','fixed450']);
export const EPOCH_STEPS=8;
export function assignment(behavior,epoch,seed){
 if(!BEHAVIORS.includes(behavior)||!Number.isInteger(epoch)||epoch<0||epoch>512||!Number.isInteger(seed)||seed<0||seed>0xffffffff)throw Error('bounded declared training hold/epoch/seed required');
 if(behavior==='fixed450')return 450000;
 let x=(seed^Math.imul(epoch+1,0x9e3779b9))>>>0;
 x=(x^(x>>>16))>>>0;x=Math.imul(x,0x7feb352d)>>>0;
 x=(x^(x>>>15))>>>0;x=Math.imul(x,0x846ca68b)>>>0;
 x=(x^(x>>>16))>>>0;
 return CAPS[x%CAPS.length];
}
export function explorationCap(behavior,step,seed,observation){const f=observation.features;
 if(!Number.isInteger(step)||step<0||step>EPOCH_STEPS*512||!Array.isArray(f)||f.length!==16||!f.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0)||![0,1].includes(f[9]))throw Error('causal sender features and bounded exploration step required');
 return assignment(behavior,Math.floor(step/EPOCH_STEPS),seed);
}
