"""Derive privacy-minimized one-second service-rate windows for V11."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/home/agent/.cache/networkrlcd/independent-v11-sources/network")
DEFAULT_OUTPUT = REPO / "data/native-v11/network_profiles.json"
RATE_LIMIT_MBPS = 10.0
STATE_SPLIT_MBPS = 0.5
WINDOW_SECONDS = 18
MIN_SAMPLES_EACH_SIDE = 4

SOURCES = {
    "ucc_lte_operator_A": {
        "campaign_id": "ucc_misl_mobile_measurement",
        "campaign_title": "UCC/MISL 4G LTE dataset",
        "dataset_url": "https://zenodo.org/records/1219679",
        "download_url": "https://zenodo.org/records/1219679",
        "license": "CC-BY-4.0",
        "archive": "ucc-lte-dataset.zip",
        "archive_sha256": "45e95f8a6934da230067803983b45b20e5dfb0179431d43902c8193db770e6bd",
        "archive_md5": "27da16b90a94ded3511bad9682f2e166",
        "member_mode": "LTE",
        "operator": "A",
        "family_label": "UCC 4G LTE, operator A",
        "resampling": "mean DL_bitrate across records with each one-second timestamp; Kbit/s to Mbit/s",
        "select_distinct_files": True,
    },
    "ucc_5g_operator_B": {
        "campaign_id": "ucc_misl_mobile_measurement",
        "campaign_title": "UCC/MISL 5G production dataset",
        "dataset_url": "https://github.com/uccmisl/5Gdataset/tree/306d92eba81cb4f1195d8b8eba625666a02a10ec",
        "download_url": "https://github.com/uccmisl/5Gdataset/blob/306d92eba81cb4f1195d8b8eba625666a02a10ec/5G-production-dataset.zip",
        "license": "GPL-3.0",
        "repository_revision": "306d92eba81cb4f1195d8b8eba625666a02a10ec",
        "archive": "ucc-5g-production-dataset.zip",
        "archive_sha256": "abc729d696b5e0ba34a9c6ed35a851f2868d2b5071be5efb8a49691c23bb1a9b",
        "archive_git_blob_sha1": "0eb79f8507753a5fd512096221f5e87d098abcbd",
        "member_mode": "5G",
        "operator": "B",
        "family_label": "UCC 5G, operator B",
        "resampling": "mean DL_bitrate across records with each one-second timestamp; Kbit/s to Mbit/s",
        "select_distinct_files": True,
    },
    "vienna_lte_operator_C": {
        "campaign_id": "vienna_full_4g_5g",
        "campaign_title": "Vienna full 4G/5G drive-test dataset",
        "dataset_url": "https://zenodo.org/records/18322066",
        "download_url": "https://squid.nt.tuwien.ac.at/gitlab/vienna-4g-5g-dataset/Vienna-full-4G-5G-dataset/-/raw/e4e2368d9a1c78dc673805f06f62486a41839d27/phone/phone_data_lte.csv",
        "license": "CC-BY-4.0",
        "repository_revision": "e4e2368d9a1c78dc673805f06f62486a41839d27",
        "file": "vienna-lte-phone.csv",
        "file_sha256": "a7e4c43cbad6aa306c2cd4ee2e741c03ceda26912d911484d67d1e3df7233f72",
        "operator": "C",
        "family_label": "Vienna LTE, operator C",
        "resampling": "mean dl_throughput_mbps within each one-second wall-clock bin",
        "select_distinct_files": False,
    },
    "vienna_5g_operator_A": {
        "campaign_id": "vienna_full_4g_5g",
        "campaign_title": "Vienna full 4G/5G drive-test dataset",
        "dataset_url": "https://zenodo.org/records/18322066",
        "download_url": "https://squid.nt.tuwien.ac.at/gitlab/vienna-4g-5g-dataset/Vienna-full-4G-5G-dataset/-/raw/e4e2368d9a1c78dc673805f06f62486a41839d27/phone/phone_data_5g.csv",
        "license": "CC-BY-4.0",
        "repository_revision": "e4e2368d9a1c78dc673805f06f62486a41839d27",
        "file": "vienna-5g-phone.csv",
        "file_sha256": "f9f3a89386b14b4c2f10fc14e95a7656dcf762eca93ff2d7af61f04915133242",
        "operator": "A",
        "family_label": "Vienna 5G, operator A",
        "resampling": "mean dl_throughput_mbps within each one-second wall-clock bin",
        "select_distinct_files": False,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_ucc_time(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y.%m.%d_%H.%M.%S")


def eligible(rates: list[float]) -> bool:
    return (
        len(rates) == WINDOW_SECONDS
        and all(0 <= rate <= RATE_LIMIT_MBPS for rate in rates)
        and sum(rate <= STATE_SPLIT_MBPS for rate in rates) >= MIN_SAMPLES_EACH_SIDE
        and sum(rate > STATE_SPLIT_MBPS for rate in rates) >= MIN_SAMPLES_EACH_SIDE
    )


def fingerprint(*parts: object) -> str:
    data = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def ucc_candidates(source_root: Path, source: dict) -> list[dict]:
    archive = source_root / source["archive"]
    if sha256(archive) != source["archive_sha256"]:
        raise ValueError(f"pinned source archive checksum mismatch: {archive.name}")
    candidates = []
    with zipfile.ZipFile(archive) as bundle:
        for member in sorted(bundle.namelist()):
            if not member.lower().endswith(".csv") or "__MACOSX" in member:
                continue
            grouped: dict[dt.datetime, list[tuple[float, int]]] = defaultdict(list)
            text = io.TextIOWrapper(bundle.open(member), encoding="utf-8-sig", newline="")
            for row_index, row in enumerate(csv.DictReader(text), start=2):
                if (row.get("Operatorname", "").strip() != source["operator"]
                        or row.get("NetworkMode", "").strip() != source["member_mode"]):
                    continue
                try:
                    timestamp = parse_ucc_time(row["Timestamp"])
                    rate = float(row["DL_bitrate"]) / 1000.0
                except (KeyError, ValueError):
                    continue
                if rate >= 0:
                    grouped[timestamp].append((rate, row_index))
            seconds = [
                (timestamp, statistics.mean(rate for rate, _ in rows),
                 min(index for _, index in rows), max(index for _, index in rows))
                for timestamp, rows in sorted(grouped.items())
            ]
            runs: list[list[tuple[dt.datetime, float, int, int]]] = []
            current = []
            for point in seconds:
                if current and (point[0] - current[-1][0]).total_seconds() > 1.5:
                    runs.append(current)
                    current = []
                current.append(point)
            if current:
                runs.append(current)
            file_id = hashlib.sha256(member.encode()).hexdigest()[:16]
            for run_index, run in enumerate(runs):
                for start in range(0, len(run) - WINDOW_SECONDS + 1, WINDOW_SECONDS):
                    window = run[start:start + WINDOW_SECONDS]
                    rates = [round(point[1], 6) for point in window]
                    if eligible(rates):
                        candidates.append({
                            "source_trace_id": file_id,
                            "source_member": member,
                            "source_record_range": [window[0][2], window[-1][3]],
                            "run_index": run_index,
                            "window_index": start // WINDOW_SECONDS,
                            "rates_mbps": rates,
                        })
    return candidates


def vienna_candidates(source_root: Path, source: dict) -> list[dict]:
    path = source_root / source["file"]
    if sha256(path) != source["file_sha256"]:
        raise ValueError(f"pinned source file checksum mismatch: {path.name}")
    candidates = []
    runs: list[list[tuple[dt.datetime, float, int]]] = []
    current: list[tuple[dt.datetime, float, int]] = []
    previous: dt.datetime | None = None
    # Deliberately read only time, throughput, and operator. No GPS, cell, or radio-ID
    # values are loaded into the derived profiles or used for selection.
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row_index, row in enumerate(csv.DictReader(stream), start=2):
            if row.get("operator", "").strip() != source["operator"]:
                continue
            try:
                timestamp = dt.datetime.strptime(row["time"], "%Y-%m-%d %H:%M:%S.%f")
                rate = float(row["dl_throughput_mbps"])
            except (KeyError, ValueError):
                continue
            if rate < 0:
                continue
            if previous is not None and (timestamp - previous).total_seconds() > 1.5:
                if current:
                    runs.append(current)
                current = []
            current.append((timestamp, rate, row_index))
            previous = timestamp
    if current:
        runs.append(current)

    for run_index, run in enumerate(runs):
        bins: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for timestamp, rate, row_index in run:
            second = timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
            bins[second].append((rate, row_index))
        seconds = [
            (second, statistics.mean(rate for rate, _ in rows),
             min(index for _, index in rows), max(index for _, index in rows))
            for second, rows in sorted(bins.items())
        ]
        for start in range(0, len(seconds) - WINDOW_SECONDS + 1, WINDOW_SECONDS):
            window = seconds[start:start + WINDOW_SECONDS]
            rates = [round(point[1], 6) for point in window]
            if eligible(rates):
                candidates.append({
                    "source_trace_id": source["file"],
                    "source_member": source["file"],
                    "source_record_range": [window[0][2], window[-1][3]],
                    "run_index": run_index,
                    "window_index": start // WINDOW_SECONDS,
                    "rates_mbps": rates,
                })
    return candidates


def choose_profiles(key: str, source: dict, candidates: list[dict]) -> list[dict]:
    candidates.sort(key=lambda row: (row["source_member"], row["run_index"], row["window_index"]))
    if source["select_distinct_files"]:
        selected = []
        used = set()
        for row in candidates:
            if row["source_member"] in used:
                continue
            selected.append(row)
            used.add(row["source_member"])
            if len(selected) == 4:
                break
    else:
        if len(candidates) < 4:
            selected = []
        else:
            indices = [round(i * (len(candidates) - 1) / 3) for i in range(4)]
            selected = [candidates[index] for index in indices]
    if len(selected) != 4:
        raise ValueError(f"{key}: found only {len(selected)} eligible disjoint trace windows")
    result = []
    for index, row in enumerate(selected):
        profile = {
            "profile_id": f"{key}-{index + 1:02d}",
            "network_family": key,
            "campaign_id": source["campaign_id"],
            "source_member": row["source_member"],
            "source_trace_id": row["source_trace_id"],
            "source_record_range": row["source_record_range"],
            "source_window_index": row["window_index"],
            "sampling_seconds": WINDOW_SECONDS,
            "rates_mbps": row["rates_mbps"],
            "rate_summary_mbps": {
                "mean": round(statistics.mean(row["rates_mbps"]), 6),
                "minimum": min(row["rates_mbps"]),
                "maximum": max(row["rates_mbps"]),
                "seconds_at_or_below_500kbps": sum(
                    rate <= STATE_SPLIT_MBPS for rate in row["rates_mbps"]),
                "seconds_above_500kbps": sum(
                    rate > STATE_SPLIT_MBPS for rate in row["rates_mbps"]),
            },
        }
        profile["profile_sha256"] = fingerprint(profile)
        result.append(profile)
    return result


def derive(source_root: Path, output: Path) -> dict:
    families = {}
    profiles = []
    for key, source in SOURCES.items():
        candidates = (ucc_candidates(source_root, source) if "archive" in source
                      else vienna_candidates(source_root, source))
        selected = choose_profiles(key, source, candidates)
        families[key] = {
            **{name: value for name, value in source.items()
               if name not in ("operator", "member_mode", "select_distinct_files")},
            "eligible_window_count": len(candidates),
            "selected_profile_ids": [row["profile_id"] for row in selected],
        }
        profiles.extend(selected)
    document = {
        "abi": "native_independent_v11_measured_rate_profiles_v1",
        "selection_protocol": {
            "window_seconds": WINDOW_SECONDS,
            "resampling": "one Mbit/s value per chronological second; average simultaneous samples",
            "eligibility": {
                "maximum_mbps": RATE_LIMIT_MBPS,
                "minimum_seconds_at_or_below_500kbps": MIN_SAMPLES_EACH_SIDE,
                "minimum_seconds_above_500kbps": MIN_SAMPLES_EACH_SIDE,
                "missing_seconds_allowed": False,
                "overlapping_windows_allowed": False,
            },
            "selection": "first eligible window per distinct source trace for UCC; four equally spaced eligible windows for each single-file Vienna family",
            "excluded_fields": ["latitude", "longitude", "cell_id", "measurement_id", "radio identifiers"],
            "interpretation": "measured DL throughput values drive a symmetric local service-rate schedule; no original packet trace or live Internet path is replayed",
        },
        "families": families,
        "profiles": profiles,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    doc = derive(args.source_root.expanduser().resolve(), args.output.expanduser().resolve())
    print(json.dumps({"output": str(args.output), "families": {
        name: {"eligible_windows": row["eligible_window_count"],
               "selected_profiles": row["selected_profile_ids"]}
        for name, row in doc["families"].items()},
        "profiles": len(doc["profiles"])}))


if __name__ == "__main__":
    main()
