"""Self-contained artificial native-study fixtures; never empirical performance evidence."""

import json
from copy import deepcopy

import numpy as np

from media_rl.native_learning import native_metadata
from media_rl.native_study import plan_native_study, trial_schedule
from media_rl.networks import MLP


def bundle():
    rng = np.random.default_rng(93)
    return dict(
        metadata=native_metadata(),
        q_weights=MLP(64, 8, 7, rng).to_dict(),
        risk_weights=[MLP(71, 8, 1, rng).to_dict() for _ in range(3)],
        platt=[1.0, 0.0],
        risk_cutoff=0.5,
        disagreement_cutoff=0.2,
        provenance=dict(generated_scene_ranges=[[0, 500]]),
    )


def plan(tmp_path, stage="repeatability", groups=2):
    model = tmp_path / "source.json"
    if not model.exists():
        model.write_text(json.dumps(bundle()))
    path = tmp_path / (stage + ".json")
    p = plan_native_study(
        model,
        path,
        stage="calibration" if stage == "calibration" else "repeatability",
        groups_per_family=groups,
    )
    if stage in ("validation", "test"):
        p["stage"] = stage
        p["models"]["candidate"] = deepcopy(p["models"]["source"])
        p["conditions"] = dict(
            baseline=dict(controller="rlcd", model="source"),
            candidate=dict(controller="rlcd", model="candidate"),
            bwe=dict(controller="bwe", model="source"),
        )
        for g in p["groups"]:
            g["orders"] = [["baseline", "candidate", "bwe"], ["bwe", "baseline", "candidate"]]
        p["repeatability_run"] = str(tmp_path / "controls")
        if stage == "test":
            p["validation_lock"] = dict(path=str(tmp_path / "selection.json"), sha256="a" * 64)
    return p, path, model


def rows(p):
    result = []
    for trial in trial_schedule(p):
        c = trial["condition"]
        utility = {"rlcd-a": 20, "rlcd-b": 20, "bwe": 18, "baseline": 19, "candidate": 22, "source": 20}[c]
        ontime = 0.9 if c == "candidate" else 0.8
        result.append(
            dict(
                **trial,
                utility=utility + trial["repetition"] * 0.01,
                ontime_fraction=ontime,
                inference_p99_ms=1.0,
                signals=dict(bwe_mbps=2.0, media_rtt_ms=50.0),
                phases={
                    phase: dict(utility=utility, ontime_fraction=ontime)
                    for phase in ("high", "collapse", "recovery")
                },
            )
        )
    return result
