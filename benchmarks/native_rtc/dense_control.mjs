// Scalar-rate diagnostic controls; NEVER learned-policy credit.
import {RepairPolicy as LegacyShadow,CONFIG,SenderContentEncoder,warmRepair,explorationCap as legacyExploration} from './repair5_policy.mjs';
import {CAPS} from './repair3_policy.mjs';
export {CONFIG,SenderContentEncoder};
export const CONTROL_ABI='native_dense_diagnostic_control_v1';
export const ACTUATION_ABI='native_scalar_encoder_cap_playout_v1';
export const CAP_DOMAIN=Object.freeze([150000,4000000]);
export const BEHAVIORS=Object.freeze(['bwe','bwe-continuous','fixed450','gcc']);
export function scalarCap(value){if(typeof value!=='number'||!Number.isSafeInteger(value)||value<CAP_DOMAIN[0]||value>CAP_DOMAIN[1])throw Error('bounded integer scalar encoder cap required');return value;}
export function legacyCapProjection(value){scalarCap(value);return CAPS.findLast(c=>c<=value);}
export function explorationCap(behavior,step,seed,observation){const f=observation.features;if(!BEHAVIORS.includes(behavior)||!Array.isArray(f)||f.length!==16||!f.every(x=>typeof x==='number'&&Number.isFinite(x)&&x>=0)||![0,1].includes(f[9]))throw Error('declared dense diagnostic/sender features required');if(behavior==='fixed450')return 450000;if(behavior==='bwe-continuous'&&f[9]===1)return Math.max(CAP_DOMAIN[0],Math.min(CAP_DOMAIN[1],Math.floor(CONFIG.fallback_headroom*(f[0]*4000000))));return legacyExploration(behavior==='bwe-continuous'?'bwe':behavior,step,seed,observation);}
export class RepairPolicy{
 constructor(bundle=null){if(bundle!==null)throw Error('dense mechanism probe must not load a learned actor');this.shadow=new LegacyShadow();}
 acknowledge(cap,now){return this.shadow.acknowledge(legacyCapProjection(cap),now);}
 observe(observation,feedback=null){const f=observation.features.slice(),raw=f[7]*4000000,actual=scalarCap(Math.round(raw));if(Math.abs(raw-actual)>=.01)throw Error('actual scalar cap not integral');const projected=legacyCapProjection(actual);f[7]=projected/4000000;const d=this.shadow.observe({...observation,features:f},feedback);if(!d.fallback||d.learned_departure)throw Error('diagnostic shadow cannot earn learned credit');return {...d,shadow_only:true,actual_scalar_cap_bps:actual,shadow_projected_cap_bps:projected,shadow_projection:'legacy_floor_cap'};}
}
export function warmDense(bundle=null,iterations=64){if(bundle!==null)throw Error('dense warmup cannot load a learned actor');return warmRepair(null,iterations);}
export {warmDense as warmRepair};
