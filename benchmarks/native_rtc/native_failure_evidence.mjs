// Post-browser diagnostic persistence only; never imported by page/controller code.
import {writeFile} from 'node:fs/promises';
export const ABI='native_pre_rejection_failure_evidence_v1';
const TAG='__native_evidence_number_v1__';
export function losslessJSON(value){return JSON.stringify(value,(_key,v)=>{
 if(v===undefined)return {[TAG]:'undefined'};
 if(typeof v==='number'&&!Number.isFinite(v))return {[TAG]:Number.isNaN(v)?'NaN':v>0?'+Infinity':'-Infinity'};
 if(v&&typeof v==='object'&&Object.hasOwn(v,TAG))throw Error('reserved diagnostic number tag collision');
 return v;
},2)+'\n';}
export function nativeValidation(result,unexpected=false){
 const snapshots=result.snapshots;
 const checks=[{code:'no_unexpected_udp_endpoint',passed:!unexpected},
 {code:'all_remote_candidates_loopback',passed:snapshots.every(s=>s.remote_candidate_address==='127.0.0.1')},
 {code:'at_least_100_forwarded_packets',passed:result.relay.a_to_b.forwarded_packets>=100},
 {code:'a_to_b_capacity_integral',passed:!!result.relay.a_to_b.capacity_integral_upper_bound_ok},
 {code:'b_to_a_capacity_integral',passed:!!result.relay.b_to_a.capacity_integral_upper_bound_ok},
 {code:'native_rtc',passed:!!result.native_rtc},
 {code:'connected',passed:result.connection==='connected'},
 ...snapshots.flatMap((s,i)=>[
 {code:`snapshot_${i}_frames_decoded_gt_10`,passed:s.frames_decoded>10},
 {code:`snapshot_${i}_frames_encoded_gt_10`,passed:s.frames_encoded>10},
 {code:`snapshot_${i}_mean_encode_finite`,passed:Number.isFinite(s.mean_encode_s)}])];
 // Exact original rejection ordering/predicates, no weaker substitute thresholds.
 const guards=[
 {message:'unexpected UDP source endpoint',passed:!unexpected},
 {message:'media bypassed relay or did not progress',passed:snapshots.every(s=>s.remote_candidate_address==='127.0.0.1')&&!(result.relay.a_to_b.forwarded_packets<100)},
 {message:'service exceeded capacity integral',passed:!!result.relay.a_to_b.capacity_integral_upper_bound_ok&&!!result.relay.b_to_a.capacity_integral_upper_bound_ok},
 {message:'native media stats not valid',passed:!!result.native_rtc&&result.connection==='connected'&&snapshots.every(s=>s.frames_decoded>10&&s.frames_encoded>10&&Number.isFinite(s.mean_encode_s))}];
 return {abi:ABI,diagnostic_only:true,checks,guards,all_original_guards_passed:guards.every(g=>g.passed),first_rejection:guards.find(g=>!g.passed)?.message??null};
}
export async function retainNativeResult(root,result,unexpected,rawEventCount){
 // Store the entire actual Node-received result BEFORE evaluating diagnostics or any guard.
 await writeFile(root+'/native_result_before_validation.json',losslessJSON({abi:ABI,diagnostic_only:true,unexpected_udp:unexpected,raw_event_count:rawEventCount,native_result:result}),{flag:'wx'});
 let validation;
 try{validation=nativeValidation(result,unexpected);}catch(error){validation={abi:ABI,diagnostic_only:true,evaluation_error:String(error),all_original_guards_passed:false,first_rejection:null};}
 await writeFile(root+'/native_validation.json',losslessJSON(validation),{flag:'wx'});
}
