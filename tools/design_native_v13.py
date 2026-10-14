"""V13 continuous BWE assay: registration and strictly outcome-free gates.

Development uses reused V11D content and labeled synthetic service only.
The new measured panel remains untouched until a subsequent registered run.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import shutil
import statistics as st
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
CACHE=Path.home()/".cache/networkrlcd"
ROOT=CACHE/"native-continuous-validation-v13"
SUPPORT_ROOT=CACHE/"native-continuous-validation-v13-support"
DEV_ROOT=CACHE/"native-continuous-validation-v13-development"
CONFIG=REPO/"configs/native_continuous_validation_v13.json"
RECORDER=REPO/"benchmarks/native_v13/clock_action_turn_tcp_episode_v13.mjs"
ACTION_SEED,ORDER_SEED,DEV_SEED=20261102,20261101,20261103


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


legacy=module("v13_qualified_dependencies",REPO/"tools/native_support_validation_v12.py")
core,frozen=legacy.core,legacy.frozen
core.RECORDER=RECORDER


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(4<<20),b""):h.update(b)
    return h.hexdigest()


def read(p):return json.loads(p.read_text())


def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if p.exists() and p.read_text()!=encoded:raise ValueError(f"preserve completed artifact: {p}")
    if not p.exists():p.write_text(encoded)


def inventory():
    result=legacy.inventory()
    for name in ("tools/design_native_v13.py","tools/prepare_native_v13_sources.py","tools/analyze_native_v13.py",
        "benchmarks/native_v13/clock_action_turn_tcp_episode_v13.mjs","benchmarks/native_v13/native_continuous_support_v13.mjs"):
        result[name]=sha(REPO/name)
    return result


core.source_inventory=inventory


def panel_for(trial_id,content,profile,pair_id,slot,seed,support_only):
    schedule=[[profile["rates_mbps"][12*i],f"block_{i}",12600 if i==2 else 12000,profile["rates_mbps"][12*i:12*(i+1)]] for i in range(3)]
    episode={"id":trial_id,"role":"discovery","content_index":0,"content_id":content["content_id"],
        "network_family":profile["family_id"],"network_campaign_id":profile["campaign_id"],"network_profile_id":profile["profile_id"],
        "video_segment":[0,45000],"action_randomization_seed":seed,"schedule":schedule,"episode_timeout_s":90,
        "support_config":{"pair_id":pair_id,"pair_slot":slot,"support_only":support_only}}
    return {"panel_abi":"native_clock_action_probe_v1","stage":"discovery","source_kind":"recorded_video_v1","repair_model":None,
        "video_source":{"path":str(CACHE/content["clip_cache_path"]),"sha256":content["clip_sha256"]},"models":{},
        "common_shadow_inference":True,"SOTA_achieved":False,"episode_timeout_s":90,
        "measurement_recipe":{"abi":"native_continuous_bwe_v13_measurement","action_ratios":[.65,1.05],"action_hold_ms":3000,
            "endpoint_window_ms":[1800,2600],"deadline_ms":150,"quality_protocol":"recorded_video_640x360_sampled_RGB_v1",
            "common_pre_treatment_cap_bps":4000000,"support_only":support_only},
        "conditions":{"micro":{"controller":"micro","behavior":"ratio-randomized","level":None}},"episodes":[episode]}


def trial_for(root,content,profile,pair_id,slot,seed,support_only,rep):
    trial_id=f"{pair_id}-s{slot}"+("-support" if support_only else "")
    panel=panel_for(trial_id,content,profile,pair_id,slot,seed,support_only);relative=f"panels/{trial_id}.json";write(root/relative,panel)
    return {"id":trial_id,"condition":"micro","panel":relative,"panel_sha256":sha(root/relative),"pair_id":pair_id,"pair_slot":slot,
        "repetition":rep,"support_only":support_only,"content_id":content["content_id"],"network_family":profile["family_id"],
        "network_campaign_id":profile["campaign_id"],"network_profile_id":profile["profile_id"],
        "cell_cluster":content["content_id"]+"__"+profile["family_id"]}


def protocol_for(root,trials,kind,seed):
    prior=read(REPO/"configs/native_support_validation_v12.json")
    return {"abi":"native_continuous_bwe_v13_protocol","kind":kind,"anchor_commit":"a7ea1b0","confirmatory":kind=="confirmatory",
        "source_hashes":inventory(),"randomization":{"seed":seed,"namespace":"networkrlcd-native-v13"},
        **{k:prior[k] for k in ("runtime","calibration","clock_calibration_reference","preflight_reference","transport")},
        "trace_replay":{**prior["trace_replay"],"phase_duration_ms":[12000,12000,12600],"measured_ticks":36,"tick_tolerance_ms":150},
        "storage":{"raw_capture_root":str(root)},"trials":trials,"randomized_order":[t["id"] for t in trials],
        "analysis":{"fit_or_promote_controller":False,"outcomes_read":False},
        "support":{"decision_window_ms":[18000,18300],"eligible_bwe_bounds_bps":[240000,3800000],"history_samples":11,
            "minimum_history_span_ms":900,"maximum_sample_gap_ms":250,"minimum_profile_log2_span":1.0,
            "minimum_profile_log2_sample_sd":.35,"maximum_repeat_difference_log2":.25,"maximum_actual_census_difference_log2":.25,
            "maximum_ack_delay_ms":100,"hold_ms":3000,"ratios":[.65,1.05],"no_bin_membership_requirement":True}}


def seal(root,protocol):
    write(root/"protocol.json",protocol);(root/"protocol.sha256").write_text(sha(root/"protocol.json")+"  protocol.json\n")
    source=CACHE/"native-clock-action-turntcp-v11d/clock_report.json"
    assert sha(source)==protocol["clock_calibration_reference"]["report_sha256"]
    shutil.copy2(source,root/"clock_report.json")


def support_projection(directory,trial,protocol):
    sender=read(directory/"sender_observations.json");screen=sender["support_screen"];cfg=screen["config"]
    assert cfg=={"pair_id":trial["pair_id"],"pair_slot":trial["pair_slot"],"support_only":trial["support_only"]}
    points=[{"ms":d["sample_ms"],"bwe":d["policy_input"]["features"][0]*4000000,"valid":d["policy_input"]["features"][9]==1} for d in sender["decisions"]]
    qualified=None
    for i,p in enumerate(points):
        tail=points[max(0,i-10):i+1];elapsed=p["ms"]-sender["measurement_start_ms"]
        if (18000<=elapsed<=18300 and len(tail)==11 and tail[-1]["ms"]-tail[0]["ms"]>=900
            and all(0<b["ms"]-a["ms"]<=250 for a,b in zip(tail,tail[1:]))
            and all(q["valid"] and 240000<=q["bwe"]<=3800000 for q in tail)):
            qualified=(i,tail);break
    if qualified is None:
        assert screen["qualification"] is None and not screen["action_assigned"]
        assert all(d.get("actuator_assignment") is None and d["actuation_readback"]["encoder_max_bitrate_bps"]==4000000 for d in sender["decisions"])
        return {"passed":False,"reason":"no registered continuous BWE support","outcomes_read":False}
    index,tail=qualified;q=screen["qualification"];boundary=sender["decisions"][index];x=st.mean(math.log2(p["bwe"]/500000) for p in tail)
    assert q["passed"] and abs(q["continuous_log2_bwe"]-x)<1e-10
    assert q["sample_history_ms"]==[p["ms"] for p in tail] and all(abs(a-b["bwe"])<.01 for a,b in zip(q["bwe_history_bps"],tail,strict=True))
    assert all(d.get("actuator_assignment") is None and d["actuation_readback"]["encoder_max_bitrate_bps"]==4000000 for d in sender["decisions"][:index])
    result={"passed":True,"continuous_log2_bwe":x,"geometric_mean_bwe_bps":500000*2**x,"qualification":q,"outcomes_read":False}
    if trial["support_only"]:
        assert not screen["action_assigned"] and all(d.get("actuator_assignment") is None and d["actuation_readback"]["encoder_max_bitrate_bps"]==4000000 for d in sender["decisions"])
        return result
    draw=int.from_bytes(hashlib.sha256(f"networkrlcd-native-v13:{protocol['randomization']['seed']}:{trial['pair_id']}".encode()).digest()[:4],"big")
    arm=(draw&1)^trial["pair_slot"];ratio=(.65,1.05)[arm];base=points[index]["bwe"];cap=math.floor(base*ratio+.5);a=boundary["actuator_assignment"]
    assert a["pair_id"]==trial["pair_id"] and a["pair_slot"]==trial["pair_slot"] and a["trial_id"]==trial["id"]
    assert a["draw_uint32"]==draw and a["ratio"]==ratio and a["propensity"]==.5 and a["state_bin"]=="continuous_bwe"
    assert a["randomization_seed"]==protocol["randomization"]["seed"] and a["conditional_propensity_given_prior_pair_slot"]==(1 if trial["pair_slot"] else .5)
    assert abs(a["base_bwe_bps"]-base)<.01 and a["assignment_ms"]==boundary["sample_ms"] and a["requested_bps"]==cap and 150000<=cap<=4000000
    ack=boundary["ack_ms"];assert 0<=ack-a["assignment_ms"]<=100 and screen["ack_ms"]==ack and sender["measurement_cutoff_ms"]-ack>=3000
    assert all(d.get("actuator_assignment")==a and d["proposed_action"]["encoder_max_bitrate_bps"]==cap and d["actuation_readback"]["encoder_max_bitrate_bps"]==cap for d in sender["decisions"][index:])
    result.update({"ratio":ratio,"cap_bps":cap,"ack_ms":ack,"assignment_ms":a["assignment_ms"]})
    return result


def trace_gate(root,trial):
    panel=read(root/trial["panel"]);directory=root/"sessions"/trial["id"]
    phases,ticks=[],[]
    with gzip.open(directory/"events.jsonl.gz","rt") as stream:
        for line in stream:
            event=json.loads(line)
            if event.get("kind")=="phase":phases.append(event)
            elif event.get("kind")=="trace_capacity":ticks.append(event)
    assert len(phases)==3 and len(ticks)==36
    for phase,schedule in zip(phases,panel["episodes"][0]["schedule"],strict=True):
        _,name,_,rates=schedule;assert phase["phase"]==name and phase["trace_mbps"]==rates and phase["capacity_mbps"]==rates[0]
        t=[e for e in ticks if e["phase"]==name];assert [e["sample_index"] for e in t]==list(range(12))
        assert all(e["capacity_mbps"]==rate and abs(e["at_ms"]-phase["at_ms"]-i*1000)<=150 for i,(e,rate) in enumerate(zip(t,rates,strict=True)))
    return {"passed":True,"exact_tick_count":36,"tick_tolerance_ms":150,"outcomes_read":False}


def gate(root):
    protocol,index=core.check_capture_integrity(root);rows=[]
    for item in index["sessions"]:
        trial=next(t for t in protocol["trials"] if t["id"]==item["trial"]);directory=root/"sessions"/trial["id"]
        row={"trial":trial["id"],"capture_status":item["status"],"passed":False,
            **{k:trial[k] for k in ("cell_cluster","content_id","network_family","network_campaign_id","network_profile_id","repetition")}}
        if item["status"]=="sealed":
            markers=core.load_marker_pair(directory/"clock_markers_browser.json",directory/"clock_markers_node.json")
            assert [m["marker_id"] for m in markers]==[f"m{i:04d}" for i in range(1,13)]
            assert [m["endpoint"] for m in markers]==["/clock-marker","/clock-marker","/phase","/clock-marker","/clock-marker","/phase","/clock-marker","/clock-marker","/phase","/clock-marker","/clock-marker","/clock-marker"]
            assert [m.get("phase") for m in markers]==[None,None,"block_0",None,None,"block_1",None,None,"block_2",None,None,None]
            alignment=core.validate_markers(markers,[0,1,3,4,6,7,9,11],[2,5,8,10])
            ice=read(directory/"ice_evidence.json");urls={c.get("url") for peer in ("a","b") for c in ice.get("candidates",{}).get(peer,[])}
            transport=frozen.base.transport_checks(root,trial["id"],next(iter(urls)) if len(urls)==1 else "")
            trace=trace_gate(root,trial);cleanup=frozen.terminal_cleanup_gate(root,trial,markers,protocol);support=support_projection(directory,trial,protocol)
            summary=read(directory/"summary.json");snap=summary.get("snapshots",[])
            media=summary.get("native_rtc") is True and summary.get("connection")=="connected" and len(snap)==3 and all(s.get("frames_encoded",0)>10 and s.get("frames_decoded",0)>10 and isinstance(s.get("mean_encode_s"),(int,float)) and math.isfinite(s["mean_encode_s"]) for s in snap)
            if media:media &= all(snap[i][field]-snap[i-1][field]>10 for i in (1,2) for field in ("frames_encoded","frames_decoded"))
            row.update({"clock":{k:v for k,v in alignment.items() if k!="checks"},"transport_passed":transport["passed"],
                "trace":trace,"cleanup_passed":cleanup["passed"],"media_passed":bool(media),"support":support})
            row["passed"]=all([alignment["passed"],transport["passed"],trace["passed"],cleanup["passed"],media,support["passed"]])
        rows.append(row)
    passed=all(r["passed"] for r in rows) and len(rows)==len(protocol["trials"]);census_states={};cells={}
    if protocol["kind"]=="support_census":
        groups=defaultdict(list)
        for row in rows:
            if row["passed"]:groups[row["cell_cluster"],row["network_profile_id"]].append(row["support"]["continuous_log2_bwe"])
        for (cell,profile),values in groups.items():
            ok=len(values)==2 and max(values)-min(values)<=.25
            census_states[cell+"::"+profile]={"x":st.mean(values),"replicate_x":values,"passed":ok}
            passed &= ok
        for cell in {t["cell_cluster"] for t in protocol["trials"]}:
            selected=[s["x"] for k,s in census_states.items() if k.startswith(cell+"::")];ok=len(selected)==4 and max(selected)-min(selected)>=1 and st.stdev(selected)>=.35
            cells[cell]={"passed":ok,"profile_count":len(selected),"x_min_max":[min(selected),max(selected)] if selected else None,"x_sample_sd":st.stdev(selected) if len(selected)>1 else None}
            passed &= ok
    if protocol["kind"]=="confirmatory":
        support=gate(SUPPORT_ROOT);passed &= support["passed"];census_states=support["census_states"]
        counts=Counter()
        for row in rows:
            key=row["cell_cluster"]+"::"+row["network_profile_id"]
            if row["passed"] and key in census_states:
                row["actual_state_matches_census"]=abs(row["support"]["continuous_log2_bwe"]-census_states[key]["x"])<=.25
                row["passed"] &= row["actual_state_matches_census"]
                counts[key,row["support"]["ratio"]]+=int(row["passed"])
            else:row["passed"]=False
        passed &= all(r["passed"] for r in rows) and all(counts[key,ratio]==2 for key in census_states for ratio in (.65,1.05))
        cells=support["cells"]
    common=None
    if cells and all(c["passed"] for c in cells.values()):
        common=[max(c["x_min_max"][0] for c in cells.values()),min(c["x_min_max"][1] for c in cells.values())]
    report={"abi":"native_v13_support_clock_transport_gate_v1","kind":protocol["kind"],"passed":bool(passed),
        "protocol_sha256":sha(root/"protocol.json"),"capture_index_sha256":sha(root/"capture_index.json"),
        "planned_sessions":len(rows),"qualified_sessions":sum(r["passed"] for r in rows),"sessions":rows,
        "census_states":census_states,"cells":cells,"common_support_log2_interval":common,
        "common_support_at_least_half_octave":bool(common and common[1]-common[0]>=.5),
        "outcomes_read":False,"controller_fitted":False}
    write(root/"support_clock_transport_gate.json",report)
    return report


def verify_assets():
    sources=read(REPO/"data/native-v13/sources.json")
    for s in sources["content_sources"]:
        for kind in ("original","clip"):
            p=CACHE/s[kind+"_cache_path"];assert p.stat().st_size==s[kind+"_bytes"] and sha(p)==s[kind+"_sha256"]
    for s in sources["network_sources"]:assert sha(CACHE/s["cache_path"])==s["sha256"]
    return sources


def development():
    if DEV_ROOT.exists():raise ValueError("preserve completed development")
    original=read(REPO/"data/native-v11d/content_sources.json")["sources"][0];assert sha(CACHE/original["original_cache_path"])==original["original_sha256"]
    clip=CACHE/"independent-v13-sources/content-clips/development_cicada_reused-45s.mp4"
    content={"content_id":"development_reused_v11d_cicada","clip_cache_path":clip.relative_to(CACHE).as_posix(),"clip_sha256":sha(clip)}
    trials=[]
    for i,rate in enumerate((.35,1.2)):
        profile={"profile_id":f"synthetic_constant_{rate}","family_id":"synthetic_development_only","campaign_id":"no_measured_campaign","rates_mbps":[rate]*36}
        pair=f"v13-development-p{i}"
        trials.append(trial_for(DEV_ROOT,content,profile,pair+"-census",0,DEV_SEED,True,0))
        for slot in (0,1):trials.append(trial_for(DEV_ROOT,content,profile,pair,slot,DEV_SEED,False,0))
    protocol=protocol_for(DEV_ROOT,trials,"development",DEV_SEED);protocol["scientific_evidence"]=False
    protocol["source_note"]="Reused V11D content and synthetic constants. Instrument qualification only; all outcome files remain unopened. No V12 rerun, altered gate or new independent action-effect evidence."
    seal(DEV_ROOT,protocol);frozen.v2.set_runtime_env(protocol)
    capture=core.capture(DEV_ROOT);result=gate(DEV_ROOT)
    write(REPO/"reports/native-v13-development-qualification.json",result)
    return {"capture":capture,"gate_passed":result["passed"],"outcomes_read":False}


def prepare():
    if CONFIG.exists() or ROOT.exists() or SUPPORT_ROOT.exists():raise ValueError("fresh untouched registration required")
    sources=verify_assets();development_report=read(REPO/"reports/native-v13-development-qualification.json");assert development_report["passed"]
    assert gate(DEV_ROOT)==development_report
    trials,census=[],[]
    for ci,c in enumerate(sources["content_sources"]):
        for pi,p in enumerate(sources["network_profiles"]):
            for rep in (0,1):
                pair=f"v13-c{ci:02}-p{pi:02}-r{rep}"
                census.append(trial_for(SUPPORT_ROOT,c,p,pair,0,ACTION_SEED,True,rep))
                for slot in (0,1):trials.append(trial_for(ROOT,c,p,pair,slot,ACTION_SEED,False,rep))
    main=protocol_for(ROOT,trials,"confirmatory",ACTION_SEED)
    main.update({"support_census_root":str(SUPPORT_ROOT),"cells":sorted({t["cell_cluster"] for t in trials}),"session_order_seed":ORDER_SEED,
        "content_groups":2,"network_families":2,"collection_bundles":2,"independent_collection_programs":1,
        "state_formulation":"For each content/profile, freeze mean log2(geometric mean eleven-sample BWE /500kbps) from its two common-ceiling support-census repeats. Every action-run state must be within .25 octaves. Census state precedes all randomization and supplies the continuous modifier.",
        "primary":"Within each crossed cell, least-squares slope of paired hold PSNR differences (1.05 minus .65) on frozen census log2 BWE; equal pair weights; dB per BWE doubling; no dichotomized-state effect claimed.",
        "minimum_holds_per_profile_action":2,"required_complete_cells":4,
        "preregistration_files":{name:sha(REPO/name) for name in ["docs/NATIVE_CONTINUOUS_VALIDATION_V13_PLAN.md","docs/NATIVE_BWE_DYNAMICS_V13_DIAGNOSIS.md","data/native-v13/sources.json","data/native-v13/LICENSE-network-GPL-3.0.txt","reports/native-v13-bwe-dynamics-diagnosis.json","reports/native-v13-development-qualification.json","acquisition/native-independent-v13/source_screening.json"]}})
    # Preserve every file present at the user's anchor, including failed and
    # negative studies. New V13 files are not retroactively added to old freezes.
    names=subprocess.check_output(["git","ls-tree","-r","--name-only","a7ea1b0"],cwd=REPO,text=True).splitlines()
    main["prior_evidence_sha256"]={name:sha(REPO/name) for name in names}
    seal(ROOT,main);shutil.copy2(ROOT/"protocol.json",CONFIG)
    support=protocol_for(SUPPORT_ROOT,census,"support_census",ACTION_SEED);support["confirmatory_protocol_sha256"]=sha(CONFIG);seal(SUPPORT_ROOT,support)
    return verify()


def verify():
    main=read(CONFIG);core.verify_sources(main);verify_assets();assert sha(ROOT/"protocol.json")==sha(CONFIG)
    for name,expected in {**main["preregistration_files"],**main["prior_evidence_sha256"]}.items():assert sha(REPO/name)==expected,name
    support=read(SUPPORT_ROOT/"protocol.json");assert support["confirmatory_protocol_sha256"]==sha(CONFIG)
    for key in ("source_hashes","runtime","calibration","clock_calibration_reference","transport","trace_replay","support"):
        assert support[key]==main[key]
    assert len(main["trials"])==64 and len(support["trials"])==32 and len(main["cells"])==4
    assert {t["pair_id"] for t in main["trials"]}=={t["pair_id"] for t in support["trials"]}
    for root,protocol in ((ROOT,main),(SUPPORT_ROOT,support)):
        assert (root/"protocol.sha256").read_text().split()[0]==sha(root/"protocol.json")
        for trial in protocol["trials"]:assert sha(root/trial["panel"])==trial["panel_sha256"]
    for census in support["trials"]:
        pair=[t for t in main["trials"] if t["pair_id"]==census["pair_id"]];assert len(pair)==2 and sorted(t["pair_slot"] for t in pair)==[0,1]
        a,b=read(SUPPORT_ROOT/census["panel"]),read(ROOT/pair[0]["panel"])
        assert a["video_source"]==b["video_source"] and a["episodes"][0]["schedule"]==b["episodes"][0]["schedule"]
    return {"verified":True,"protocol_sha256":sha(CONFIG),"support_census_sessions":32,"action_sessions":64,"cells":4,
        "support_started":(SUPPORT_ROOT/"sessions").exists(),"confirmatory_started":(ROOT/"sessions").exists()}


def run(support_only):
    verify();main=read(CONFIG);root=SUPPORT_ROOT if support_only else ROOT
    if not support_only:
        census=gate(SUPPORT_ROOT)
        if not census["passed"]:raise ValueError("all 32 support checks, repeatability, four-cell range/variation gates must pass before any treatment")
    current,_=frozen.base.runtime_provenance(Path(main["preflight_reference"]["path"]));assert current==main["runtime"]
    frozen.v2.set_runtime_env(main);capture=core.capture(root);result=gate(root)
    return {"capture":capture,"gate_passed":result["passed"],"outcomes_read":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("command",choices=["development","prepare","verify","support-census","capture","gate"]);args=parser.parse_args()
    if args.command=="development":result=development()
    elif args.command=="prepare":result=prepare()
    elif args.command=="verify":result=verify()
    elif args.command=="support-census":result=run(True)
    elif args.command=="capture":result=run(False)
    else:verify();result=gate(ROOT)
    print(json.dumps(result))
