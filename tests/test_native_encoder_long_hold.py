import copy
from pathlib import Path

import pytest

from media_rl import native_action_excitation as base
from media_rl import native_encoder_long_hold as lag
from media_rl import native_encoder_response as encoder


def synthetic():
    decisions = []
    for i in range(17):
        cap = lag.hold_cap("random-hold-a", i)
        previous = 300000 if i == 0 else lag.hold_cap("random-hold-a", i - 1)
        raw = dict(
            stream_key="tx:7",
            encoder_cap_bps=previous,
            bytes_sent=i * 1000,
            frames_encoded=i * 3,
            total_encode_s=i * 0.01,
        )
        obs = dict(sample_ms=i * 100, raw_source=raw)
        values = {
            k: dict(status="present", value=0 if k in encoder.NUMERIC_FIELDS else "none")
            for k in encoder.FIELDS
        }
        for key, value in dict(
            targetBitrate=previous,
            qpSum=i * 150,
            framesEncoded=i * 3,
            bytesSent=i * 1000,
            totalEncodeTime=i * 0.01,
            frameWidth=640,
            frameHeight=360,
        ).items():
            values[key]["value"] = value
        sidecar = dict(
            abi=encoder.ABI,
            used_by_controller=False,
            stream_key="tx:7",
            stats_id="tx",
            ssrc="7",
            codec_id="codec",
            mime_type="video/VP8",
            stats_timestamp_ms=10000 + i * 100,
            sample_ms=i * 100,
            time_origin_epoch_ms=100000,
            capture_cost_ms=0,
            fields=values,
        )
        decisions.append(
            dict(
                step_id=i,
                observation=obs,
                encoder_response=sidecar,
                ack_ms=i * 100 + 5,
                actuation_readback=dict(encoder_max_bitrate_bps=cap),
                proposed_action=dict(encoder_max_bitrate_bps=cap),
            )
        )
    labels = [
        dict(
            source_id=j,
            encoder_cap_bps=450000,
            decision_id=int(t // 100),
            capture_request_ms=t,
            action_transition_inflight=False,
            identifiable_ontime=j != 0,
            ontime_sampled_psnr_contribution=0 if j == 0 else 80,
        )
        for j, t in enumerate((250, 350, 650, 750, 1050, 1150))
    ]
    return (
        dict(decisions=decisions, learned_policy=False, measurement_cutoff_ms=1700),
        dict(time_origin_epoch_ms=100000),
        labels,
    )


def test_frozen_sequence_aliases_safe_support_not_oracle():
    for step in range(400):
        assert lag.hold_cap("random-hold-a", step, 123, [999]) == lag.hold_cap(
            "random-hold-b", step, 999, [-999]
        )
        assert lag.hold_cap("random-hold-a", step) in (300000, 450000, 900000)
        assert lag.hold_cap("fixed450", step) == 450000
    assert lag.hold_cap("random-hold-a", 15) == 450000 and lag.hold_cap("random-hold-a", 16) == 300000
    assert lag.GEOMETRY["bands_after_ack_ms"] == [[200, 600], [600, 1000], [1000, 1400]]
    assert lag.RAW_AUDIT.__code__ is base._RAW_AUDIT.__code__
    assert lag.RAW_AUDIT.__globals__["exploration_cap"] is lag.hold_cap


@pytest.mark.parametrize(
    "behavior,step", [("rlcd", 0), ("random-hold-a", True), ("fixed450", -1), ("random-hold-a", 0.5)]
)
def test_invalid_control(behavior, step):
    with pytest.raises(ValueError):
        lag.hold_cap(behavior, step)


def test_projection_is_only_declared_control_and_routes():
    old = Path("benchmarks/native_rtc/encoder_response_episode.mjs").read_text()
    new = lag.project_long_collector(old)
    actor = "const policyInput={observation_abi:observation.observation_abi,feature_names:observation.feature_names,features:observation.features};"
    assert (
        old.count(actor) == new.count(actor) == 1
        and "holdProbeCap(nativeConfig.behavior,decisions.length)" in new
    )
    with pytest.raises(ValueError):
        lag.project_long_collector(new)


def test_bands_ack_whole_intervals_misses_and_no_mutation():
    sender, frames, labels = synthetic()
    before = copy.deepcopy((sender, frames, labels))
    result = lag.summarize_response(sender, frames, labels, "random-hold-a")
    bands = result["epochs"][0]["bands"]
    assert [b["band"] for b in bands] == [[200, 600], [600, 1000], [1000, 1400]]
    assert bands[0]["utility"] == 0.4 and bands[0]["miss"] == 0.5 and bands[0]["requests"] == 2
    assert all(b["frame_weighted_mean_vp8_qp"] == 50 for b in bands)
    assert (
        result["total_band_requests"] == 6
        and not result["causal_quality_effect_proven"]
        and before == (sender, frames, labels)
    )
    assert result["dropped_bands"][-1]["reason"] == "future_action_or_cutoff_before_last_deadline"
    assert result["epochs"][0]["sampled_directional_target_latency_ms"] == 95


def test_censored_or_already_met_is_not_zero_latency():
    sender, frames, labels = synthetic()
    for r in sender["decisions"][:16]:
        r["encoder_response"]["fields"]["targetBitrate"]["value"] = 100000
    event = lag.summarize_response(sender, frames, labels, "random-hold-a")["epochs"][0]
    assert event["target_latency_censored"] and event["sampled_directional_target_latency_ms"] is None
    sender["decisions"][0]["encoder_response"]["fields"]["targetBitrate"]["value"] = 450000
    event = lag.summarize_response(sender, frames, labels, "random-hold-a")["epochs"][0]
    assert (
        event["threshold_already_met_before_ack"] and event["sampled_directional_target_latency_ms"] is None
    )


@pytest.mark.parametrize("kind", ["duplicate", "cap", "decision", "pre-ack", "utility", "readback", "clock"])
def test_invalid_attribution_and_horizon(kind):
    sender, frames, labels = synthetic()
    if kind == "duplicate":
        labels.append(copy.deepcopy(labels[0]))
    elif kind == "cap":
        labels[0]["encoder_cap_bps"] = 900000
    elif kind == "decision":
        labels[0]["decision_id"] = 99
    elif kind == "pre-ack":
        labels[0]["decision_id"] = 3
    elif kind == "utility":
        labels[0]["ontime_sampled_psnr_contribution"] = 101
    elif kind == "readback":
        sender["decisions"][3]["actuation_readback"]["encoder_max_bitrate_bps"] = 300000
    else:
        sender["decisions"][0]["ack_ms"] = -1
    with pytest.raises(ValueError):
        lag.summarize_response(sender, frames, labels, "random-hold-a")


def test_future_deadline_inflight_and_zero_frames_are_not_qualified():
    sender, frames, labels = synthetic()
    sender["measurement_cutoff_ms"] = 1500
    sender["decisions"] = sender["decisions"][:16]
    labels[0]["action_transition_inflight"] = True
    result = lag.summarize_response(sender, frames, labels, "random-hold-a")
    assert (
        len(result["epochs"][0]["bands"]) == 2
        and result["epochs"][0]["bands"][0]["inflight_requests_excluded"] == 1
    )
    assert result["epochs"][0]["bands"][0]["utility"] == 0.8
    sender, frames, labels = synthetic()
    for r in sender["decisions"]:
        r["observation"]["raw_source"]["frames_encoded"] = 0
        r["encoder_response"]["fields"]["framesEncoded"]["value"] = 0
    assert all(
        b["frame_weighted_mean_vp8_qp"] is None
        for b in lag.summarize_response(sender, frames, labels, "random-hold-a")["epochs"][0]["bands"]
    )
