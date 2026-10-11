import test from 'node:test';
import assert from 'node:assert/strict';
import {ABI,LADDER,SAFE,CRUISE,HIGH,START,HOLD_MS,MAX_EPOCHS,LOW_MS,HIGH_MS,PANIC_MS,GUARD_MS,CALM_HOLDS,MEMORY_MS,MEMORY_MAX_MS,PolicySampler,requestedBps} from './margin_control.mjs';

const poll=(ms,bwe)=>({sample_ms:ms,raw_source:{bwe_bps:bwe}});
const ack=(id,received,age)=>({source_id:id,capture_request_ms:received-age,received_ms:received,presented_fps:30});
// Polls every 100 ms from `from` to just before `to`. The poll at t carries a fresh acknowledgement of
// age `age(t)`, received 5 ms earlier, or none when `age(t)` is null. Every assignment is acknowledged
// 4 ms after it, so that holds begin at 100, 3200, 6300, ... unless a cut restarts the clock.
async function run(s,state,from,to,age){
 const made=[];
 for(let t=from;t<to;t+=100){
  const a=age(t),c=await s.observe(poll(t,800000),null,null,null,a===null?null:ack(++state.id,t-5,a));
  if(c.epoch!==state.epoch){state.epoch=c.epoch;made.push(c);s.acknowledge(t+4,c.requested_bps);}
 }
 return made;
}
const fresh=policy=>[new PolicySampler(policy),{id:0,epoch:-1}];

test('constants: the ladder, the marks of the controller pilot, and the memory',()=>{
 assert.equal(ABI,'native_margin_pilot_v1');
 assert.deepEqual([...LADDER],[0.25,0.65,0.85,1.05]);assert.deepEqual([SAFE,CRUISE,HIGH,START],[0,1,2,3]);
 assert.deepEqual([LOW_MS,HIGH_MS,PANIC_MS,GUARD_MS,HOLD_MS],[104,132,159,1000,3000]);
 assert.deepEqual([CALM_HOLDS,MEMORY_MS,MEMORY_MAX_MS,MAX_EPOCHS],[2,30000,120000,40]);
 assert.equal(requestedBps(0,400000),150000);assert.equal(requestedBps(3,5000000),4000000);assert.equal(requestedBps(1,800000),520000);
 assert.throws(()=>requestedBps(4,800000));assert.throws(()=>requestedBps(1,0));
 assert.throws(()=>new PolicySampler({kind:'margin'}));assert.throws(()=>new PolicySampler({kind:'fixed',step:4,arm:0}));assert.throws(()=>new PolicySampler({kind:'ladder',fast:true,arm:0}));
});

test('a fixed arm keeps its step at every hold and never cuts',async()=>{
 const [s,state]=fresh({kind:'fixed',step:1,arm:2});
 const made=await run(s,state,100,9500,()=>300);
 assert.deepEqual(made.map(c=>[c.decision,c.assignment_ms]),[['fixed',100],['fixed',3200],['fixed',6300],['fixed',9400]]);
 assert.ok(made.every(c=>c.step===1&&c.ratio===0.65&&c.requested_bps===520000&&c.drops===0&&c.last_late_ms===null&&c.arm===2&&c.kind==='fixed'));
});

test('the rule starts at the top, cruises, goes up after two calm holds and comes back from the high mark',async()=>{
 const [s,state]=fresh({kind:'margin',arm:0});
 // The second before each hold has one age throughout: calm, calm, calm, between the marks, at the high mark, calm, not calm, calm.
 const age=t=>t<11500?100:t<14600?120:t<17700?140:t<20800?100:t<23900?110:100;
 const made=await run(s,state,100,25000,age);
 assert.deepEqual(made.map(c=>c.assignment_ms),[100,3200,6300,9400,12500,15600,18700,21800,24900]);
 assert.deepEqual(made.map(c=>c.decision),['start','cruise','hold','up','hold','down','hold','hold','hold']);
 assert.deepEqual(made.map(c=>c.step),[START,CRUISE,CRUISE,HIGH,HIGH,CRUISE,CRUISE,CRUISE,CRUISE]);
 assert.equal(made[0].requested_bps,840000);assert.equal(made[3].requested_bps,680000);assert.equal(made[4].feedback_age_ms,120);
 assert.ok(made.every(c=>c.drops===0&&c.memory_ms===MEMORY_MS&&c.last_late_ms===null&&c.kind==='margin'));
});

