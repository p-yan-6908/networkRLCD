// Independent recorded-input hypothesis; no existing native collector imports this.
import {CONFIG,scalarCap} from './action_policy.mjs';
import {FEATURE_LIMITS} from './sender_observation.mjs';
export const GUARD_ABI='native_action_fallback_growth_hold_v1';
const finite=x=>typeof x==='number'&&Number.isFinite(x),check=(x,m)=>{if(!x)throw Error(m);};
const reasons=new Set(['learned','sender_congestion','startup_or_feedback','risk_or_support','upward_guard','training_skill']);
export function growthHoldAction(d){
 check(d&&typeof d==='object','verified canonical decision required');
 const f=d.features,ff=d.feedback_features;
 check(Array.isArray(f)&&f.length===16&&f.every((x,i)=>finite(x)&&x>=0&&x<=FEATURE_LIMITS[i])&&f.slice(8,15).every(x=>x===0||x===1),'bounded actual sender state required');
 check(Array.isArray(ff)&&ff.length===4&&ff.every((x,i)=>finite(x)&&x>=0&&x<=[20,20,1,2][i])&&(ff[2]===0||ff[2]===1),'bounded causal feedback features required');
 check(typeof d.fallback==='boolean'&&reasons.has(d.reason)&&d.fallback===(d.reason!=='learned'),'canonical fallback/reason identity required');
 check(d.receiver_jitter_buffer_target_ms===0,'unchanged native zero receiver target required');
 const own=scalarCap(Math.round(f[7]*4e6));check(Math.abs(f[7]*4e6-own)<.01,'integer actual acknowledged cap required');
 const cap=scalarCap(d.encoder_max_bitrate_bps),sender=d.reason==='sender_congestion',ack=ff[2]===1&&ff[0]*150>=CONFIG.context_delay_ms,hold=d.fallback&&(sender||ack),proposed=hold?Math.min(cap,own):cap;
 return {guard_abi:GUARD_ABI,encoder_max_bitrate_bps:proposed,receiver_jitter_buffer_target_ms:0,canonical_cap_bps:cap,actual_acknowledged_cap_bps:own,sender_congestion_alarm:sender,fresh_ack_delay_alarm:ack,fallback_growth_hold_active:hold,fallback_growth_hold_applied:proposed!==cap,neural_proposal_preserved:!d.fallback,native_deployment_qualified:false};
}
