"""Frozen, role-disjoint native study contracts; no implicit deployment or promotion."""

import hashlib
import json
import math
import re
from pathlib import Path

from .native_learning import validate_native_bundle

STUDY_ABI = "native_reliability_study_v1"
STAGES = ("repeatability", "calibration", "validation", "test")
ASSET_NAMES = (
    "episode.mjs",
    "frame_marker.mjs",
    "native_actuation.mjs",
    "sender_observation.mjs",
    "source_quality.mjs",
    "bwe_cap_controller.mjs",
    "native_policy.mjs",
)
DEFAULT_LIMITS = dict(
    repeatability_utility_span=3.0,
    repeatability_ontime_span=0.15,
    inference_p99_ms=10.0,
    min_validation_groups=8,
    min_utility_gain=0.0,
    max_ontime_drop=0.02,
    max_family_utility_drop=0.5,
)
SCHEDULES = {
    "stable": [[2, "high", 3000], [2, "collapse", 3000], [2, "recovery", 3000]],
    "collapse": [[2, "high", 3000], [0.5, "collapse", 3000], [2, "recovery", 3000]],
    "variable": [[3.2, "high", 3000], [0.7, "collapse", 3000], [2.8, "recovery", 3000]],
    "brief-collapse": [[2, "high", 4000], [0.5, "collapse", 1000], [2, "recovery", 4000]],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def reject(value):
        raise ValueError("nonfinite JSON: " + value)

    return json.loads(Path(path).read_text(), parse_constant=reject)


def write_json(path, data):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(data, indent=2, allow_nan=False) + "\n")


def asset_directory():
    installed = Path(__file__).with_name("native_assets")
    return installed if installed.is_dir() else Path(__file__).resolve().parents[2] / "benchmarks/native_rtc"


def source_identity():
    assets = asset_directory()
    sources = {"assets/" + name: digest(assets / name) for name in ASSET_NAMES}
    for name in [
        "native_protocol.py",
        "native_study.py",
        "native_statistics.py",
        "native_wire.py",
        "native_calibration.py",
        "native_learning.py",
        "native_dataset.py",
        "native_observations.py",
        "native_policy_replay.py",
        "native_quality.py",
        "native_frame_metrics.py",
        "networks.py",
    ]:
        sources["python/" + name] = digest(Path(__file__).with_name(name))
    return sources


def artifact_path(root, name):
    path = Path(name)
    require(not path.is_absolute() and path.parts and ".." not in path.parts, "unsafe artifact path")
    target = Path(root) / path
    require(target.resolve().is_relative_to(Path(root).resolve()), "artifact escaped sealed directory")
    require(not target.is_symlink(), "symlink artifacts forbidden")
    return target


def verify_seal(root, stage=None):
    seal = read_json(Path(root) / "manifest.json")
    if stage is not None:
        require(seal.get("stage") == stage, "wrong or incomplete native evidence stage")
    hashes = seal.get("artifacts_sha256", {})
    require(isinstance(hashes, dict) and hashes, "empty native evidence seal")
    for name, sha in hashes.items():
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "invalid artifact digest")
        require(digest(artifact_path(root, name)) == sha, "native artifact changed: " + name)
    return seal


def seal_directory(root, names, stage, **extra):
    write_json(
        Path(root) / "manifest.json",
        dict(
            stage=stage,
            artifacts_sha256={name: digest(artifact_path(root, name)) for name in names},
            **extra,
        ),
    )


def spans_overlap(left, right):
    return not (left[1] < right[0] or right[1] < left[0])


