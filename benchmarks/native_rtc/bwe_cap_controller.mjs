// Conventional cap adaptation on Chrome's own BWE; no phase, capacity or receiver labels.
import {NATIVE_ACTIONS} from './native_actuation.mjs';
import {NATIVE_OBSERVATION_ABI,FEATURE_NAMES} from './sender_observation.mjs';
export const BWE_CAP_PROTOCOL=Object.freeze({controller:'native_bwe_cap_headroom_v1',headroom:0.85,fixed_receiver_target_ms:0,missing_bwe:'hold current encoder cap',control_input:'only the versioned normalized sender observation',transport_control:'native Chrome GCC remains active'});
export function chooseBweCapAction(input){
 if(input.observation_abi!==NATIVE_OBSERVATION_ABI||JSON.stringify(input.feature_names)!==JSON.stringify(FEATURE_NAMES)||input.features?.length!==16||!input.features.every(v=>typeof v==='number'&&Number.isFinite(v)))throw Error('native normalized observation required');
 const actions=NATIVE_ACTIONS.filter(a=>a.receiver_jitter_buffer_target_ms===0);
 const observedCap=input.features[7]*4000000,current=actions.find(a=>Math.abs(a.encoder_max_bitrate_bps-observedCap)<0.001);
 if(!current)throw Error('unsupported current encoder cap');
 if(input.features[9]!==0&&input.features[9]!==1)throw Error('binary BWE validity required');
 if(input.features[9]===0)return current;
 const budget=input.features[0]*4000000*BWE_CAP_PROTOCOL.headroom;
 return actions.findLast(a=>a.encoder_max_bitrate_bps<=budget)??actions[0];
}
