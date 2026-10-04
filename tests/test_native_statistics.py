from copy import deepcopy

import pytest
from native_study_helpers import plan, rows

from media_rl.native_statistics import analyze_native_rows, cluster_estimate, validation_selection


def test_intervals_use_independent_groups_not_repeated_frames(tmp_path):
    p, _, _ = plan(tmp_path, "validation")
    r = analyze_native_rows(rows(p), p)
    assert r["independent_groups"] == 8 and r["episodes"] == 48
    effect = r["candidate_minus_control"]["baseline"]["aggregate"]["utility"]
    assert effect["groups"] == 8 and effect["mean"] == 3
    assert effect["ci95"] == [3, 3]
    assert validation_selection(r, p)["selected"] == "candidate"
    assert not r["SOTA_achieved"]
    assert cluster_estimate([4])["ci95"] is None
    assert cluster_estimate([1, 2, 3]) == cluster_estimate([1, 2, 3])


def test_nominal_or_tail_harm_rejects_despite_aggregate_gain(tmp_path):
    p, _, _ = plan(tmp_path, "validation")
    data = rows(p)
    for row in data:
        if row["condition"] == "candidate" and row["family"] == "stable":
            row["utility"] = 17
            row["ontime_fraction"] = 0.5
    result = analyze_native_rows(data, p)
    assert any("stable" in x for x in validation_selection(result, p)["failures"])
    data = rows(p)
    data[0]["inference_p99_ms"] = 20
    assert "inference_tail_budget" in validation_selection(analyze_native_rows(data, p), p)["failures"]


def test_same_policy_outcome_noise_cannot_be_claimed_as_causal_gain(tmp_path):
    p, _, _ = plan(tmp_path)
    data = rows(p)
    for x in data:
        if x["condition"] == "rlcd-a":
            x["utility"] += 8
    r = analyze_native_rows(data, p)
    assert r["identical_policy"]["passed"] is False
    assert r["identical_policy"]["causal_policy_gain_inferred"] is False
    assert all(x["utility_span"] > 8 for x in r["identical_policy"]["group_spreads"])


def test_missing_duplicate_and_nonfinite_episode_metrics_reject(tmp_path):
    p, _, _ = plan(tmp_path)
    data = rows(p)
    for bad in [data[:-1], [*data, data[0]]]:
        with pytest.raises(ValueError, match="panel"):
            analyze_native_rows(bad, p)
    bad = deepcopy(data)
    bad[0]["utility"] = float("nan")
    with pytest.raises(ValueError):
        analyze_native_rows(bad, p)


def test_small_panel_never_promotes_even_with_large_point_gain(tmp_path):
    p, _, _ = plan(tmp_path, "validation", groups=1)
    selection = validation_selection(analyze_native_rows(rows(p), p), p)
    assert selection["selected"] == "baseline" and "insufficient_independent_groups" in selection["failures"]
