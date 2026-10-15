// Minimal support-only RTC event-log v2 decoder. FrameDecodedEvents (field 7)
// and RTP packet bodies are opaque. Encoding follows pinned WebRTC rtclog2,
// delta_encoding.cc and blob_encoding.cc; BSD notice in data/native-m11r/.
const fail=message=>{throw Error(message);};
export function varint(bytes,start=0){
 let value=0n;for(let i=0;i<10;i++){if(start+i>=bytes.length)return null;const c=bytes[start+i];value|=BigInt(c&127)<<BigInt(7*i);if(!(c&128))return {value,end:start+i+1};}
 return fail('invalid varint');
}
export function record(bytes,start=0){
 const key=varint(bytes,start);if(!key)return null;const wire=Number(key.value&7n),field=Number(key.value>>3n);if(field<1)fail('invalid field');
 let end,value;
 if(wire===0){const v=varint(bytes,key.end);if(!v)return null;end=v.end;value=v.value;}
 else if(wire===2){const len=varint(bytes,key.end);if(!len)return null;if(len.value>100000000n)fail('oversize field');end=len.end+Number(len.value);if(end>bytes.length)return null;value=bytes.subarray(len.end,end);}
 else if(wire===1||wire===5){end=key.end+(wire===1?8:4);if(end>bytes.length)return null;value=bytes.subarray(key.end,end);}
 else fail('unsupported protobuf wire '+wire);
 return {field,wire,value,start,end};
}
export function fields(bytes){
 const out={};let at=0;while(at<bytes.length){const x=record(bytes,at);if(!x)fail('incomplete nested protobuf');(out[x.field]??=[]).push(x.value);at=x.end;}return out;
}
class Bits{
 constructor(bytes){this.bytes=bytes;this.at=0;}
 read(n){let x=0n;if(this.at+n>this.bytes.length*8)fail('short delta bits');for(let i=0;i<n;i++,this.at++)x=(x<<1n)|BigInt((this.bytes[this.at>>3]>>(7-(this.at&7)))&1);return x;}
}
export function deltas(data,base,n){
 if(!n)return [];if(!data?.length)return Array(n).fill(base);
 const b=new Bits(data),kind=Number(b.read(2)),dw=Number(b.read(6))+1;if(kind>1)fail('unknown delta encoding');
 const signed=kind===1?Boolean(b.read(1)):false,optional=kind===1?Boolean(b.read(1)):false,vw=kind===1?Number(b.read(6))+1:64;
 if(dw>vw)fail('invalid delta width');const exists=optional?Array.from({length:n},()=>Boolean(b.read(1))):Array(n).fill(true),mask=(1n<<BigInt(vw))-1n;
 let previous=base;return exists.map(ok=>{if(!ok)return null;let value;
  if(previous===null||previous===undefined){let v=0n;for(let i=0;i<10;i++){const c=b.read(8);v|=(c&127n)<<BigInt(i*7);if(!(c&128n)){value=v;break;}}if(value===undefined)fail('invalid bit varint');}
  else{let d=b.read(dw);if(signed&&(d&(1n<<BigInt(dw-1))))d-=1n<<BigInt(dw);value=(previous+d)&mask;}
  previous=value;return value;
 });
}
export function blobs(data,n){
 let at=0;const lengths=[];for(let i=0;i<n;i++){const v=varint(data,at);if(!v)fail('short blob length');lengths.push(Number(v.value));at=v.end;}
 const out=lengths.map(len=>{if(at+len>data.length)fail('short blob');const z=data.subarray(at,at+len);at+=len;return z;});if(at!==data.length)fail('blob trailer');return out;
}
export function rtcpHeaders(bytes){
 const packets=[];let at=0;while(at+4<=bytes.length){const version=bytes[at]>>6,fmt=bytes[at]&31,pt=bytes[at+1],len=(bytes.readUInt16BE(at+2)+1)*4;
  if(version!==2||len<4||at+len>bytes.length)fail('invalid RTCP compound packet');
  const q={packet_type:pt,fmt,bytes:len};if(len>=8)q.sender_ssrc=bytes.readUInt32BE(at+4);if(len>=12)q.media_ssrc=bytes.readUInt32BE(at+8);
  if(pt===205&&fmt===15){if(len<20)fail('short TCC feedback');Object.assign(q,{base_sequence:bytes.readUInt16BE(at+12),packet_status_count:bytes.readUInt16BE(at+14),feedback_packet_count:bytes[at+19]});}
  packets.push(q);at+=len;
 }if(at!==bytes.length)fail('RTCP trailer');return packets;
}
const names={3:'outgoing_rtp_identity',4:'incoming_rtcp',16:'begin_log',17:'end_log',18:'loss_bwe_update',19:'delay_bwe_update',21:'probe_created',22:'probe_success',23:'probe_failure',24:'alr_state',104:'video_send_config'};
export function decodeSupportMessage(field,bytes){
 if(!Object.hasOwn(names,field))return [];
 const f=fields(bytes),one=k=>f[k]?.[0],base=one(1);if(base===undefined)fail('missing native timestamp');
 if(field===3){const raw=one(6);if(!Buffer.isBuffer(raw)||raw.length!==4)fail('invalid fixed32 outgoing SSRC');return [{kind:names[field],native_ms:Number(base),ssrc:raw.readUInt32LE(),header_only:true}];}
 if(field===104)return [{kind:names[field],native_ms:Number(base),ssrc:Number(one(2)),rtx_ssrc:one(3)===undefined?null:Number(one(3))}];
 const countField=field===4?3:field===18?5:field===19?4:null,n=countField?Number(one(countField)??0n):0;
 const times=[base,...deltas(one(101),base,n)];
 const bitrate=(field===18||field===19)?[one(2),...deltas(one(102),one(2),n)]:[],detector=field===19?[one(3),...deltas(one(103),one(3),n)]:[];
 const packets=field===4?[one(2),...(n?blobs(one(102)??Buffer.alloc(0),n):[])]:[];
 return times.map((t,i)=>{
  if(t===null)fail('absent required timestamp');const result={kind:names[field],native_ms:Number(t),batch_events:n+1,batch_index:i};
  if(field===4){result.rtcp=rtcpHeaders(packets[i]);result.tcc=result.rtcp.filter(p=>p.packet_type===205&&p.fmt===15);}
  else if(field===18||field===19){result.bitrate_bps=Number(bitrate[i]);if(field===19)result.detector_state=Number(detector[i]);}
  else if(field===21||field===22||field===23){result.probe_id=Number(one(2));result.parameter=Number(one(3));}
  return result;
 });
}
