"""Prepare new V13 sources using rights, source bytes and input rates only."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import statistics as st
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path.home()/".cache/networkrlcd"
SCREEN = CACHE/"v13-source-screen"


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(4<<20),b""):h.update(b)
    return h.hexdigest()


def read(p):return json.loads(p.read_text())


def write(p,d):
    if p.exists():raise ValueError(f"preserve existing manifest: {p}")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+"\n")


def prepare():
    output=REPO/"data/native-v13"
    if output.exists():raise ValueError("preserve the prepared source panel")
    metadata=read(SCREEN/"commons-selected-detail.json")
    source_defs=[(122934090,"content_kampar_boating_01","lelly-marliana-joaquim-baeta-kampar-boating-production","CC-BY-4.0","kampar"),
                 (48770370,"content_volga_lock_01","vitaliy-voland-volga-lock-timelapse-2014","CC-BY-3.0","volga")]
    content=[]
    for page_id,content_id,group,license_id,sheet in source_defs:
        p=metadata["query"]["pages"][str(page_id)];info=p["imageinfo"][0];rights=info["extmetadata"]
        original=CACHE/f"independent-v13-sources/content-originals/commons-{page_id}.webm"
        clip=CACHE/f"independent-v13-sources/content-clips/{content_id}-45s.mp4"
        contact=CACHE/f"independent-v13-sources/contact-sheets/{sheet}.png"
        assert original.stat().st_size==info["size"] and hashlib.sha1(original.read_bytes()).hexdigest()==info["sha1"]
        probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_name,profile,width,height,r_frame_rate","-of","json",str(clip)],text=True))
        assert float(probe["format"]["duration"])==45 and len(probe["streams"])==1
        assert probe["streams"][0]["codec_name"]=="h264" and probe["streams"][0]["profile"]=="Main"
        assert probe["streams"][0]["width"]==640 and probe["streams"][0]["height"]==360 and probe["streams"][0]["r_frame_rate"]=="30/1"
        content.append({"content_id":content_id,"capture_group":group,"page_id":page_id,"title":p["title"],
            "metadata_revision":p["revisions"][0],"metadata_document_sha256":sha(SCREEN/"commons-selected-detail.json"),
            "artist":rights["Artist"]["value"],"credit":rights["Credit"]["value"],
            "license":license_id,"license_url":rights["LicenseUrl"]["value"],"catalogue_license":rights["LicenseShortName"]["value"],
            "original_url":info["url"].split("?")[0],"original_sha1":info["sha1"],"original_sha256":sha(original),"original_bytes":original.stat().st_size,
            "original_cache_path":original.relative_to(CACHE).as_posix(),"clip_cache_path":clip.relative_to(CACHE).as_posix(),
            "clip_sha256":sha(clip),"clip_bytes":clip.stat().st_size,"segment_ms":[0,45000],"looped":False,
            "derivation":"first 45 seconds, no audio; scale/pad 640x360; 30fps; libx264 Main/yuv420p CRF18 medium; faststart",
            "visual_review":{"sheet_cache_path":contact.relative_to(CACHE).as_posix(),"sha256":sha(contact),"sample_times_s":[0,8,16,24,32,40],"passed":True},
            "source_pixels_native_outcomes_observed":False})
    prior_groups={}
    for file in sorted((REPO/"data").glob("native*/content_sources.json")):
        prior_groups.update({s["capture_group"]:str(file.relative_to(REPO)) for s in read(file).get("sources",[]) if "capture_group" in s})
    assert not set(prior_groups).intersection(s["capture_group"] for s in content)
    tree=read(SCREEN/"mahimahi-tree.json");revision=tree["sha"]
    families={"sprout_verizon_evdo":{"campaign_id":"sprout_evaluation_bundle","collection_program":"mahimahi_measurement_program",
        "source_members":["traces/Verizon-EVDO-driving.down","traces/Verizon-EVDO-driving.up"],"source_import_commit":"1a775777d2f8e667c59447bf0ff268178b6ff4ad","recording_date":"unspecified in raw file; Sprout evaluation provenance"},
        "att_lte_driving_2016":{"campaign_id":"att_driving_2016_bundle","collection_program":"mahimahi_measurement_program",
        "source_members":["traces/ATT-LTE-driving-2016.down","traces/ATT-LTE-driving-2016.up"],"source_import_commit":"524fe6bda7ebe94de98d00fdbe5bf61df7a3b2d4","recording_date":"2016 in original trace name; exact measurement day unspecified"}}
    sources,profiles,screen=[],[],{}
    for family,family_row in families.items():
        for member in family_row["source_members"]:
            entry=next(x for x in tree["tree"] if x["path"]==member)
            path=SCREEN/("mahimahi-"+member.split("/")[-1]);b=path.read_bytes()
            assert len(b)==entry["size"] and hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()==entry["sha"]
            timestamps=[int(x) for x in b.splitlines()];assert timestamps==sorted(timestamps)
            # Discard the incomplete terminal second. Do not wrap the trace.
            counts=[0]*(timestamps[-1]//1000)
            for t in timestamps:
                if t//1000<len(counts):counts[t//1000]+=1
            rates=[round(n*.012,6) for n in counts]
            candidates=[]
            for offset in range(len(rates)-35):
                window=rates[offset:offset+36]
                if all(.3<=rate<=10 for rate in window):
                    # No post-decision samples enter the conditioning hint.
                    hint=math.exp(st.mean(math.log(rate) for rate in window[:19]))
                    candidates.append((hint,offset,window))
            assert len(candidates)>=2,(family,member)
            ordered=sorted(candidates,key=lambda x:(x[0],x[1]))
            selected=[ordered[0],ordered[-1]];assert selected[0][1]!=selected[1][1]
            screen[member]={"native_telemetry_observed":False,"candidate_windows":len(candidates),"selection":"minimum and maximum conditioning-only geometric mean, then source offset",
                "selected_offsets_s":[x[1] for x in selected],"same_file_window_overlap_seconds":max(0,36-abs(selected[1][1]-selected[0][1]))}
            direction="downlink" if member.endswith(".down") else "uplink"
            sources.append({"member":member,"family_id":family,"campaign_id":family_row["campaign_id"],"direction":direction,
                "url":f"https://raw.githubusercontent.com/ravinet/mahimahi/{revision}/{member}","revision":revision,"git_blob_sha1":entry["sha"],
                "bytes":len(b),"sha256":sha(path),"cache_path":path.relative_to(CACHE).as_posix(),"license":"GPL-3.0", "source_import_commit":family_row["source_import_commit"]})
            for rank,(hint,offset,window) in zip(("lower","upper"),selected,strict=True):
                profiles.append({"profile_id":f"{family}-{direction}-{rank}","family_id":family,"campaign_id":family_row["campaign_id"],
                    "source_member":member,"source_sha256":sha(path),"source_offset_seconds":offset,"duration_seconds":36,
                    "direction":direction,"rates_mbps":window,"conditioning_geometric_mean_hint_mbps":hint,
                    "resampling":"count 1500-byte packet service opportunities in each original [s*1000,(s+1)*1000) ms interval; multiply by 12000/1e6; no scaling, clipping, wrapping or missing-bin imputation",
                    "representation":"one-second binned measured service opportunities replayed symmetrically through the native queue; subsecond opportunities and directional asymmetry are not retained"})
    output.mkdir(parents=True)
    shutil.copy2(SCREEN/"mahimahi-copying.txt",output/"LICENSE-network-GPL-3.0.txt")
    provenance={"abi":"native_v13_source_panel_v1","anchor_commit":"a7ea1b0","new_native_telemetry_observed":False,
        "content_sources":content,"network_sources":sources,"network_families":families,"network_profiles":profiles,
        "network_source_screen":screen,"license_document_sha256":sha(output/"LICENSE-network-GPL-3.0.txt"),
        "trace_semantics_reference":{"path":"man/mm-link.1","revision":revision,"cache_path":"v13-source-screen/mahimahi-man-mm-link.1","sha256":sha(SCREEN/"mahimahi-man-mm-link.1")},
        "independence":"All raw productions/traces are new to prior native panels. Two distinct trace-import bundles and two radio families share one measurement program; directions, offsets, overlapping windows and repetitions remain nested. Neither four profiles nor crossed cells are independent campaign replicates. No multi-program population claim is permitted.",
        "sources_excluded":[{"source":"UCC 5G 3751194","reason":"Already included in V11; also no uninterrupted 36-second .35-3.2Mbps file-download window. Not a new source."},
            {"source":"Fjord5G CAU-8395, 14627352","sha256":"5115bd6840f0358759e70cda8b1b2137c5e52b3a941ecf6baf9b5fb161e41565","reason":"Verified 229878301-byte CC-BY-4.0 source. Router traffic counters do not document saturation or packet-service opportunities; traffic volume cannot be assumed to be path capacity."},
            {"source":"6GSMART-EZ 17737767","reason":"Verified explicitly licensed iperf samples; all complete buffer-tuning and standalone cases are substantially above the conservative state-support service range. No rate scaling or clamping."},
            {"source":"EdgeInfrastructure 7311294","reason":"Verified CC-BY-4.0 source; sparse, roughly 10-second tests near hundreds of Mbps, not a contiguous 1Hz service-opportunity history."},
            {"source":"DEDICAT6G 10829862","reason":"Sparse minute-separated throughput tests, no continuous support histories; reused source screen only."},
            {"source":"Pensieve cooked/FCC/Norway mirrors","reason":"Separate upstream data rights are not established by mirror code licenses; not selected."},
            {"source":"Airport/Pothole/Traffic/Oshodi Commons candidates","reason":"Under 36.6 seconds or insufficient original spatial resolution for the unchanged 640x360 sampled-quality recipe; not captured natively."}],
        "capacity_hints_do_not_guarantee_observed_bwe":True}
    write(output/"sources.json",provenance)
    write(REPO/"acquisition/native-independent-v13/source_screening.json",{k:provenance[k] for k in ["anchor_commit","network_source_screen","independence","sources_excluded","capacity_hints_do_not_guarantee_observed_bwe","new_native_telemetry_observed"]})
    return {"content_groups":len(content),"network_families":len(families),"collection_bundles":2,"independent_collection_programs":1,"profiles":len(profiles),"confirmatory_untouched":True}


if __name__=="__main__":print(json.dumps(prepare()))
