"""Portable unit tests use synthetic graphs; the real released models are probed separately."""

import hashlib
import json
import sys
from dataclasses import replace
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from media_rl import published_rtc_peer as peer
from media_rl.cli import main


@pytest.fixture
def fake(tmp_path, monkeypatch):
    data = b"unit-test-graph"
    checkpoint = tmp_path / "test.onnx"
    checkpoint.write_bytes(data)
    spec = peer.PeerSpec(
        "test",
        "tests/fixture",
        "a" * 40,
        "fixture.onnx",
        hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest(),
        hashlib.sha256(data).hexdigest(),
        len(data),
        "https://example.invalid/paper",
    )
    monkeypatch.setattr(peer, "PEERS", MappingProxyType({"test": spec}))
    sessions = []

    class Session:
        def __init__(self, verified, options, providers):
            assert verified == data
            assert options.intra_op_num_threads == options.inter_op_num_threads == 1
            assert options.execution_mode == "sequential"
            assert providers == ["CPUExecutionProvider"]
            self.feeds = []
            self.bad = None
            sessions.append(self)

        def get_inputs(self):
            return [
                SimpleNamespace(name=name, shape=list(shape), type="tensor(float)")
                for name, shape in peer.INPUTS
            ]

        def get_outputs(self):
            return [
                SimpleNamespace(name=name, shape=list(shape), type="tensor(float)")
                for name, shape in peer.OUTPUTS
            ]

        def get_providers(self):
            return ["CPUExecutionProvider"]

        def run(self, names, feed):
            assert names is None
            assert set(feed) == {"obs", "hidden_states", "cell_states"}
            assert all(x.dtype == np.float32 for x in feed.values())
            self.feeds.append({k: v.copy() for k, v in feed.items()})
            bandwidth = float(feed["obs"].sum() + feed["hidden_states"][0, 0] + 3)
            outputs = [
                np.array([[[bandwidth, 0.25]]], dtype=np.float32),
                feed["hidden_states"] + 1,
                feed["cell_states"] + 2,
            ]
            if self.bad is not None:
                return self.bad(outputs)
            return outputs

    runtime = SimpleNamespace(
        __version__="unit-test",
        SessionOptions=SimpleNamespace,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        InferenceSession=Session,
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", runtime)
    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps(
            dict(observations=[[1.0] * 150, [2.0] * 150], true_capacity=[1e99], video_quality="NOT AN INPUT")
        )
    )
    return SimpleNamespace(
        checkpoint=checkpoint,
        trace=trace,
        sessions=sessions,
        out=tmp_path / "replay.json",
        spec=spec,
        runtime=runtime,
    )


