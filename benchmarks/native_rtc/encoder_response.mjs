// Auxiliary native encoder counters only; never an actor observation or rate guarantee.
export const ENCODER_RESPONSE_ABI='native_encoder_response_sidecar_v1';
export const NUMERIC_FIELDS=Object.freeze({targetBitrate:false,qpSum:true,framesEncoded:true,keyFramesEncoded:true,bytesSent:true,retransmittedBytesSent:true,headerBytesSent:true,totalEncodeTime:false,totalEncodedBytesTarget:true,frameWidth:true,frameHeight:true});
const numeric=(v,integer)=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&(!integer||Number.isSafeInteger(v));
export function captureEncoderResponse(stats,source,sampleMs,timeOrigin){
 const begin=performance.now(),values=Array.isArray(stats)?stats:[...stats.values()];
 if(!numeric(sampleMs,false)||!numeric(timeOrigin,false))throw Error('explicit finite nonnegative clocks required');
 const streams=values.filter(s=>s.type==='outbound-rtp'&&s.kind==='video'&&String(s.id)+':'+String(s.ssrc??'')===source.stream_key);
 if(streams.length!==1)throw Error('exact unique sender outbound id/SSRC required');
 const s=streams[0],codec=values.find(c=>c.id===s.codecId&&c.type==='codec');
 if(codec?.mimeType?.toLowerCase()!=='video/vp8')throw Error('exact selected VP8 codec required');
 const fields={};
 for(const [key,integer] of Object.entries(NUMERIC_FIELDS)){
  const present=Object.hasOwn(s,key),valid=present&&numeric(s[key],integer);
  fields[key]={status:!present?'absent':valid?'present':'invalid',value:valid?s[key]:null};
 }
 const key='qualityLimitationReason',present=Object.hasOwn(s,key),valid=present&&['none','cpu','bandwidth','other'].includes(s[key]);
 fields[key]={status:!present?'absent':valid?'present':'invalid',value:valid?s[key]:null};
 return {abi:ENCODER_RESPONSE_ABI,used_by_controller:false,stream_key:source.stream_key,stats_id:String(s.id),ssrc:String(s.ssrc??''),codec_id:String(s.codecId),mime_type:codec.mimeType,
  stats_timestamp_ms:numeric(s.timestamp,false)?s.timestamp:null,sample_ms:sampleMs,time_origin_epoch_ms:timeOrigin,capture_cost_ms:performance.now()-begin,fields};
}
