"""Produce the M7 collector from the immutable M4R recorder; no native execution."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "benchmarks/native_m4r/prefix_instrumentation_episode_m4r.mjs"
DEST = REPO / "benchmarks/native_m7/state_conditioning_episode_m7.mjs"


def build():
    text = SOURCE.read_text()
    def replace(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)
    replace('// M4R startup/clock qualification and prospective M5 prefix-only collector.',
            '// M7 fixed network-service conditioning, derived from the frozen M4R collector.')
    replace('// Randomized whole-session comparison of two fixed sender-estimate ratios; never a controller.',
            '// Support only: fixed encoder cap, causal BWE feedback changes owned network service.')
    replace('episode.schedule.some(([c,label,ms,trace])=>', 'episode.schedule.some(([c,label,ms,trace],i)=>')
    replace("ms>12600||!Array.isArray(trace)||trace.length!==12", "ms!==[10000,32000,12600][i]||!Array.isArray(trace)||trace.length!==[10,1,12][i]")
    replace("throw Error('invalid V13 support-qualified recorded-content action trial');", "throw Error('invalid frozen M7 support-only conditioning trial');")
    replace("throw Error('M2 requires a registered initialization and support-only capture');", "throw Error('M7 requires exact initialization and support-only capture');\nif(![0,0.5,1,1.5].includes(episode.conditioning_target_x)||episode.video_segment[1]!==60000)throw Error('unregistered M7 target/source segment');")
    replace("await copyFile(path.join(assetDir,'../native_v13/native_continuous_support_v13.mjs'),root+'/native_continuous_support_v13.mjs');", "await copyFile(path.join(assetDir,'../native_v13/native_continuous_support_v13.mjs'),root+'/native_continuous_support_v13.mjs');\nawait copyFile(path.join(assetDir,'../native_m7/state_conditioning_support_m7.mjs'),root+'/state_conditioning_support_m7.mjs');")
    replace("import {FRAME_PROTOCOL,writeFrameMarker,readFrameMarker} from '/frame-marker.mjs';", "import {FRAME_PROTOCOL,writeFrameMarker,readFrameMarker} from '/frame-marker.mjs';\nimport {conditionServiceM7} from '/state_conditioning_support_m7.mjs';")
    replace("}else await sleep(duration);const phaseEnd=performance.now();", "}else if(label==='block_1')await conditionServiceM7(decisions,phaseStart,nativeConfig.conditioning_target_x);else await sleep(duration);const phaseEnd=performance.now();")
    replace("const moduleRoutes=new Set([", "const moduleRoutes=new Set(['/state_conditioning_support_m7.mjs',")
    replace("const instrumentNode=[],instrumentBrowser=[],startupSamples=[];", "const instrumentNode=[],instrumentBrowser=[],startupSamples=[],conditioningBrowser=[];let conditioningRelease=null,conditioningInitial=null,conditioningSequence=0,currentServicePhase=null;")
    replace("setup_delay_ms:episode.setup_delay_ms,support_initial_bwe_kbps:initialBweKbps", "setup_delay_ms:episode.setup_delay_ms,conditioning_target_x:episode.conditioning_target_x,support_initial_bwe_kbps:initialBweKbps")
    replace("else if(req.url==='/ledger'){", """else if(req.url==='/condition-service'){
  const body=await readBody(req),now=performance.now();
  if(currentServicePhase!=='block_1'||conditioningRelease||body.sequence!==conditioningSequence+1||body.sequence>26||body.target_x!==episode.conditioning_target_x||!Number.isFinite(body.requested_mbps)||body.requested_mbps<0.2||body.requested_mbps>5||Math.abs(body.previous_mbps-capacity)>1e-12)throw Error('invalid M7 service intervention');
  for(const l of links)pumpLink(l,now);const previous_mbps=capacity;capacity=body.requested_mbps;conditioningSequence=body.sequence;
  const readback={sequence:body.sequence,capacity_mbps:capacity,previous_mbps,node_applied_ms:now};events.push({kind:'conditioning_service',at_ms:now,...readback,browser_request_ms:body.browser_request_ms});
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(readback));
 }
 else if(req.url==='/conditioning-browser'){const body=await readBody(req);conditioningBrowser.push(body);await appendFile(root+'/conditioning_stream.jsonl',JSON.stringify({kind:'browser',...body})+'\\n');res.end('{}');}
 else if(req.url==='/conditioning-release'){const body=await readBody(req);if(currentServicePhase!=='block_1'||conditioningRelease||conditioningSequence!==26||body.sequence!==27||body.capacity_mbps!==capacity)throw Error('invalid M7 release');conditioningRelease=body;await appendFile(root+'/conditioning_stream.jsonl',JSON.stringify({kind:'release',...body,node_persist_ms:performance.now()})+'\\n');res.end('{}');}
 else if(req.url==='/ledger'){""")
    replace("trace.length!==12||trace.some", "trace.length!==({block_0:10,block_1:1,block_2:12}[body.phase])||trace.some")
    replace("throw Error('invalid frozen twelve-second measured-rate block');", "throw Error('invalid frozen M7 source/service block');currentServicePhase=body.phase;")
    replace("events.push({kind:'trace_capacity',phase:body.phase,sample_index:sampleIndex,at_ms:now,capacity_mbps:capacity});", "events.push({kind:body.phase==='block_1'?'conditioning_initial':'trace_capacity',phase:body.phase,sample_index:sampleIndex,at_ms:now,capacity_mbps:capacity});if(body.phase==='block_1')conditioningInitial={at_ms:now,capacity_mbps:capacity};")
    replace("await writeMissing('instrument_clock_node.json'", "await writeMissing('conditioning_evidence.json',JSON.stringify({initial:conditioningInitial,commands:conditioningBrowser,release:conditioningRelease})+'\\n');\n await writeMissing('instrument_clock_node.json'")
    replace("const frameEvidence=result.frame_evidence;delete result.frame_evidence;", """const frameEvidence=result.frame_evidence;delete result.frame_evidence;
 await writeFile(root+'/phase_windows.json',JSON.stringify({measurement_start_ms:frameEvidence.measurement_start_ms,measurement_cutoff_ms:frameEvidence.measurement_cutoff_ms,phase_windows:frameEvidence.phase_windows})+'\\n',{flag:'wx'});
 await writeFile(root+'/media_progress.json',JSON.stringify(result.snapshots.map(s=>({phase:s.phase,frames_encoded:s.frames_encoded,frames_decoded:s.frames_decoded,mean_encode_s:s.mean_encode_s})))+'\\n',{flag:'wx'});""")
    replace("'The local userspace queue replays one-second measured application throughput, with upload/downlink provenance in the source profile, as symmetric service rates; it is not a live Internet path or a packet-trace replay.'", "'M7 separates a constructed equal-integral prefix, synthetic feedback conditioning, and an original measured-source probe, replayed as symmetric service. This is not an end-to-end live network or packet replay.'")
    if DEST.exists():
        assert DEST.read_text() == text, 'preserve an existing M7 collector'
    else:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(text)
    return {'generated': str(DEST.relative_to(REPO)), 'frozen_parent_unchanged': True}


if __name__ == '__main__':
    print(build())
