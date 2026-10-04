// Causal sender-only adapter state. No trace phase, relay queue, capacity or pixels.
import {FEATURE_SCALES,FEATURE_LIMITS} from './sender_observation.mjs';
export const CONTEXT_CONTROLLER='native_causal_context_horizon_v5';
export const CONTEXT_PROTOCOL=Object.freeze({abi:CONTEXT_CONTROLLER,window_ms:2000,max_gap_ms:1000,bwe_drop_fraction:.2,offered_over_bwe_ratio:1.05,rtt_rise_ms:30,rtt_max_observed_age_ms:1000,packet_send_delay_ms:25,consecutive_alarm_samples:2,long_hold_after_alarm_ms:2000,clean_recovery_ms:1000,risk_cutoff:.5,disagreement_cutoff:.2,default_horizon:3,deterioration_horizon:20,no_queue_capacity_pixel_or_phase_inputs:true,prediction_screen_not_safety_certificate:true});
export class NativeContextSwitch{
 constructor(){this.reset();}
 reset(){this.last=null;this.stream=null;this.window=[];this.mode='base';this.bad=0;this.alarmAt=null;this.cleanAt=null;}
 observe(f,now,stream){
  if(!Number.isFinite(now)||now<0||(this.last!==null&&now<=this.last))throw Error('strictly increasing context clock required');
  if(typeof stream!=='string'||!stream||!Array.isArray(f)||f.length!==16||f.some((v,i)=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>FEATURE_LIMITS[i])||f.slice(8,15).some(v=>v!==0&&v!==1))throw Error('exact native context features/stream required');
  const p=CONTEXT_PROTOCOL,previous=this.mode,gap=this.last!==null&&now-this.last>p.max_gap_ms;if(this.stream!==null&&(this.stream!==stream||gap))this.reset();this.stream=stream;this.last=now;this.window=this.window.filter(r=>now-r[0]<=p.window_ms);
  const bwe=f[9]===1?f[0]*FEATURE_SCALES[0]*1e6:null,offered=f[12]===1?f[3]*FEATURE_SCALES[3]*1e6:null,rtt=f[10]===1&&f[11]===1&&f[2]*FEATURE_SCALES[2]<=p.rtt_max_observed_age_ms?f[1]*FEATURE_SCALES[1]:null,delay=f[14]===1?f[6]*FEATURE_SCALES[6]:null;
  this.window.push([now,bwe,rtt]);const rates=this.window.filter(r=>r[1]!==null).map(r=>r[1]),rtts=this.window.filter(r=>r[2]!==null).map(r=>r[2]),peak=rates.length?Math.max(...rates):0,floor=rtts.length?Math.min(...rtts):null;
  const alarms={bwe_drop_under_load:bwe!==null&&offered!==null&&peak>0&&bwe<=peak*(1-p.bwe_drop_fraction)&&offered>=bwe*p.offered_over_bwe_ratio,rtcp_rtt_rise:rtt!==null&&floor!==null&&rtt-floor>=p.rtt_rise_ms,packet_send_delay:delay!==null&&delay>=p.packet_send_delay_ms},alarm=Object.values(alarms).some(Boolean),valid=(bwe!==null&&offered!==null)||rtt!==null||delay!==null;
  if(alarm){this.bad++;this.alarmAt=now;this.cleanAt=null;}else{this.bad=0;if(valid){if(this.cleanAt===null)this.cleanAt=now;}else this.cleanAt=null;}
  if(this.mode==='base'&&this.bad>=p.consecutive_alarm_samples)this.mode='long';
  if(this.mode==='long'&&!alarm&&valid&&this.alarmAt!==null&&now-this.alarmAt>=p.long_hold_after_alarm_ms&&this.cleanAt!==null&&now-this.cleanAt>=p.clean_recovery_ms)this.mode='base';
  return {selected_model:this.mode,switched:this.mode!==previous,alarms,consecutive_alarm_samples:this.bad,valid_causal_signal:valid,peak_bwe_bps:peak,rtcp_rtt_floor_ms:floor,elapsed_since_alarm_ms:this.alarmAt===null?null:now-this.alarmAt,reason:this.mode==='long'&&alarm?'alarm_long':this.mode==='long'?'hold_long':previous==='long'?'clear_to_short':'short_default',prediction_screen_not_safety_certificate:true};
 }
}
