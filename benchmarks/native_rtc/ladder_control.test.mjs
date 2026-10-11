import test from 'node:test';
import assert from 'node:assert/strict';
import {ABI,LADDER,HOLD_MS,MAX_EPOCHS,FAST_EPOCHS,LOW_MS,HIGH_MS,PANIC_MS,GUARD_MS,PolicySampler,nextStep,requestedBps} from './ladder_control.mjs';

const poll=(ms,bwe)=>({sample_ms:ms,raw_source:{bwe_bps:bwe}});
const ack=(id,received,age)=>({source_id:id,capture_request_ms:received-age,received_ms:received,presented_fps:30});

test('the rule: up below the low mark, down from the high mark, to the bottom from the panic mark or with no feedback',()=>{
 assert.deepEqual([...LADDER],[0.25,0.65,0.85,1.05]);
 assert.deepEqual([LOW_MS,HIGH_MS,PANIC_MS,GUARD_MS],[104,132,159,1000]);
 assert.equal(nextStep(1,LOW_MS-1),2);assert.equal(nextStep(3,50),3);          // the top stays the top
 assert.equal(nextStep(1,LOW_MS),1);assert.equal(nextStep(2,HIGH_MS-1),2);     // inside the band: hold
 assert.equal(nextStep(2,HIGH_MS),1);assert.equal(nextStep(0,HIGH_MS),0);      // one step down, not below the bottom
 assert.equal(nextStep(3,PANIC_MS),0);assert.equal(nextStep(2,null),0);        // to the bottom
 assert.equal(requestedBps(0,400000),150000);assert.equal(requestedBps(3,3900000),4000000);
 assert.equal(requestedBps(2,300001),255001);
});

test('a fixed policy keeps its step whatever the feedback says',async()=>{
 const s=new PolicySampler({kind:'fixed',step:1,arm:2});let now=0,last=null,id=0;
 for(let k=0;k<3*MAX_EPOCHS;k++){now+=HOLD_MS;last=await s.observe(poll(now,500000),null,null,null,ack(++id,now-10,400));s.acknowledge(now+1,last.requested_bps);}
 assert.equal(last.epoch,MAX_EPOCHS-1);assert.equal(last.step,1);assert.equal(last.decision,'fixed');assert.equal(last.arm,2);
 assert.equal(last.requested_bps,325000);assert.equal(last.abi,ABI);assert.equal(last.feedback_age_ms,400);assert.equal(last.fast,false);
 assert.throws(()=>new PolicySampler({kind:'fixed',step:4,arm:0}));assert.throws(()=>new PolicySampler({kind:'ladder',arm:0}));
});

test('the ladder starts at the top and moves at hold boundaries with the age of the last second',async()=>{
 const s=new PolicySampler({kind:'ladder',fast:false,arm:0});let id=0;
 const first=await s.observe(poll(100,300000),null,null,null,null);
 assert.equal(first.step,3);assert.equal(first.decision,'start');assert.equal(first.feedback_age_ms,null);assert.equal(first.requested_bps,315000);
 s.acknowledge(104,315000);
 // Polls through the hold: acknowledgements aged 170 ms, one of them seen twice and counted once.
 for(let t=200;t<3100;t+=100){const f=ack(t<400?1:++id+1,t-5,170);assert.equal((await s.observe(poll(t,300000),null,null,null,f)).epoch,0);}
 const second=await s.observe(poll(104+HOLD_MS,600000),null,null,null,ack(999,3100,170));
 assert.equal(second.epoch,1);assert.equal(second.decision,'down');assert.equal(second.step,0);   // 170 ms: to the bottom, but only now
 assert.equal(second.feedback_age_ms,170);assert.equal(second.requested_bps,150000);assert.equal(second.clipped,false);
 assert.ok(second.feedback_seen>=9&&second.feedback_seen<=11);                                     // the last second only
 s.acknowledge(3110,150000);
 for(let t=3200;t<6200;t+=100)await s.observe(poll(t,600000),null,null,null,ack(2000+t,t-5,90));
 const third=await s.observe(poll(3110+HOLD_MS,600000),null,null,null,ack(9000,6105,90));
 assert.equal(third.decision,'up');assert.equal(third.step,1);assert.equal(third.requested_bps,390000);
 s.acknowledge(6120,390000);
 // A second without any acknowledgement: the receiver shows nothing, so the rule goes to the bottom.
 for(let t=6200;t<9200;t+=100)await s.observe(poll(t,600000),null,null,null,ack(9000,6105,90));
 const fourth=await s.observe(poll(6120+HOLD_MS,600000),null,null,null,ack(9000,6105,90));
 assert.equal(fourth.feedback_age_ms,null);assert.equal(fourth.feedback_seen,0);assert.equal(fourth.step,0);assert.equal(fourth.decision,'down');
});

test('a fast ladder cuts to the bottom inside a hold, after the guard and only on late acknowledgements',async()=>{
 const s=new PolicySampler({kind:'ladder',fast:true,arm:1});let id=0;
 const first=await s.observe(poll(100,800000),null,null,null,null);
 assert.equal(first.step,3);assert.equal(first.fast,true);s.acknowledge(104,first.requested_bps);
 // Late acknowledgements from the start: nothing happens before the guard has passed.
 for(let t=200;t<104+GUARD_MS;t+=100)assert.equal((await s.observe(poll(t,800000),null,null,null,ack(++id,t-5,200))).epoch,0);
 const cut=await s.observe(poll(104+GUARD_MS,800000),null,null,null,ack(++id,1100,200));
 assert.equal(cut.epoch,1);assert.equal(cut.decision,'cut');assert.equal(cut.step,0);assert.equal(cut.requested_bps,200000);
 s.acknowledge(1110,200000);
 // At the bottom there is nothing to cut: the next change comes at the hold boundary.
 for(let t=1200;t<1110+HOLD_MS;t+=100)assert.equal((await s.observe(poll(t,800000),null,null,null,ack(++id,t-5,200))).epoch,1);
 const next=await s.observe(poll(1110+HOLD_MS,800000),null,null,null,ack(++id,4100,90));
 assert.equal(next.epoch,2);assert.equal(next.decision,'hold');assert.equal(next.step,0);   // the second still averages late ones
 // No acknowledgement is not a reason to cut inside a hold; and a slow ladder never cuts.
 const quiet=new PolicySampler({kind:'ladder',fast:true,arm:1});
 const q=await quiet.observe(poll(100,800000),null,null,null,null);quiet.acknowledge(104,q.requested_bps);
 for(let t=200;t<3000;t+=100)assert.equal((await quiet.observe(poll(t,800000),null,null,null,null)).epoch,0);
 const slow=new PolicySampler({kind:'ladder',fast:false,arm:0});
 const z=await slow.observe(poll(100,800000),null,null,null,null);slow.acknowledge(104,z.requested_bps);
 for(let t=200;t<3000;t+=100)assert.equal((await slow.observe(poll(t,800000),null,null,null,ack(++id,t-5,300))).epoch,0);
 assert.equal(FAST_EPOCHS,12);
});
