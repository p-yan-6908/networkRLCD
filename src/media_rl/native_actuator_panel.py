"""Preregistered fresh clip x regime x replicate panel over unchanged native physics."""

import argparse
import copy
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import native_actuator_panel_statistics as statistics
from . import native_actuator_study as physical
from . import native_panel_assets as assets
from .native_protocol import (
    asset_directory,
    digest,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_actuator_source_panel_v2"
SCREEN_ABI = "owned_preintervention_source_complexity_v2"
CLIP_MS = 20000
REGIMES = {
    "underutilized": [[4.0, "high", 6000], [4.0, "collapse", 6000], [4.0, "recovery", 6600]],
    "near-capacity": [[0.85, "high", 6000], [0.85, "collapse", 6000], [0.85, "recovery", 6600]],
    "queue-building": [[1.2, "high", 6000], [0.6, "collapse", 6000], [0.6, "recovery", 6600]],
    "collapse-recovery": [[1.2, "high", 6000], [0.35, "collapse", 6000], [1.2, "recovery", 6600]],
}
SCREEN_RECIPE = dict(
    abi=SCREEN_ABI,
    clip_ms=CLIP_MS,
    fps=5,
    rgb_geometry="owned_center_crop_fill_640x360",
    feature_geometry="gray_40x20",
    spatial="mean_absolute_neighbor_gradient_div_255",
    temporal="mean_absolute_consecutive_frame_change_div_255",
    motion_score="temporal_absolute_change_proxy_not_optical_flow",
    score="arithmetic_mean_spatial_temporal",
    strata="frozen_source_cluster_median_score_terciles",
    labels_preassignment=True,
    no_QP_bitrate_or_QoE_used=True,
)


def source_bindings():
    return {
        "controller_freeze": digest(assets.FREEZE),
        **{
            "python/" + name: digest(Path(__file__).with_name(name))
            for name in (
                "native_actuator_panel.py",
                "native_actuator_panel_statistics.py",
                "native_panel_assets.py",
            )
        },
    }


def clip_identity(sha, segment):
    return hashlib.sha256(f"{sha}:{segment[0]}:{segment[1]}".encode()).hexdigest()[:24]


def inventory(catalog_paths, reservation_root):
    assets.verify_controller_freeze()

    excluded, inputs = physical.reservations.reservations(reservation_root)
    clips, catalogs = [], {}
    for path in catalog_paths:
        catalog = physical.donor.dense.validate_catalog(read_json(path))
        catalog["path"] = str(Path(catalog["path"]).resolve())
        require(digest(catalog["path"]) == catalog["sha256"], "licensed source bytes changed")
        require(catalog["sha256"] not in catalogs, "duplicate movie catalog")
        catalogs[catalog["sha256"]] = catalog
        for start in range(60000, catalog["duration_ms"] - CLIP_MS + 1, CLIP_MS):
            segment = [start, start + CLIP_MS]
            if any(
                e["sha256"] == catalog["sha256"] and physical.donor.dense.video_overlap(segment, e["segment"])
                for e in excluded
            ):
                continue
            clips.append(
                dict(
                    clip_id=clip_identity(catalog["sha256"], segment),
                    source_sha256=catalog["sha256"],
                    segment=segment,
                )
            )
    records = list(catalogs.values())
    good = [c for c in records if assets.source_status(c)["eligible"]]
    grouped = assets.assign_clusters(good)
    cluster_by_sha = {c["sha256"]: group for c, group in zip(good, grouped, strict=True)}
    catalog_by_cluster = {}
    for clip in clips:
        c = catalogs[clip["source_sha256"]]
        cluster = cluster_by_sha.get(c["sha256"], "unverified-" + c["sha256"][:24])
        previously_used = any(e["sha256"] in {c["sha256"], c.get("parent_sha256")} for e in excluded)
        catalog_by_cluster[cluster] = catalog_by_cluster.get(cluster, False) or previously_used
        clip.update(
            cluster_id=cluster,
            source_title=c.get("source_title", "unverified"),
            capture_group=c.get("capture_group", "unverified"),
            parent_sha256=c.get("parent_sha256"),
            panel_eligible=c["sha256"] in cluster_by_sha,
            source_previously_used=previously_used,
            source=c.get("source"),
            license=c.get("license"),
            license_url=c["license_url"],
            resolution=[c.get("width"), c.get("height")],
            fps=c.get("frame_rate"),
            duration_ms=CLIP_MS,
            sha256=c["sha256"],
            panel_split="unassigned",
        )
    for clip in clips:
        clip["panel_eligible"] = clip["panel_eligible"] and not catalog_by_cluster[clip["cluster_id"]]
    return dict(
        abi=ABI + "_inventory",
        catalogs=catalogs,
        clips=sorted(clips, key=lambda c: c["clip_id"]),
        available_unique_clips=len({c["clip_id"] for c in clips}),
        candidate_source_clusters=len({c["cluster_id"] for c in clips}),
        eligible_source_clusters=len({c["cluster_id"] for c in clips if c["panel_eligible"]}),
        quarantine_reasons={sha: assets.source_status(catalog) for sha, catalog in catalogs.items()},
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        content_screened=False,
        outcome_data_used=False,
        no_content_reserved_by_inventory=True,
    )


def complexity_features(gray):
    require(
        isinstance(gray, np.ndarray)
        and gray.ndim == 3
        and gray.shape[1:] == (20, 40)
        and gray.shape[0] >= 80
        and np.all(np.isfinite(gray))
        and np.min(gray) >= 0
        and np.max(gray) <= 255,
        "complete owned preintervention grayscale movie samples required",
    )
    x = gray.astype(float) / 255.0
    spatial = float((np.mean(np.abs(np.diff(x, axis=1))) + np.mean(np.abs(np.diff(x, axis=2)))) / 2)
    temporal = float(np.mean(np.abs(np.diff(x, axis=0))))
    return dict(
        spatial=spatial,
        temporal=temporal,
        score=(spatial + temporal) / 2,
        sampled_frames=gray.shape[0],
        no_treatment_outcomes_used=True,
    )


def _screen_clip(catalog, segment, ffmpeg):
    vf = "scale=640:360:force_original_aspect_ratio=increase,crop=640:360,fps=5,scale=40:20,format=gray"
    capture = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-ss",
            str(segment[0] / 1000),
            "-i",
            catalog["path"],
            "-t",
            "20",
            "-vf",
            vf,
            "-an",
            "-sn",
            "-dn",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    require(len(capture.stdout) % 800 == 0, "owned screening frame geometry changed")
    gray = np.frombuffer(capture.stdout, np.uint8).reshape(-1, 20, 40)
    return complexity_features(gray)


def screen_inventory(catalog_paths, reservation_root, out, limit=120, ffmpeg="ffmpeg"):
    require(type(limit) is int and 6 <= limit <= 600, "bounded screening pool required")
    out = Path(out).resolve()
    require(not out.exists(), "screening artifact directory must be fresh")
    result = inventory(catalog_paths, reservation_root)
    eligible = [c for c in result["clips"] if c["panel_eligible"]]
    # Round robin by source: long films do not consume the screening pool first.
    pools = {}
    for clip in eligible:
        pools.setdefault(clip["cluster_id"], []).append(clip)
    selected = []
    for index in range(max((len(p) for p in pools.values()), default=0)):
        for key in sorted(pools):
            if index < len(pools[key]) and len(selected) < limit:
                selected.append(pools[key][index])
    require(
        len({c["cluster_id"] for c in selected}) >= 6,
        "at least six fresh licensed independent source clusters needed before screening",
    )
    require(len(selected) >= 6, "at least six fresh licensed clips needed for tercile screening")
    version = subprocess.run(
        [ffmpeg, "-version"], check=True, capture_output=True, text=True, timeout=10
    ).stdout.splitlines()[0]
    clips = []
    for clip in selected:
        features = _screen_clip(result["catalogs"][clip["source_sha256"]], clip["segment"], ffmpeg)
        clips.append(
            dict(
                clip,
                complexity=features,
                spatial_complexity=features["spatial"],
                temporal_complexity=features["temporal"],
                motion_score=features["temporal"],
                motion_score_method=SCREEN_RECIPE["motion_score"],
                sha256_scope="referenced_source_media",
            )
        )
    scores, thresholds = cluster_scores(clips)
    require(
        thresholds[0] < thresholds[1], "screened pool lacks identifiable low/medium/high complexity strata"
    )
    for clip in clips:
        score = scores[clip["cluster_id"]]
        clip["source_complexity_score"] = score
        clip["complexity_stratum"] = (
            "low" if score <= thresholds[0] else "medium" if score <= thresholds[1] else "high"
        )
        clip["content_stratum"] = clip["complexity_stratum"]
    result.update(
        abi=SCREEN_ABI,
        clips=clips,
        source_clusters=len(scores),
        screening_recipe=SCREEN_RECIPE,
        thresholds=thresholds,
        ffmpeg_version=version,
        implementation_sha256=source_bindings(),
        content_screened=True,
        outcome_data_used=False,
    )
    out.mkdir()
    write_json(out / "screen.json", result)
    seal_directory(
        out, ["screen.json"], SCREEN_ABI + "_complete", policy_models_fitted=0, SOTA_achieved=False
    )
    return result


def _screen(path):
    verify_seal(Path(path).resolve().parent, SCREEN_ABI + "_complete")
    result = read_json(path)
    require(
        result["abi"] == SCREEN_ABI
        and result["screening_recipe"] == SCREEN_RECIPE
        and result["implementation_sha256"] == source_bindings()
        and result["outcome_data_used"] is False,
        "frozen preintervention complexity screening required",
    )
    assets.verify_controller_freeze()
    for sha, catalog in result["catalogs"].items():
        physical.donor.dense.validate_catalog(catalog)
        if any(c["source_sha256"] == sha for c in result["clips"]):
            assets.validate_source(catalog)
        require(catalog["sha256"] == sha and digest(catalog["path"]) == sha, "screened movie source changed")
    scores, thresholds = cluster_scores(result["clips"])
    require(
        result["thresholds"] == thresholds and thresholds[0] < thresholds[1],
        "frozen complexity terciles differ",
    )
    ids = set()
    seen_segments = []
    for clip in result["clips"]:
        require(
            clip["clip_id"] == clip_identity(clip["source_sha256"], clip["segment"])
            and clip["clip_id"] not in ids
            and clip["complexity"]["no_treatment_outcomes_used"] is True,
            "unique owned complexity clip required",
        )
        features = clip["complexity"]
        catalog = result["catalogs"][clip["source_sha256"]]
        require(
            all(
                clip[k] == catalog[k]
                for k in ("source_title", "capture_group", "source", "license", "license_url")
            )
            and clip.get("parent_sha256") == catalog.get("parent_sha256")
            and clip["content_stratum"] == clip["complexity_stratum"]
            and clip["spatial_complexity"] == features["spatial"]
            and clip["temporal_complexity"] == features["temporal"]
            and clip["motion_score"] == features["temporal"]
            and clip["sha256"] == catalog["sha256"]
            and clip["sha256_scope"] == "referenced_source_media"
            and clip["resolution"] == [catalog["width"], catalog["height"]]
            and clip["fps"] == catalog["frame_rate"]
            and 60000 <= clip["segment"][0] < clip["segment"][1] <= catalog["duration_ms"],
            "screened clip/asset manifest binding changed",
        )
        require(
            clip["source_sha256"] in result["catalogs"]
            and clip["segment"][1] - clip["segment"][0] == CLIP_MS
            and all(
                isinstance(features[k], (int, float)) and 0 <= features[k] <= 1
                for k in ("spatial", "temporal", "score")
            )
            and features["sampled_frames"] >= 80
            and features["score"] == (features["spatial"] + features["temporal"]) / 2,
            "owned content-complexity feature binding invalid",
        )
        score = scores[clip["cluster_id"]]
        require(
            clip["source_complexity_score"] == score and clip["panel_eligible"],
            "source complexity/provenance changed",
        )
        expected_stratum = "low" if score <= thresholds[0] else "medium" if score <= thresholds[1] else "high"
        require(clip["complexity_stratum"] == expected_stratum, "pretreatment complexity label drift")
        require(
            all(
                c["source_sha256"] != clip["source_sha256"]
                or not physical.donor.dense.video_overlap(c["segment"], clip["segment"])
                for c in seen_segments
            ),
            "overlapping content clips cannot create independent blocks",
        )
        seen_segments.append(clip)
        ids.add(clip["clip_id"])
    verify_pool_clusters(result["clips"])
    return result


def cluster_scores(clips):
    pooled = {}
    for clip in clips:
        pooled.setdefault(clip["cluster_id"], []).append(clip["complexity"]["score"])
    scores = {key: float(np.median(values)) for key, values in pooled.items()}
    require(len(scores) >= 6, "six independent source clusters required for frozen terciles")
    return scores, np.quantile(list(scores.values()), [1 / 3, 2 / 3]).tolist()


def verify_pool_clusters(clips):
    records = [dict(c, block_id=c["cluster_id"], role="screening") for c in clips]
    assets.validate_cluster_rows(records)
    strata = {}
    for clip in clips:
        require(
            clip["cluster_id"] not in strata or strata[clip["cluster_id"]] == clip["complexity_stratum"],
            "one primary pretreatment stratum per independent source unit required",
        )
        strata[clip["cluster_id"]] = clip["complexity_stratum"]


def _settings(p):
    require(
        p["abi"] == ABI
        and type(p["source_units_per_stratum_role"]) is int
        and 8 <= p["source_units_per_stratum_role"] <= 100
        and type(p["replicates"]) is int
        and 1 <= p["replicates"] <= 20
        and type(p["seed"]) is int
        and 0 <= p["seed"] < 2**32
        and p["iv_assumptions_explicitly_assumed"] is False,
        "preregistered bounded panel sizes/seed and unverified IV assumptions required",
    )
    return p


def _build(settings, screened, excluded):
    assets.verify_controller_freeze()
    verify_pool_clusters(screened["clips"])
    rng = np.random.default_rng(settings["seed"])
    chosen = []
    reserved_sha = {e["sha256"] for e in excluded}
    previously_used_clusters = {
        c["cluster_id"]
        for c in screened["clips"]
        if c["source_sha256"] in reserved_sha or c.get("parent_sha256") in reserved_sha
    }
    for stratum in statistics.STRATA:
        candidates = sorted(
            (
                c
                for c in screened["clips"]
                if c["complexity_stratum"] == stratum and c["cluster_id"] not in previously_used_clusters
            ),
            key=lambda c: c["clip_id"],
        )
        candidates = [
            c
            for c in candidates
            if all(
                e["sha256"] != c["source_sha256"]
                or not physical.donor.dense.video_overlap(c["segment"], e["segment"])
                for e in excluded
            )
        ]
        # One representative file/window per source unit in this fixed design.
        # Arbitrarily many same-title excerpts cannot satisfy a source-unit quota.
        units = {}
        for clip in candidates:
            require(clip["panel_eligible"], "quarantined source cannot enter panel")
            distance = abs(clip["complexity"]["score"] - clip["source_complexity_score"])
            prior = units.get(clip["cluster_id"])
            if prior is None or (distance, clip["clip_id"]) < (prior[0], prior[1]["clip_id"]):
                units[clip["cluster_id"]] = distance, clip
        candidates = [v[1] for _, v in sorted(units.items())]
        require(
            len(candidates) >= settings["source_units_per_stratum_role"] * 2,
            f"fresh {stratum} independent source clusters insufficient for both roles: {len(candidates)} available",
        )
        order = rng.permutation(len(candidates))
        for role_index, role in enumerate(statistics.ROLES):
            start = role_index * settings["source_units_per_stratum_role"]
            for index in order[start : start + settings["source_units_per_stratum_role"]]:
                chosen.append(dict(candidates[int(index)], role=role, panel_split=role))
    template = read_json(settings["template"])
    require(
        physical.donor.compatible_engines(template)
        and template["repair_model"] is None
        and template["learner"] is None,
        "unchanged catalog/shadow-only template required; no outcomes reused",
    )
    verify_seal(Path(settings["template"]).resolve().parent, physical.donor.PARENT_SEAL)
    runtimes = {}
    for clip_index, clip in enumerate(chosen):
        groups = []
        for regime in statistics.REGIMES:
            for replicate in range(settings["replicates"]):
                key = f"{clip['clip_id']}:{regime}:{replicate}:{settings['seed']}"
                seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big")
                groups.append(
                    dict(
                        id=f"{clip['role']}-{clip['clip_id']}-{regime}-p{replicate}",
                        family=regime,
                        scene_seed=(clip_index % 32) * 2000,
                        video_segment=clip["segment"],
                        reservation_frames=1000,
                        schedule=copy.deepcopy(REGIMES[regime]),
                        orders=[["instrument"]],
                        block_id=clip["cluster_id"],
                        instrument_seed=seed,
                    )
                )
        # Reuse exactly the prior ABI, sampler, observer, credit and raw auditor.
        runtime = physical._runtime(
            template, screened["catalogs"][clip["source_sha256"]], clip["role"], groups
        )
        # Panel bindings live on the enclosing protocol; frozen physical runtime
        # retains its exact original extra_source_sha256 key set.
        for trial in runtime["episodes"]:
            group = next(g for g in groups if g["id"] == trial["group"])
            trial.update(
                clip_id=clip["clip_id"],
                cluster_id=clip["cluster_id"],
                source_title=clip["source_title"],
                capture_group=clip["capture_group"],
                source_sha256=clip["source_sha256"],
                parent_sha256=clip.get("parent_sha256"),
                complexity_stratum=clip["complexity_stratum"],
                network_regime=group["family"],
                replicate=int(group["id"].rsplit("-p", 1)[1]),
            )
        runtimes[clip["role"] + "-" + clip["clip_id"]] = runtime
    return chosen, runtimes


def plan_panel(settings_path, screening_path, out):
    settings = _settings(read_json(settings_path))
    screened = _screen(screening_path)
    excluded, inputs = physical.reservations.reservations(settings["reservation_root"])
    chosen, runtimes = _build(settings, screened, excluded)
    power = statistics.power_projection(
        settings["source_units_per_stratum_role"],
        settings["replicates"],
        settings["power_assumptions"],
        settings["power_simulations"],
        settings["seed"],
    )
    require(
        power["projected_80_percent_power"],
        "specified content-cluster design fails prospective 80% power lower bound; increase clips or revise justified assumptions before collection",
    )
    out = Path(out).resolve()
    require(not out.exists(), "panel plan must be fresh")
    protocol = dict(
        abi=ABI,
        settings=settings,
        screened=dict(path=str(Path(screening_path).resolve()), sha256=digest(screening_path)),
        clips=chosen,
        runtimes=runtimes,
        power=power,
        criteria=statistics.CRITERIA,
        regimes=REGIMES,
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        implementation_sha256=source_bindings(),
        policy_models_fitted=0,
        learned_controller_promoted=False,
        SOTA_achieved=False,
    )
    out.mkdir()
    write_json(out / "protocol.json", protocol)
    seal_directory(out, ["protocol.json"], ABI + "_plan", policy_models_fitted=0, SOTA_achieved=False)
    return protocol


def validate_panel(protocol):
    require(
        protocol["abi"] == ABI
        and protocol["criteria"] == statistics.CRITERIA
        and protocol["regimes"] == REGIMES
        and protocol["implementation_sha256"] == source_bindings()
        and protocol["policy_models_fitted"] == 0
        and protocol["learned_controller_promoted"] is False
        and protocol["SOTA_achieved"] is False,
        "sealed panel sources/criteria/architecture freeze drift",
    )
    _settings(protocol["settings"])
    entry = protocol["screened"]
    require(digest(entry["path"]) == entry["sha256"], "screening source changed")
    screened = _screen(entry["path"])
    excluded = []
    for path, sha in protocol["excluded_inputs_sha256"].items():
        require(digest(path) == sha, "prospective all-role reservation changed")
        raw = read_json(path)
        for p in [raw, *raw.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                excluded.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    require(excluded == protocol["excluded_video_ranges"], "complete all-role reservation coverage required")
    chosen, runtimes = _build(protocol["settings"], screened, excluded)
    require(
        chosen == protocol["clips"] and runtimes == protocol["runtimes"],
        "exact factorial assignments/runtime mismatch",
    )
    expected = statistics.power_projection(
        protocol["settings"]["source_units_per_stratum_role"],
        protocol["settings"]["replicates"],
        protocol["settings"]["power_assumptions"],
        protocol["settings"]["power_simulations"],
        protocol["settings"]["seed"],
    )
    require(
        expected == protocol["power"] and expected["projected_80_percent_power"],
        "prospective power assumptions/design changed",
    )
    return protocol


def prohibit_prefix_qualification(report):
    report.update(
        prefix_only_not_qualification=True,
        all_cells_first_stage_qualified=False,
        first_stage_valid_cells=[],
        outcome_sensitive_cells=[],
        effect_heterogeneity_established=False,
    )
    for cell in [report["pooled"], *report["cells"].values()]:
        cell["stage1"]["qualified"] = False
        cell["stage2"].update(
            qualified=False,
            actual_bitrate_causal_effect_established=False,
            status="prefix_only_not_qualification",
        )
    for test in report["interactions"].values():
        test["replicated"] = False


def peer_queue_realization(root):
    # Called ONLY after the original native auditor has replayed FIFO accounting.
    # Relay and browser windows do not share an asserted clock transform, so this
    # is peer-scoped network evidence, never a fabricated cohort-aligned outcome.
    queues, drops, wire_bytes, capacities = [], 0, 0, []
    with gzip.open(Path(root) / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            event = json.loads(line)
            if event["kind"] == "phase":
                capacities.append(event["capacity_mbps"])
            elif event["kind"] == "offer" and event["direction"] == "a_to_b":
                queues.append(event["queue_after_wire_bytes"])
                drops += int(event["dropped"])
                wire_bytes += event["wire_bytes"]
    return dict(
        scope="entire_peer_not_cohort_aligned",
        observed_capacity_mbps=capacities,
        offered_datagrams=len(queues),
        offered_wire_bytes=wire_bytes,
        dropped_datagrams=drops,
        event_sampled_queue_p95_wire_bytes=float(np.quantile(queues, 0.95)) if queues else None,
        max_queue_wire_bytes=max(queues) if queues else None,
        no_cross_clock_alignment_assumed=True,
        native_FIFO_replay_required=True,
    )


def _panel_rows(rows, trial, derived):
    wire = derived["wire"]
    for row in rows:
        row.update(
            clip_id=trial["clip_id"],
            cluster_id=trial["cluster_id"],
            source_title=trial["source_title"],
            capture_group=trial["capture_group"],
            source_sha256=trial["source_sha256"],
            parent_sha256=trial.get("parent_sha256"),
            complexity_stratum=trial["complexity_stratum"],
            network_regime=trial["network_regime"],
            replicate=trial["replicate"],
            network_realization=dict(verified_wire=wire, peer_queue=derived.get("panel_peer_queue")),
            regime_is_configured_not_guaranteed_realized=True,
        )
    return rows


def run_panel(protocol_path, out, max_peers=None):
    verify_seal(Path(protocol_path).resolve().parent, ABI + "_plan")
    cfg = validate_panel(read_json(protocol_path))
    peers = [(key, p, t) for key, p in cfg["runtimes"].items() for t in p["episodes"]]
    rng = np.random.default_rng(cfg["settings"]["seed"] + 1)
    peers = [peers[int(i)] for i in rng.permutation(len(peers))]
    require(
        max_peers is None or type(max_peers) is int and 1 <= max_peers <= len(peers),
        "bounded collection prefix",
    )
    out = Path(out).resolve()
    require(not out.exists(), "fresh panel capture required; never overwrite failed prefixes")
    out.mkdir()
    write_json(out / "protocol.json", cfg)
    rows, completed = [], {}
    try:
        for key, p, trial in peers[:max_peers]:
            runtime = out / (key + ".json")
            if not runtime.exists():
                write_json(runtime, p)
            child = out / trial["id"]
            subprocess.run(
                [
                    "node",
                    str(asset_directory() / "actuator_episode.mjs"),
                    str(child),
                    str(runtime),
                    trial["id"],
                    "instrument",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
            native, derived, cohorts = physical.audit_peer(child, p, trial)
            derived["panel_peer_queue"] = peer_queue_realization(child)
            cohorts = _panel_rows(cohorts, trial, derived)
            write_json(child / "native_row.json", native)
            write_json(child / "native_derived.json", derived)
            write_json(child / "cohorts.json", cohorts)
            seal_directory(
                child,
                sorted(str(f.relative_to(child)) for f in child.rglob("*") if f.is_file()),
                ABI + "_peer_verified",
                policy_models_fitted=0,
                SOTA_achieved=False,
            )
            completed[trial["id"]] = digest(child / "manifest.json")
            rows.extend(cohorts)
        full = len(completed) == len(peers)
        report = statistics.analyze_panel(rows)
        report.update(
            complete_prospective_inventory=full,
            planned_native_peers=len(peers),
            collected_native_peers=len(completed),
        )
        if not full:
            prohibit_prefix_qualification(report)
        write_json(out / "cohorts.json", rows)
        write_json(out / "report.json", report)
        seal_directory(
            out,
            sorted(str(f.relative_to(out)) for f in out.rglob("*") if f.is_file()),
            ABI + ("_complete" if full else "_prefix"),
            episodes=completed,
            policy_models_fitted=0,
            SOTA_achieved=False,
        )
        return report
    except Exception as error:
        write_json(
            out / "failure.json",
            dict(
                error=str(error),
                collector_stderr=error.stderr[-6000:]
                if isinstance(error, subprocess.CalledProcessError) and error.stderr
                else None,
                completed=completed,
                rerun_requires_fresh_path=True,
                learned_controller_promoted=False,
            ),
        )
        raise


def audit_panel(root):
    root = Path(root).resolve()
    manifest = verify_seal(root)
    require(
        manifest["stage"] in (ABI + "_complete", ABI + "_prefix"),
        "complete or explicitly bounded panel prefix required",
    )
    cfg = validate_panel(read_json(root / "protocol.json"))
    trials = {t["id"]: (key, p, t) for key, p in cfg["runtimes"].items() for t in p["episodes"]}
    require(set(manifest["episodes"]) <= set(trials), "unknown native peer")
    full = manifest["stage"] == ABI + "_complete"
    require(
        not full or set(manifest["episodes"]) == set(trials),
        "complete native factorial peer inventory required",
    )
    rows = []
    for identifier in manifest["episodes"]:
        key, p, trial = trials[identifier]
        require(read_json(root / (key + ".json")) == p, "factorial runtime drift")
        child = root / identifier
        verify_seal(child, ABI + "_peer_verified")
        require(digest(child / "manifest.json") == manifest["episodes"][identifier], "peer binding changed")
        native, derived, cohorts = physical.audit_peer(child, p, trial)
        derived["panel_peer_queue"] = peer_queue_realization(child)
        cohorts = _panel_rows(cohorts, trial, derived)
        require(
            native == read_json(child / "native_row.json")
            and derived == read_json(child / "native_derived.json")
            and cohorts == read_json(child / "cohorts.json"),
            "original raw/frame/encoder/byte/QoE replay differs",
        )
        rows.extend(cohorts)
    # JSON manifests sort keys, so canonical cohort order is native collection order.
    saved = read_json(root / "cohorts.json")
    require(
        sorted(rows, key=lambda r: (r["trial_id"], r["epoch"]))
        == sorted(saved, key=lambda r: (r["trial_id"], r["epoch"])),
        "factual cohort inventory differs",
    )
    report = statistics.analyze_panel(saved)
    report.update(
        complete_prospective_inventory=full,
        planned_native_peers=len(trials),
        collected_native_peers=len(manifest["episodes"]),
    )
    if not full:
        prohibit_prefix_qualification(report)
    require(report == read_json(root / "report.json"), "clip-clustered panel report differs")
    return dict(
        read_only=True,
        original_native_raw_replay=True,
        native_peers=len(manifest["episodes"]),
        cohorts=len(rows),
        complete_prospective_inventory=full,
        policy_models_fitted=0,
        learned_controller_promoted=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "screen"):
        p = sub.add_parser(name)
        p.add_argument("--catalog", action="append", required=True)
        p.add_argument("--reservation-root", default="results")
        p.add_argument("--out", required=True)
        if name == "screen":
            p.add_argument("--limit", type=int, default=120)
    power = sub.add_parser("power")
    power.add_argument("--config", required=True)
    power.add_argument("--out", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--config", required=True)
    plan.add_argument("--screen", required=True)
    plan.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--protocol", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--max-peers", type=int)
    audit = sub.add_parser("audit")
    audit.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    if args.command == "inventory":
        result = inventory(args.catalog, args.reservation_root)
        require(not Path(args.out).exists(), "fresh inventory output required")
        write_json(args.out, result)
        answer = dict(
            available_unique_clips=result["available_unique_clips"],
            candidate_source_clusters=result["candidate_source_clusters"],
            eligible_source_clusters=result["eligible_source_clusters"],
            output=args.out,
        )
    elif args.command == "screen":
        result = screen_inventory(args.catalog, args.reservation_root, args.out, args.limit)
        answer = dict(
            screened_clips=len(result["clips"]),
            strata_counts={
                s: sum(c["complexity_stratum"] == s for c in result["clips"]) for s in statistics.STRATA
            },
        )
    elif args.command == "power":
        p = _settings(read_json(args.config))
        result = statistics.power_projection(
            p["source_units_per_stratum_role"],
            p["replicates"],
            p["power_assumptions"],
            p["power_simulations"],
            p["seed"],
        )
        require(not Path(args.out).exists(), "fresh power output required")
        write_json(args.out, result)
        answer = result
    elif args.command == "plan":
        result = plan_panel(args.config, args.screen, args.out)
        answer = dict(
            unique_clips=len(result["clips"]),
            native_peers=sum(len(p["episodes"]) for p in result["runtimes"].values()),
            expected_cohorts=sum(len(p["episodes"]) for p in result["runtimes"].values()) * 6,
        )
    elif args.command == "run":
        result = run_panel(args.protocol, args.out, args.max_peers)
        answer = dict(
            complete_prospective_inventory=result["complete_prospective_inventory"],
            collected_native_peers=result["collected_native_peers"],
            first_stage_valid_cells=result["first_stage_valid_cells"],
            learned_controller_promoted=False,
        )
    else:
        answer = audit_panel(args.root)
    print(json.dumps(answer, sort_keys=True))
