// Fixed, open-loop service intervention. No BWE, receiver or outcome enters inputs.
export const STEP_PROTOCOL_M8=Object.freeze({plateau_ms:24000,total_ms:96000,
 clock_brackets_ms:Object.freeze([12000,24000,36000,48000,60000,72000,84000,90000])});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function runStepPlateausM8(start,rates,clockBracket){
 const allowed=['[0.5,1.5,0.5,1.5]','[1.5,1.5,0.5,1.5]'];
 if(!allowed.includes(JSON.stringify(rates)))throw Error('unregistered M8 service sequence');
 const until=async elapsed=>{const deadline=start+elapsed;while(performance.now()<deadline)await sleep(Math.max(1,deadline-performance.now()));};
 let previous=rates[0];
 for(const elapsed of STEP_PROTOCOL_M8.clock_brackets_ms){
  await until(elapsed);
  if([24000,48000,72000].includes(elapsed)){
   const sequence=elapsed/24000,browser_request_ms=performance.now();
   const request={sequence,browser_request_ms,scheduled_ms:start+elapsed,previous_mbps:previous,requested_mbps:rates[sequence]};
   const response=await fetch('/system-service',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)});
   const readback=await response.json(),browser_receive_ms=performance.now();
   if(!response.ok||readback.sequence!==sequence||readback.capacity_mbps!==request.requested_mbps)throw Error('M8 service readback mismatch');
   await fetch('/system-service-browser',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...request,readback,browser_receive_ms})});
   if(browser_request_ms<request.scheduled_ms||browser_request_ms-request.scheduled_ms>150||browser_receive_ms-browser_request_ms>100)throw Error('M8 strict service timing/readback gate failed');
   previous=readback.capacity_mbps;
  }
  await clockBracket('m8_'+elapsed);
 }
 await until(96000);
 const completion={browser_start_ms:start,browser_end_ms:performance.now(),service_sequence_mbps:rates,commands:3};
 const response=await fetch('/system-id-complete',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(completion)});
 if(!response.ok)throw Error('M8 completion persistence failed');
 return completion;
}