test('lateness takes the rule to the bottom at once, memory keeps it there, and a second drop doubles the memory',async()=>{
 const [s,state]=fresh({kind:'margin',arm:0});
 const age=t=>t<4000?90:t<10000?300:t<43700?90:300;
 let made=await run(s,state,100,4300,age);                            // cruising from 3200, acknowledged at 3204
 assert.deepEqual(made.map(c=>c.decision),['start','cruise']);        // late from 4000, but the guard runs to 4204
 made=await run(s,state,4300,4400,age);
 assert.deepEqual(made.map(c=>[c.decision,c.step,c.drops,c.memory_ms,c.last_late_ms,c.requested_bps]),[['cut',SAFE,1,MEMORY_MS,4300,200000]]);
 assert.equal(made[0].feedback_age_ms,174);                           // six acknowledgements of 90 ms and four of 300 ms
 made=await run(s,state,4400,10600,age);                              // at the bottom lateness is still seen: the memory keeps running
 assert.deepEqual(made.map(c=>[c.decision,c.step,c.drops,c.last_late_ms,c.assignment_ms]),[['hold',SAFE,1,7400,7400],['hold',SAFE,1,10500,10500]]);
 made=await run(s,state,10600,41500,age);                             // calm, and kept at the bottom by the memory
 assert.equal(made.length,9);assert.ok(made.every(c=>c.decision==='hold'&&c.step===SAFE&&c.last_late_ms===10500));
 made=await run(s,state,41500,43700,age);                             // 10500 + MEMORY has passed
 assert.deepEqual(made.map(c=>[c.decision,c.step,c.assignment_ms]),[['return',CRUISE,41500]]);
 made=await run(s,state,43700,44100,age);
 assert.deepEqual(made.map(c=>[c.decision,c.step,c.drops,c.memory_ms,c.assignment_ms]),[['cut',SAFE,2,2*MEMORY_MS,44000]]);
});

test('lateness first seen as a hold begins is a drop, silence as a hold begins too, and the memory is capped',async()=>{
 const [s,state]=fresh({kind:'margin',arm:0});
 let made=await run(s,state,100,3300,t=>t===3200?2000:90);            // one very late acknowledgement at the boundary
 assert.deepEqual(made.map(c=>[c.decision,c.step,c.drops]),[['start',START,0],['drop',SAFE,1]]);
 const [quiet,q]=fresh({kind:'margin',arm:0});
 made=await run(quiet,q,100,3300,t=>t<2000?90:null);                  // the last second without any acknowledgement
 assert.deepEqual(made.map(c=>[c.decision,c.step,c.feedback_age_ms]),[['start',START,90],['drop',SAFE,null]]);
 made=await run(quiet,q,3300,6500,()=>null);                          // silence inside a hold is no reason to cut; the bottom is counted once
 assert.deepEqual(made.map(c=>[c.decision,c.drops]),[['hold',1]]);
 const many=new PolicySampler({kind:'margin',arm:0});
 many.drops=4;many.step=CRUISE;many.current={epoch:0,assignment_ms:0,requested_bps:520000};many.ack=0;many.lastMs=0;
 const c=await many.observe(poll(3000,800000),null,null,null,ack(1,2995,400));
 assert.equal(c.decision,'drop');assert.equal(c.drops,5);assert.equal(c.memory_ms,MEMORY_MAX_MS);
});
