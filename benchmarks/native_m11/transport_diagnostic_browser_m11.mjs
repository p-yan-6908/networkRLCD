// Causal receiver of supported diagnostic events; no future-trained clock.
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export class TransportDiagnosticBrowserM11{
 constructor(){this.receipts=[];this.anchors=[];this.errors=[];this.cursor=0;this.senderSsrc=null;this.running=false;}
 setSenderSource(ssrc){if(!Number.isSafeInteger(ssrc)||ssrc<1)return;if(this.senderSsrc!==null&&this.senderSsrc!==ssrc)this.errors.push('sender SSRC changed');this.senderSsrc=ssrc;}
 async clock(){
  const browser_request_ms=performance.now();
  try{
   const r=await fetch('/transport-clock',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({browser_request_ms})}),body=await r.json(),browser_receive_ms=performance.now();
   const valid=r.ok&&body.status==='present'&&Number.isFinite(body.native_monotonic_ms)&&browser_receive_ms-browser_request_ms<=100;
   this.anchors.push({id:this.anchors.length+1,browser_request_ms,browser_receive_ms,body,status:valid?'present':'invalid',
    offset_bounds_ms:valid?[browser_request_ms-body.native_monotonic_ms,browser_receive_ms-body.native_monotonic_ms]:null,
    mapping_uses_future_information:false});
  }catch(error){this.errors.push({kind:'clock',browser_request_ms,error:String(error)});}
 }
 async start(){
  await this.clock();this.running=true;this.epoch=performance.now();
  this.clockTask=(async()=>{while(this.running){await sleep(1000);if(this.running)await this.clock();}})();
  this.snapshotTask=(async()=>{let next=this.epoch;while(this.running){
   while(this.running&&performance.now()<next)await sleep(Math.max(1,next-performance.now()));if(!this.running)break;
   const browser_request_ms=performance.now(),after=this.cursor;
   try{
    const r=await fetch('/transport-diagnostics',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({after,browser_request_ms})}),snapshot=await r.json(),browser_receive_ms=performance.now();
    const anchor=[...this.anchors].reverse().find(a=>a.status==='present'&&a.browser_receive_ms<=browser_receive_ms&&browser_receive_ms-a.browser_receive_ms<=1500);
    const events=snapshot.events?.map(event=>{
     const file=snapshot.files.find(f=>f.name===event.file),identified=!!file&&file.send_ssrcs.length===1&&file.send_ssrcs[0]===this.senderSsrc;
     const bounds=anchor&&Number.isFinite(event.native_ms)?[event.native_ms+anchor.offset_bounds_ms[0]-1,event.native_ms+anchor.offset_bounds_ms[1]+1]:null;
     return {...event,sender_identity_status:event.source==='rtc_event_log_v2'?(identified?'uniquely_linked':'unknown_or_other_peer'):'no_explicit_sender_link',
      anchor_id:anchor?.id??null,native_event_sender_bounds_ms:bounds,
      clock_uncertainty_ms:bounds?bounds[1]-bounds[0]:null,
      availability_delay_bounds_ms:bounds?[browser_receive_ms-bounds[1],browser_receive_ms-bounds[0]]:null,
      sender_available_ms:browser_receive_ms,used_future_clock_information:false};
    })??[];
    this.receipts.push({sequence:this.receipts.length+1,browser_request_ms,browser_receive_ms,after,
     latest_id:snapshot.latest_id,sender_ssrc:this.senderSsrc,files:snapshot.files,events,
     diagnostic_errors:snapshot.errors,status:r.ok?'present':'invalid'});
    this.cursor=snapshot.latest_id;
   }catch(error){this.errors.push({kind:'snapshot',browser_request_ms,error:String(error)});}
   next=this.epoch+100*(Math.floor((performance.now()-this.epoch)/100)+1);
  }})();
 }
 async stop(cutoff){
  this.running=false;await Promise.all([this.clockTask,this.snapshotTask]);
  const evidence={abi:'native_transport_diagnostic_browser_m11_v1',measurement_cutoff_ms:cutoff,
   anchors:this.anchors,receipts:this.receipts,errors:this.errors,sender_ssrc:this.senderSsrc,
   native_clock_contract:'Linux CLOCK_MONOTONIC, WebRTC TimeMicros and CDP Performance Timestamp; past ACK fences only',
   future_response_or_receiver_outcomes_read:false};
  const r=await fetch('/transport-stop',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(evidence)});
  if(!r.ok)throw Error('diagnostic persistence failed');return await r.json();
 }
}
