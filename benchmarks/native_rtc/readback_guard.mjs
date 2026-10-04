// Causal readback consumer: no feature substitution, refit or safety certificate.
import {CONFIG} from './action_policy.mjs';
import {growthHoldAction} from './action_fallback_guard.mjs';
import {feedbackFeatures} from './repair3_policy.mjs';
import {CLOCK_DOMAIN,presentationPacket,receivePresentationPacket as receiveOriginal} from './presentation_feedback.mjs';
export {CLOCK_DOMAIN,presentationPacket};
export const GUARD_ABI='native_readback_fallback_growth_hold_v1',PRESENTATION_ABI='native_readback_guard_transport_v1',WIRE_CHANNEL='presentation-readback-guard-v1';
const check=(x,m)=>{if(!x)throw Error(m);};
export function receivePresentationPacket(packet,capture_request_ms,received_ms,previous=null,guarded=false){
 check(typeof guarded==='boolean','explicit readback guard usage required');
 const result=receiveOriginal(packet,capture_request_ms,received_ms,previous);
 result.presentation={...result.presentation,abi:PRESENTATION_ABI,fields_used_for_actuation:guarded};return result;
}
export function validateReadbackInput(feedback,presentation,now,guarded=null){
 check(typeof now==='number'&&Number.isFinite(now)&&now>=0&&now<=Number.MAX_SAFE_INTEGER,'bounded causal sample clock required');
 const ff=feedbackFeatures(feedback,now);
 check((feedback===null)===(presentation===null),'missing or unmatched readback input');
 if(presentation===null)return ff;
 check(presentation&&typeof presentation==='object'&&!Array.isArray(presentation),'exact transported readback required');
 const mode=presentation.fields_used_for_actuation;
 check(typeof mode==='boolean'&&(guarded===null||mode===guarded),'wrong readback usage mode');
 const packet=presentationPacket(presentation.source_id,presentation.presented_frames,presentation.readback_ms);
 const expected=receivePresentationPacket(packet,feedback.capture_request_ms,feedback.received_ms,null,mode).presentation;
 check(Object.keys(presentation).sort().join()===Object.keys(expected).sort().join()&&Object.keys(expected).every(k=>presentation[k]===expected[k])&&presentation.source_id===feedback.source_id,'readback source, clock, fields or delay decomposition mismatch');
 return ff;
}
export function readbackGrowthHoldAction(d,feedback,presentation,now){
 const ff=validateReadbackInput(feedback,presentation,now),legacy=growthHoldAction(d);
 check(d.feedback_features.every((x,i)=>x===ff[i]),'canonical feedback features changed');
 const readback=presentation!==null&&ff[2]===1&&presentation.forward_readback_delay_ms>=CONFIG.context_delay_ms;
 const hold=d.fallback&&(legacy.sender_congestion_alarm||readback),cap=legacy.canonical_cap_bps,own=legacy.actual_acknowledged_cap_bps,proposed=hold?Math.min(cap,own):cap;
 return {guard_abi:GUARD_ABI,encoder_max_bitrate_bps:proposed,receiver_jitter_buffer_target_ms:0,canonical_cap_bps:cap,actual_acknowledged_cap_bps:own,sender_congestion_alarm:legacy.sender_congestion_alarm,legacy_fresh_ack_delay_alarm:legacy.fresh_ack_delay_alarm,fresh_readback_delay_alarm:readback,forward_readback_delay_ms:presentation===null?null:presentation.forward_readback_delay_ms,fallback_growth_hold_active:hold,fallback_growth_hold_applied:proposed!==cap,neural_proposal_preserved:!d.fallback,native_deployment_qualified:false};
}
