import test from 'node:test';
import assert from 'node:assert/strict';
import {assignment,explorationCap,CAPS} from './excitation_control.mjs';
import {legacyVideoConfig} from './streamed_excitation_video.mjs';

test('seeded aliases hold cap across eight decisions and do not read feature values',()=>{
 const f=Array(16).fill(0);f[9]=1;
 for(const seed of [0,8101,4294967295])for(let epoch=0;epoch<60;epoch++){
  const cap=assignment('random-hold-a',epoch,seed);
  assert(CAPS.includes(cap));
  for(let i=0;i<8;i++)assert.equal(explorationCap('random-hold-b',epoch*8+i,seed,{features:f}),cap);
 }
});
test('invalid assignments reject and fixed control remains 450kbps',()=>{
 for(const args of [['unknown',0,1],['random-hold-a',-1,1],['random-hold-a',0,true],['random-hold-a',0,4294967296]])assert.throws(()=>assignment(...args));
 assert.equal(assignment('fixed450',15,8101),450000);
 assert.throws(()=>explorationCap('random-hold-a',0,8101,{features:Array(64).fill(0)}));
});
test('owned video namespace preserves old source physics and rejects other roles',()=>{
 const input={source_kind:'recorded_video_randomized_cap_hold_v1',video_sha:'unchanged'};
 assert.equal(legacyVideoConfig(input).source_kind,'recorded_video_repair_v5');
 assert.equal(input.source_kind,'recorded_video_randomized_cap_hold_v1');
 assert.throws(()=>legacyVideoConfig({source_kind:'recorded_video_exact_cap_coverage_v1'}));
});
