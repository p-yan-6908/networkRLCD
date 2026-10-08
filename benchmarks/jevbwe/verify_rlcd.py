"""Read-only exact numeric RLCD refit/credit/control replay; no Laya inference.

The optional receipt must be outside the sealed run. Monotonic inference durations
are replayed from logs (not silently replaced by today's faster/slower hardware).
"""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

from media_rl.jevbwe_rlcd import (
    ROLES,
    NumericModel,
    calibrated_forecasts,
    fit_policy,
    load_config,
    split_seed,
)
from media_rl.jevbwe_rlcd_experiment import (
    arrays,
    audit,
    calibrate,
    choice_skill,
    collect,
    control_episode,
    inspect_data,
    promotion_panel,
    skill,
    sources,
    summarize,
)
from media_rl.networks import MLP


def compressed(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def verify(path):
    path = Path(path)
    checked = audit(path)
    cfg = load_config(path / "config.json")
    fitting, evaluation = path / "training", path / "evaluation"
    model = json.loads((fitting / "model.json").read_text())
    report = json.loads((fitting / "training_report.json").read_text())
    baseline_bytes = (fitting / "baseline_model.json").read_bytes()
    assert hashlib.sha256(baseline_bytes).hexdigest() == model["baseline_model_sha256"]
    assert model["baseline_bundle"] == json.loads(baseline_bytes)
    assert model["source_sha256"] == sources()
    assert model["fitting_hash"] == cfg.fitting_hash() and model["evaluation_hash"] == cfg.evaluation_hash()
    assert (evaluation / "model.json").read_bytes() == (fitting / "model.json").read_bytes()
    evidence = json.loads((evaluation / "evaluation_report.json").read_text())
    assert evidence["optional_laya"] == "not_run", (
        "Laya replay requires the actual separately pinned local backend"
    )
    cohorts, samples = 0, 0
    data = {}
    for role in ROLES:
        actual, raw = collect(cfg, role)
        expected = compressed(fitting / f"{role}_cohorts.json.gz")
        assert actual == expected
        assert raw == compressed(fitting / f"{role}_samples.json.gz")
        data[role] = [r for r in expected if not r["censored"]]
        cohorts += len(actual)
        samples += len(raw)
    all_data = {role: compressed(fitting / f"{role}_cohorts.json.gz") for role in ROLES}
    assert inspect_data(all_data) == report["data_support"]
    train_x = np.asarray([r["state"] for r in data["train"]])
    mean, scale = train_x.mean(axis=0), np.maximum(train_x.std(axis=0), 0.05)
    np.testing.assert_array_equal(mean, model["mean"])
    np.testing.assert_array_equal(scale, model["scale"])
    for target in ("reward", "delivered_reward"):
        x, a, y, mu = arrays(data["train"], target, cfg)
        nets, cals = {}, {}
        for name, blind in (("conditional", False), ("blind", True)):
            net = fit_policy(
                np.clip((x - mean) / scale, -12, 12),
                a,
                y,
                mu,
                cfg,
                split_seed(cfg.study.seed, "optimizer", 0),
                blind=blind,
            )
            for got, expected in zip(net.params, model["qualification_controls"][target][name]):
                np.testing.assert_allclose(got, expected, rtol=0, atol=1e-12)
            cals[name] = calibrate(net, data["calibration"], mean, scale, target, cfg, blind=blind)
            assert cals[name] == model["qualification_calibration"][target][name]
            nets[name] = net
        assert (
            skill(
                data["qualification"],
                nets["conditional"],
                nets["blind"],
                mean,
                scale,
                cals["conditional"],
                cals["blind"],
                target,
                cfg,
            )
            == report["qualification"][target]
        )
    _, probabilities = calibrated_forecasts(
        MLP.from_dict(model["policy_weights"]),
        [r["state"] for r in data["qualification"]],
        mean,
        scale,
        model["calibration"],
    )
    assert choice_skill(data["qualification"], probabilities, cfg) == report["qualification"]["choice"]
    assert model["policy_weights"] == model["qualification_controls"]["reward"]["conditional"]
    assert model["calibration"] == model["qualification_calibration"]["reward"]["conditional"]
    qualified = (
        report["data_support"]["no_outcome_dependent_censoring"]
        and all(v["passed"] for v in report["qualification"].values())
        and model["calibration"]["binary"]["method"] == "ipw_platt"
    )
    assert qualified == model["action_value_passed"] == report["supports_causal_discrimination"]
    decisions, positive_probability_rows, panel_cohorts = 0, 0, {"validation": [], "test": []}
    for episode in evidence["episodes"]:
        split, scenario, seed, method = [episode[k] for k in ("split", "scenario", "seed", "method")]
        name = f"{split}_{scenario}_{seed}_{method}"
        recorded = compressed(evaluation / f"{name}_decisions.json.gz")
        durations = [
            r["decision"]["inference_ms"]
            for r in recorded
            if r["decision"].get("action_probabilities") is not None
        ]
        clock = []
        for i, duration in enumerate(durations):
            clock.extend([float(i), float(i) + duration / 1000])
        with patch("media_rl.jevbwe_rlcd.time.perf_counter", side_effect=clock):
            fresh, outcomes = control_episode(
                cfg,
                NumericModel(copy.deepcopy(model)),
                model["baseline_bundle"],
                scenario,
                seed,
                split,
                method,
            )
        assert outcomes == compressed(evaluation / f"{name}_settled_cohorts.json.gz")
        for got, expected in zip(fresh, recorded):
            got["decision"].pop("inference_ms", None)
            expected["decision"].pop("inference_ms", None)
            p = got["decision"].get("action_probabilities")
            if p is not None:
                assert len(p) == 6 and np.isfinite(p).all() and abs(sum(p) - 1) < 1e-12
                positive_probability_rows += 1
        assert fresh == recorded
        assert summarize(fresh, outcomes, cfg) == {
            k: v for k, v in episode.items() if k not in ("split", "scenario", "seed", "method")
        }
        panel_cohorts[split].extend(outcomes)
        decisions += len(fresh)
    for split in panel_cohorts:
        panel = [e for e in evidence["episodes"] if e["split"] == split]
        assert (
            promotion_panel(panel, panel_cohorts[split], "numeric_rlcd", cfg)
            == evidence["panels"][split]["numeric_rlcd"]
        )
    eligible = qualified and all(evidence["panels"][s]["numeric_rlcd"]["eligible"] for s in panel_cohorts)
    assert eligible == evidence["promotion_eligible"]["numeric_rlcd"]
    assert model["promoted"] is False and evidence["promoted"] is False
    return dict(
        artifacts=checked["artifacts"],
        factual_cohorts=cohorts,
        fitting_samples=samples,
        replayed_decisions=decisions,
        six_action_probability_rows=positive_probability_rows,
        baseline_and_risk_unchanged=True,
        proper_reward_refit=True,
        promoted=False,
        causal_discrimination=qualified,
        promotion_eligible=eligible,
        laya="not_run",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = verify(args.run)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.receipt:
        if args.receipt.exists() or args.receipt.resolve().is_relative_to(args.run.resolve()):
            raise ValueError("receipt must be a new file outside the immutable run")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(text)
    print(text)
