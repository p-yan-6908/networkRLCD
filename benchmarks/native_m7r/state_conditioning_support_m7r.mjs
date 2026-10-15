// Fixed support intervention. This changes owned network service, never sender bitrate.
// No parameters are fitted and no delivery/receiver/QoE fields enter this module.
export const CONDITIONING_M7R = Object.freeze({gain:0.25,max_step_octaves:0.125,
 min_service_mbps:0.2,max_service_mbps:5,updates:26,feedback_off_ms:27000,duration_ms:32000});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function conditionServiceM7R(decisions,start,target_x){
 let service=0.5*2**target_x;
 const until=async elapsed=>{const deadline=start+elapsed;while(performance.now()<deadline)await sleep(Math.max(1,deadline-performance.now()));};
 for(let sequence=1;sequence<=CONDITIONING_M7R.updates;sequence++){
  await until(sequence*1000);
  const decision_cutoff_ms=performance.now();
  const input=decisions.filter(d=>decision_cutoff_ms-1000<d.observation.sample_ms&&d.observation.sample_ms<=decision_cutoff_ms)
   .map(d=>({sample_ms:d.observation.sample_ms,valid:d.policy_input.features[9]===1,
    bwe_bps:d.policy_input.features[0]*4000000}));
  if(input.length<7||input.some(p=>!p.valid||!(p.bwe_bps>0))||
     input.some((p,i)=>i>0&&p.sample_ms-input[i-1].sample_ms>250))throw Error('M7R conditioning BWE input not observable');
  const mean_x=input.reduce((sum,p)=>sum+Math.log2(p.bwe_bps/500000),0)/input.length;
  const step=Math.max(-0.125,Math.min(0.125,0.25*(target_x-mean_x)));
  const requested_mbps=Math.max(0.2,Math.min(5,service*2**step));
  const browser_request_ms=performance.now();
  const request={sequence,target_x,decision_cutoff_ms,browser_request_ms,scheduled_ms:start+sequence*1000,
   input,mean_x,previous_mbps:service,requested_mbps};
  const response=await fetch('/condition-service',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)});
  const readback=await response.json(),browser_receive_ms=performance.now();
  if(!response.ok||readback.sequence!==sequence||readback.capacity_mbps!==requested_mbps)throw Error('M7R network-service readback mismatch');
  await fetch('/conditioning-browser',{method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({...request,readback,browser_receive_ms})});
  if(browser_receive_ms-browser_request_ms>100||browser_request_ms-request.scheduled_ms>150)
   throw Error('M7R network-service command missed registered timing/readback gate');
  service=readback.capacity_mbps;
 }
 await until(27000);
 const release={sequence:27,feedback_off:true,browser_ms:performance.now(),scheduled_ms:start+27000,capacity_mbps:service};
 const response=await fetch('/conditioning-release',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(release)});
 if(!response.ok)throw Error('M7R feedback release not persisted');
 await until(32000);
 return release;
}
