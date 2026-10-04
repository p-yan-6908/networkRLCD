"""Versioned recorded-video sources, without changing legacy labels or policy inputs."""

import copy
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np

from .native_learning import validate_native_bundle
from .native_protocol import (
    DEFAULT_LIMITS,
    SCHEDULES,
    STUDY_ABI,
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    source_identity,
    spans_overlap,
    validate_protocol,
    write_json,
)
from .native_quality import QUALITY_PROTOCOL, summarize_native_quality

VIDEO_ABI = "recorded_video_v1"
VIDEO_QUALITY_PROTOCOL = dict(
    QUALITY_PROTOCOL, source="recorded video; reference RGB sampled before the owned capture request"
)
EXTRA_NAMES = ("python/native_video.py", "assets/recorded_video.mjs")


def extra_sources():
    return {
        "python/native_video.py": Path(__file__),
        "assets/recorded_video.mjs": asset_directory() / "recorded_video.mjs",
    }


def import_video_source(video, out, attribution, license_url, source_url):
    video = Path(video).resolve()
    require(
        video.is_file() and attribution.strip() and license_url.startswith("https://"),
        "local video, attribution and license URL required",
    )
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration:stream=codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    require(
        len(streams) == 1 and streams[0]["codec_name"] == "h264",
        "one browser-decodable H.264 video stream required",
    )
    duration = float(info["format"]["duration"]) * 1000
    require(
        math.isfinite(duration) and duration >= 60000, "finite recorded source duration >=60 seconds required"
    )
    catalog = dict(
        source_abi=VIDEO_ABI,
        path=str(video),
        sha256=digest(video),
        duration_ms=int(duration),
        width=streams[0]["width"],
        height=streams[0]["height"],
        frame_rate=streams[0]["r_frame_rate"],
        attribution=attribution,
        license_url=license_url,
        source_url=source_url,
        rights_asserted_by_importer=True,
        not_representative_corpus=True,
    )
    write_json(out, catalog)
    return catalog


def validate_catalog(catalog):
    require(
        catalog.get("source_abi") == VIDEO_ABI and re.fullmatch(r"[0-9a-f]{64}", catalog.get("sha256", "")),
        "versioned hashed video source required",
    )
    require(
        type(catalog.get("duration_ms")) is int and catalog["duration_ms"] >= 60000,
        "bounded recorded source duration required",
    )
    require(
        catalog.get("attribution") and catalog.get("license_url", "").startswith("https://"),
        "recorded-source attribution/license required",
    )
    require(
        catalog.get("rights_asserted_by_importer") is True
        and catalog.get("not_representative_corpus") is True,
        "do not invent rights or representative-corpus claims",
    )
    return catalog


def validate_video_protocol(protocol):
    require(protocol.get("source_kind") == VIDEO_ABI, "recorded source kind required")
    catalog = validate_catalog(protocol["video_source"])
    projected = copy.deepcopy(protocol)
    projected["source_kind"] = "generated_canvas"
    projected["excluded_scene_ranges"] = []
    for i, group in enumerate(projected["groups"]):
        group["scene_seed"] = i * 2000
    validate_protocol(projected)  # unchanged role/model/guard/order/schedule validation
    require(
        set(protocol.get("extra_source_sha256", {})) == set(EXTRA_NAMES),
        "complete recorded-source code bindings required",
    )
    reserved = []
    for group in protocol["groups"]:
        segment = group.get("video_segment")
        require(
            isinstance(segment, list)
            and len(segment) == 2
            and all(type(x) is int for x in segment)
            and 0 <= segment[0] < segment[1] <= catalog["duration_ms"]
            and segment[1] - segment[0] >= 20000,
            "full recorded warmup/playback reservation required",
        )
        require(all(not spans_overlap(segment, old) for old in reserved), "recorded source group leakage")
        reserved.append(segment)
        for old in protocol.get("excluded_video_ranges", []):
            require(set(old) == {"sha256", "segment"}, "declared recorded source exclusions required")
            require(
                old["sha256"] != catalog["sha256"] or not spans_overlap(segment, old["segment"]),
                "recorded source role leakage",
            )
    return protocol


