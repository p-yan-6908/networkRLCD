"""Post-hoc simulator diagnosis: unchanged JevBWE weights versus fallback-only.

Reuses the already evaluated traces, never fits/tunes a model or claims fresh test
validation. Zero calibration support disables all neural execution; all physical,
BWE, fallback-headroom, emergency and dwell rules remain identical.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from media_rl.jevbwe import ResidualModel
from media_rl.jevbwe_experiment import audit_study, dump, dump_gzip, evaluate_episode, load_study, seal


def diagnose(root, out):
    before = audit_study(root)
    config = load_study(root / "config.json")
    checkpoint = root / "training" / "model.json"
    original = checkpoint.read_bytes()
    bundle = json.loads(original)
    assert bundle["action_value_passed"] is True
    ablated = copy.deepcopy(bundle)
    ablated["calibration_rows"] = [0] * 6
    ablated["calibration_episodes"] = [0] * 6
    assert ablated["utility_weights"] == bundle["utility_weights"]
    assert ablated["risk_weights"] == bundle["risk_weights"]
    model = ResidualModel(ablated)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(
        out / "plan.json",
        dict(
            posthoc=True,
            reused_evaluation_traces=True,
            no_fitting_or_tuning=True,
            ablation="zero calibration support; exact unchanged 0.85 BWE fallback",
            source_model_sha256=hashlib.sha256(original).hexdigest(),
            config=config.to_dict(),
        ),
    )
    reference = json.loads((root / "evaluation" / "evaluation_report.json").read_text())
    effects, per_scenario = [], {}
    for seed in config.test_seeds:
        seed_effects = []
        for scenario in config.scenarios:
            rows = evaluate_episode(config, model, scenario, seed, "jevbwe")
            assert not any(r["decision"]["learned_executed"] for r in rows)
            dump_gzip(out / f"{scenario}_{seed}_fallback_only.json.gz", rows)
            value = float(np.mean([r["utility"] for r in rows]))
            learned = next(
                r["utility"]
                for r in reference["episodes"]
                if r["seed"] == seed and r["scenario"] == scenario and r["method"] == "jevbwe"
            )
            effect = learned - value
            seed_effects.append(effect)
            per_scenario.setdefault(scenario, []).append(effect)
        effects.append(float(np.mean(seed_effects)))
    rng = np.random.default_rng(0)
    boots = np.mean(rng.choice(effects, (2000, len(effects)), replace=True), axis=1)
    report = dict(
        posthoc=True,
        synthetic_only=True,
        native_validation=False,
        promoted=False,
        reused_evaluation_traces=True,
        no_fitting_or_tuning=True,
        jevbwe_minus_fallback_only=float(np.mean(effects)),
        interval95=np.quantile(boots, [0.025, 0.975]).tolist(),
        per_scenario={k: float(np.mean(v)) for k, v in per_scenario.items()},
        neural_control_steps=0,
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    assert checkpoint.read_bytes() == original and audit_study(root) == before
    dump(out / "diagnosis.json", report)
    seal(out)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.run, args.out), indent=2))
