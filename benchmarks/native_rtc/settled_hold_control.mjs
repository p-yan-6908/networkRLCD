// Versioned longer random holds; seed/epoch only, never learned or target-conditioned.
import {assignment} from './excitation_control.mjs';
export const EPOCH_STEPS=32;
export function settledHoldCap(behavior,step,seed,observation){const f=observation.features;
 if(!Number.isInteger(step)||step<0||step>EPOCH_STEPS*512||!Array.isArray(f)||f.length!==16||!f.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0)||![0,1].includes(f[9]))throw Error('bounded causal 32-step hold required');
 return assignment(behavior,Math.floor(step/EPOCH_STEPS),seed);
}
