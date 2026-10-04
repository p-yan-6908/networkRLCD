"""Same exact train diagnosis, corrected alias identity metadata + empirical collisions."""

import argparse
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_atomic_diagnosis as original
from . import native_action_ordered_projection as ordered
from .native_protocol import digest, require

ABI = "native_atomic_train_mechanism_identity_collision_diagnosis_v2"
CONTRACT = {
    **original.CONTRACT,
    "abi": ABI,
    "diagnostics": [
        *original.CONTRACT["diagnostics"],
        "exact_full_current_ordered_input_collision_empirical_bounds",
    ],
    "empirical_collision_bound_not_population_irreducibility": True,
    "original_alias_identity_metadata_corrected_only": True,
}


def empirical_input_collisions(x, data):
    _, inverse, count = np.unique(x, axis=0, return_inverse=True, return_counts=True)
    classes = []
    sse = 0.0
    y = data["targets"][:, 0]
    w = data["weight"]
    for k, n in enumerate(count):
        if n < 2:
            continue
        i = np.flatnonzero(inverse == k)
        mean = np.average(y[i], weights=w[i])
        part = float(np.sum(w[i] * (y[i] - mean) ** 2))
        sse += part
        classes.append(
            dict(
                indices=i.tolist(),
                rows=int(n),
                requests=int(w[i].sum()),
                utility_range=[float(y[i].min()), float(y[i].max())],
                steps=sorted(set(data["step"][i].tolist())),
                films=sorted(set(data["film"][i].tolist())),
                groups=sorted(set(data["group"][i].tolist())),
                caps=sorted(set(data["cap"][i].tolist())),
                weighted_empirical_class_SSE=part,
                descriptive_label_group_mean_not_fitted_or_promotable_model=True,
            )
        )
    return dict(
        unique_input_rows=len(count),
        duplicate_classes=len(classes),
        duplicate_rows=sum(c["rows"] for c in classes),
        class_membership=classes,
        empirical_any_deterministic_function_minimum_utility_SSE=sse,
        empirical_any_deterministic_function_minimum_utility_MSE=sse / float(w.sum()),
        not_population_irreducibility_or_cause_of_gate_failure=True,
    )


def alias_support(data, oof, metadata):
    r = original.alias_support(data, oof, metadata)
    for p in r["alias_pairs"]:
        p["same_cap_and_stratum_not_same_model_input"] = not p["full_history_arrays_identical"]
    r["same_input_alias_flag_matches_actual_array_equality"] = True
    return r


_NS = {
    **original.__dict__,
    "__file__": __file__,
    "ABI": ABI,
    "CONTRACT": CONTRACT,
    "alias_support": alias_support,
}
_BASE_DERIVE = FunctionType(original.derive.__code__, _NS, "derive_identity_corrected_train_mechanisms")


def derive(cv):
    r = _BASE_DERIVE(cv)
    with np.load(Path(cv) / "train_rows.npz", allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files}
    full = empirical_input_collisions(np.column_stack([data["state"], data["cap"]]), data)
    compact = empirical_input_collisions(ordered.original.design(data["state"], data["cap"]), data)
    temporal = empirical_input_collisions(ordered.design(data["state"], data["cap"]), data)

    def memberships(obj):
        return sorted(c["indices"] for c in obj["class_membership"])

    require(
        memberships(full) == memberships(compact) == memberships(temporal),
        "current exact empirical collision memberships changed",
    )
    r.update(
        original_diagnosis_implementation_sha256=digest(original.__file__),
        original_numeric_gradient_contribution_noise_response_sampling_math_unmodified=True,
        alias_identity_boolean_corrected_for_actual_11_equal_histories=True,
        exact_input_collisions=dict(
            full_736_history_plus_cap=full,
            current_95_compact_proposal=compact,
            ordered_118_compact_proposal=temporal,
            current_dataset_projection_adds_no_exact_input_collisions=True,
            ordered_projection_does_not_resolve_actual_existing_collisions=True,
            no_cohort_excluded_or_label_eligibility_changed=True,
        ),
    )
    return r


_NS["derive"] = derive
diagnose = FunctionType(original.diagnose.__code__, _NS, "diagnose_exact_identity_collision_train")
audit = FunctionType(original.audit.__code__, _NS, "audit_exact_identity_collision_train")


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_atomic_diagnosis_v2")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("diagnose")
    d.add_argument("--cv", required=True)
    d.add_argument("--out", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--run", required=True)
    args = p.parse_args()
    print(
        json.dumps(diagnose(args.cv, args.out) if args.command == "diagnose" else audit(args.run), indent=2)
    )


if __name__ == "__main__":
    main()
