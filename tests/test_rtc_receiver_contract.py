import json

import numpy as np
import pytest

from media_rl import rtc_receiver_contract as contract


def valid_observation():
    """Hand-computed two-packet aggregates, NOT an original packet/extractor fixture."""
    obs = np.zeros((15, 10))
    for k, duration in [(0, 60), (5, 600)]:
        obs[:, k] = [1200 * 8000 / duration, 2, 1200, 10, 10, 200, 210 / 205, 5, 20, 2, 0, 0, 0.5, 0.5, 0]
    return obs.reshape(150)


def test_schema_names_units_indices_windows_and_no_equivalence_claim():
    schema = contract.receiver_feature_schema()
    assert len(schema["features"]) == 15 and schema["feature_count"] == 150
    assert schema["windows_ms"] == [60] * 5 + [600] * 5
    assert schema["features"][0]["unit"] == "bps"
    assert schema["features"][11]["name"] == "lost_packets_conditional_mean"
    indices = [j for f in schema["features"] for j in f["short_indices"] + f["long_indices"]]
    assert indices == list(range(150))
    assert all(value is False for value in schema["claims"].values())
    assert any("paired RTP" in item for item in schema["unresolved"])
    schema["features"][0]["unit"] = "mutated"
    assert contract.receiver_feature_schema()["features"][0]["unit"] == "bps"


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
def test_known_math_passes_without_mutation_or_deployment_permission(dtype):
    obs = valid_observation().astype(dtype)
    before = obs.copy()
    result = contract.validate_receiver_observation(obs)
    assert result["passed"] and result["active_windows"] == 2
    assert np.array_equal(obs, before)
    assert not any(result["claims"].values())


@pytest.mark.parametrize(
    "obs",
    [
        [0] * 64,
        [0] * 16,
        [[0] * 150],
        [True] * 150,
        ["0"] * 150,
        [None] * 150,
        [float("nan")] * 150,
        [float("inf")] * 150,
        [1e300] * 150,
        {"true_capacity": 9},
    ],
)
def test_bad_shapes_types_nonfinite_and_model_overflow_reject(obs):
    with pytest.raises(ValueError):
        contract.check_receiver_observation(obs)


@pytest.mark.parametrize(
    "index,value,check",
    [
        (0, 160, "rate_byte_units"),  # same bytes / ms incorrectly labelled bps
        (10, 2.5, "packet_count_nonnegative_integer"),
        (10, -1, "packet_count_nonnegative_integer"),
        (20, 1200.5, "received_bytes_nonnegative_integer"),
        (20, -1, "received_bytes_nonnegative_integer"),
        (11, 0, "zero_packet_byte_accounting"),
        (30, 9, "delay_queue_minimum_identity"),
        (60, 10 / 205, "delay_ratio_interval_minimum_identity"),  # wrong normalized numerator
        (70, -200, "delay_ratio_interval_minimum_identity"),
        (50, 220, "minimum_seen_not_above_interval_minimum"),
        (80, -10, "packet_interarrival_time_nonnegative"),
        (90, -1, "packet_jitter_nonnegative"),
        (100, 1.1, "packet_loss_ratio_range"),
        (100, -0.1, "packet_loss_ratio_range"),
        (110, 2, "zero_loss_zero_conditional_mean"),  # (1 - loss) * received is NOT conditional losses
        (120, 0.5624007667367734, "video_packets_proportion_count_consistency"),
        (130, 1.1, "audio_packets_proportion_range"),
        (140, 0.00461964258628507, "probing_packets_proportion_count_consistency"),
    ],
)
def test_documented_aggregate_contradictions_are_not_shape_only_passes(index, value, check):
    obs = valid_observation()
    if index == 11:
        obs[21] = 100
        obs[1] = 100 * 8000 / 60
    obs[index] = value
    result = contract.check_receiver_observation(obs)
    assert not result["passed"]
    assert check in {x["check"] for x in result["violations"]}
    with pytest.raises(ValueError, match="contradiction"):
        contract.validate_receiver_observation(obs)


def test_positive_loss_requires_conditional_mean_of_missing_packet_events():
    obs = valid_observation()
    obs[100] = 1 / 3
    obs[110] = 1
    assert contract.validate_receiver_observation(obs)["passed"]
    obs[110] = 0.5
    failures = contract.check_receiver_observation(obs)["violations"]
    assert "conditional_loss_mean_at_least_one" in {x["check"] for x in failures}


