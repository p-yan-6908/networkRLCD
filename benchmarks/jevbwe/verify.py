"""Read-only deterministic JevBWE replay; no fitting, collection or native claims.

Usage: uv run --frozen benchmarks/jevbwe/verify.py --run RUN --out NEW_RECEIPT.json
"""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from media_rl.jevbwe import RATIOS, JevBWE, ResidualModel, Sample, clipped_rate
from media_rl.jevbwe_experiment import (
    METHODS,
    ROLES,
    audit_study,
    collect_role,
    load_study,
    qualify_action_value,
)
from media_rl.networks import MLP


def compressed(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def verify(root):
    integrity = audit_study(root)
    config = load_study(root / "config.json")
    checkpoint = root / "training" / "model.json"
    original = checkpoint.read_bytes()
    bundle = json.loads(original)
    model = ResidualModel(bundle)
    rows_by_role = {}
    fitting_samples = 0
    for role in ROLES:
        cohorts, samples = collect_role(config, role)  # deterministic simulation replay, NOT new native data
        assert cohorts == compressed(root / "training" / f"{role}_cohorts.json.gz")
        assert samples == compressed(root / "training" / f"{role}_samples.json.gz")
        rows_by_role[role] = [r for r in cohorts if not r["censored"]]
        fitting_samples += len(samples)
    train = rows_by_role["train"]
    states = np.asarray([r["state"] for r in train])
    np.testing.assert_array_equal(states.mean(axis=0), bundle["mean"])
    np.testing.assert_array_equal(np.maximum(states.std(axis=0), 0.05), bundle["scale"])
    report = json.loads((root / "training" / "training_report.json").read_text())
    utility = qualify_action_value(
        rows_by_role["qualification"],
        model.utility,
        MLP.from_dict(bundle["blind_control_weights"]),
        bundle["mean"],
        bundle["scale"],
        bundle["reward_mean"],
        bundle["reward_scale"],
    )
    saved = bundle["delivered_qualification_weights"]
    delivered = qualify_action_value(
        rows_by_role["qualification"],
        MLP.from_dict(saved["conditional"]),
        MLP.from_dict(saved["blind"]),
        bundle["mean"],
        bundle["scale"],
        saved["mean"],
        saved["scale"],
        target="delivered_reward",
    )
    assert utility == report["qualification"]["utility"]
    assert delivered == report["qualification"]["delivered_only"]
    assert bundle["action_value_passed"] == (utility["passed"] and delivered["passed"])
    counts = Counter()
    for scenario in config.scenarios:
        for seed in config.test_seeds:
            for method in METHODS:
                policy = JevBWE(
                    model if method.startswith("jevbwe") else None,
                    config.residual,
                    ungated=method == "jevbwe_ungated",
                )
                last_change = 0
                rows = compressed(root / "evaluation" / f"{scenario}_{seed}_{method}.json.gz")
                assert len(rows) == config.steps
                for row in rows:
                    sample = Sample(**row["sample"])
                    decision = policy.observe(sample)
                    if method == "bwe_raw":
                        rate = clipped_rate(
                            1,
                            sample.bwe_bps,
                            min(config.residual.max_bps, RATIOS[-1] * sample.bwe_bps),
                            config.residual,
                        )
                        decision.update(
                            requested_bps=rate,
                            reason="raw_bwe",
                            effective_ratio=rate / sample.bwe_bps,
                            base_bps=sample.bwe_bps,
                            safe_bps=min(config.residual.max_bps, RATIOS[-1] * sample.bwe_bps),
                        )
                    assert decision == row["decision"]
                    rate = decision["requested_bps"]
                    assert 0 <= rate <= decision["safe_bps"] + 1e-6, (
                        method,
                        scenario,
                        seed,
                        sample.sample_ms,
                        rate,
                        decision["safe_bps"],
                    )
                    assert rate >= min(config.residual.min_bps, decision["safe_bps"]) - 1e-6
                    if row["changed"]:
                        if rate > sample.requested_bps + 1:
                            if method != "bwe_raw":
                                assert sample.sample_ms - last_change >= config.residual.up_dwell_ms
                            counts[f"{method}:increases"] += 1
                        else:
                            counts[f"{method}:decreases"] += 1
                        last_change = sample.sample_ms
                        policy.acknowledge(rate, sample.sample_ms)
                    if decision["learned_executed"]:
                        assert decision["reason"] in ("learned_residual", "ungated_ablation")
                        candidates = [
                            clipped_rate(r, decision["base_bps"], decision["safe_bps"], config.residual)
                            for r in RATIOS
                        ]
                        assert abs(rate - candidates[decision["proposal_index"]]) <= 1
                        assert sum(abs(v - rate) <= 1 for v in candidates) == 1
                        counts[f"{method}:learned_steps"] += 1
                    counts[f"{method}:rows"] += 1
    assert checkpoint.read_bytes() == original
    assert audit_study(root) == integrity
    evaluation = json.loads((root / "evaluation" / "evaluation_report.json").read_text())
    scenario_effects = {}
    for scenario in config.scenarios:
        values = {
            m: np.mean(
                [
                    r["utility"]
                    for r in evaluation["episodes"]
                    if r["scenario"] == scenario and r["method"] == m
                ]
            )
            for m in METHODS
        }
        scenario_effects[scenario] = {
            m: float(values["jevbwe"] - values[m]) for m in ("bwe_raw", "bwe_dwell")
        }
    return dict(
        synthetic_only=True,
        native_validation=False,
        promoted=False,
        artifact_integrity=integrity,
        fitting_samples_replayed=fitting_samples,
        factual_cohorts=sum(len(rows_by_role[r]) for r in ROLES),
        decision_checks=dict(counts),
        qualification=report["qualification"],
        scenario_utility_effects=scenario_effects,
        model_sha256=hashlib.sha256(original).hexdigest(),
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    receipt = verify(args.run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "fitting_samples_replayed",
                    "factual_cohorts",
                    "decision_checks",
                    "scenario_utility_effects",
                    "artifact_integrity",
                )
            },
            indent=2,
        )
    )
