"""Strict fresh mixed-native fitting loader; previous panels are never imported."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from media_rl.native_dataset import factual_transitions
from media_rl.native_mixed_evidence import validate_mixed_behavior
from media_rl.native_quality import summarize_native_quality


def load_native_mixed_panel(root):
    root = Path(root)
    panel_bytes = (root / "panel.json").read_bytes()
    panel = json.loads(panel_bytes)
    manifest = json.loads((root / "manifest.json").read_text())

    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if (
        manifest["stage"] != "native_mixed_training_panel_verified"
        or panel["panel_abi"] != "native_mixed_training_panel_v3"
        or panel["candidate_selection_or_promotion_allowed"] is not False
        or hashlib.sha256(panel_bytes).hexdigest() != manifest["panel_sha256"]
    ):
        raise ValueError("verified frozen training panel required")
    for name, sha in manifest["artifacts_sha256"].items():
        if digest(root / name) != sha:
            raise ValueError("panel artifact changed")
    roles = dict(train=[], calibration=[])
    coverage = defaultdict(lambda: np.zeros(7, dtype=int))
    inputs = {}
    rejected = {}
    ranges = []
    old_ranges = []
    for prior_root in [
        "results/native-training-v1",
        "results/native-development-v1",
        "results/native-cadence-v2",
    ]:
        prior_root = Path(prior_root)
        prior_seal = json.loads((prior_root / "manifest.json").read_text())
        for old_id, old_sha in prior_seal["episodes"].items():
            old_child = prior_root / old_id
            if digest(old_child / "manifest.json") != old_sha:
                raise ValueError("prior source seal changed")
            old_manifest = json.loads((old_child / "manifest.json").read_text())
            raw_frames = (old_child / "frame_events.json").read_bytes()
            if (
                hashlib.sha256(raw_frames).hexdigest()
                != old_manifest["artifacts_sha256"]["frame_events.json"]
            ):
                raise ValueError("prior source frame group changed")
            old_frames = json.loads(raw_frames)
            old_ranges.append(
                (
                    old_frames["scene_seed"] + min(s["source_id"] for s in old_frames["sources"]),
                    old_frames["scene_seed"] + max(s["source_id"] for s in old_frames["sources"]),
                )
            )
    previous = [
        e
        for name in [
            "configs/native_training_v1.json",
            "configs/native_development_v1.json",
            "configs/native_cadence_v2.json",
        ]
        for e in json.loads(Path(name).read_text())["episodes"]
    ]
    if {e["scene_seed"] for e in panel["episodes"]} & {e["scene_seed"] for e in previous}:
        raise ValueError("old native source offset reused for fitting")
    if len({e["id"] for e in panel["episodes"]}) != len(panel["episodes"]):
        raise ValueError("duplicate fit episode ID")
    for episode in panel["episodes"]:
        if episode["role"] not in roles:
            raise ValueError("validation/test episode forbidden in fit data")
        path = root / episode["id"]
        seal = json.loads((path / "manifest.json").read_text())
        if (
            digest(path / "manifest.json") != manifest["episodes"][episode["id"]]
            or seal["stage"] != "native_mixed_episode_verified"
            or len(seal["artifacts_sha256"]) != 23
        ):
            raise ValueError("unverified exploration episode")
        for name, sha in seal["artifacts_sha256"].items():
            if digest(path / name) != sha:
                raise ValueError("native episode artifact changed")
        if (path / "panel_snapshot.json").read_bytes() != panel_bytes:
            raise ValueError("episode panel mismatch")
        sender = json.loads((path / "sender_observations.json").read_text())
        frames = json.loads((path / "frame_events.json").read_text())
        summary = json.loads((path / "summary.json").read_text())
        if (
            summary["collection_config"]["id"] != episode["id"]
            or summary["collection_config"]["role"] != episode["role"]
            or frames["scene_seed"] != episode["scene_seed"]
        ):
            raise ValueError("role/source mismatch")
        validate_mixed_behavior(sender, episode)
        span = (
            episode["scene_seed"] + min(s["source_id"] for s in frames["sources"]),
            episode["scene_seed"] + max(s["source_id"] for s in frames["sources"]),
        )
        if any(not (span[1] < old[0] or old[1] < span[0]) for old in [*old_ranges, *ranges]):
            raise ValueError("generated scene frame ranges overlap across new fit episodes")
        ranges.append(span)
        quality = summarize_native_quality(frames)
        if quality != json.loads((path / "quality_metrics.json").read_text()):
            raise ValueError("finalized native quality labels changed")
        rows, exclusions = factual_transitions(sender, quality, episode["id"], panel["reward"])
        roles[episode["role"]].extend(rows)
        rejected[episode["id"]] = exclusions
        for row in rows:
            coverage[episode["role"]][row["action"]] += row["label_count"]
        inputs[episode["id"]] = dict(role=episode["role"], manifest_sha256=digest(path / "manifest.json"))
    if any(np.any(coverage[role] == 0) for role in roles):
        raise ValueError("every cap needs factual outcome coverage in both fit roles")
    return (
        roles,
        panel,
        dict(
            inputs=inputs,
            source_label_coverage={k: v.tolist() for k, v in coverage.items()},
            excluded_labels=rejected,
            panel_sha256=manifest["panel_sha256"],
            test_used_for_training=False,
            previous_development_used_for_training=False,
            generated_scene_ranges=ranges,
            excluded_prior_generated_scene_ranges=old_ranges,
        ),
    )
