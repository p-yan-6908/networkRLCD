import numpy as np
import pytest

from media_rl import native_action_atomic_diagnosis as original
from media_rl import native_action_atomic_diagnosis_v2 as v2
from media_rl import native_action_ordered_projection as ordered


def test_exact_duplicate_input_empirical_weighted_bound_not_population_noise():
    d = dict(
        targets=np.asarray([[0.1, 0], [0.3, 0], [0.8, 0]]),
        weight=np.asarray([1, 3, 2]),
        step=np.asarray([0, 0, 32]),
        film=np.asarray(["a", "a", "b"]),
        group=np.asarray(["g", "g", "h"]),
        cap=np.asarray([300000, 300000, 450000]),
    )
    r = v2.empirical_input_collisions(np.asarray([[0], [0], [1]]), d)
    assert r["duplicate_classes"] == 1 and r["duplicate_rows"] == 2 and r["unique_input_rows"] == 2
    assert r["empirical_any_deterministic_function_minimum_utility_SSE"] == pytest.approx(0.03)
    assert r["empirical_any_deterministic_function_minimum_utility_MSE"] == pytest.approx(0.005)
    assert r["not_population_irreducibility_or_cause_of_gate_failure"]


def test_actual_full_current_ordered_26_collision_pairs_are_same_initial_rows():
    with np.load("results/native-action-atomic-value-cv-v4/train_rows.npz", allow_pickle=False) as z:
        d = {k: z[k] for k in z.files}
    designs = [
        np.column_stack([d["state"], d["cap"]]),
        ordered.original.design(d["state"], d["cap"]),
        ordered.design(d["state"], d["cap"]),
    ]
    r = [v2.empirical_input_collisions(x, d) for x in designs]
    assert all(
        q["unique_input_rows"] == 254 and q["duplicate_classes"] == 26 and q["duplicate_rows"] == 52
        for q in r
    )
    assert all(q["class_membership"] == r[0]["class_membership"] for q in r)
    assert all(c["steps"] == [0] for c in r[0]["class_membership"])
    assert r[0]["empirical_any_deterministic_function_minimum_utility_MSE"] == pytest.approx(
        0.00006079824787893669
    )


def test_equal_history_alias_metadata_fixed_without_changing_other_fields(monkeypatch):
    monkeypatch.setattr(
        original,
        "alias_support",
        lambda *_: dict(
            alias_pairs=[
                dict(
                    full_history_arrays_identical=True,
                    same_cap_and_stratum_not_same_model_input=True,
                    observed_abs_utility_gap=0.1,
                ),
                dict(
                    full_history_arrays_identical=False,
                    same_cap_and_stratum_not_same_model_input=True,
                    observed_abs_utility_gap=0.2,
                ),
            ]
        ),
    )
    r = v2.alias_support(None, None, None)
    assert [p["same_cap_and_stratum_not_same_model_input"] for p in r["alias_pairs"]] == [False, True]
    assert [p["observed_abs_utility_gap"] for p in r["alias_pairs"]] == [0.1, 0.2]
    assert v2._BASE_DERIVE.__code__ is original.derive.__code__
    assert v2.diagnose.__code__ is original.diagnose.__code__ and v2.audit.__code__ is original.audit.__code__
