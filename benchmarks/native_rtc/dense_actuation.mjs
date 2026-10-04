// Honest scalar maxBitrate ABI. NOT native 14-action ABI, FEC, codec or pacing.
export const NATIVE_ACTION_ABI='native_scalar_encoder_cap_playout_v1';
export const SCALAR_CAP_DOMAIN=Object.freeze([150000,4000000]);
function accessor(receiver){if(Object.hasOwn(receiver,'jitterBufferTarget'))return null;for(let p=Object.getPrototypeOf(receiver);p;p=Object.getPrototypeOf(p)){const d=Object.getOwnPropertyDescriptor(p,'jitterBufferTarget');if(d)return typeof d.get==='function'&&typeof d.set==='function'?d:null;}return null;}
export async function applyNativeAction(sender,receiver,action){
 if(!action||Object.keys(action).length!==2||!Object.hasOwn(action,'encoder_max_bitrate_bps')||!Object.hasOwn(action,'receiver_jitter_buffer_target_ms'))throw Error('only scalar encoder cap and native playout target are actuated');
 const rate=action.encoder_max_bitrate_bps,target=action.receiver_jitter_buffer_target_ms;
 if(!Number.isSafeInteger(rate)||rate<SCALAR_CAP_DOMAIN[0]||rate>SCALAR_CAP_DOMAIN[1]||target!==0)throw Error('unsupported scalar native action');
 const binding=accessor(receiver);if(!binding)throw Error('native jitterBufferTarget getter/setter unavailable; no shadow-property fallback');
 const previous=binding.get.call(receiver),p=sender.getParameters();if(!p.encodings?.length)throw Error('negotiated encoding required');
 binding.set.call(receiver,target);if(binding.get.call(receiver)!==target)throw Error('native playout target did not reflect requested action');
 p.encodings[0].maxBitrate=rate;p.encodings[0].maxFramerate=30;
 try{await sender.setParameters(p);}catch(error){binding.set.call(receiver,previous);throw error;}
 const actual=sender.getParameters().encodings[0].maxBitrate;if(actual!==rate)throw Error('native sender cap did not reflect requested action');
 return {native_action_abi:NATIVE_ACTION_ABI,scalar_cap_domain_bps:Array.from(SCALAR_CAP_DOMAIN),encoder_max_bitrate_bps:actual,native_jitter_target_supported:true,receiver_jitter_buffer_target_ms:binding.get.call(receiver),encoder_cap_is_not_wire_rate:true,FEC_or_encoder_latency_mode_actuated:false};
}
