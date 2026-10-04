// Seed-only train assignment: every arm each epoch; all nine transitions per 3-epoch block.
export const ABI='native_three_arm_balanced_hold_control_v1';
export const EPOCH_STEPS=32;
const CAPS=Object.freeze([300000,450000,900000]);
const MODES=Object.freeze(['random-hold-a','random-hold-b','fixed450']);
const PERMS=Object.freeze([[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]]);
export const MAX_BLOCK_SEED=Math.floor((0xffffffff-2)/3);
export function encodedSeed(blockSeed,repetition){if(!Number.isInteger(blockSeed)||blockSeed<0||blockSeed>MAX_BLOCK_SEED||!Number.isInteger(repetition)||repetition<0||repetition>2)throw Error('bounded block seed/exact three repetitions required');return blockSeed*3+repetition;}
function mix(seed,counter){let x=(seed^Math.imul(counter+1,0x9e3779b9))>>>0;x=(x^(x>>>16))>>>0;x=Math.imul(x,0x7feb352d)>>>0;x=(x^(x>>>15))>>>0;x=Math.imul(x,0x846ca68b)>>>0;return (x^(x>>>16))>>>0;}
export function assignment(mode,epoch,seed){if(!MODES.includes(mode)||!Number.isInteger(epoch)||epoch<0||epoch>512||!Number.isInteger(seed)||seed<0||seed>encodedSeed(MAX_BLOCK_SEED,2))throw Error('bounded balanced training hold/epoch/encoded seed required');if(mode==='fixed450')return 450000;const blockSeed=Math.floor(seed/3),repetition=seed%3,initial=PERMS[mix(blockSeed,0)%6];let offset=0;if(epoch){const block=Math.floor((epoch-1)/3),position=(epoch-1)%3,shifts=PERMS[mix(blockSeed,block+1)%6];offset=shifts.slice(0,position+1).reduce((a,b)=>a+b,0)%3;}return CAPS[initial[(repetition+offset)%3]];}
export function settledHoldCap(mode,step,seed,observation){const f=observation.features;if(!Number.isInteger(step)||step<0||step>EPOCH_STEPS*512||!Array.isArray(f)||f.length!==16||!f.every(x=>typeof x==='number'&&Number.isFinite(x)&&x>=0)||![0,1].includes(f[9]))throw Error('bounded causal 32-step balanced hold required');return assignment(mode,Math.floor(step/EPOCH_STEPS),seed);}
