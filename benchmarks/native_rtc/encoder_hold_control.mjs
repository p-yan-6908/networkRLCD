// Prescribed conventional diagnostic sequence, never learned or oracle-conditioned.
export const HOLD_STEPS=16;
export const SEQUENCE=Object.freeze([450000,300000,900000,300000,900000,450000,300000,900000,300000,450000,900000,450000]);
export function holdProbeCap(behavior,step){
 if(!['random-hold-a','random-hold-b','fixed450'].includes(behavior)||!Number.isSafeInteger(step)||step<0)throw Error('legal conventional behavior and causal step required');
 return behavior==='fixed450'?450000:SEQUENCE[Math.floor(step/HOLD_STEPS)%SEQUENCE.length];
}
