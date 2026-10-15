// Fixed network inputs only. State features never alter this observation schedule.
export const PHASE_PROTOCOL_M9=Object.freeze({initial_ms:24000,common_ms:64000,total_ms:88000,
 clock_brackets_ms:Object.freeze([12000,24000,36000,48000,60000,72000,80000,84000])});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function observePhaseStateM9(start,rates,clockBracket){
 if(rates.length!==2||![0,0.5,1,1.5].some(x=>rates[1]===0.5*2**x&&rates[0]===(x<1?1.5:0.5)))throw Error('unregistered M9 input');
 const until=async elapsed=>{const deadline=start+elapsed;while(performance.now()<deadline)await sleep(Math.max(1,deadline-performance.now()));};
 for(const elapsed of PHASE_PROTOCOL_M9.clock_brackets_ms){
  await until(elapsed);
  if(elapsed===24000){
   const browser_request_ms=performance.now();
   const request={sequence:1,browser_request_ms,scheduled_ms:start+elapsed,previous_mbps:rates[0],requested_mbps:rates[1]};
   const response=await fetch('/system-service',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)});
   const readback=await response.json(),browser_receive_ms=performance.now();
   if(!response.ok||readback.sequence!==1||readback.capacity_mbps!==rates[1])throw Error('M9 service readback mismatch');
   await fetch('/system-service-browser',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...request,readback,browser_receive_ms})});
   if(browser_request_ms<request.scheduled_ms||browser_request_ms-request.scheduled_ms>150||browser_receive_ms-browser_request_ms>100)throw Error('M9 strict timing failed');
  }
  await clockBracket('m9_'+elapsed);
 }
 await until(88000);
 const completion={browser_start_ms:start,browser_end_ms:performance.now(),service_sequence_mbps:rates,commands:1};
 const response=await fetch('/system-id-complete',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(completion)});
 if(!response.ok)throw Error('M9 completion persistence failed');
 return completion;
}