def validate_protocol(protocol):
    require(protocol.get("panel_abi") == STUDY_ABI, "native reliability protocol ABI required")
    stage = protocol.get("stage")
    require(stage in STAGES, "explicit native study role required")
    require(protocol.get("SOTA_achieved") is False, "native prototype cannot certify SOTA")
    require(
        protocol.get("risk_cutoff") == 0.5 and protocol.get("disagreement_cutoff") == 0.2,
        "native screens must remain 0.5/0.2",
    )
    require(protocol.get("source_kind") == "generated_canvas", "collector only supports generated canvas")
    require(protocol.get("common_shadow_inference") is True, "common model compute required")
    repeats = protocol.get("repetitions")
    require(type(repeats) is int and 2 <= repeats <= 20, "at least two declared repetitions required")
    limits = protocol.get("limits", {})
    require(set(limits) == set(DEFAULT_LIMITS), "all predeclared native limits required")
    require(all(finite(v) and v >= 0 for v in limits.values()), "finite nonnegative native limits required")
    require(
        type(limits["min_validation_groups"]) is int and limits["min_validation_groups"] >= 8,
        "at least eight validation groups required",
    )
    require(
        0 <= limits["max_ontime_drop"] <= 1 and 0 <= limits["repeatability_ontime_span"] <= 1,
        "native on-time bounds must be fractions",
    )
    require(
        type(protocol.get("episode_timeout_s")) is int and 30 <= protocol["episode_timeout_s"] <= 180,
        "bounded native episode deadline required",
    )
    models, conditions = protocol.get("models", {}), protocol.get("conditions", {})

    def safe_name(x):
        return isinstance(x, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", x)

    require(models and all(safe_name(k) for k in models), "safe native model keys required")
    for entry in models.values():
        require(
            set(entry) == {"path", "sha256"}
            and isinstance(entry["path"], str)
            and isinstance(entry["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]),
            "pinned native model path/hash required",
        )
    require(conditions and all(safe_name(k) for k in conditions), "safe condition keys required")
    for condition in conditions.values():
        require(
            set(condition) == {"controller", "model"}
            and condition["controller"] in ("rlcd", "bwe", "fixed")
            and condition["model"] in models,
            "supported native control/model required",
        )
    if stage == "repeatability":
        require(set(conditions) == {"rlcd-a", "rlcd-b", "bwe"}, "identical-policy controls required")
        require(
            conditions["rlcd-a"] == conditions["rlcd-b"] and conditions["rlcd-a"]["controller"] == "rlcd",
            "repeatability aliases must execute the exact same policy",
        )
    if stage == "calibration":
        require(
            set(conditions) == {"source"} and conditions["source"]["controller"] == "rlcd",
            "fresh factual source-selected calibration only",
        )
    if stage in ("validation", "test"):
        require(
            set(conditions) == {"baseline", "candidate", "bwe"}
            and all(conditions[k]["controller"] == "rlcd" for k in ("baseline", "candidate"))
            and conditions["bwe"]["controller"] == "bwe",
            "native candidate/baseline/BWE controls required",
        )
        require(protocol.get("repeatability_run") is not None, "verified repeatability prerequisite required")
    excluded = protocol.get("excluded_scene_ranges", [])
    require(
        all(
            isinstance(s, list) and len(s) == 2 and all(type(x) is int and x >= 0 for x in s) and s[0] <= s[1]
            for s in excluded
        ),
        "valid excluded content ranges required",
    )
    groups = protocol.get("groups", [])
    require(groups and len({g["id"] for g in groups}) == len(groups), "unique native source groups required")
    reserved = []
    for group in groups:
        require(
            safe_name(group["id"]) and group["family"] in SCHEDULES, "known family and safe group ID required"
        )
        seed, count = group["scene_seed"], group["reservation_frames"]
        require(
            type(seed) is int and 0 <= seed <= 64500 and type(count) is int and count >= 1000,
            "bounded scene seed and full warmup reservation required",
        )
        span = [seed, seed + count]
        require(all(not spans_overlap(span, s) for s in [*reserved, *excluded]), "source group/role leakage")
        reserved.append(span)
        schedule = group["schedule"]
        require(isinstance(schedule, list) and len(schedule) == 3, "three native phases required")
        for row, phase in zip(schedule, ("high", "collapse", "recovery"), strict=True):
            require(
                isinstance(row, list)
                and len(row) == 3
                and finite(row[0])
                and 0 < row[0] <= 4
                and row[1] == phase
                and type(row[2]) is int
                and 1000 <= row[2] <= 6000,
                "invalid native capacity schedule",
            )
        orders = group["orders"]
        require(
            len(orders) == repeats
            and all(len(o) == len(conditions) and set(o) == set(conditions) for o in orders),
            "complete predeclared trial order required",
        )
    if stage == "test":
        lock = protocol.get("validation_lock", {})
        require(set(lock) == {"path", "sha256"}, "validation selection must be frozen before test")
    return protocol


def load_protocol(path, check_sources=True):
    path = Path(path)
    protocol = validate_protocol(read_json(path))
    if check_sources:
        require(
            protocol["source_sha256"] == source_identity(), "native implementation changed after plan freeze"
        )
    bundles = {}
    for key, entry in protocol["models"].items():
        model = Path(entry["path"])
        if not model.is_absolute():
            model = path.parent / model
        require(digest(model) == entry["sha256"], "native model changed after freeze")
        bundles[key] = read_json(model)
        validate_native_bundle(bundles[key])
        require(
            bundles[key]["risk_cutoff"] == 0.5 and bundles[key]["disagreement_cutoff"] == 0.2,
            "no native cutoff relaxation permitted",
        )
    return protocol, bundles
