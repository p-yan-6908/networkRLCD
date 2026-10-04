import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,rm,access} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {gzipSync} from 'node:zlib';
import {ABI,losslessJSON,nativeValidation,retainNativeResult} from './native_failure_evidence.mjs';

const original=await readFile(new URL('./balanced_hold_episode.mjs',import.meta.url),'utf8');
const entry=await readFile(new URL('./native_failure_episode.mjs',import.meta.url),'utf8');
const start=entry.indexOf(' await retainNativeResult('),end=entry.indexOf(' console.log(JSON.stringify(result));');
assert(start>0&&end>start);
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const actualGuardTail=new AsyncFunction('root','result','links','events','retainNativeResult','writeFile','gzipSync',entry.slice(start,end));
function good(){return {native_rtc:true,connection:'connected',identity:'actual browser result',snapshots:[{phase:'high',remote_candidate_address:'127.0.0.1',frames_decoded:11,frames_encoded:12,mean_encode_s:.003}],relay:{a_to_b:{forwarded_packets:100,capacity_integral_upper_bound_ok:true},b_to_a:{capacity_integral_upper_bound_ok:true}}};}
async function exists(p){try{await access(p);return true;}catch{return false;}}

test('exact original guard tail retained, helper stays host-only after browser return',()=>{
 const oldStart=original.indexOf(" if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');");
 const oldEnd=original.indexOf(' console.log(JSON.stringify(result));');
 assert.equal(entry.slice(start,end).replace(' await retainNativeResult(root,result,links.some(l=>l.unexpected),events.length);\n',''),original.slice(oldStart,oldEnd));
 assert(start>entry.indexOf('const result=answer.result.value;'));
 assert.equal((entry.match(/retainNativeResult\(/g)??[]).length,1);
});

test('fresh-file lossless special numeric identities never become null; source object untouched',async()=>{
 const r=good();r.snapshots[0].mean_encode_s=NaN;r.special={positive:Infinity,negative:-Infinity,missing:undefined,nullable:null};
 const root=await mkdtemp(path.join(tmpdir(),'native-failure-'));
 try{await retainNativeResult(root,r,false,10);const p=JSON.parse(await readFile(root+'/native_result_before_validation.json','utf8'));
 assert.equal(p.abi,ABI);assert.deepEqual(p.native_result.special,{positive:{__native_evidence_number_v1__:'+Infinity'},negative:{__native_evidence_number_v1__:'-Infinity'},missing:{__native_evidence_number_v1__:'undefined'},nullable:null});
 assert.deepEqual(p.native_result.snapshots[0].mean_encode_s,{__native_evidence_number_v1__:'NaN'});
 assert(Number.isNaN(r.snapshots[0].mean_encode_s));assert(!Object.hasOwn(r,'raw_event_count'));
 await assert.rejects(retainNativeResult(root,r,false,10));
 }finally{await rm(root,{recursive:true,force:true});}
 assert.throws(()=>losslessJSON({__native_evidence_number_v1__:'NaN'}),/collision/);
});

test('actual original accepted guard branch stores prevalidation result and unmodified summary',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'native-failure-'));const r=good();
 try{await actualGuardTail(root,r,[],[{}],retainNativeResult,writeFile,gzipSync);assert(await exists(root+'/summary.json'));
 const raw=JSON.parse(await readFile(root+'/native_result_before_validation.json','utf8'));const summary=JSON.parse(await readFile(root+'/summary.json','utf8'));
 assert.equal(summary.raw_event_count,1);delete summary.raw_event_count;assert.deepEqual(summary,raw.native_result);
 assert.equal(nativeValidation(raw.native_result).all_original_guards_passed,true);
 }finally{await rm(root,{recursive:true,force:true});}
});

for(const [name,mutate,message] of [
 ['endpoint',()=>{},'unexpected UDP source endpoint'],
 ['loopback',r=>r.snapshots[0].remote_candidate_address='10.0.0.1','media bypassed relay or did not progress'],
 ['forwarded',r=>r.relay.a_to_b.forwarded_packets=99,'media bypassed relay or did not progress'],
 ['capacity',r=>r.relay.b_to_a.capacity_integral_upper_bound_ok=false,'service exceeded capacity integral'],
 ['connected',r=>r.connection='disconnected','native media stats not valid'],
 ['decoded',r=>r.snapshots[0].frames_decoded=10,'native media stats not valid'],
 ['encoded',r=>r.snapshots[0].frames_encoded=10,'native media stats not valid'],
 ['nonfinite',r=>r.snapshots[0].mean_encode_s=Infinity,'native media stats not valid']]){
 test(`actual original ${name} guard rejects but full result/predicate survive and no summary`,async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'native-failure-'));const r=good();mutate(r);const links=name==='endpoint'?[{unexpected:true}]:[];
 try{await assert.rejects(actualGuardTail(root,r,links,[{}],retainNativeResult,writeFile,gzipSync),e=>e.message===message);
 assert(await exists(root+'/native_result_before_validation.json'));assert(!await exists(root+'/summary.json'));
 const v=JSON.parse(await readFile(root+'/native_validation.json','utf8'));assert.equal(v.first_rejection,message);assert.equal(v.all_original_guards_passed,false);
 }finally{await rm(root,{recursive:true,force:true});}
 });
}

test('malformed diagnostic evaluation still retains actual result and original guard throws',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'native-failure-'));const r=good();delete r.snapshots;
 try{await assert.rejects(actualGuardTail(root,r,[],[{}],retainNativeResult,writeFile,gzipSync));
 assert(await exists(root+'/native_result_before_validation.json'));assert(!await exists(root+'/summary.json'));
 const v=JSON.parse(await readFile(root+'/native_validation.json','utf8'));assert.match(v.evaluation_error,/TypeError/);
 }finally{await rm(root,{recursive:true,force:true});}
});
