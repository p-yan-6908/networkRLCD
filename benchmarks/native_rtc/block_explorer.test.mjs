import test from 'node:test';
import assert from 'node:assert/strict';
import {explorationOrder,NativeBlockExplorer} from './block_explorer.mjs';
test('seeded permutation covers every supported cap once before repeat',()=>{const order=explorationOrder(101);assert.deepEqual([...order].sort((a,b)=>a-b),[150000,300000,600000,1000000,1600000,2500000,4000000]);assert.deepEqual(explorationOrder(101),order);assert.notDeepEqual(explorationOrder(211),order);});
test('block boundary holds one acknowledged command, with fixed zero target',()=>{const e=new NativeBlockExplorer(101,100);assert.deepEqual(e.action(1099),e.action(100));assert.notEqual(e.action(1100).encoder_max_bitrate_bps,e.action(1099).encoder_max_bitrate_bps);assert.deepEqual(e.action(7100),e.action(100));assert.equal(e.action(1100).receiver_jitter_buffer_target_ms,0);});
test('behavior seed/clock reject invalid and stale inputs',()=>{for(const s of [0,-1,1.5,2**32])assert.throws(()=>explorationOrder(s));assert.throws(()=>new NativeBlockExplorer(1,-1));assert.throws(()=>new NativeBlockExplorer(1,100).action(99));});