def test_inactive_defaults_and_category_partition_are_not_invented():
    obs = np.zeros(150)
    obs[50] = 200  # unknown inactive minimum defaults are not an extraction certificate
    assert contract.validate_receiver_observation(obs)["passed"]
    obs = valid_observation()
    obs[120] = 0.5
    obs[130] = 0.5
    obs[140] = 0.5  # overlap classification must be resolved against original RTP implementation
    assert contract.validate_receiver_observation(obs)["passed"]
    assert not contract.validate_receiver_observation(obs)["claims"]["original_extractor_equivalence"]


def test_float32_proportions_have_count_based_rounding_allowance():
    obs = valid_observation()
    for k in (0, 5):
        obs[10 + k] = 3
        obs[120 + k] = 1 / 3
        obs[130 + k] = 2 / 3
    assert contract.validate_receiver_observation(obs.astype(np.float32))["passed"]
    obs[120] += 0.01
    assert not contract.check_receiver_observation(obs)["passed"]


@pytest.fixture
def trace(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            dict(observations=[valid_observation().tolist()], true_capacity="ignored", video_quality=None)
        )
    )
    return path


def test_trace_audit_both_precisions_labels_ignored_and_no_policy_claim(trace, tmp_path):
    out = tmp_path / "audit.json"
    report = contract.audit_receiver_trace(trace, out)
    before = out.read_bytes()
    assert report["documented_checks_pass"] and report["checked_float64_and_model_float32"]
    assert not report["original_controller_ready"] and not any(report["claims"].values())
    assert report["active_monitor_cells"] == 2
    assert report["source"]["model_fields"] == ["observations"]
    source = json.loads(trace.read_text())
    source["true_capacity"] = {"must-not-be-read": float("nan")}
    source["video_quality"] = [1e99]
    source["audio_quality"] = None
    trace.write_text(json.dumps(source))
    poisoned = contract.audit_receiver_trace(trace)
    assert (
        report["source"]["observations_float64_sha256"] == poisoned["source"]["observations_float64_sha256"]
    )
    assert report["source"]["sha256"] != poisoned["source"]["sha256"]
    with pytest.raises(ValueError, match="overwrite"):
        contract.audit_receiver_trace(trace, out)
    assert before == out.read_bytes()


def test_future_prefix_observations_not_consumed(trace):
    source = json.loads(trace.read_text())
    source["observations"].append(["invalid future"])
    trace.write_text(json.dumps(source))
    report = contract.audit_receiver_trace(trace, limit=1)
    assert report["source"]["audited_rows"] == 1 and report["source"]["total_rows"] == 2
    with pytest.raises(ValueError, match="row 1"):
        contract.audit_receiver_trace(trace, limit=2)


@pytest.mark.parametrize("limit", [0, -1, 4097, True, 1.0, None])
def test_bad_limits_reject(trace, limit):
    with pytest.raises(ValueError, match="limit"):
        contract.audit_receiver_trace(trace, limit=limit)


def test_bounded_trace_size_and_invalid_sources(trace, monkeypatch):
    monkeypatch.setattr(contract, "MAX_TRACE_BYTES", 5)
    with pytest.raises(ValueError, match="size"):
        contract.audit_receiver_trace(trace)
    monkeypatch.setattr(contract, "MAX_TRACE_BYTES", 10000)
    for source in [[], {}, {"observations": []}, {"observations": [[0] * 64]}]:
        trace.write_text(json.dumps(source))
        with pytest.raises(ValueError):
            contract.audit_receiver_trace(trace)


def test_temporal_diagnostic_does_not_certify_unknown_clocks_or_reject_declared_reset(trace):
    a = valid_observation()
    b = valid_observation()
    b[50] = 205
    b[30] = 5
    trace.write_text(json.dumps(dict(observations=[a.tolist(), b.tolist()])))
    report = contract.audit_receiver_trace(trace)
    assert report["diagnostics"]["current_short_minimum_delay_increases"] == 1
    assert not report["diagnostics"]["temporal_order_and_clock_resets_verified"]
    assert not report["original_controller_ready"]


def test_standalone_public_schema_and_audit_command(trace, tmp_path, capsys):
    schema = contract.main(["schema"])
    assert schema["feature_count"] == 150
    out = tmp_path / "cli.json"
    report = contract.main(["audit", "--trace", str(trace), "--out", str(out), "--limit", "1"])
    assert report["documented_checks_pass"] and out.is_file()
    assert contract.SCOPE in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        contract.main(["audit", "--trace", str(trace), "--out", str(out)])
    assert exc.value.code == 2
