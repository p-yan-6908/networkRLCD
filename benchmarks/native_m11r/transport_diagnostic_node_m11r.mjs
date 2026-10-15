// Supported diagnostics only; timestamps are never silently backdated to receipt.
import {mkdir,readdir,open,stat,writeFile,appendFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {record,decodeSupportMessage} from './rtc_log_decoder_m11r.mjs';
const wait=ms=>new Promise(r=>setTimeout(r,ms));
export class TransportDiagnosticNodeM11R{
 constructor(root){this.root=root;this.files=new Map();this.events=[];this.reads=[];this.errors=[];this.traceEnvelopes=[];this.traceComplete=null;this.running=false;this.traceBytes=0;this.next=0;this.call=null;}
 async start(){await mkdir(this.root+'/rtc_event_logs',{recursive:false});this.running=true;
  this.task=(async()=>{while(this.running){await this.tail();await wait(25);}})();
 }
 async tail(){
  try{for(const name of await readdir(this.root+'/rtc_event_logs')){
   const file=this.root+'/rtc_event_logs/'+name,info=await stat(file);if(!info.isFile())continue;
   let state=this.files.get(name);if(!state){state={name,offset:0,pending:Buffer.alloc(0),parsed_bytes:0,send_ssrcs:[],config_send_ssrcs:[],identity_available_node_ms:null};this.files.set(name,state);}
   if(info.size<state.offset)throw Error('event log shrank');if(info.size>100000000)throw Error('event log exceeds frozen bound');
   if(info.size===state.offset)continue;
   const request_node_ms=performance.now(),h=await open(file,'r'),buffer=Buffer.alloc(info.size-state.offset);
   let bytesRead;try{({bytesRead}=await h.read(buffer,0,buffer.length,state.offset));}finally{await h.close();}
   const available_node_ms=performance.now(),bytes=buffer.subarray(0,bytesRead),offset=state.offset;state.offset+=bytesRead;
   const read={file:name,start_offset:offset,end_offset:state.offset,request_node_ms,available_node_ms,sha256:createHash('sha256').update(bytes).digest('hex')};this.reads.push(read);
   await appendFile(this.root+'/rtc_tail_reads.jsonl',JSON.stringify(read)+'\n');
   state.pending=Buffer.concat([state.pending,bytes]);let cursor=0;
   while(cursor<state.pending.length){const item=record(state.pending,cursor);if(!item)break;
    // Field7 and RTP bodies stay opaque; only outgoing timestamp/SSRC bind identity.
    if(item.wire===2){for(const event of decodeSupportMessage(item.field,item.value)){
     if(event.kind==='video_send_config')state.config_send_ssrcs.push(event.ssrc);
     if(event.kind==='outgoing_rtp_identity'){state.send_ssrcs.push(event.ssrc);state.send_ssrcs=[...new Set(state.send_ssrcs)];state.identity_available_node_ms=performance.now();}
     this.events.push({...event,id:++this.next,file:name,record_start_offset:state.parsed_bytes+item.start,
      record_end_offset:state.parsed_bytes+item.end,complete_record_available_node_ms:available_node_ms,parsed_node_ms:performance.now(),source:'rtc_event_log_v2'});
    }}cursor=item.end;
   }
   state.pending=state.pending.subarray(cursor);state.parsed_bytes+=cursor;
  }}catch(error){this.errors.push({node_ms:performance.now(),error:String(error)});this.running=false;}
 }
 async startTracing(call){
  this.call=call;const methods={};
  for(const [method,params] of [['Performance.enable',{}],['Tracing.getCategories',{}],['Tracing.start',{
   transferMode:'ReportEvents',bufferUsageReportingInterval:100,
   traceConfig:{recordMode:'recordContinuously',includedCategories:['disabled-by-default-webrtc','webrtc','blink.user_timing'],excludedCategories:['*']}}]]){
   try{methods[method]={status:'ok',result:await call(method,params)};}catch(error){methods[method]={status:'unsupported_or_failed',error:String(error)};}
  }
  await writeFile(this.root+'/diagnostic_methods.json',JSON.stringify(methods,null,2)+'\n',{flag:'wx'});
 }
 onCdpEvent(message){
  if(message.method==='Tracing.dataCollected'){
   const node_receive_ms=performance.now(),values=message.params?.value??[];
   this.traceEnvelopes.push({node_receive_ms,events:values.length});
   for(const event of values){
    const raw=JSON.stringify(event);this.traceBytes+=raw.length;
    if(this.traceBytes>250000000&&!this.boundExceeded){this.boundExceeded=true;this.errors.push({error:'trace exceeds frozen250MB diagnostic bound; stopping trace, retaining delivered events',node_ms:node_receive_ms});this.call?.('Tracing.end',{}).catch(error=>this.errors.push({error:String(error)}));}
    this.events.push({id:++this.next,source:'cdp_trace',kind:'trace_event',native_ms:typeof event.ts==='number'?event.ts/1000:null,
     complete_record_available_node_ms:node_receive_ms,parsed_node_ms:performance.now(),event});
   }
  }else if(message.method==='Tracing.tracingComplete')this.traceComplete={node_receive_ms:performance.now(),params:message.params};
 }
 onStderr(text){
  const node_receive_ms=performance.now();this.stderrPending=(this.stderrPending??'')+text;
  const lines=this.stderrPending.split('\n');this.stderrPending=lines.pop();
  for(const line of lines){
   if(!/goog_cc_network_control|probe_controller|pacing_controller|task_queue_paced_sender|transport_feedback_adapter|rtcp_receiver/.test(line))continue;
   const bwe=line.match(/\bbwe (\d+) pushback_target_bps=(\d+)/);
   this.events.push({id:++this.next,source:'chrome_verbose',kind:bwe?'verbose_bwe_update':'verbose_transport_log',
    native_ms:bwe?Number(bwe[1]):null,bitrate_bps:bwe?Number(bwe[2]):null,
    complete_record_available_node_ms:node_receive_ms,parsed_node_ms:performance.now(),line,
    sender_identity_status:'not_exposed_in_log_line'});
  }
 }
 snapshot(after){return {node_snapshot_ms:performance.now(),latest_id:this.next,
  events:this.events.filter(e=>e.id>after&&(e.source!=='cdp_trace'||/^TaskQueuePacedSender::(MaybeProcessPackets|EnqueuePackets)/.test(e.event?.name??''))),files:[...this.files.values()].map(x=>({name:x.name,bytes:x.offset,parsed_bytes:x.parsed_bytes,pending_bytes:x.pending.length,
   send_ssrcs:x.send_ssrcs,config_send_ssrcs:x.config_send_ssrcs,identity_available_node_ms:x.identity_available_node_ms})),errors:this.errors,
  trace_envelopes:this.traceEnvelopes.length};}
 async clock(body){
  const node_receive_ms=performance.now();
  if(!this.call)return {status:'unavailable',reason:'CDP not initialized'};
  try{const answer=await this.call('Performance.getMetrics',{});const timestamp=answer.metrics?.find(x=>x.name==='Timestamp')?.value;
   return {status:Number.isFinite(timestamp)?'present':'absent',browser_request_ms:body.browser_request_ms,
    native_monotonic_ms:Number.isFinite(timestamp)?timestamp*1000:null,node_receive_ms,node_send_ms:performance.now()};
  }catch(error){return {status:'unavailable',error:String(error),node_receive_ms,node_send_ms:performance.now()};}
 }
 async stop(){
  if(this.stopped)return this.stopResult;this.stopped=true;
  if(this.call){try{await this.call('Tracing.end',{});for(let i=0;i<100&&!this.traceComplete;i++)await wait(25);}
   catch(error){this.errors.push({source:'Tracing.end',error:String(error),node_ms:performance.now()});}}
  this.running=false;await this.task;await this.tail();
  const files=[...this.files.values()].map(x=>({name:x.name,bytes:x.offset,parsed_bytes:x.parsed_bytes,pending_bytes:x.pending.length,send_ssrcs:x.send_ssrcs,config_send_ssrcs:x.config_send_ssrcs}));
  await writeFile(this.root+'/transport_diagnostic_events.json',JSON.stringify(this.events)+'\n',{flag:'wx'});
  this.stopResult={abi:'native_transport_diagnostic_m11r_v1',files,events:this.events.length,errors:this.errors,
   trace_envelopes:this.traceEnvelopes,trace_complete:this.traceComplete,trace_bytes:this.traceBytes,
   stopped_node_ms:performance.now(),receiver_outcomes_read:false};
  await writeFile(this.root+'/transport_diagnostic_summary.json',JSON.stringify(this.stopResult,null,2)+'\n',{flag:'wx'});return this.stopResult;
 }
}
