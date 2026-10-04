from copy import deepcopy

import pytest
from test_native_frame_metrics import evidence, observation

from media_rl.native_quality import QUALITY_PROTOCOL, compute_rgb_quality, summarize_native_quality


def quality():
    observed, reference = [1] * 2400, [0] * 2400
    return dict(**compute_rgb_quality(observed, reference), observed_rgb=observed, reference_rgb=reference)


def qualified():
    e = evidence()
    e["quality_protocol"] = dict(QUALITY_PROTOCOL)
    e["observations"] = (
        e["observations"][:1] + [observation(2, 251 + i) for i in range(30)] + e["observations"][1:]
    )
    for row in e["observations"]:
        row["quality"] = quality()
    return e


def test_known_rgb_psnr_and_exact_match_representation():
    assert compute_rgb_quality([0, 0, 0], [255, 255, 255])["psnr_db"] == 0
    assert compute_rgb_quality([0, 0, 0], [1, 1, 1])["psnr_db"] == pytest.approx(48.1308036086791)
    exact = compute_rgb_quality([1, 2, 3], [1, 2, 3])
    assert exact["psnr_db"] is None and exact["exact_match"]


def test_utility_is_eligible_opportunity_weighted_not_conditional_or_duplicate_inflated():
    s = summarize_native_quality(qualified())
    assert s["eligible_requests"] == 4 and s["identified_ontime"] == 1
    assert s["utility"] == pytest.approx(48.1308036086791 / 4)
    assert [x["source_id"] for x in s["source_labels"]] == [2, 3, 4, 5]
    assert sum(x["ontime_sampled_psnr_contribution"] > 0 for x in s["source_labels"]) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("rgb_mse", float("nan")),
        ("rgb_mse", False),
        ("rgb_mse", 3),
        ("psnr_db", float("inf")),
        ("psnr_db", 17),
        ("channels", 3),
    ],
)
def test_hash_valid_forged_quality_metadata_rejects(field, value):
    e = qualified()
    e["observations"][0]["quality"][field] = value
    with pytest.raises(ValueError):
        summarize_native_quality(e)


def test_raw_pair_and_sampling_protocol_corruption_rejects():
    e = qualified()
    e["observations"][0]["quality"]["reference_rgb"][0] = 200
    with pytest.raises(ValueError):
        summarize_native_quality(e)
    e = qualified()
    e["quality_protocol"]["grid_step"] = 32
    with pytest.raises(ValueError):
        summarize_native_quality(e)


def test_exact_match_cap_and_censoring_are_declared_not_infinity():
    e = qualified()
    q = e["observations"][0]["quality"]
    q["observed_rgb"] = list(q["reference_rgb"])
    q.update(compute_rgb_quality(q["observed_rgb"], q["reference_rgb"]))
    s = summarize_native_quality(e)
    assert s["utility"] == 25 and s["exact_match_psnr_cap_db"] == 100


def test_invalid_rgb_and_unqualified_markers_are_never_filled_safe():
    with pytest.raises(ValueError):
        compute_rgb_quality([True, 0, 0], [0, 0, 0])
    e = qualified()
    e["observations"][0]["luma"][23] = 245 - e["observations"][0]["luma"][23]
    with pytest.raises(ValueError):
        summarize_native_quality(e)


def test_quality_labels_are_not_sender_policy_fields():
    s = summarize_native_quality(deepcopy(qualified()))
    assert s["research_proxy_not_perceptual_QoE"] and s["physical_capture_or_scanout_verified"] is False
