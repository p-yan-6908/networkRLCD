"""Build outcome-blind V12 source manifests from verified external assets.

Originals remain in the external cache. Irish single-second sampling gaps are
explicitly represented by holding the preceding measured value (at most two
isolated missing seconds per window). Murcia uses the documented nominal 1Hz
row cadence of measured TCP upload throughput, not GPS timestamps. These
representation assumptions are visible in every selected profile.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import statistics
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCREEN = Path.home() / ".cache/networkrlcd/v12-source-screen"
CACHE = Path.home() / ".cache/networkrlcd/independent-v12-sources"
STATE_NAMES = {"low": "bwe_lt_500k", "high": "bwe_ge_500k"}
SOURCE_FILES = {
    "irish_lte": ("1219679-LTE_Dataset.zip", "45e95f8a6934da230067803983b45b20e5dfb0179431d43902c8193db770e6bd"),
    "umu_campus_tcp_upload": ("15516876-UMU 5G Dataset 1.zip", "add4518d318d8684da7eeb56cbdd15c5e58800143ebdc0cdbbf785ecf2cd5d8d"),
    "nyu_lte": ("nyu-Dataset_1.rar", "30c5e6b7f2e8897dc959bf16443feee1152356ada6ec5f8cb28b5e8fb68e44da"),
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as s:
        for b in iter(lambda: s.read(4 << 20), b""):
            h.update(b)
    return h.hexdigest()


def state_hint(rates: list[float]) -> str | None:
    if len(rates) != 18 or any(not 0 <= x <= 10 for x in rates):
        return None
    if any(rates[i] == rates[i + 1] == 0 for i in range(17)):
        return None
    mean = statistics.mean(rates[3:13])
    return "low" if 0.28 <= mean <= 0.42 else "high" if 0.8 <= mean <= 4 else None


def irish_candidates() -> list[dict]:
    candidates = []
    with zipfile.ZipFile(SCREEN / SOURCE_FILES["irish_lte"][0]) as archive:
        for member in sorted(archive.namelist()):
            if not member.endswith(".csv") or "/A_" not in member:
                continue
            bins = defaultdict(list)
            for i, row in enumerate(csv.DictReader(io.StringIO(archive.read(member).decode()))):
                if row["NetworkMode"] != "LTE":
                    continue
                try:
                    timestamp = int(dt.datetime.strptime(row["Timestamp"], "%Y.%m.%d_%H.%M.%S")
                                    .replace(tzinfo=dt.timezone.utc).timestamp())
                    rate = float(row["DL_bitrate"]) / 1000
                except ValueError:
                    continue
                bins[timestamp].append((rate, i))
            points = {t: (statistics.median(x[0] for x in rows),
                          [min(x[1] for x in rows), max(x[1] for x in rows)])
                      for t, rows in bins.items()}
            for start in sorted(points):
                selected, held = [], []
                for k in range(18):
                    if start + k in points:
                        selected.append(points[start + k])
                    elif start + k - 1 in points and start + k + 1 in points:
                        selected.append(points[start + k - 1])
                        held.append(k)
                    else:
                        break
                if len(selected) != 18 or len(held) > 2:
                    continue
                rates = [round(x[0], 6) for x in selected]
                state = state_hint(rates)
                if state:
                    candidates.append({"member": member, "source_record_range": [selected[0][1][0], selected[-1][1][1]],
                        "rates_mbps": rates, "state_hint": state, "held_missing_second_indices": held,
                        "source_radio_filter": "anonymized operator A and observed LTE in every measured bin",
                        "resampling": "median of duplicate Unix-second samples; at most two isolated missing seconds hold the preceding measured value; kbps / 1000"})
    return candidates


def umu_candidates() -> list[dict]:
    candidates = []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(SCREEN / SOURCE_FILES["umu_campus_tcp_upload"][0]) as outer:
        for member in sorted(outer.namelist()):
            if not member.endswith(".xlsx") or "/tcp_" not in member:
                continue
            with zipfile.ZipFile(io.BytesIO(outer.read(member))) as archive:
                strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)]
                def value(cell):
                    v = cell.find("m:v", ns)
                    return strings[int(v.text)] if cell.get("t") == "s" and v is not None else v.text if v is not None else ""
                rows = ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall("m:sheetData/m:row", ns)
                header = next(row for row in rows if any(value(c) == "throughput_upload_speed_kbps" for c in row.findall("m:c", ns)))
                col = next(c.attrib["r"].rstrip("0123456789") for c in header.findall("m:c", ns) if value(c) == "throughput_upload_speed_kbps")
                points = []
                for row in rows:
                    cell = next((c for c in row.findall("m:c", ns) if c.attrib["r"].rstrip("0123456789") == col), None)
                    try:
                        points.append((int(row.attrib["r"]), float(value(cell)) / 1000))
                    except (ValueError, AttributeError):
                        continue
                for start in range(len(points) - 17):
                    selected = points[start:start + 18]
                    if any(selected[i + 1][0] != selected[i][0] + 1 for i in range(17)):
                        continue
                    rates = [round(x[1], 6) for x in selected]
                    state = state_hint(rates)
                    if state:
                        candidates.append({"member": member, "source_record_range": [selected[0][0], selected[-1][0]],
                            "rates_mbps": rates, "state_hint": state, "held_missing_second_indices": [],
                            "resampling": "contiguous spreadsheet rows at the source's documented nominal 1Hz polling cadence; measured throughput_upload_speed_kbps / 1000; no GPS clock used",
                            "source_radio_filter": "private 5G campus deployment described by the source; no per-row RAT/SA claim",
                            "measured_direction": "upload"})
    return candidates


def nyu_candidates() -> list[dict]:
    candidates = []
    inventory = json.loads((SCREEN / "nyu-Dataset_1-members.json").read_text())
    for entry in sorted(inventory, key=lambda x: x["member"]):
        path = SCREEN / "nyu-Dataset_1" / entry["local_file"]
        if sha(path) != entry["sha256"]:
            raise ValueError("NYU extracted source drift")
        values = []
        for row in csv.reader(path.open()):
            try:
                values.append(float(row[0]) * {"Mbits/sec": 1, "Kbits/sec": .001, "bits/sec": .000001, "Gbits/sec": 1000}[row[1].strip()])
            except (ValueError, IndexError, KeyError):
                values.append(float("nan"))
        for start in range(len(values) - 17):
            rates = [round(x, 6) for x in values[start:start + 18]]
            state = state_hint(rates)
            if state:
                candidates.append({"member": entry["member"], "member_sha256": entry["sha256"],
                    "source_record_range": [start, start + 17], "rates_mbps": rates, "state_hint": state,
                    "held_missing_second_indices": [], "resampling": "18 contiguous native 1Hz server-side iPerf samples; units explicitly converted to Mbit/s",
                    "source_radio_filter": "measured LTE campaign per pinned source README", "measured_direction": "server receive"})
    return candidates


def select(candidates: list[dict], family: str) -> tuple[list[dict], dict]:
    selected = []
    counts = {}
    for state in ("low", "high"):
        eligible = [row for row in candidates if row["state_hint"] == state]
        counts[state] = {"eligible_windows": len(eligible), "source_runs": len({row["member"] for row in eligible})}
        # The earliest eligible window in two distinct source files. Windows
        # remain nested in campaigns; no count of independent campaigns grows.
        chosen_members = set()
        for row in eligible:
            if row["member"] in chosen_members:
                continue
            chosen_members.add(row["member"])
            chosen = {**row, "profile_id": f"{family}-{state}-{len(chosen_members):02d}",
                      "family_id": family, "target_state": STATE_NAMES[state],
                      "conditioning_mean_mbps": statistics.mean(row["rates_mbps"][3:13])}
            selected.append(chosen)
            if len(chosen_members) == 2:
                break
        if len(chosen_members) != 2:
            raise ValueError(f"two distinct measured source files unavailable: {family}/{state}")
    return selected, counts


def content_manifest() -> dict:
    content_tool = REPO / "tools/derive_native_independent_v11d_content.py"
    spec = importlib.util.spec_from_file_location("frozen_content_derivation", content_tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rights_path = REPO / "acquisition/native-independent-v12/commons-rights.json"
    rights = json.loads(rights_path.read_text())
    sources = []
    clip_dir = CACHE / "content-clips"
    clip_dir.mkdir(exist_ok=True)
    for row in rights["sources"]:
        if row["license"] != "CC-BY-SA-3.0" or row["source_claim"] != "Own work" or row["rights_review_decision"] != "pass":
            raise ValueError("selected V12 source lacks explicit rights review")
        original = CACHE / "content-originals" / (row["candidate_id"] + ".webm")
        if original.stat().st_size != row["original_bytes"] or sha(original) != row["original_sha256"] or module.sha(original, "sha1") != row["original_sha1"]:
            raise ValueError("new Commons original differs from pinned catalogue")
        if float(module.ffprobe(original)["format"]["duration"]) < 30:
            raise ValueError("30 second unlooped source clip unavailable")
        clip = clip_dir / (row["content_id"] + "-30s.mp4")
        if not clip.exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(original), "-ss", "0", "-t", "30",
                "-map", "0:v:0", "-an", "-sn", "-dn", "-map_metadata", "-1",
                "-vf", "fps=30,scale=w='min(640,iw)':h='min(360,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-profile:v", "main", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip)], check=True)
        probe = module.ffprobe(clip)
        video = probe["streams"][0]
        if len(probe["streams"]) != 1 or video["codec_type"] != "video" or video["codec_name"] != "h264" or video["profile"] != "Main" or (video["width"], video["height"], video["pix_fmt"], video["avg_frame_rate"]) != (640, 360, "yuv420p", "30/1") or abs(float(probe["format"]["duration"]) - 30) > .1:
            raise ValueError("new native-ready clip failed unchanged media checks")
        sources.append({**row, "rights_manifest_sha256": sha(rights_path),
            "original_cache_path": "independent-v12-sources/content-originals/" + original.name,
            "clip_cache_path": "independent-v12-sources/content-clips/" + clip.name,
            "clip_bytes": clip.stat().st_size, "clip_sha256": sha(clip), "segment_start_s": 0, "segment_duration_s": 30,
            "derivative": "unlooped first 30s, H.264 Main yuv420p 640x360 30fps, audio removed, aspect-preserving scale and pad, metadata removed",
            "derivative_license": "CC-BY-SA-3.0"})
    content = {"abi": "native_v12_independent_content_sources_v1", "content_capture_groups": 2,
        "sources": sources, "derivative_tool": "tools/prepare_native_v12_sources.py",
        "rights_manifest_sha256": sha(rights_path), "source_pixels_saved_in_capture": False}
    return content


def build() -> dict:
    content = content_manifest()
    excluded_groups = set()
    for name in ("data/native-v11/content_sources.json", "data/native-v11d/content_sources.json"):
        excluded_groups.update(row["capture_group"] for row in json.loads((REPO / name).read_text())["sources"])
    pool = json.loads((REPO / "acquisition/native-n1/pool-and-plan.json").read_text())
    excluded_groups.update(row["capture_group"] for row in pool["sources"] if row["stage"] == "one")
    if excluded_groups.intersection(row["capture_group"] for row in content["sources"]):
        raise ValueError("content capture group overlaps prior native evidence")
    profiles, families, screen = [], {}, {}
    docs = {
        "irish_lte": {"campaign_id": "ucc_irish_lte_2017_2018", "license": "CC-BY-4.0", "record_url": "https://zenodo.org/records/1219679", "doi": "10.5281/zenodo.1219679", "attribution": "Darijo Raca, Jason Quinlan, Ahmed Zahran, Cormac Sreenan; Beyond Throughput: a 4G LTE Dataset with Channel and Context Metrics (2018).", "direction": "downlink"},
        "umu_campus_tcp_upload": {"campaign_id": "umu_private_campus_2024_2025", "license": "CC-BY-4.0", "record_url": "https://zenodo.org/records/15516876", "doi": "10.5281/zenodo.15516876", "attribution": "Rodrigo Asensio-Garriga et al.; University of Murcia 5G Dataset 1 (2025).", "direction": "upload"},
        "nyu_lte": {"campaign_id": "nyu_mets_lte", "license": "ODbL-1.0 (database); DbCL-1.0 (contents)", "record_url": "https://github.com/NYU-METS/Main/tree/886c73b1398457ba5f87faefe7a9ea3755e713f7", "git_revision": "886c73b1398457ba5f87faefe7a9ea3755e713f7", "attribution": "Lifan Mei et al.; NYU Metropolitan Mobile Bandwidth Trace; Realtime Mobile Bandwidth Prediction using LSTM Neural Networks (2019) / Bayesian fusion (2020).", "direction": "server-side LTE TCP receive; selected Dataset_1 only", "readme_sha256": "ed7f9ec26972d30835d4627b871e0da5dab0ac6fb02b40a5ec5277798b77252b"},
    }
    for family, function in (("irish_lte", irish_candidates), ("nyu_lte", nyu_candidates), ("umu_campus_tcp_upload", umu_candidates)):
        filename, expected = SOURCE_FILES[family]
        source = SCREEN / filename
        if sha(source) != expected:
            raise ValueError(f"pinned archive checksum mismatch: {family}")
        rows, counts = select(function(), family)
        screen[family] = counts
        metadata = {**docs[family], "archive_cache_path": f"v12-source-screen/{filename}",
                    "archive_sha256": expected, "archive_bytes": source.stat().st_size,
                    "selected_profile_ids": [row["profile_id"] for row in rows]}
        if family != "nyu_lte":
            record = json.loads((SCREEN / f"zenodo-{1219679 if family == 'irish_lte' else 15516876}.json").read_text())
            assert record["metadata"]["license"]["id"] == "cc-by-4.0"
            file_record = next(x for x in record["files"] if Path(x["key"]).name in filename)
            if hashlib.md5(source.read_bytes()).hexdigest() != file_record["checksum"].split(":")[1]:
                raise ValueError("Zenodo published MD5 mismatch")
            metadata["published_md5"] = file_record["checksum"].split(":")[1]
        else:
            tree = json.loads((SCREEN / "nyu-tree.json").read_text())
            blob = next(x for x in tree["tree"] if x["path"] == "Dataset/Dataset_1.rar")
            raw = source.read_bytes()
            assert hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == blob["sha"]
            assert sha(SCREEN / "nyu-README.md") == metadata["readme_sha256"]
            metadata["git_blob_sha1"] = blob["sha"]
        families[family] = metadata
        profiles.extend({**row, "campaign_id": metadata["campaign_id"], "license": metadata["license"]} for row in rows)
    network = {"abi": "native_v12_measured_network_profiles_v1", "families": families, "profiles": profiles,
        "selection": {"source_values_only": True, "native_outcomes_read": False, "window_seconds": 18,
            "conditioning_hint_mean_indices": [3, 13], "conditioning_hint_mean_ranges_mbps": {"low": [.28, .42], "high": [.8, 4]},
            "rule": "canonical family/member/offset order; earliest eligible window in two distinct source files per state",
            "maximum_rate_mbps": 10, "consecutive_zero_samples_allowed": False,
            "capacity_scaling_or_clamping": False, "profiles_per_family_state": 2},
        "source_screen": screen,
        "scope": "Three distinct acquisition campaigns; source files/windows and crossed contents are nested. Measured application throughput is replayed symmetrically as local queue service, not live radio paths. Irish isolated-gap holds and Murcia nominal row cadence are representation assumptions. Source hints never substitute for browser BWE qualification."}
    output_dir = REPO / "data/native-v12"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, document in (("content_sources.json", content), ("network_profiles.json", network)):
        path = output_dir / name
        if path.exists():
            raise ValueError(f"preserve frozen source manifest: {path}")
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return {"content_groups": 2, "campaigns": 3, "profiles": len(profiles), "support_screen": screen}


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build()))
