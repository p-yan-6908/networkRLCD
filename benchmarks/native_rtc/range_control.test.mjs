import test from 'node:test';
import assert from 'node:assert/strict';
import {ABI,LEVELS,HOLD_MS,MAX_EPOCHS,LevelSampler,requestedBps,captureLink} from './range_control.mjs';

const poll=(ms,bwe)=>({sample_ms:ms,raw_source:{bwe_bps:bwe}});

test('a level is a ratio of the estimate inside the cap domain, or the ceiling',()=>{
 assert.deepEqual([...LEVELS],[0.25,0.65,0.85,1.05,null]);
 assert.equal(requestedBps(0,400000),150000);      // a quarter would be 100 kbit/s: the floor
 assert.equal(requestedBps(1,400000),260000);
 assert.equal(requestedBps(3,3900000),4000000);    // above the ceiling
 assert.equal(requestedBps(4,123456),4000000);     // no ratio
 assert.equal(requestedBps(2,300001),255001);      // 255000.85 rounds half up, as in N1
 assert.throws(()=>requestedBps(5,400000));
 assert.throws(()=>requestedBps(1,0));
 assert.equal(typeof captureLink,'function');
});

test('one level for the whole session, a new hold three seconds after each acknowledgement',async()=>{
 const s=new LevelSampler(1);
 assert.equal(await s.observe(poll(100,null)),null);                 // no estimate yet: no assignment
 const first=await s.observe(poll(200,400000));
 assert.deepEqual(first,{abi:ABI,level:1,epoch:0,arm:1,ratio:0.65,assignment_ms:200,base_bwe_bps:400000,requested_bps:260000,clipped:false});
 assert.throws(()=>s.acknowledge(210,300000));                        // another cap was applied
 s.acknowledge(210,260000);s.acknowledge(310,260000);
 assert.equal((await s.observe(poll(300,900000))).epoch,0);          // held: the estimate moved, the cap did not
 assert.equal((await s.observe(poll(210+HOLD_MS-1,900000))).epoch,0);
 const second=await s.observe(poll(210+HOLD_MS,900000));
 assert.equal(second.epoch,1);assert.equal(second.requested_bps,585000);assert.equal(second.arm,1);
 await assert.rejects(s.observe(poll(210+HOLD_MS,900000)));           // the clock must advance
});

test('the session ends after six holds and the ceiling never changes',async()=>{
 const s=new LevelSampler(4);let now=0,last=null;
 for(let k=0;k<3*MAX_EPOCHS;k++){now+=HOLD_MS;last=await s.observe(poll(now,500000+k));s.acknowledge(now+1,4000000);}
 assert.equal(last.epoch,MAX_EPOCHS-1);assert.equal(last.ratio,null);assert.equal(last.requested_bps,4000000);assert.equal(last.clipped,false);
 const low=new LevelSampler(0),a=await low.observe(poll(10,300000));
 assert.equal(a.requested_bps,150000);assert.equal(a.clipped,true);
 assert.throws(()=>new LevelSampler(5));
});
