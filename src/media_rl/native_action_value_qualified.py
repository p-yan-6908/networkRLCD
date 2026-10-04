"""Model-bound, numerically reverified action-value qualification before actor init.

Opt-in only. Existing experiments/defaults remain unchanged. A passing predictive
check is necessary, not sufficient for causal gain, risk certification or SOTA.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from .native_action_learning import LEARNER
from .native_action_live_study import _candidate
from .native_action_policy import ActionPolicy
from .native_action_value_skill import CHECK_CONFIG, audit_value_skill, require_action_value_skill
from .native_protocol import digest, read_json, require
from .native_repair3_policy import INPUT_DIM
from .networks import MLP, sigmoid

QUALIFICATION_ABI = "native_action_value_qualified_policy_v1"


def audit_model_value_skill(model_directory, skill_run, *, expected_manifest_sha256=None):
    """Recompute held-out predictions/MSE from cached factual inputs and six controls.

    No fitting, raw capture replay, counterfactual labels or candidate inference.
    Negative results are valid complete audit evidence, not qualification.
    """
    directory, root = Path(model_directory).resolve(), Path(skill_run).resolve()
    if expected_manifest_sha256 is not None:
        require(
            isinstance(expected_manifest_sha256, str)
            and len(expected_manifest_sha256) == 64
            and all(c in "0123456789abcdef" for c in expected_manifest_sha256)
            and digest(root / "manifest.json") == expected_manifest_sha256,
            "frozen external value-skill manifest binding changed",
        )
    _candidate(dict(path=str(directory / "model.json"), sha256=digest(directory / "model.json")))
    audit_value_skill(root)
    report = read_json(root / "report.json")
    require(
        digest(directory / "model.json") == report["original_model_sha256"]
        and digest(directory / "training_report.json") == report["original_training_report_sha256"],
        "value skill is bound to a different candidate or original CV receipt",
    )
    original = read_json(directory / "training_report.json")
    with np.load(root / "train_rows.npz", allow_pickle=False) as arrays:
        state, target, weight = arrays["state"], arrays["targets"], arrays["weight"]
        group, cap = arrays["group"], arrays["cap"]
        unique = sorted(set(group.tolist()))
        require(
            state.shape == (report["rows"], INPUT_DIM)
            and target.shape == (report["rows"], 2)
            and weight.shape == cap.shape == group.shape == (report["rows"],)
            and np.isfinite(state).all()
            and np.isfinite(target).all()
            and ((target >= 0) & (target <= 1)).all()
            and (weight > 0).all()
            and np.issubdtype(weight.dtype, np.integer)
            and np.issubdtype(cap.dtype, np.integer)
            and ((cap >= 150000) & (cap <= 4000000)).all(),
            "invalid factual cached inputs/targets",
        )
        require(
            len(unique) == report["physical_groups"] == original["physical_groups"]["train"]
            and len(state) == original["rows"]["train"]
            and int(weight.sum()) == original["requests"]["train"]
            and len(set(zip(arrays["episode"].tolist(), arrays["step"].tolist(), strict=True))) == len(state),
            "cached factual scope or row/weight identity changed",
        )
        for fold, row in enumerate(report["folds"]):
            prior = original["training_cv"]["folds"][fold]
            held = unique[fold :: CHECK_CONFIG["cv_folds"]]
            fit_groups = sorted(set(unique) - set(held))
            require(
                row["held_out_groups"] == prior["held_out_groups"] == held
                and row["fit_groups"] == prior["fit_groups"] == fit_groups,
                "fold identity differs from original independent physical split",
            )
            mask = np.isin(group, held)
            x = np.column_stack([state[mask], np.zeros((int(mask.sum()), 3))])
            mean = state[~mask].mean(axis=0)
            scale = np.maximum(state[~mask].std(axis=0), LEARNER["state_scale_floor"])
            predictions = []
            for seed in CHECK_CONFIG["model_seeds"]:
                model = read_json(root / "models" / f"fold-{fold}-seed-{seed}.json")
                norm = model["normalization"]
                require(
                    model["model_abi"] == "native_action_blind_skill_control_v1"
                    and model["seed"] == seed
                    and model["updates"] == CHECK_CONFIG["cv_updates"]
                    and model["fit_groups"] == fit_groups
                    and model["held_out_groups"] == held
                    and norm["fitted_roles"] == ["train"]
                    and norm["fused_into_weights"] is True
                    and np.allclose(norm["mean"], mean, atol=1e-12, rtol=0)
                    and np.allclose(norm["scale"], scale, atol=1e-12, rtol=0),
                    "model normalization/group/seed leaked or changed",
                )
                w, b, v, c = [np.asarray(p, dtype=float) for p in model["weights"]]
                require(
                    b.ndim == 1
                    and 1 <= len(b) <= LEARNER["hidden"]
                    and w.shape == (INPUT_DIM + 3, len(b))
                    and v.shape == (len(b), 2)
                    and c.shape == (2,)
                    and all(np.isfinite(p).all() for p in (w, b, v, c))
                    and np.all(w[INPUT_DIM:] == 0),
                    "control weights malformed or action-dependent",
                )
                predictions.append(sigmoid(MLP.from_dict(model["weights"])(x)))
            prediction = np.mean(predictions, axis=0)
            mse = np.average((prediction - target[mask]) ** 2, axis=0, weights=weight[mask])
            gain = float((mse[0] - prior["utility_mse"]) / max(1e-12, float(mse[0])))
            require(
                row["conditional_utility_mse"] == prior["utility_mse"]
                and row["test_rows"] == int(mask.sum())
                and row["test_requests"] == int(weight[mask].sum())
                and np.isclose(row["state_only_utility_mse"], mse[0], atol=1e-12, rtol=0)
                and np.isclose(row["state_only_risk_brier"], mse[1], atol=1e-12, rtol=0)
                and np.isclose(row["action_conditioning_utility_skill"], gain, atol=1e-10, rtol=0)
                and row["passed"] is (gain >= CHECK_CONFIG["min_utility_skill"]),
                "held-out prediction/MSE/skill result mismatch",
            )
        same = int(np.sum(cap == np.rint(state[:, -23 + 7] * 4e6)))
        require(
            same == report["factual_action_equals_previous_own_cap_rows"]
            and np.isclose(
                same / len(state), report["factual_action_equals_own_fraction"], atol=1e-12, rtol=0
            ),
            "factual previous-cap/action-overlap count changed",
        )
    return report


def load_value_qualified_candidate(model_directory, skill_run, *, expected_manifest_sha256):
    require(expected_manifest_sha256 is not None, "external frozen skill receipt required for qualification")
    report = audit_model_value_skill(
        model_directory, skill_run, expected_manifest_sha256=expected_manifest_sha256
    )
    require_action_value_skill(report)
    path = Path(model_directory).resolve() / "model.json"
    return _candidate(dict(path=str(path), sha256=digest(path)))


class ValueQualifiedActionPolicy(ActionPolicy):
    def __init__(self, model_directory, skill_run, *, expected_manifest_sha256):
        # The skill guard runs before actor state/weights can be initialized.
        super().__init__(
            load_value_qualified_candidate(
                model_directory, skill_run, expected_manifest_sha256=expected_manifest_sha256
            )
        )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_value_qualified")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--skill-run", required=True)
    parser.add_argument("--expected-manifest-sha256", help="optional frozen receipt pin for read-only audit")
    args = parser.parse_args(argv)
    result = audit_model_value_skill(
        args.model_dir, args.skill_run, expected_manifest_sha256=args.expected_manifest_sha256
    )
    print(
        json.dumps(
            dict(
                qualification_abi=QUALIFICATION_ABI,
                read_only=True,
                numerically_recomputed_folds=len(result["folds"]),
                rows=result["rows"],
                candidate_value_qualified=result["passed"],
                native_deployment_qualified=False,
                SOTA_achieved=False,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
