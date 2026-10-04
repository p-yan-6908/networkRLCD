import numpy as np
import pytest

from media_rl import native_action_balanced_value_cv as original
from media_rl import native_action_balanced_value_cv_v3 as fixed


def test_metadata_adapter_unchanged_fit_predict_eval_bytecode_and_frozen_contract():
    assert fixed.FIT is original.FIT and fixed.PREDICT is original.PREDICT
    assert fixed.fit_cv.__code__ is original.fit_cv.__code__
    assert fixed.audit_cv.__code__ is original.audit_cv.__code__
    assert fixed.CONTRACT is original.CONTRACT and fixed.RECIPE is original.RECIPE
    assert fixed._NS["evaluate"] is original.evaluate
    assert fixed.MODEL_ABI == original.MODEL_ABI and fixed.ABI != original.ABI


def test_actual_metadata_width_bug_repaired_without_touching_any_numeric_array():
    old = np.asarray(["old-full-episode-id"])
    ids = ["x" * 108 + "a", "x" * 108 + "b"]
    data = dict(
        episode=np.asarray([*old, *ids], dtype="<U103"),
        state=np.zeros((3, 736)),
        targets=np.zeros((3, 2)),
        cap=np.full(3, 450000),
        weight=np.full(3, 12),
        group=np.asarray(["g0", "g1", "g1"]),
    )
    assert data["episode"][1] == data["episode"][2]
    result = fixed.repair_episode_metadata(data, old, ids)
    assert result["episode"].dtype == np.dtype("<U109")
    assert result["episode"].tolist() == [*old, *ids] and len(set(result["episode"])) == 3
    assert data["episode"].dtype == np.dtype("<U103")
    assert all(result[k] is data[k] for k in data if k != "episode")


@pytest.mark.parametrize("case", ["missing-id", "old-prefix"])
def test_lossless_identity_canonical_row_prefix_or_count_drift_rejected(case):
    old = np.asarray(["old"])
    data = dict(episode=np.asarray(["old", "new"]))
    if case == "missing-id":
        ids = []
    else:
        old = np.asarray(["other"])
        ids = ["new"]
    with pytest.raises(ValueError):
        fixed.repair_episode_metadata(data, old, ids)
