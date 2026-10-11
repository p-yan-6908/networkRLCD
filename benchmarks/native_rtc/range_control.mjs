// Development pilot only: one fixed cap level for a whole session. Not the N1 instrument, never a controller.
export {captureLink} from './actuator_control.mjs';
export const ABI='native_range_pilot_v1';
// Ratios of the browser's estimate, frozen at the start of each hold as in N1. null is no ratio: the ceiling.
export const LEVELS=Object.freeze([0.25,0.65,0.85,1.05,null]);
export const HOLD_MS=3000,MAX_EPOCHS=6,FLOOR_BPS=150000,CEILING_BPS=4000000;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
export function requestedBps(level,bwe){
 if(!Number.isInteger(level)||level<0||level>=LEVELS.length||!finite(bwe)||bwe<=0)throw Error('pilot level and positive estimate required');
 const ratio=LEVELS[level];
 return ratio===null?CEILING_BPS:Math.max(FLOOR_BPS,Math.min(CEILING_BPS,Math.round(ratio*bwe)));
}
export class LevelSampler{
 constructor(level){if(!Number.isInteger(level)||level<0||level>=LEVELS.length)throw Error('pilot level required');this.level=level;this.current=null;this.ack=null;this.lastMs=null;}
 async observe(observation){
  const now=observation.sample_ms,bwe=observation.raw_source.bwe_bps;
  if(!finite(now)||now<0||this.lastMs!==null&&now<=this.lastMs)throw Error('strictly causal pilot sample clock');
  this.lastMs=now;
  const epoch=this.current===null?0:this.current.epoch+1,ready=this.current===null||this.ack!==null&&now>=this.ack+HOLD_MS;
  if(ready&&epoch<MAX_EPOCHS&&finite(bwe)&&bwe>0){
   const ratio=LEVELS[this.level],requested=requestedBps(this.level,bwe);
   this.current={abi:ABI,level:this.level,epoch,arm:this.level,ratio,assignment_ms:now,base_bwe_bps:bwe,requested_bps:requested,clipped:ratio!==null&&requested!==Math.round(ratio*bwe)};this.ack=null;
  }
  return structuredClone(this.current);
 }
 acknowledge(now,applied){if(this.current===null)return;if(!finite(now)||now<this.current.assignment_ms||applied!==this.current.requested_bps)throw Error('owned pilot cap acknowledgment required');if(this.ack===null)this.ack=now;}
}
