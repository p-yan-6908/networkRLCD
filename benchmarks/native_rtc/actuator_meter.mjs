// Identity transform: count actual encoded video payload, NOT target or RTP bytes.
export const METER_ABI='native_encoded_payload_meter_v1';
export function installEncodedMeter(sender,clock=()=>performance.now()){
 if(typeof sender.createEncodedStreams!=='function')throw Error('actual encoded output meter unavailable; do not substitute target/send counters');
 const streams=sender.createEncodedStreams();
 if(!streams?.readable||!streams?.writable)throw Error('native encoded streams unavailable');
 const started=clock(),events=[];let bytes=0,frames=0,error=null,ended=null;
 const transform=new TransformStream({transform(frame,controller){
  const at=clock(),n=frame.data?.byteLength;
  if(!Number.isSafeInteger(n)||n<0||!Number.isFinite(at)||at<started||events.length&&at<events.at(-1).at_ms)throw Error('invalid native encoded frame counter/clock');
  bytes+=n;frames++;
  if(!Number.isSafeInteger(bytes)||!Number.isSafeInteger(frames))throw Error('encoded counters overflow');
  events.push({at_ms:at,byte_length:n,total_bytes:bytes,total_frames:frames,rtp_timestamp:Number.isFinite(frame.timestamp)?frame.timestamp:null,frame_type:typeof frame.type==='string'?frame.type:null});
  controller.enqueue(frame); // same object/data, no compression or codec changes
 }});
 streams.readable.pipeThrough(transform).pipeTo(streams.writable).then(()=>{ended=clock();}).catch(e=>{error=String(e);ended=clock();});
 return {
  snapshot(now){const latest=events.findLast(e=>e.at_ms<=now);return {abi:METER_ABI,status:error?'failed':ended!==null?'ended':'active',sample_ms:now,total_bytes:latest?.total_bytes??0,total_frames:latest?.total_frames??0};},
  evidence(start,cutoff){if(error||ended!==null&&ended<cutoff)throw Error('encoded output observer did not cover capture: '+error);return {abi:METER_ABI,owner:'unique_owned_video_sender',measurement_start_ms:start,measurement_cutoff_ms:cutoff,started_ms:started,error,ended_ms:ended,pass_through_no_frame_mutation:true,unit:'encoded_video_payload_bytes_before_RTP_packetization',events:structuredClone(events.filter(e=>e.at_ms<=cutoff))};}
 };
}