def load_video_protocol(path, check_sources=True):
    protocol = validate_video_protocol(read_json(path))
    if check_sources:
        require(
            protocol["source_sha256"] == source_identity(), "native implementation changed after plan freeze"
        )
        require(
            protocol["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()},
            "recorded-source implementation changed after freeze",
        )
        require(
            digest(protocol["video_source"]["path"]) == protocol["video_source"]["sha256"],
            "recorded video changed",
        )
    bundles = {}
    for key, entry in protocol["models"].items():
        model = Path(entry["path"])
        if not model.is_absolute():
            model = Path(path).resolve().parent / model
        require(digest(model) == entry["sha256"], "native model changed after freeze")
        bundles[key] = read_json(model)
        validate_native_bundle(bundles[key])
        require(
            bundles[key]["risk_cutoff"] == 0.5 and bundles[key]["disagreement_cutoff"] == 0.2,
            "no native cutoff relaxation permitted",
        )
    return protocol, bundles


def plan_video_study(
    model,
    out,
    video_source,
    *,
    stage="repeatability",
    candidate=None,
    repetitions=2,
    groups_per_family=2,
    seed=1901,
    exclude_runs=(),
    repeatability_run=None,
    validation_run=None,
    results_directory="results",
    families=None,
):
    from .native_study import audit_native_study

    catalog_path = Path(video_source).resolve()
    catalog = validate_catalog(read_json(catalog_path))
    require(digest(catalog["path"]) == catalog["sha256"], "video source bytes changed")
    require(
        type(repetitions) is int
        and repetitions >= 2
        and type(groups_per_family) is int
        and groups_per_family >= 1,
        "at least two repetitions and positive group count required",
    )
    models = dict(source=dict(path=str(Path(model).resolve()), sha256=digest(model)))
    if stage in ("validation", "test"):
        require(candidate is not None and repeatability_run is not None, "candidate/repeatability required")
        models["candidate"] = dict(path=str(Path(candidate).resolve()), sha256=digest(candidate))
        conditions = dict(
            baseline=dict(controller="rlcd", model="source"),
            candidate=dict(controller="rlcd", model="candidate"),
            bwe=dict(controller="bwe", model="source"),
        )
    elif stage == "calibration":
        conditions = dict(source=dict(controller="rlcd", model="source"))
    else:
        conditions = {
            k: dict(controller="bwe" if k == "bwe" else "rlcd", model="source")
            for k in ("rlcd-a", "rlcd-b", "bwe")
        }
    excluded, inputs = [], {str(catalog_path): digest(catalog_path)}
    # A planned/interrupted panel consumes its source reservations too. Never recycle partial outcomes.
    for path in sorted(Path(results_directory).glob("native-*/protocol.json")):
        prior = read_json(path)
        if prior.get("source_kind") != VIDEO_ABI:
            continue
        validate_video_protocol(prior)
        inputs[str(path.resolve())] = digest(path)
        excluded += [
            dict(sha256=prior["video_source"]["sha256"], segment=g["video_segment"]) for g in prior["groups"]
        ]
    for root in [
        *exclude_runs,
        *([repeatability_run] if repeatability_run else []),
        *([validation_run] if stage == "test" and validation_run else []),
    ]:
        audit_native_study(root)
        prior = read_json(Path(root) / "protocol.json")
        inputs[str((Path(root) / "manifest.json").resolve())] = digest(Path(root) / "manifest.json")
        if prior.get("source_kind") == VIDEO_ABI:
            excluded += [
                dict(sha256=prior["video_source"]["sha256"], segment=g["video_segment"])
                for g in prior["groups"]
            ]
    families = list(SCHEDULES) if families is None else list(families)
    require(
        families and len(set(families)) == len(families) and set(families) <= set(SCHEDULES),
        "unique known families required",
    )
    rng = np.random.default_rng(seed)
    groups, used = [], list(excluded)
    for family in families:
        for index in range(groups_per_family):
            start = next(
                (
                    s
                    for s in range(60000, catalog["duration_ms"] - 20000, 20000)
                    if all(
                        x["sha256"] != catalog["sha256"] or not spans_overlap([s, s + 20000], x["segment"])
                        for x in used
                    )
                ),
                None,
            )
            require(
                start is not None,
                "recorded source exhausted; import another independently identified licensed video",
            )
            segment = [start, start + 20000]
            used.append(dict(sha256=catalog["sha256"], segment=segment))
            order = list(rng.permutation(list(conditions)))
            groups.append(
                dict(
                    id=f"{family}-{index}",
                    family=family,
                    scene_seed=len(groups) * 2000,
                    reservation_frames=1000,
                    video_segment=segment,
                    schedule=SCHEDULES[family],
                    orders=[order[r % len(order) :] + order[: r % len(order)] for r in range(repetitions)],
                )
            )
    protocol = dict(
        panel_abi=STUDY_ABI,
        stage=stage,
        source_kind=VIDEO_ABI,
        models=models,
        conditions=conditions,
        repetitions=repetitions,
        groups=groups,
        order_seed=seed,
        limits=DEFAULT_LIMITS.copy(),
        risk_cutoff=0.5,
        disagreement_cutoff=0.2,
        common_shadow_inference=True,
        episode_timeout_s=90,
        excluded_scene_ranges=[],
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        source_sha256=source_identity(),
        extra_source_sha256={k: digest(v) for k, v in extra_sources().items()},
        video_source=catalog,
        repeatability_run=str(Path(repeatability_run).resolve()) if repeatability_run else None,
        SOTA_achieved=False,
        transport_role="encoder_cap_overlay_on_native_GCC",
        natural_content_or_measured_link=False,
        published_learned_peer_comparison=False,
        one_recorded_film_not_representative=True,
    )
    if stage == "test":
        require(validation_run is not None, "sealed validation required")
        lock = Path(validation_run).resolve() / "selection.json"
        protocol["validation_lock"] = dict(path=str(lock), sha256=digest(lock))
    validate_video_protocol(protocol)
    write_json(out, protocol)
    load_video_protocol(out)
    return protocol


def summarize_video_quality(frames, protocol, trial):
    expected = dict(
        sha256=protocol["video_source"]["sha256"],
        segment=trial["video_segment"],
        geometry="center_crop_fill_640x360",
    )
    require(
        frames.get("video_source") == expected and frames.get("quality_protocol") == VIDEO_QUALITY_PROTOCOL,
        "recorded reference/source geometry changed",
    )
    by_id, previous = {}, -1
    for source in frames["sources"]:
        rgb, time = source.get("reference_rgb"), source.get("source_media_ms")
        require(
            isinstance(rgb, list) and len(rgb) == 2400 and all(type(v) is int and 0 <= v <= 255 for v in rgb),
            "owned pre-capture RGB reference required",
        )
        require(
            finite(time)
            and trial["video_segment"][0] - 1 <= time < trial["video_segment"][1]
            and time >= previous,
            "recorded source escaped reservation or moved backwards",
        )
        previous = time
        by_id[source["source_id"]] = rgb
    measured = [s for s in frames["sources"] if s["capture_request_ms"] >= frames["measurement_start_ms"]]
    require(
        measured
        and measured[-1]["source_media_ms"] - measured[0]["source_media_ms"]
        >= 0.7 * (frames["measurement_cutoff_ms"] - frames["measurement_start_ms"]),
        "recorded source did not advance",
    )
    for row in frames["observations"]:
        if row.get("known_source"):
            require(
                row["quality"]["reference_rgb"] == by_id[row["source_id"]],
                "readback reference differs from captured source",
            )
    adapted = dict(frames, quality_protocol=QUALITY_PROTOCOL)
    return summarize_native_quality(adapted)
