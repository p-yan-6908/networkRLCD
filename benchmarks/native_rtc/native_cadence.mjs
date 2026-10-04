import {NATIVE_ACTIONS} from './native_actuation.mjs';
export const CADENCE_CONTROLLER='native_rlcd_screened_cadence_v1';
export const CADENCE_PROTOCOL=Object.freeze({abi:'native_screened_cadence_v1',dwell_ms:1000,clock:'owned_changed_command_ack_ms',current_cap_prediction_screen_required:true,unsafe_current_or_fallback_immediate_release:true});
const caps=NATIVE_ACTIONS.filter(a=>a.receiver_jitter_buffer_target_ms===0).map(a=>a.encoder_max_bitrate_bps);
const finite=x=>typeof x==='number'&&Number.isFinite(x);
// Owned elapsed-since-command time is arbiter state, never a neural model feature.
export function nativeCadenceAction(decision,ownCap,sampleMs,lastChangedAckMs,riskCutoff,disagreementCutoff,dwellMs=1000){
 if(![sampleMs,lastChangedAckMs,riskCutoff,disagreementCutoff,dwellMs].every(finite)||lastChangedAckMs<0||lastChangedAckMs>sampleMs||dwellMs<=0||riskCutoff<0||riskCutoff>1||disagreementCutoff<0||disagreementCutoff>1)throw Error('owned monotonic ack clock and native screens required');
 if(!caps.includes(ownCap)||!caps.includes(decision.encoder_max_bitrate_bps)||decision.receiver_jitter_buffer_target_ms!==0||typeof decision.fallback!=='boolean')throw Error('supported zero-target native decision required');
 const miss=decision.predicted_frame_miss,spread=decision.risk_disagreement;if(miss?.length!==7||spread?.length!==7||![...miss,...spread].every(x=>finite(x)&&x>=0&&x<=1))throw Error('finite native per-action predictions required');
 const own=caps.indexOf(ownCap),proposed=caps.indexOf(decision.encoder_max_bitrate_bps),eligible=i=>miss[i]<=riskCutoff&&spread[i]<=disagreementCutoff;
 if(!decision.fallback&&!eligible(proposed))throw Error('base native proposal violates its declared prediction screens');
 const held=!decision.fallback&&proposed!==own&&eligible(own)&&sampleMs-lastChangedAckMs<dwellMs;
 return {action:{encoder_max_bitrate_bps:held?ownCap:caps[proposed],receiver_jitter_buffer_target_ms:0},held_by_cadence:held,elapsed_since_changed_ack_ms:sampleMs-lastChangedAckMs,dwell_ms:dwellMs,reason:held?'screened_current_cap_dwell':'base_or_emergency_release',prediction_screen_is_not_safety_certificate:true};
}
