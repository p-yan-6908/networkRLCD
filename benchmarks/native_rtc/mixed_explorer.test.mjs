import test from 'node:test';
import assert from 'node:assert/strict';
import {NativeMixedExplorer} from './mixed_explorer.mjs';
import {explorationOrder} from './block_explorer.mjs';
for(const dwell of [250,1000,4000])test(`mixed ${dwell}ms block follows exact causal boundaries and seven caps`,()=>{const e=new NativeMixedExplorer(1701,100,dwell),order=explorationOrder(1701);assert.deepEqual(e.order,order);for(let i=0;i<7;i++){assert.equal(e.action(100+i*dwell).encoder_max_bitrate_bps,order[i]);assert.equal(e.action(100+(i+1)*dwell-.001).encoder_max_bitrate_bps,order[i]);}assert.throws(()=>e.action(99));});
test('mixed dwell must be one of the frozen choices',()=>{assert.throws(()=>new NativeMixedExplorer(1701,100,500));assert.throws(()=>new NativeMixedExplorer(0,100,250));});
