// Existing sender-only 0.85-BWE headroom baseline, held for the registered
// three-second action window so its delivered outcomes can be clock-joined.
import {chooseBweCapAction,BWE_CAP_PROTOCOL} from './bwe_cap_controller.mjs';

export const BWE_HOLD_PROTOCOL=Object.freeze({
 abi:'native_bwe_cap_hold_v1',
 hold_ms:3000,
 max_epochs:6,
 source_policy:BWE_CAP_PROTOCOL,
});
const finite=value=>typeof value==='number'&&Number.isFinite(value);

export class BweCapHoldSampler{
 constructor(){this.current=null;this.ack=null;this.lastMs=null;}
 async observe(observation,_encoder,_meter,_link,policyInput){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal BWE hold sample clock');
  this.lastMs=now;
  const epoch=this.current===null?0:this.current.epoch+1;
  const ready=this.current===null||this.ack!==null&&now>=this.ack+BWE_HOLD_PROTOCOL.hold_ms;
  if(ready&&epoch<BWE_HOLD_PROTOCOL.max_epochs){
   const selected=chooseBweCapAction(policyInput);
   this.current={abi:BWE_HOLD_PROTOCOL.abi,policy:'bwe-headroom-085',epoch,
    assignment_ms:now,base_bwe_bps:finite(bwe)?bwe:null,
    requested_bps:selected.encoder_max_bitrate_bps,
    receiver_jitter_buffer_target_ms:selected.receiver_jitter_buffer_target_ms};
   this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){
  if(this.current===null)return;
  if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)throw Error('BWE baseline native cap readback mismatch');
  if(this.ack===null)this.ack=now;
 }
}
