import test from 'node:test';
import assert from 'node:assert/strict';
import {SupportQualifiedRatioSampler, supportCheck, SUPPORT_PROTOCOL} from './native_support_qualified_ratio_v12.mjs';
const history=bwe=>Array.from({length:11},(_,i)=>({sample_ms:8000+i*100,bwe_bps:bwe}));
const config=(slot=0,support=false)=>({target_state:'bwe_ge_500k',pair_id:'development-pair',pair_slot:slot,support_only:support});
async function feed(sampler,bwe=800000){sampler.start(0);let result;for(let i=0;i<=90;i++)result=await sampler.observe({sample_ms:i*100,raw_source:{bwe_bps:bwe}});return result;}
test('startup, wrong state, clipped actions and sparse history do not qualify',()=>{
 assert.equal(supportCheck(history(300000),'bwe_lt_500k',50).passed,false);
 assert.equal(supportCheck(history(300000),'bwe_ge_500k',9000).passed,false);
 assert.equal(supportCheck(history(200000),'bwe_lt_500k',9000).passed,false);
 assert.equal(supportCheck(history(4000000),'bwe_ge_500k',9000).passed,false);
 assert.equal(supportCheck(history(800000).slice(1),'bwe_ge_500k',9000).passed,false);
 const gap=history(800000);gap[4].sample_ms-=300;
 assert.equal(supportCheck(gap,'bwe_ge_500k',9000).passed,false);
 assert.equal(supportCheck(history(500000),'bwe_ge_500k',9000).passed,true);
 assert.equal(supportCheck(history(499999),'bwe_lt_500k',9000).passed,true);
});
test('both paired actions follow the same qualified pre-treatment history',async()=>{
 const samplers=[0,1].map(slot=>new SupportQualifiedRatioSampler(20261083,'dev-'+slot,config(slot)));
 const actions=await Promise.all(samplers.map(s=>feed(s)));
 assert.deepEqual(actions.map(a=>a.ratio).sort(),[0.65,1.05]);
 assert.equal(actions[0].draw_uint32,actions[1].draw_uint32);
 assert.deepEqual(actions[0].support_qualification,actions[1].support_qualification);
 assert.equal(actions[0].conditional_propensity_given_prior_pair_slot,0.5);
 assert.equal(actions[1].conditional_propensity_given_prior_pair_slot,1);
 for(let i=0;i<2;i++){
  samplers[i].acknowledge(9001,actions[i].requested_bps);
  assert.deepEqual(await samplers[i].observe({sample_ms:12001,raw_source:{bwe_bps:200000}}),actions[i]);
 }
});
test('support census applies no randomized cap and rejects any baseline drift',async()=>{
 const s=new SupportQualifiedRatioSampler(20261083,'support-only',config(0,true));
 assert.equal(await feed(s),null);assert.equal(s.evidence().qualification.passed,true);
 assert.equal(s.evidence().action_assigned,false);
 s.acknowledge(9001,SUPPORT_PROTOCOL.baseline_cap_bps);
 assert.throws(()=>s.acknowledge(9001,300000),/ceiling changed/);
});
test('same qualified action cannot be acknowledged with a different native cap',async()=>{
 const s=new SupportQualifiedRatioSampler(20261083,'bad-readback',config());
 const a=await feed(s);assert.throws(()=>s.acknowledge(9001,a.requested_bps+1),/readback mismatch/);
});
