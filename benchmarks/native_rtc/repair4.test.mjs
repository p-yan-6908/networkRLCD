import {legacyVideoConfig} from './streamed_video4.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {RepairPolicy,CONFIG,GCC_CEILING,explorationCap,warmRepair} from './repair4_policy.mjs';
const obs=(now,cap=300000)=>({sample_ms:now,features:[.5,.3,0,0,1,0,0,cap/4e6,0,1,1,0,0,0,1,0],content_features:[.2,.1,1]});
test('all no-model startup/low-BWE/stale/queue paths defer to native GCC',()=>{const p=new RepairPolicy();for(const now of [0,1000,2400]){const o=obs(now);o.features[0]=.075;assert.equal(p.observe(o).encoder_max_bitrate_bps,GCC_CEILING);}});
test('native GCC and old BWE are distinct explicit comparators',()=>{assert.equal(explorationCap('gcc',0,0,obs(0)),4e6);assert.equal(explorationCap('bwe',0,0,obs(0)),1.6e6);assert.equal(CONFIG.miss_budget,.1);assert.equal(CONFIG.bwe_headroom,.95);assert.equal(CONFIG.min_calibration_groups,3);});
test('V4 movie namespace is explicitly projected to frozen verified-inode loader',()=>{const config={source_kind:'recorded_video_repair_v4',video_source:{sha256:'a'.repeat(64)}};const mapped=legacyVideoConfig(config);assert.equal(mapped.source_kind,'recorded_video_repair_v2');assert.equal(mapped.video_source,config.video_source);assert.equal(config.source_kind,'recorded_video_repair_v4');assert.throws(()=>legacyVideoConfig({source_kind:'recorded_video_repair_v3'}),/versioned repair4/);});

test('warmup remains disposable and old ABI is rejected',()=>{assert.equal(warmRepair(null,64),64);assert.throws(()=>new RepairPolicy({model_abi:'native_temporal_repair_v3',config:{}}),/repair4/);});
