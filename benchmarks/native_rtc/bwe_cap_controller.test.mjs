import test from 'node:test';
import assert from 'node:assert/strict';
import {chooseBweCapAction,BWE_CAP_PROTOCOL} from './bwe_cap_controller.mjs';
import {NATIVE_OBSERVATION_ABI,FEATURE_NAMES} from './sender_observation.mjs';
function observation(bwe,valid=1){const f=Array(16).fill(0);f[0]=bwe/4e6;f[7]=1;f[8]=1;f[9]=valid;return {observation_abi:NATIVE_OBSERVATION_ABI,feature_names:FEATURE_NAMES,features:f};}
test('85% headroom maps native estimate, not true phase capacity',()=>{assert.equal(chooseBweCapAction(observation(2e6)).encoder_max_bitrate_bps,1600000);assert.equal(chooseBweCapAction(observation(0.5e6)).encoder_max_bitrate_bps,300000);});
test('missing estimate holds own applied cap; no fake zero-bandwidth observation',()=>{assert.equal(chooseBweCapAction(observation(0,0)).encoder_max_bitrate_bps,4000000);});
test('extreme estimates choose only supported scalar caps and verified zero target',()=>{assert.equal(chooseBweCapAction(observation(1000)).encoder_max_bitrate_bps,150000);assert.equal(chooseBweCapAction(observation(1e7)).encoder_max_bitrate_bps,4000000);assert.equal(chooseBweCapAction(observation(2e6)).receiver_jitter_buffer_target_ms,0);assert.equal(BWE_CAP_PROTOCOL.transport_control,'native Chrome GCC remains active');});
test('legacy and nonfinite/unsupported observations reject',()=>{assert.throws(()=>chooseBweCapAction({features:Array(16).fill(0)}));const o=observation(2e6);o.features[0]=Infinity;assert.throws(()=>chooseBweCapAction(o));const p=observation(2e6);p.features[7]=0.123;assert.throws(()=>chooseBweCapAction(p));});
