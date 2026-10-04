// Native encoder caps + receiver playout target. NOT simulator FEC/codec-mode ABI.
export const NATIVE_ACTION_ABI='native_encoder_cap_playout_v1';
const RATES=Object.freeze([150000,300000,600000,1000000,1600000,2500000,4000000]);
export const NATIVE_ACTIONS=Object.freeze(RATES.flatMap(rate=>[null,0].map(target=>Object.freeze({encoder_max_bitrate_bps:rate,receiver_jitter_buffer_target_ms:target}))));
export function validateNativeActionManifest(metadata){if(!metadata||metadata.native_action_abi!==NATIVE_ACTION_ABI||metadata.action_count!==NATIVE_ACTIONS.length)throw Error('native 14-action ABI required; legacy simulator checkpoint is incompatible');return true;}
function accessor(receiver){if(Object.hasOwn(receiver,'jitterBufferTarget'))return null;for(let p=Object.getPrototypeOf(receiver);p;p=Object.getPrototypeOf(p)){const d=Object.getOwnPropertyDescriptor(p,'jitterBufferTarget');if(d)return typeof d.get==='function'&&typeof d.set==='function'?d:null;}return null;}
export async function applyNativeAction(sender,receiver,action){
 if(!action||Object.keys(action).length!==2||!Object.hasOwn(action,'encoder_max_bitrate_bps')||!Object.hasOwn(action,'receiver_jitter_buffer_target_ms'))throw Error('only encoder cap and receiver playout target are actuated; no FEC/codec/pacing override');
 const rate=action.encoder_max_bitrate_bps,target=action.receiver_jitter_buffer_target_ms;
 if(!RATES.includes(rate)||(target!==null&&target!==0))throw Error('unsupported native action');
 const binding=accessor(receiver);if(target===0&&!binding)throw Error('native jitterBufferTarget getter/setter unavailable; no shadow-property fallback');
 const previous=binding?binding.get.call(receiver):null,p=sender.getParameters();
 if(!p.encodings?.length)throw Error('negotiated encoding required');
 if(binding){binding.set.call(receiver,target);if(binding.get.call(receiver)!==target)throw Error('native playout target did not reflect requested action');}
 p.encodings[0].maxBitrate=rate;p.encodings[0].maxFramerate=30;
 try{await sender.setParameters(p);}catch(error){if(binding)binding.set.call(receiver,previous);throw error;}
 const actual=sender.getParameters().encodings[0].maxBitrate;
 if(actual!==rate)throw Error('native sender cap did not reflect requested action');
 return {native_action_abi:NATIVE_ACTION_ABI,action_count:NATIVE_ACTIONS.length,encoder_max_bitrate_bps:actual,
         native_jitter_target_supported:!!binding,receiver_jitter_buffer_target_ms:binding?binding.get.call(receiver):null,
         encoder_cap_is_not_wire_rate:true,FEC_or_encoder_latency_mode_actuated:false};
}
