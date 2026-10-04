"""Pure response diagnostic guards; fixtures are never native benefit evidence."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "hold_response",
    Path(__file__).resolve().parents[1] / "results/jobs/native_action_hold_response_diagnosis.py",
)
if SPEC is None or SPEC.loader is None or not Path(SPEC.origin or "").is_file():
    pytest.skip("Requires a local results/jobs helper omitted from the public source repo.", allow_module_level=True)
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)


def records():
    return [
        dict(
            observation=dict(
                sample_ms=t,
                raw_source=dict(
                    stream_key="sender",
                    encoder_cap_bps=300000,
                    bytes_sent=b,
                    frames_encoded=f,
                    total_encode_s=e,
                    packets_sent=f,
                    total_packet_send_delay_s=f * 0.001,
                ),
            )
        )
        for t, b, f, e in (
            (950, 0, 0, 0),
            (1050, 200, 1, 0.001),
            (1150, 400, 3, 0.003),
            (1250, 700, 7, 0.007),
            (1450, 9999, 99, 0.099),
        )
    ]


def cohort():
    return dict(window_start_ms=1000, window_end_ms=1400, cap=300000)


def test_entire_intervals_only_never_interpolate_across_ack_or_window_end():
    r = D.window_stats(records(), cohort())
    assert r["payload_send_mbps"] == pytest.approx(0.02)
    assert r["encoder_fps"] == pytest.approx(30)
    assert r["encode_ms_per_frame"] == pytest.approx(1)
    assert r["payload_observed_ms"] == 200 and r["counters"]["payload_intervals"] == 2
    assert not r["encoder_target_bitrate_or_qp_observed"]


def test_counter_reset_does_not_become_a_negative_or_fabricated_rate():
    rows = records()
    rows[1]["observation"]["raw_source"]["bytes_sent"] = 500
    r = D.window_stats(rows, cohort())
    assert r["payload_send_mbps"] == pytest.approx(0.024)
    assert r["payload_observed_ms"] == 100 and r["counters"]["missing_or_reset_bytes_sent"] == 1


@pytest.mark.parametrize(
    "field,value,reason",
    [("stream_key", "replacement", "stream_reset"), ("encoder_cap_bps", 900000, "cap_mismatch")],
)
def test_changed_stream_or_treatment_cannot_add_response_intervals(field, value, reason):
    rows = records()
    rows[2]["observation"]["raw_source"][field] = value
    r = D.window_stats(rows, cohort())
    assert r["payload_send_mbps"] is None and r["payload_observed_ms"] == 0
    assert r["counters"][reason] == 2


def test_missing_encoder_counter_is_not_imputed_from_payload_rate():
    rows = records()
    for row in rows:
        row["observation"]["raw_source"]["frames_encoded"] = None
    r = D.window_stats(rows, cohort())
    assert r["payload_send_mbps"] == pytest.approx(0.02) and r["encoder_fps"] is None
    assert r["encode_ms_per_frame"] is None and r["counters"]["missing_or_reset_frames_encoded"] == 2


def test_zero_encoded_frames_is_a_real_zero_fps_not_missing():
    rows = records()
    for row in rows:
        row["observation"]["raw_source"].update(frames_encoded=1, total_encode_s=0.001)
    r = D.window_stats(rows, cohort())
    assert r["encoder_fps"] == 0 and r["encode_ms_per_frame"] is None


@pytest.mark.parametrize("replacement", [950, 1050, float("nan"), True])
def test_invalid_or_nonmonotonic_samples_fail_closed(replacement):
    rows = records()
    rows[2]["observation"]["sample_ms"] = replacement
    with pytest.raises(ValueError):
        D.window_stats(rows, cohort())


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_start_ms", -1),
        ("window_end_ms", 1000),
        ("window_start_ms", float("nan")),
        ("cap", True),
        ("cap", 0),
    ],
)
def test_invalid_credit_boundary_or_treatment_fails_closed(field, value):
    with pytest.raises(ValueError):
        D.window_stats(records(), dict(cohort(), **{field: value}))


def test_error_decomposition_identifies_bias_without_refitting_or_promoting():
    r = D.prediction_metrics(D.np.asarray([0.5, 0.5]), D.np.asarray([0.4, 0.4]), D.np.asarray([1, 9]))
    assert r["mse"] == pytest.approx(0.01) and r["squared_mean_bias_fraction"] == pytest.approx(1)
    assert r["target_variance"] == 0 and r["signed_mean_bias"] == pytest.approx(0.1)


def test_payload_and_utility_averages_use_their_distinct_observed_denominators():
    rows = [
        dict(
            weight=w,
            utility=u,
            miss=0,
            payload_send_mbps=p,
            payload_observed_ms=dt,
            encoder_fps=0,
            encode_observed_ms=dt,
        )
        for w, u, p, dt in ((1, 1, 0.1, 100), (9, 0, 0.3, 300))
    ]
    r = D.aggregate(rows)
    assert r["utility"] == pytest.approx(0.1) and r["payload_send_mbps"] == pytest.approx(0.25)
    assert r["encoder_fps"] == 0 and r["requests"] == 10
