"""Derive privacy-minimized V11D rate profiles from two licensed field datasets.

Only timestamp, service/downlink throughput, radio technology, operator, band,
active-service status, and campaign fields are used. No location, cell, or
mobility columns are inspected or retained.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path("/home/agent/.cache/networkrlcd/independent-v11d-sources/network")
OUTPUT = REPO / "data/native-v11d/network_profiles.json"

WINDOW_SECONDS = 18
BLOCK_SECONDS = 6
MAX_RATE_MBPS = 10.0
STATE_SPLIT_MBPS = 0.5
MIN_BLOCK_MEAN_MBPS = 0.25
MAX_SOURCE_GAP_S = 1.5
MIN_SOURCE_STEP_S = 0.75
MAX_SOURCE_STEP_S = 1.25
ROME_MAX_RAT_OFFSET_S = 1.5
PROFILES_PER_FAMILY = 4

NORDIC = {
    "path": "nordicdat.csv",
    "record_url": "https://zenodo.org/records/10964584",
    "doi": "10.5281/zenodo.10964584",
    "license": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "md5": "3681daeaccfa78654858922c0df4a863",
    "sha256": "d1637c587ac01ce41ee24115eaa07758006bd513cf806a5daec31caf075c0249",
    "campaign_id": "nordicdat_cross_border_measurement",
    "campaign_title": "NordicDat cross-border LTE and 5G-NSA drive-test campaign",
    "attribution": "Topi Miekkala, Pasi Pyykonen, and Georgios Drainakis, “NordicDat: A Cross-Border Predictive QoS Dataset,” Zenodo, 2024, CC BY 4.0.",
}
ROME = {
    "path": "rome-throughput-tests-speedtest-active.csv",
    "record_url": "https://zenodo.org/records/8224890",
    "doi": "10.5281/zenodo.8224890",
    "license": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "md5": "4c6d46d645df9fbd7b050e4464040b5f",
    "sha256": "97de559315f6ec872ef87f4165587251f30e42bd5c7a3d67df1042919d6dbd3f",
    "campaign_id": "rome_active_speedtest_measurement",
    "campaign_title": "Rome active speedtest campaign across two anonymized operators",
    "attribution": "Konstantinos Kousias et al., “A Large-Scale Dataset of 4G, NB-IoT, and 5G Non-Standalone Network Measurements,” Zenodo, 2023, CC BY 4.0.",
}

FAMILY_SPECS = [
    {"key": "nordic_op1_5g_nsa_b20", "source": "nordic", "operator": "1",
     "ran": "5G-NSA", "band": "LTE_B20",
     "label": "NordicDat anonymized operator 1, measured 5G-NSA, LTE_B20"},
    {"key": "nordic_op1_lte_b20", "source": "nordic", "operator": "1",
     "ran": "LTE", "band": "LTE_B20",
     "label": "NordicDat anonymized operator 1, measured LTE, LTE_B20"},
    {"key": "nordic_op3_lte_b3", "source": "nordic", "operator": "3",
     "ran": "LTE", "band": "LTE_B3",
     "label": "NordicDat anonymized operator 3, measured LTE, LTE_B3"},
    {"key": "rome_op2_lte", "source": "rome", "operator": "Op2",
     "ran": "LTE", "band": None,
     "ue_mode": "5G-enabled",
     "label": "Rome anonymized operator 2, observed LTE with 5G-enabled UE mode"},
]


def file_hashes(path: Path) -> tuple[str, str]:
    h1, h256 = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            h1.update(block)
            h256.update(block)
    return h1.hexdigest(), h256.hexdigest()


def digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def number(value: str) -> float | None:
    try:
        result = float(value.strip().replace(",", "."))
    except (AttributeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def eligible(values: list[float]) -> bool:
    if len(values) != WINDOW_SECONDS or any(not 0 <= value <= MAX_RATE_MBPS for value in values):
        return False
    if any(values[i] == 0 and values[i + 1] == 0 for i in range(WINDOW_SECONDS - 1)):
        return False
    blocks = [values[start:start + BLOCK_SECONDS] for start in (0, 6, 12)]
    return all(
        statistics.mean(block) >= MIN_BLOCK_MEAN_MBPS
        and any(value <= STATE_SPLIT_MBPS for value in block)
        and any(value > STATE_SPLIT_MBPS for value in block)
        for block in blocks
    )


def source_manifest(source_root: Path) -> dict:
    files = {}
    for key, source in (("nordic", NORDIC), ("rome", ROME)):
        path = source_root / source["path"]
        md5, sha256 = file_hashes(path)
        if md5 != source["md5"] or sha256 != source["sha256"]:
            raise ValueError(f"pinned {key} source checksum mismatch: {path}")
        files[key] = {**source, "file": source["path"], "bytes": path.stat().st_size,
                      "sha256": sha256, "md5": md5}
    return files


def split_runs(points: list[dict]) -> list[list[dict]]:
    points = sorted(points, key=lambda row: (row["timestamp"], row["record_index"]))
    runs: list[list[dict]] = []
    current: list[dict] = []
    for point in points:
        if current and point["timestamp"] - current[-1]["timestamp"] > MAX_SOURCE_GAP_S:
            runs.append(current)
            current = []
        current.append(point)
    if current:
        runs.append(current)
    return runs


def screen_window(points: list[dict]) -> dict | None:
    if len(points) != WINDOW_SECONDS:
        return None
    steps = [points[i + 1]["timestamp"] - points[i]["timestamp"]
             for i in range(WINDOW_SECONDS - 1)]
    if any(step < MIN_SOURCE_STEP_S or step > MAX_SOURCE_STEP_S for step in steps):
        return None
    values = [round(point["rate_mbps"], 6) for point in points]
    if not eligible(values):
        return None
    result = {
        "rates_mbps": values,
        "source_record_range": [min(point["record_index"] for point in points),
                                max(point.get("record_index_end", point["record_index"])
                                    for point in points)],
    }
    if any("rat_offset_s" in point for point in points):
        result["max_radio_context_offset_s"] = round(
            max(point["rat_offset_s"] for point in points), 6)
        result["rome_campaign_id"] = points[0]["campaign"]
    return result


def nordic_candidates(source_root: Path, family: dict) -> tuple[list[dict], dict]:
    path = source_root / NORDIC["path"]
    wanted = (family["operator"], family["ran"], family["band"])
    source_bins: dict[int, list[tuple[float, int]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        columns = {name: header.index(name) for name in
                   ("timestamp", "operator", "ran", "band", "service_status", "throughput_downlink")}
        for row_index, row in enumerate(reader, start=2):
            if ((row[columns["operator"]], row[columns["ran"]], row[columns["band"]]) != wanted
                    or row[columns["service_status"]] != "1"):
                continue
            timestamp = number(row[columns["timestamp"]])
            kb_per_second = number(row[columns["throughput_downlink"]])
            if timestamp is None or kb_per_second is None or kb_per_second < 0:
                continue
            source_bins[int(timestamp)].append((kb_per_second * 0.008, row_index))

    points = [
        {"timestamp": float(second), "record_index": min(row_index for _, row_index in values),
         "record_index_end": max(row_index for _, row_index in values),
         "rate_mbps": statistics.median(rate for rate, _ in values)}
        for second, values in sorted(source_bins.items())
    ]

    candidates_by_run = []
    runs = split_runs(points)
    for run_index, run in enumerate(runs):
        run_candidates = []
        for start in range(0, len(run) - WINDOW_SECONDS + 1):
            item = screen_window(run[start:start + WINDOW_SECONDS])
            if item is not None:
                item.update({"source_run_index": run_index,
                             "source_window_index": start,
                             "_start_timestamp": run[start]["timestamp"]})
                run_candidates.append(item)
        if run_candidates:
            candidates_by_run.append(run_candidates)
    summary = {"eligible_source_rows": len(points), "continuous_runs": len(runs),
               "eligible_runs": len(candidates_by_run),
               "eligible_windows": sum(len(items) for items in candidates_by_run)}
    candidates = sorted((item for items in candidates_by_run for item in items),
                        key=lambda item: (item["_start_timestamp"], item["source_run_index"],
                                          item["source_window_index"]))
    if len(candidates) < PROFILES_PER_FAMILY:
        raise ValueError(f"{family['key']} has fewer than four eligible source windows: {summary}")
    # Four nonoverlapping windows are selected across the source-time range.
    targets = [candidates[min(len(candidates) - 1,
                              int((index + 0.5) * len(candidates) / PROFILES_PER_FAMILY))]
               ["_start_timestamp"] for index in range(PROFILES_PER_FAMILY)]
    selected = []
    for target in targets:
        options = [item for item in candidates
                   if all(abs(item["_start_timestamp"] - chosen["_start_timestamp"]) >= WINDOW_SECONDS
                          for chosen in selected)]
        if not options:
            raise ValueError(f"{family['key']} cannot select four nonoverlapping source windows")
        selected.append(min(options, key=lambda item: (abs(item["_start_timestamp"] - target),
                                                        item["_start_timestamp"])))
    if len({item["_start_timestamp"] for item in selected}) != PROFILES_PER_FAMILY:
        raise ValueError(f"{family['key']} source windows overlap or duplicate")
    for item in selected:
        item.pop("_start_timestamp", None)
    return selected, summary


def parse_rome_timestamp(date: str, clock: str) -> dt.datetime:
    return dt.datetime.strptime(date + " " + clock, "%d.%m.%Y %H:%M:%S.%f")


def rome_candidates(source_root: Path, family: dict) -> tuple[list[dict], dict]:
    path = source_root / ROME["path"]
    group_rows: dict[tuple[str, str], dict] = defaultdict(lambda: {"radio": [], "rate": []})
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        columns = {name: header.index(name) for name in
                   ("Date", "Time", "RAT Info", "Current Netw. DL", "UE Mode", "Operator", "Campaign")}
        for row_index, row in enumerate(reader, start=2):
            if (row[columns["Operator"]] != family["operator"]
                    or row[columns["UE Mode"]] != family["ue_mode"]):
                continue
            try:
                timestamp = parse_rome_timestamp(row[columns["Date"]], row[columns["Time"]]).timestamp()
            except ValueError:
                continue
            campaign = row[columns["Campaign"]]
            group = (campaign, row[columns["Date"]])
            rat = row[columns["RAT Info"]]
            if rat in ("LTE", "5G EN-DC"):
                group_rows[group]["radio"].append((timestamp, rat, row_index))
            kbps = number(row[columns["Current Netw. DL"]])
            if kbps is not None and kbps >= 0:
                group_rows[group]["rate"].append((timestamp, kbps, row_index))

    by_campaign: dict[str, list[dict]] = defaultdict(list)
    aligned_rows = 0
    matched_radio_rows = 0
    for (campaign, date), group in group_rows.items():
        radio = sorted(group["radio"])
        radio_times = [entry[0] for entry in radio]
        second_bins: dict[int, list[tuple[float, int, float]]] = defaultdict(list)
        for timestamp, kbps, row_index in group["rate"]:
            position = __import__("bisect").bisect_left(radio_times, timestamp)
            nearest = []
            if position < len(radio):
                nearest.append(radio[position])
            if position:
                nearest.append(radio[position - 1])
            if not nearest:
                continue
            match = min(nearest, key=lambda item: abs(item[0] - timestamp))
            offset = abs(match[0] - timestamp)
            matched_radio_rows += 1
            if offset > ROME_MAX_RAT_OFFSET_S or match[1] != family["ran"]:
                continue
            aligned_rows += 1
            second_bins[int(timestamp)].append((kbps / 1000.0, row_index, offset))

        # Multiple same-second callbacks are collapsed by median; no other fields are used.
        seconds = {}
        for second, values in second_bins.items():
            seconds[second] = {
                "timestamp": float(second),
                "rate_mbps": statistics.median(value[0] for value in values),
                "record_index": min(value[1] for value in values),
                "record_index_end": max(value[1] for value in values),
                "rat_offset_s": max(value[2] for value in values),
                "campaign": campaign,
            }
        for run in split_runs(list(seconds.values())):
            for start in range(0, len(run) - WINDOW_SECONDS + 1):
                item = screen_window(run[start:start + WINDOW_SECONDS])
                if item is None:
                    continue
                item["source_record_range"] = [
                    min(point["record_index"] for point in run[start:start + WINDOW_SECONDS]),
                    max(point["record_index_end"] for point in run[start:start + WINDOW_SECONDS]),
                ]
                item["source_run_index"] = start
                by_campaign[campaign].append(item)

    campaigns = sorted(by_campaign, key=lambda label: int(label.rsplit("_", 1)[-1]))
    if len(campaigns) < PROFILES_PER_FAMILY:
        raise ValueError(f"Rome stratum has fewer than four eligible speedtest subcampaigns: {len(campaigns)}")
    selected_campaign_indices = [min(len(campaigns) - 1,
                                     int((index + 0.5) * len(campaigns) / PROFILES_PER_FAMILY))
                                 for index in range(PROFILES_PER_FAMILY)]
    if len(set(selected_campaign_indices)) != PROFILES_PER_FAMILY:
        raise ValueError("Rome family could not select four distinct speedtest subcampaigns")
    selected = []
    for campaign_index in selected_campaign_indices:
        campaign = campaigns[campaign_index]
        options = sorted(by_campaign[campaign], key=lambda item: item["source_record_range"])
        item = dict(options[len(options) // 2])
        item["source_trace_id"] = campaign
        item["source_subcampaign_id"] = campaign
        selected.append(item)
    summary = {"matched_radio_rows": matched_radio_rows, "LTE_aligned_speedtest_rows": aligned_rows,
               "eligible_subcampaigns": len(campaigns),
               "eligible_windows": sum(len(items) for items in by_campaign.values()),
               "selected_subcampaigns": [item["source_subcampaign_id"] for item in selected]}
    return selected, summary


def profile_record(family: dict, source: dict, selected: dict, index: int) -> dict:
    rates = selected["rates_mbps"]
    return {
        "profile_id": f"{family['key']}-{index + 1:02d}",
        "network_family": family["key"],
        "campaign_id": source["campaign_id"],
        "source_file": source["path"],
        "source_file_sha256": source["sha256"],
        "source_trace_id": selected.get("source_trace_id", family["key"]),
        "source_subcampaign_id": selected.get("source_subcampaign_id"),
        "source_run_index": selected["source_run_index"],
        "source_record_range": selected["source_record_range"],
        "max_radio_context_offset_s": selected.get("max_radio_context_offset_s"),
        "profile_sha256": digest(rates),
        "sampling_seconds": WINDOW_SECONDS,
        "rate_summary_mbps": {
            "minimum": min(rates), "maximum": max(rates),
            "mean": round(statistics.mean(rates), 6),
            "seconds_at_or_below_500kbps": sum(value <= STATE_SPLIT_MBPS for value in rates),
            "seconds_above_500kbps": sum(value > STATE_SPLIT_MBPS for value in rates),
            "block_means_mbps": [round(statistics.mean(rates[start:start + 6]), 6)
                                  for start in (0, 6, 12)],
            "block_terminal_rates_mbps": [rates[index] for index in (5, 11, 17)],
        },
        "rates_mbps": rates,
    }


def derive(source_root: Path, output: Path) -> dict:
    files = source_manifest(source_root)
    family_rows = {}
    profiles = []
    for family in FAMILY_SPECS:
        source_key = family["source"]
        if source_key == "nordic":
            candidates, summary = nordic_candidates(source_root, family)
        else:
            candidates, summary = rome_candidates(source_root, family)
        family_rows[family["key"]] = {
            "label": family["label"], "operator_anonymized": family["operator"],
            "ran": family["ran"], "band": family["band"],
            "ue_mode": family.get("ue_mode"), "campaign_id": files[source_key]["campaign_id"],
            "campaign_title": files[source_key]["campaign_title"],
            "dataset_url": files[source_key]["record_url"], "doi": files[source_key]["doi"],
            "license": files[source_key]["license"], "license_url": files[source_key]["license_url"],
            "file": files[source_key]["path"], "file_sha256": files[source_key]["sha256"],
            "measurement": "application-level measured downlink throughput replayed as local service rate",
            "resampling": ("median measured throughput within each Unix-second bin; KB/s × 0.008 to Mbit/s"
                           if source_key == "nordic" else
                           "median Current Netw. DL in each UTC-second bin; kb/s ÷ 1000 to Mbit/s; each rate row must align to LTE RAT Info within 1.5 s"),
            "eligible_source_screen": summary,
            "selected_profile_ids": [f"{family['key']}-{number:02d}" for number in range(1, 5)],
        }
        profiles.extend(profile_record(family, files[source_key], item, index)
                        for index, item in enumerate(candidates))

    smoke_profile = min(profiles, key=lambda row: sum(row["rate_summary_mbps"]["block_terminal_rates_mbps"]))
    document = {
        "abi": "native_independent_v11d_measured_rate_profiles_v1",
        "source_files": files,
        "families": family_rows,
        "profiles": profiles,
        "technical_smoke_profile_id": smoke_profile["profile_id"],
        "selection_protocol": {
            "window_seconds": WINDOW_SECONDS, "samples_per_second": 1,
            "profile_count_per_family": PROFILES_PER_FAMILY,
            "max_rate_mbps": MAX_RATE_MBPS, "state_split_mbps": STATE_SPLIT_MBPS,
            "min_mean_each_six_second_block_mbps": MIN_BLOCK_MEAN_MBPS,
            "each_six_second_block_has_both_rate_states": True,
            "consecutive_zero_sample_limit": 1,
            "max_source_gap_seconds": MAX_SOURCE_GAP_S,
            "source_sample_step_seconds": [MIN_SOURCE_STEP_S, MAX_SOURCE_STEP_S],
            "network_source_family_order": [row["key"] for row in FAMILY_SPECS],
            "nordic_profile_rule": "median measured throughput within each Unix-second bin; split at >1.5-second gaps; select four temporally stratified, nonoverlapping eligible windows per operator/RAN/band family; windows remain nested under the same campaign",
            "rome_profile_rule": "use only Op2, 5G-enabled UE mode; align each speedtest throughput row to the nearest actual LTE RAT Info observation within 1.5 seconds in the same date and Speedtest_Campaign; median same-second rates; select four temporally stratified eligible windows from four distinct Speedtest_Campaign IDs",
            "technical_smoke_profile_rule": "among the 16 registered main-panel profiles, select the profile with the lowest sum of the three six-second terminal rates; require residual pre-cleanup queue and empty post-cleanup queue in the technical smoke",
            "no_outcomes_used": True,
            "excluded_source_fields": ["latitude", "longitude", "elevation", "serving_cell_id", "GNSS mode", "heading", "velocity", "acceleration", "PCI", "radio identifiers"],
        },
        "network_campaigns": [
            "nordicdat_cross_border_measurement",
            "rome_active_speedtest_measurement",
        ],
        "independence_note": "The four network families are nested in two independently collected datasets/campaigns. NordicDat contributes three anonymized operator/RAN/band strata; Rome contributes a separate anonymized operator LTE stratum. Repeated 18-second windows and Rome Speedtest_Campaign IDs are nested source segments, not independent network campaigns.",
    }
    if len(profiles) != 16:
        raise ValueError(f"expected sixteen registered source profiles, found {len(profiles)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"output": str(output), "families": len(family_rows), "profiles": len(profiles),
            "technical_smoke_profile_id": smoke_profile["profile_id"],
            "families_screened": {key: value["eligible_source_screen"]
                                  for key, value in family_rows.items()},
            "profile_hashes": {row["profile_id"]: row["profile_sha256"] for row in profiles}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(derive(args.source_root, args.output), indent=2))


if __name__ == "__main__":
    main()
