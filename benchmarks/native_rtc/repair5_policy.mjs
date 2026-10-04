// V5 retains learned budgets and restores conservative BWE fallback.
import {RepairPolicy as CorePolicy,CONFIG as CORE_CONFIG,REPAIR_ABI as CORE_ABI,CAPS,explorationCap as coreExploration} from './repair3_policy.mjs';
export {CAPS,FEATURES,SenderContentEncoder,feedbackFeatures,compileMLP} from './repair3_policy.mjs';
export const REPAIR_ABI='native_temporal_repair_v5';
export const GCC_CEILING=CAPS.at(-1);
export const CONFIG=Object.freeze({...CORE_CONFIG,rtt_baseline_window_ms:4000,encoder_degradation_preference:'maintain-framerate'});
export function coreBundle(bundle){if(bundle.model_abi!==REPAIR_ABI||Object.keys(bundle.config).sort().join()!==Object.keys(CONFIG).sort().join()||Object.entries(CONFIG).some(([k,v])=>bundle.config[k]!==v))throw Error('repair5 ABI/config required');return {...bundle,model_abi:CORE_ABI,config:{...CORE_CONFIG}};}
export class RepairPolicy{
 constructor(bundle=null){this.bundle=bundle;this.core=new CorePolicy(bundle===null?null:coreBundle(bundle));this.rtt_samples=[];}
 acknowledge(cap,now){return this.core.acknowledge(cap,now);}
 observe(observation,feedback=null){const now=observation.sample_ms,f=[...observation.features];if(typeof now!=='number'||!Number.isFinite(now)||now<0||f.length!==16||!f.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0)||this.core.lastSample!==null&&now<this.core.lastSample)throw Error('causal repair5 clock/features required');if(this.core.lastSample!==null&&now-this.core.lastSample>CONFIG.reset_gap_ms)this.rtt_samples=[];if(f[10]===1&&f[1]<=0){f[1]=f[2]=f[10]=f[11]=0;}if(f[10]===1)this.rtt_samples.push([now,f[1]*150]);this.rtt_samples=this.rtt_samples.filter(([t])=>now-t<=CONFIG.rtt_baseline_window_ms);this.core.rttFloor=this.rtt_samples.length?Math.min(...this.rtt_samples.map(([,r])=>r)):null;const d=this.core.observe({...observation,features:f},feedback);d.bwe_reference_action_index=d.baseline_action_index;d.gcc_reference_action_index=CAPS.length-1;d.gcc_departure=!d.fallback&&d.encoder_max_bitrate_bps!==GCC_CEILING;d.learned_departure=d.learned_departure&&d.gcc_departure;return d;}
}
export function warmRepair(bundle,iterations=64){const p=new RepairPolicy(bundle),f=Array(16).fill(0);f[7]=CAPS[1]/4e6;f[9]=1;for(let i=0;i<iterations;i++){f[0]=(.3+(i%7)*.1)/4;p.observe({sample_ms:i*100,features:f,content_features:[0,0,0]});}return iterations;}
export function explorationCap(behavior,step,seed,observation){return behavior==='gcc'?GCC_CEILING:behavior==='fixed600'?CAPS[2]:coreExploration(behavior,step,seed,observation);}
