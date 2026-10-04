// V4 native-GCC deferral: preserve every learned V3 screen and causal feature.
import {RepairPolicy as CorePolicy,CONFIG as CORE_CONFIG,REPAIR_ABI as CORE_ABI,CAPS,explorationCap as coreExploration} from './repair3_policy.mjs';
export {CAPS,FEATURES,SenderContentEncoder,feedbackFeatures,compileMLP} from './repair3_policy.mjs';
export const REPAIR_ABI='native_temporal_repair_v4';
export const GCC_CEILING=CAPS.at(-1);
export const CONFIG=Object.freeze({...CORE_CONFIG,fallback:'native_gcc',gcc_ceiling_bps:GCC_CEILING});
export function coreBundle(bundle){
 if(bundle.model_abi!==REPAIR_ABI||Object.keys(bundle.config).sort().join()!==Object.keys(CONFIG).sort().join()||Object.entries(CONFIG).some(([k,v])=>bundle.config[k]!==v))throw Error('repair4 ABI/config required');
 return {...bundle,model_abi:CORE_ABI,config:{...CORE_CONFIG}};
}
export class RepairPolicy{
 constructor(bundle=null){this.bundle=bundle;this.core=new CorePolicy(bundle===null?null:coreBundle(bundle));}
 acknowledge(cap,now){return this.core.acknowledge(cap,now);}
 observe(observation,feedback=null){const d=this.core.observe(observation,feedback);d.bwe_reference_action_index=d.baseline_action_index;d.baseline_action_index=CAPS.length-1;if(d.fallback){d.action_index=CAPS.length-1;d.encoder_max_bitrate_bps=GCC_CEILING;d.learned_action_index=null;}d.gcc_departure=!d.fallback&&d.encoder_max_bitrate_bps!==GCC_CEILING;d.learned_departure=d.learned_departure&&d.gcc_departure;return d;}
}
export function warmRepair(bundle,iterations=64){const p=new RepairPolicy(bundle),f=Array(16).fill(0);f[7]=CAPS[1]/4e6;f[9]=1;for(let i=0;i<iterations;i++){f[0]=(.3+(i%7)*.1)/4;p.observe({sample_ms:i*100,features:f,content_features:[0,0,0]});}return iterations;}
export function explorationCap(behavior,step,seed,observation){return behavior==='gcc'?GCC_CEILING:coreExploration(behavior,step,seed,observation);}