def test_genuine_public_registrations_do_not_import_optional_runtime(monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    records = peer.list_published_peers()
    assert {x["peer"] for x in records} == {"schaferct-mmsys2024", "mmsys2024-baseline"}
    assert next(x for x in records if x["peer"].startswith("schaferct"))["size_bytes"] == 4639039
    assert all(len(x["sha256"]) == 64 and len(x["commit"]) == 40 for x in records)
    records[0]["sha256"] = "mutated"
    assert peer.list_published_peers()[0]["sha256"] != "mutated"


def test_hash_check_precedes_optional_import_and_loads_verified_bytes(fake, monkeypatch):
    fake.checkpoint.write_bytes(b"broken")
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    with pytest.raises(ValueError, match="hash/size"):
        peer.PublishedRtcPeer("test", fake.checkpoint)
    assert not fake.sessions


def test_blob_identity_and_unknown_peer_reject(fake, monkeypatch):
    monkeypatch.setattr(peer, "PEERS", {"test": replace(fake.spec, git_blob_sha1="0" * 40)})
    with pytest.raises(ValueError, match="hash/size"):
        peer.PublishedRtcPeer("test", fake.checkpoint)
    with pytest.raises(ValueError, match="Unknown"):
        peer.PublishedRtcPeer("other", fake.checkpoint)


def test_optional_install_error_is_actionable(fake, monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    with pytest.raises(ValueError, match=r"\[rtc-peers\]"):
        peer.PublishedRtcPeer("test", fake.checkpoint)


def test_exact_channel_units_state_carry_reset_and_independent_peers(fake):
    a = peer.PublishedRtcPeer("test", fake.checkpoint)
    b = peer.PublishedRtcPeer("test", fake.checkpoint)
    obs = np.ones(150)
    assert a.act(obs)["bandwidth_bps"] == 153
    assert a.act(obs)["bandwidth_bps"] == 154
    assert b.act(obs)["bandwidth_bps"] == 153
    assert np.array_equal(obs, np.ones(150))
    assert a.act(obs)["auxiliary_output"] == 0.25
    a.reset()
    assert a.act(obs)["bandwidth_bps"] == 153
    assert a.hidden.tolist() == [[1]] and a.cell.tolist() == [[2]]


@pytest.mark.parametrize(
    "obs",
    [
        [0] * 64,
        [0] * 16,
        [[0] * 150],
        [True] * 150,
        ["1"] * 150,
        [None] * 150,
        [float("nan")] * 150,
        [float("inf")] * 150,
        [1e300] * 150,
        {"true_capacity": 5},
    ],
)
def test_native_projection_or_nonphysical_observations_never_reach_graph(fake, obs):
    estimator = peer.PublishedRtcPeer("test", fake.checkpoint)
    with pytest.raises(ValueError):
        estimator.act(obs)
    assert not fake.sessions[0].feeds
    assert not estimator.hidden.any()


@pytest.mark.parametrize("target", ["inputs", "outputs", "provider", "dtype"])
def test_wrong_graph_abi_and_provider_reject(fake, monkeypatch, target):
    session_class = fake.runtime.InferenceSession
    if target == "provider":
        monkeypatch.setattr(session_class, "get_providers", lambda self: ["CPUExecutionProvider", "CUDA"])
    else:
        name = "get_inputs" if target == "inputs" else "get_outputs"
        original = getattr(session_class, name)

        def malformed(self):
            nodes = original(self)
            if target == "dtype":
                nodes[0].type = "tensor(double)"
            else:
                nodes[0].shape[-1] += 1
            return nodes

        monkeypatch.setattr(session_class, name, malformed)
    with pytest.raises(ValueError, match="ABI|CPU"):
        peer.PublishedRtcPeer("test", fake.checkpoint)


@pytest.mark.parametrize(
    "bad",
    [
        lambda xs: xs[:2],
        lambda xs: [np.zeros((1, 1, 1)), *xs[1:]],
        lambda xs: [np.full((1, 1, 2), np.nan), *xs[1:]],
        lambda xs: [np.array([[[-1, 0.1]]]), *xs[1:]],
        lambda xs: [xs[0], np.zeros((1, 2)), xs[2]],
    ],
)
def test_bad_outputs_do_not_commit_estimator_state(fake, bad):
    estimator = peer.PublishedRtcPeer("test", fake.checkpoint)
    fake.sessions[0].bad = bad
    with pytest.raises(ValueError):
        estimator.act([0.0] * 150)
    assert not estimator.hidden.any() and not estimator.cell.any()


def test_labels_are_ignored_and_prefix_is_bounded(fake):
    first = peer.replay_published_peer("test", fake.checkpoint, fake.trace, limit=1)
    fake.trace.write_text(
        json.dumps(
            dict(
                observations=[[1.0] * 150, ["invalid future"]],
                true_capacity={"malicious": float("nan")},
                video_quality=[1e90],
                audio_quality=None,
            )
        )
    )
    second = peer.replay_published_peer("test", fake.checkpoint, fake.trace, limit=1)
    assert first["prediction_float32_sha256"] == second["prediction_float32_sha256"]
    assert first["trace"]["sha256"] != second["trace"]["sha256"]
    assert second["trace"]["model_fields"] == ["observations"]
    assert second["trace"]["replayed_rows"] == 1 and second["trace"]["total_rows"] == 2
    assert second["claims"] == dict(closed_loop=False, qoe_comparison=False, sota=False)
    assert second["auxiliary_is_calibrated_risk"] is False
    assert not second["latency"]["intel_challenge_budget_certified"]


@pytest.mark.parametrize("limit", [0, -1, 4097, 1.0, True, None])
def test_invalid_limits_reject_before_inference(fake, limit):
    with pytest.raises(ValueError, match="limit"):
        peer.replay_published_peer("test", fake.checkpoint, fake.trace, limit=limit)
    assert not fake.sessions


def test_bounded_trace_size_and_malformed_observations(fake, monkeypatch):
    monkeypatch.setattr(peer, "MAX_TRACE_BYTES", 5)
    with pytest.raises(ValueError, match="size"):
        peer.replay_published_peer("test", fake.checkpoint, fake.trace)
    monkeypatch.setattr(peer, "MAX_TRACE_BYTES", 100)
    for source in ([], {}, {"observations": []}, {"observations": [[0] * 64]}):
        fake.trace.write_text(json.dumps(source))
        with pytest.raises(ValueError):
            peer.replay_published_peer("test", fake.checkpoint, fake.trace)


def test_complete_read_only_audit_and_no_overwrite(fake):
    peer.replay_published_peer("test", fake.checkpoint, fake.trace, fake.out, limit=2)
    before = fake.out.read_bytes()
    audit = peer.audit_published_peer_replay(fake.out, fake.checkpoint, fake.trace)
    assert audit["exact_predictions"] and audit["audited_rows"] == 2
    assert not audit["timing_truth_verified"] and fake.out.read_bytes() == before
    with pytest.raises(ValueError, match="overwrite"):
        peer.replay_published_peer("test", fake.checkpoint, fake.trace, fake.out)
    assert fake.out.read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x.update(scope="closed_loop"),
        lambda x: x["claims"].update(sota=True),
        lambda x: x.update(auxiliary_is_calibrated_risk=True),
        lambda x: x["rows"][0].update(bandwidth_bps=1),
        lambda x: x["rows"][0].update(auxiliary_output=0.7),
        lambda x: x["rows"].reverse(),
        lambda x: x["rows"].pop(),
        lambda x: x["trace"].update(model_fields=["true_capacity"]),
        lambda x: x["latency"].update(p99_ms=999),
        lambda x: x["rows"][0].update(act_latency_ms=-1),
        lambda x: x["runtime"].update(provider="CUDA"),
        lambda x: x.update(implementation_sha256="0" * 64),
        lambda x: x.update(peer=None),
        lambda x: x["rows"].__setitem__(0, None),
    ],
)
def test_saved_scope_input_prediction_timing_and_manifest_forgery_reject(fake, mutation):
    report = peer.replay_published_peer("test", fake.checkpoint, fake.trace, limit=2)
    mutation(report)
    fake.out.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        peer.audit_published_peer_replay(fake.out, fake.checkpoint, fake.trace)


def test_cli_list_inspect_replay_and_audit_are_public(fake, capsys):
    listed = main(["rtc-peer-list"])
    assert listed[0]["peer"] == "test"
    result = main(["rtc-peer-inspect", "--peer", "test", "--checkpoint", str(fake.checkpoint)])
    assert result["inputs"] == peer.INPUTS and result["bandwidth_channel"] == [0, 0, 0]
    main(
        [
            "rtc-peer-replay",
            "--peer",
            "test",
            "--checkpoint",
            str(fake.checkpoint),
            "--trace",
            str(fake.trace),
            "--out",
            str(fake.out),
            "--limit",
            "2",
        ]
    )
    result = main(
        [
            "rtc-peer-audit",
            "--replay",
            str(fake.out),
            "--checkpoint",
            str(fake.checkpoint),
            "--trace",
            str(fake.trace),
        ]
    )
    assert result["audited_rows"] == 2
    assert "offline_observation_replay_not_closed_loop" in capsys.readouterr().out
