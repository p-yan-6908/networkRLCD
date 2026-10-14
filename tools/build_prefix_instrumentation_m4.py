"""Build a new instrumentation version without modifying any frozen recorder."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
text = (REPO / "benchmarks/native_m2/bwe_mechanism_support_episode_m2.mjs").read_text()


def change(old, new):
    global text
    assert text.count(old) == 1, old[:100]
    text = text.replace(old, new)


change("// M2 support-only collector: factorial early rate history and estimator initialization.",
       "// M4 startup/clock qualification and prospective M5 prefix-only collector.")
change("mkdtemp,readFile,writeFile,mkdir,rm,copyFile", "mkdtemp,readFile,writeFile,appendFile,mkdir,rm,copyFile")
change("if(![300,1200].includes(initialBweKbps)", "if(initialBweKbps!==1200")
change("const html=String.raw`", "await writeFile(root+'/instrument_stream.jsonl','',{flag:'wx'});\nconst html=String.raw`")
needle = "globalThis.run=async function(){"
extra = r"""
const extraClock=[],startupTimeline=[],startupPosts=[];let extraSequence=0,startupTimer=null,startupBusy=false,startupStopMs=null,mediaActive=false,startupStage='created';
async function extraMarker(role,label){const marker_id='x'+String(++extraSequence).padStart(4,'0'),browser_send_ms=performance.now();const response=await fetch('/instrument-clock',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({marker_id,browser_send_ms,role,label})});const body=await response.json(),browser_receive_ms=performance.now();if(!response.ok||body.marker_id!==marker_id)throw Error('instrument clock exchange failed');const record={...body,browser_receive_ms,role,label};extraClock.push(record);await fetch('/instrument-browser',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(record)});return record;}
async function clockTrain(label){for(let i=0;i<4;i++)await extraMarker('train',label);}
async function clockBracket(label){await clockTrain(label+'_before');await extraMarker('holdout',label);await clockTrain(label+'_after');}
async function startupSnapshot(pc,sender,label){const request_ms=performance.now();let stats=[],error=null;try{stats=[...(await pc.getStats()).values()];}catch(e){error=String(e);}const response_ms=performance.now();const transports=stats.filter(s=>s.type==='transport'&&s.selectedCandidatePairId),ids=[...new Set(transports.map(s=>s.selectedCandidatePairId))];const pair=ids.length===1?stats.find(s=>s.id===ids[0]&&s.type==='candidate-pair'):null,primaries=stats.filter(s=>s.type==='outbound-rtp'&&s.kind==='video'),out=primaries.length===1?primaries[0]:null;const parameters=sender?.getParameters(),encoding=parameters?.encodings?.[0];const record={label,stage:startupStage,request_ms,response_ms,connection_state:pc.connectionState,ice_connection_state:pc.iceConnectionState,media_active:mediaActive,encoder_active_readback:encoding?.active??null,encoder_cap_bps:encoding?.maxBitrate??null,selected_pair_count:ids.length,selected_pair_id:pair?.id??null,selected_pair_state:pair?.state??null,selected_pair_nominated:pair?.nominated??null,native_stats_timestamp_ms:pair?.timestamp??null,bwe_bps:pair?.availableOutgoingBitrate??null,outbound_count:primaries.length,frames_encoded:out?.framesEncoded??null,bytes_sent:out?.bytesSent??null,packets_sent:out?.packetsSent??null,error};startupTimeline.push(record);startupPosts.push(fetch('/startup-sample',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(record)}).then(r=>{if(!r.ok)throw Error('startup sample persistence failed');}));return record;}
"""
change(needle, extra + "\n" + needle)
change(" const pcConfig={iceTransportPolicy:", " await clockBracket('session_open');\n const pcConfig={iceTransportPolicy:")
change(" const timer=setInterval(draw,1000/30);let receiverTrack=false;", " let timer=null;let receiverTrack=false;")
change(" const sender=a.addTrack(stream.getVideoTracks()[0],stream);", " const sender=a.addTransceiver(stream.getVideoTracks()[0],{direction:'sendonly',streams:[stream],sendEncodings:[{active:false,maxBitrate:4000000}]}).sender;\n await clockBracket('pre_sdp');\n startupStage='before_sdp';await startupSnapshot(a,sender,'before_sdp');\n startupTimer=setInterval(async()=>{if(startupBusy)return;if(startupStopMs!==null&&performance.now()>=startupStopMs){clearInterval(startupTimer);startupTimer=null;return;}startupBusy=true;try{await startupSnapshot(a,sender,'poll');}finally{startupBusy=false;}},25);")
change(" const offer=await a.createOffer();", " startupStage='negotiating';supportStartup.sdp_call_ms=performance.now();\n const offer=await a.createOffer();")
change("native_bwe_mechanisms_m2_startup_v1", "native_prefix_instrumentation_m4_startup_v1")
change(" supportStartup.ice_gathering_complete_ms=performance.now();", " startupStage='gathered';await startupSnapshot(a,sender,'gathered');\n supportStartup.ice_gathering_complete_ms=performance.now();")
change(" supportStartup.connection_qualified_ms=performance.now();\n supportStartup.initial_native_sample_ms=performance.now();supportStartup.initial_native_source=selectSenderSource(await a.getStats(),{encoder_max_bitrate_bps:sender.getParameters().encodings[0].maxBitrate,receiver_jitter_buffer_target_ms:null});", """ supportStartup.connection_qualified_ms=performance.now();
 startupStage='connected_inactive';await startupSnapshot(a,sender,'connected_inactive');
 const setupDelay=nativeConfig.setup_delay_ms;if(![0,750].includes(setupDelay))throw Error('unregistered setup delay');supportStartup.setup_delay_ms=setupDelay;supportStartup.delay_start_ms=performance.now();await sleep(setupDelay);supportStartup.delay_end_ms=performance.now();
 await clockBracket('ready_inactive');
 supportStartup.pre_activation=await startupSnapshot(a,sender,'inactive_ready');
 if(supportStartup.pre_activation.encoder_active_readback!==false||supportStartup.pre_activation.encoder_cap_bps!==4000000||![null,0].includes(supportStartup.pre_activation.frames_encoded)||![null,0].includes(supportStartup.pre_activation.bytes_sent))throw Error('media advanced during inactive startup');""")
change(" const measurementStart=performance.now();instrument.start(measurementStart);", """ const activeParameters=sender.getParameters();activeParameters.encodings[0].active=true;await sender.setParameters(activeParameters);mediaActive=true;startupStage='active';draw();timer=setInterval(draw,1000/30);
 const activationStart=performance.now();let init;do{init=await startupSnapshot(a,sender,'initialization');if(Number.isFinite(init.bwe_bps)&&init.bwe_bps>0&&Math.abs(init.bwe_bps-1200000)>1)throw Error('first observed active native BWE differs from registered initialization');if(Number.isFinite(init.bwe_bps)&&init.bwe_bps>0&&init.outbound_count===1)break;await sleep(5);}while(performance.now()-activationStart<100);
 supportStartup.initial_native_sample_ms=init.response_ms;supportStartup.initial_native_source={bwe_bps:init.bwe_bps,frames_encoded:init.frames_encoded,bytes_sent:init.bytes_sent,packets_sent:init.packets_sent};supportStartup.initial_pair_id=init.selected_pair_id;supportStartup.initial_encoder_active=init.encoder_active_readback;supportStartup.initialization_latency_ms=init.response_ms-activationStart;supportStartup.initialization_success=init.selected_pair_count===1&&init.selected_pair_state==='succeeded'&&init.selected_pair_nominated===true&&Number.isFinite(init.bwe_bps)&&Math.abs(init.bwe_bps-1200000)<=1&&init.outbound_count===1&&init.encoder_active_readback===true&&init.encoder_cap_bps===4000000&&supportStartup.initialization_latency_ms<=100;
 if(!supportStartup.initialization_success)throw Error('native initialization unobservable within 100 ms; no fallback or retry');
 const measurementStart=performance.now();instrument.start(measurementStart);startupStopMs=measurementStart+1500;supportStartup.activation_readback=sender.getParameters().encodings[0].active;await startupSnapshot(a,sender,'measurement_start');""")
change("  const phaseMarker=await markerRequest('/phase',{capacity,phase:label,trace_mbps});currentPhase=label;", "  await clockTrain(label+'_before');\n  const phaseMarker=await markerRequest('/phase',{capacity,phase:label,trace_mbps});currentPhase=label;\n  await clockTrain(label+'_after');")
change("await sleep(duration/2);await markerRequest('/clock-marker');const remaining", "await sleep(duration/2);await clockTrain('midpoint_before');await markerRequest('/clock-marker');await clockTrain('midpoint_after');const remaining")
change(" await Promise.all(markerPosts);", " await Promise.all(markerPosts);if(startupTimer)clearInterval(startupTimer);await Promise.all(startupPosts);")
change("const senderEvidence={support_startup:", "const senderEvidence={instrumentation_m4:{extra_clock:extraClock,startup_timeline:startupTimeline},support_startup:")
change("let postedIceEvidence=null,postedTransportEvidence=null,postedBrowserMarkers=[],terminalDrainState=null;", "let postedIceEvidence=null,postedTransportEvidence=null,postedBrowserMarkers=[],terminalDrainState=null;const instrumentNode=[],instrumentBrowser=[],startupSamples=[];")
change(" if(moduleRoutes.has(req.url))", """ if(req.url==='/instrument-clock'){const body=await readBody(req),node_receive_ms=performance.now();if(!['train','holdout'].includes(body.role)||!Number.isFinite(body.browser_send_ms)||typeof body.marker_id!=='string')throw Error('invalid instrument marker');const marker={...body,node_receive_ms,node_send_ms:performance.now()};instrumentNode.push(marker);await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'clock_node',...marker})+'\\n');res.setHeader('Content-Type','application/json');res.end(JSON.stringify(marker));}
 else if(req.url==='/instrument-browser'){const body=await readBody(req);instrumentBrowser.push(body);await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'clock_browser',...body})+'\\n');res.end('{}');}
 else if(req.url==='/startup-sample'){const body=await readBody(req);startupSamples.push(body);await appendFile(root+'/instrument_stream.jsonl',JSON.stringify({kind:'startup',...body,node_persist_ms:performance.now()})+'\\n');res.end('{}');}
 else if(moduleRoutes.has(req.url))""")
change("support_initial_bwe_kbps:initialBweKbps", "setup_delay_ms:episode.setup_delay_ms,support_initial_bwe_kbps:initialBweKbps")
change("const senderEvidence=result.sender_evidence;delete result.sender_evidence;", "const senderEvidence=result.sender_evidence;delete result.sender_evidence;await writeFile(root+'/instrumentation_m4.json',JSON.stringify(senderEvidence.instrumentation_m4)+'\\n',{flag:'wx'});delete senderEvidence.instrumentation_m4;")
change(" const rawTurnLog=await readFile(turnLogPath,'utf8').catch(()=> '');", " await writeMissing('instrument_clock_node.json',JSON.stringify(instrumentNode)+'\\n');await writeMissing('instrument_clock_browser.json',JSON.stringify(instrumentBrowser)+'\\n');await writeMissing('startup_samples.json',JSON.stringify(startupSamples)+'\\n');\n const rawTurnLog=await readFile(turnLogPath,'utf8').catch(()=> '');")
target = REPO / "benchmarks/native_m4/prefix_instrumentation_episode_m4.mjs"
target.parent.mkdir(exist_ok=True)
target.write_text(text)
print(target)
