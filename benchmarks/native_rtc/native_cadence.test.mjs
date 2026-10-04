import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeCadenceAction} from './native_cadence.mjs';
const decision=()=>({encoder_max_bitrate_bps:150000,receiver_jitter_buffer_target_ms:0,fallback:false,predicted_frame_miss:Array(7).fill(.2),risk_disagreement:Array(7).fill(.1)});
test('only still-screened current cap can dwell until the exact owned-ack boundary',()=>{assert.equal(nativeCadenceAction(decision(),1000000,900,0,.5,.2).held_by_cadence,true);assert.equal(nativeCadenceAction(decision(),1000000,1000,0,.5,.2).held_by_cadence,false);});
test('unsafe current cap or fallback immediately releases, never weakens base screens',()=>{for(const reason of ['fallback','miss','spread']){const d=decision();if(reason==='fallback')d.fallback=true;else if(reason==='miss')d.predicted_frame_miss[3]=.9;else d.risk_disagreement[3]=.9;assert.equal(nativeCadenceAction(d,1000000,100,0,.5,.2).held_by_cadence,false);}const bad=decision();bad.predicted_frame_miss[0]=.9;assert.throws(()=>nativeCadenceAction(bad,1000000,100,0,.5,.2));assert.throws(()=>nativeCadenceAction(decision(),1000000,100,101,.5,.2));});
