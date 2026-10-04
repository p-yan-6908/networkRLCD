"""Outcome-complete factual native replay. No receiver/trace oracle in model state."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from media_rl.native_observations import CAPS, verify_native_sender_evidence
from media_rl.native_quality import summarize_native_quality


def history_matrix(features, steps=4):
    a = np.asarray(features, dtype=float)
    if (
        a.ndim != 2
        or a.shape[1] != 16
        or not np.isfinite(a).all()
        or np.any(a < 0)
        or type(steps) is not int
        or steps < 1
    ):
        raise ValueError("finite normalized sixteen-feature sender history required")
    padded = np.vstack([np.zeros((steps - 1, 16)), a])
    return np.asarray([padded[i : i + steps].ravel() for i in range(len(a))])


def factual_transitions(sender, quality, episode_id, reward_config):
    decisions = sender["decisions"]
    states = history_matrix([r["observation"]["features"] for r in decisions])
    labels = defaultdict(list)
    rejected = dict(transition=0, unassociated=0)
    for label in quality["source_labels"]:
        if label["action_transition_inflight"]:
            rejected["transition"] += 1
            continue
        index = label["decision_id"]
        if index is None:
            rejected["unassociated"] += 1
            continue
        if type(index) is not int or not 0 <= index < len(decisions):
            raise ValueError("invalid causal source decision")
        row = decisions[index]
        born = label["capture_request_ms"]
        if not row["ack_ms"] <= born or (
            index + 1 < len(decisions) and born >= decisions[index + 1]["ack_ms"]
        ):
            raise ValueError("future/stale action label assignment")
        actual = row["actuation_readback"]
        if (
            label["encoder_cap_bps"] != actual["encoder_max_bitrate_bps"]
            or label["receiver_target_ms"] != 0
            or actual["receiver_jitter_buffer_target_ms"] != 0
        ):
            raise ValueError("source action and zero-target policy subset mismatch")
        if (
            type(label["identifiable_ontime"]) is not bool
            or not 0 <= label["ontime_sampled_psnr_contribution"] <= 100
        ):
            raise ValueError("invalid native finalized label")
        labels[index].append(label)
    transitions = []
    for i, row in enumerate(decisions):
        outcomes = labels[i]
        if not outcomes:
            continue  # No completed opportunities != zero-reward transition.
        action = CAPS.index(row["actuation_readback"]["encoder_max_bitrate_bps"])
        count = len(outcomes)
        miss = 1 - sum(x["identifiable_ontime"] for x in outcomes) / count
        utility = (
            sum(x["ontime_sampled_psnr_contribution"] for x in outcomes)
            / count
            / reward_config["on_time_sampled_psnr_divisor"]
        )
        reward = (
            utility - reward_config["miss_penalty"] * miss - reward_config["switch_penalty"] * row["changed"]
        )
        terminal = i + 1 >= len(decisions) or not labels[i + 1]
        transitions.append(
            dict(
                episode_id=episode_id,
                step_id=i,
                state=states[i],
                next_state=states[i + 1] if not terminal else np.zeros(64),
                action=action,
                reward=reward,
                terminal=terminal,
                miss_fraction=miss,
                label_count=count,
            )
        )
    return transitions, rejected


def n_step_arrays(transitions, gamma=0.97, n=3):
    """Stop on true terminal or missing decision, never bridge gaps or episodes."""
    if not 0 < gamma < 1 or type(n) is not int or n < 1:
        raise ValueError("valid native discount/horizon required")
    by_key = {(t["episode_id"], t["step_id"]): t for t in transitions}
    rows = []
    for first in transitions:
        total = 0.0
        discount = 1.0
        current = first
        next_state = np.zeros(64)
        bootstrap = 0.0
        for k in range(n):
            total += discount * current["reward"]
            next_state = current["next_state"]
            if current["terminal"]:
                break
            discount *= gamma
            if k == n - 1:
                bootstrap = discount
                break
            following = by_key.get((first["episode_id"], current["step_id"] + 1))
            if following is None:
                next_state = np.zeros(64)
                break
            current = following
        rows.append((first["state"], first["action"], total, next_state, bootstrap))
    return dict(
        states=np.asarray([r[0] for r in rows]),
        actions=np.asarray([r[1] for r in rows], dtype=int),
        returns=np.asarray([r[2] for r in rows]),
        next_states=np.asarray([r[3] for r in rows]),
        bootstrap_discounts=np.asarray([r[4] for r in rows]),
    )


def load_native_training_panel(root):
    root = Path(root)
    panel_bytes = (root / "panel.json").read_bytes()
    panel = json.loads(panel_bytes)
    manifest = json.loads((root / "manifest.json").read_text())

    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if (
        manifest["stage"] != "native_training_panel_verified"
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
    for episode in panel["episodes"]:
        if episode["role"] not in roles:
            raise ValueError("validation/test episode forbidden in fit data")
        path = root / episode["id"]
        seal = json.loads((path / "manifest.json").read_text())
        if (
            digest(path / "manifest.json") != manifest["episodes"][episode["id"]]
            or seal["stage"] != "native_exploration_episode_verified"
            or len(seal["artifacts_sha256"]) != 20
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
        verify_native_sender_evidence(sender)
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
        ),
    )
