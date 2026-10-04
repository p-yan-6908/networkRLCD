// Explicit local clock only. No model input, cap selection or safety certification.
export const PRESENTATION_ABI='native_presentation_readback_transport_v1',CLOCK_DOMAIN='same_browser_page_performance_v1',WIRE_CHANNEL='presentation-readback-v1';
function require(condition,message){if(!condition)throw Error(message);}
function number(x){return typeof x==='number'&&Number.isFinite(x)&&x>=0&&x<=Number.MAX_SAFE_INTEGER;}
export function presentationPacket(source_id,presented_frames,readback_ms){require(Number.isSafeInteger(source_id)&&source_id>=1&&Number.isSafeInteger(presented_frames)&&presented_frames>=1&&number(readback_ms),'valid identified callback packet required');return {source_id,presented_frames,readback_ms,clock_domain:CLOCK_DOMAIN};}
export function receivePresentationPacket(packet,capture_request_ms,received_ms,previous=null){
 require(packet&&typeof packet==='object'&&!Array.isArray(packet)&&Object.keys(packet).sort().join()==='clock_domain,presented_frames,readback_ms,source_id'&&packet.clock_domain===CLOCK_DOMAIN,'declared exact readback wire fields and same-page clock required');
 presentationPacket(packet.source_id,packet.presented_frames,packet.readback_ms);
 require(number(capture_request_ms)&&number(received_ms)&&capture_request_ms<=packet.readback_ms&&packet.readback_ms<=received_ms,'future or pre-capture readback forbidden');
 if(previous!==null)require(previous&&Number.isSafeInteger(previous.source_id)&&Number.isSafeInteger(previous.presented_frames)&&number(previous.received_ms)&&packet.source_id>previous.source_id&&packet.presented_frames>=previous.presented_frames&&received_ms>previous.received_ms,'stale, duplicate or out-of-order readback feedback');
 const fps=previous===null?0:1000*(packet.presented_frames-previous.presented_frames)/(received_ms-previous.received_ms);
 return {canonical:{source_id:packet.source_id,capture_request_ms,received_ms,presented_fps:fps},presentation:{abi:PRESENTATION_ABI,clock_domain:CLOCK_DOMAIN,source_id:packet.source_id,presented_frames:packet.presented_frames,capture_request_ms,readback_ms:packet.readback_ms,received_ms,forward_readback_delay_ms:packet.readback_ms-capture_request_ms,return_ack_delay_ms:received_ms-packet.readback_ms,capture_to_ack_received_ms:received_ms-capture_request_ms,fields_used_for_actuation:false}};
}
