"""Pinned published RTC estimators. Observation replay is NOT closed-loop evaluation.

Only the released MMSys 2024 150-feature ABI is supported. Never manufacture these
inputs from the native RLCD sender ABI, and never use capacity/quality labels as
inputs. Checkpoints remain external; no foreign Python or pickle is executed.
"""

import hashlib
import json
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

import numpy as np

ABI = "published_rtc_peer_replay_v1"
SCOPE = "offline_observation_replay_not_closed_loop"
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_REPLAY_ROWS = 4096
CLAIMS = dict(closed_loop=False, qoe_comparison=False, sota=False)
INPUTS = (("obs", (1, 1, 150)), ("hidden_states", (1, 1)), ("cell_states", (1, 1)))
OUTPUTS = (("output", (1, 1, 2)), ("state_out", (1, 1)), ("cell_out", (1, 1)))


@dataclass(frozen=True)
class PeerSpec:
    peer: str
    repository: str
    commit: str
    upstream_path: str
    git_blob_sha1: str
    sha256: str
    size_bytes: int
    paper_url: str
    license: str = "MIT; retain upstream copyright/license when redistributing"

    @property
    def source_url(self):
        return f"https://raw.githubusercontent.com/{self.repository}/{self.commit}/{self.upstream_path}"


PEERS = MappingProxyType(
    {
        "schaferct-mmsys2024": PeerSpec(
            "schaferct-mmsys2024",
            "n13eho/Schaferct",
            "da49600ba1fb915181081cd8183c7cb13f278bc9",
            "onnx_model/Schaferct_model.onnx",
            "2661359dca3d1ccd63b5ea88692ae2378c814c51",
            "1638b64aae7e591db17eef793c071d04001b349f6f39697cf6b6f9e9642236a1",
            4639039,
            "https://dl.acm.org/doi/10.1145/3625468.3652183",
        ),
        "mmsys2024-baseline": PeerSpec(
            "mmsys2024-baseline",
            "microsoft/RL4BandwidthEstimationChallenge",
            "fcf857c535b7e5da1bd910bfc889ed1ab58b772c",
            "onnx_models/Offline_RL_baseline_bandwidth_estimator_model.onnx",
            "3d6939cf97d27a000da1e3f26fe90a5bb89620d6",
            "54e3113e1d0682a2aca5198e7d4f6053a239c45847e7029f48bdfb48c793a90f",
            151491,
            "https://www.microsoft.com/en-us/research/academic-program/bandwidth-estimation-challenge/",
        ),
    }
)


def list_published_peers():
    return [dict(**asdict(spec), source_url=spec.source_url) for spec in PEERS.values()]


def _checkpoint(peer, checkpoint):
    if peer not in PEERS:
        raise ValueError(f"Unknown published RTC peer: {peer}")
    spec = PEERS[peer]
    with Path(checkpoint).open("rb") as stream:
        data = stream.read(spec.size_bytes + 1)
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if (
        len(data) != spec.size_bytes
        or hashlib.sha256(data).hexdigest() != spec.sha256
        or blob != spec.git_blob_sha1
    ):
        raise ValueError("Published checkpoint hash/size mismatch; refusing inference")
    return spec, data


def _array(value, shape, name):
    array = np.asarray(value)
    if array.shape != shape or array.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be numeric with shape {shape}; no native ABI projection")
    with np.errstate(over="ignore", invalid="ignore"):
        array = array.astype(np.float32, copy=True)
    if not np.isfinite(array).all():
        raise ValueError(f"Non-finite float32 {name}")
    return array


class PublishedRtcPeer:
    """One independently resettable estimator; no sharing state between peers/calls."""

    def __init__(self, peer, checkpoint):
        spec, data = _checkpoint(peer, checkpoint)  # verify before loading the optional runtime
        try:
            import onnxruntime as ort
        except (ImportError, OSError) as exc:
            raise ValueError("Install calibrated-media-rl[rtc-peers] for CPU ONNX inference") from exc
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        # Use verified bytes, not a path that could change after the hash check.
        self.session = ort.InferenceSession(data, options, providers=["CPUExecutionProvider"])
        for nodes, expected in ((self.session.get_inputs(), INPUTS), (self.session.get_outputs(), OUTPUTS)):
            actual = tuple((x.name, tuple(x.shape)) for x in nodes)
            if actual != expected or any(x.type != "tensor(float)" for x in nodes):
                raise ValueError("Published ONNX input/output ABI mismatch")
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("Published replay requires CPUExecutionProvider only")
        self.manifest = dict(**asdict(spec), source_url=spec.source_url)
        self.runtime = dict(
            onnxruntime=ort.__version__,
            provider="CPUExecutionProvider",
            intra_op_threads=1,
            inter_op_threads=1,
            execution_mode="sequential",
            host=dict(system=platform.system(), machine=platform.machine(), python=platform.python_version()),
        )
        self.reset()

    def reset(self):
        self.hidden = np.zeros((1, 1), dtype=np.float32)
        self.cell = np.zeros((1, 1), dtype=np.float32)

    def act(self, observation):
        start = time.perf_counter_ns()
        obs = _array(observation, (150,), "observation").reshape(1, 1, 150)
        outputs = self.session.run(
            None, dict(obs=obs, hidden_states=self.hidden.copy(), cell_states=self.cell.copy())
        )
        if len(outputs) != 3:
            raise ValueError("Published ONNX output count mismatch")
        output = _array(outputs[0], (1, 1, 2), "output")
        hidden = _array(outputs[1], (1, 1), "hidden state")
        cell = _array(outputs[2], (1, 1), "cell state")
        bandwidth = float(output[0, 0, 0])  # exact original reference script channel; no clamp
        if bandwidth < 0:
            raise ValueError("Published estimator emitted a negative bandwidth")
        self.hidden, self.cell = hidden, cell
        return dict(
            bandwidth_bps=bandwidth,
            auxiliary_output=float(output[0, 0, 1]),
            act_latency_ms=(time.perf_counter_ns() - start) / 1e6,
        )


def inspect_published_peer(peer, checkpoint):
    estimator = PublishedRtcPeer(peer, checkpoint)
    return dict(
        abi=ABI,
        scope=SCOPE,
        claims=CLAIMS.copy(),
        peer=estimator.manifest,
        runtime=estimator.runtime,
        inputs=INPUTS,
        outputs=OUTPUTS,
        bandwidth_channel=[0, 0, 0],
        auxiliary_is_calibrated_risk=False,
    )


def _trace(path, limit):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_REPLAY_ROWS:
        raise ValueError(f"Replay limit must be an integer in [1, {MAX_REPLAY_ROWS}]")
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_TRACE_BYTES + 1)
    if len(data) > MAX_TRACE_BYTES:
        raise ValueError("Behavior trace exceeds bounded replay size")
    source = json.loads(data)
    if not isinstance(source, dict) or not isinstance(source.get("observations"), list):
        raise ValueError("Expected a public behavior-trace object with observations")
    observations = source["observations"]
    if not observations:
        raise ValueError("Behavior trace has no observations")
    selected = np.stack([_array(row, (150,), "observation") for row in observations[:limit]])
    manifest = dict(
        sha256=hashlib.sha256(data).hexdigest(),
        total_rows=len(observations),
        replayed_rows=len(selected),
        start_row=0,
        limit=limit,
        model_fields=["observations"],
        ignored_fields=sorted(set(source) - {"observations"}),
        observations_float32_sha256=hashlib.sha256(selected.astype("<f4").tobytes()).hexdigest(),
    )
    return selected, manifest


def replay_published_peer(peer, checkpoint, trace, out=None, limit=256):
    """Replay only supplied observations. Recorded labels are neither inputs nor QoE evidence."""
    if out is not None and Path(out).exists():
        raise ValueError("Replay output exists; refusing to overwrite evidence")
    observations, trace_manifest = _trace(trace, limit)
    estimator = PublishedRtcPeer(peer, checkpoint)
    rows = [dict(index=i, **estimator.act(obs)) for i, obs in enumerate(observations)]
    latencies = [row["act_latency_ms"] for row in rows]
    values = np.asarray([[row["bandwidth_bps"], row["auxiliary_output"]] for row in rows], dtype="<f4")
    report = dict(
        abi=ABI,
        scope=SCOPE,
        claims=CLAIMS.copy(),
        peer=estimator.manifest,
        runtime=estimator.runtime,
        trace=trace_manifest,
        rows=rows,
        prediction_float32_sha256=hashlib.sha256(values.tobytes()).hexdigest(),
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        auxiliary_is_calibrated_risk=False,
        latency=dict(
            scope="host act wall time; excludes initialization/data load/network/codec",
            median_ms=float(np.median(latencies)),
            p99_ms=float(np.quantile(latencies, 0.99)),
            max_ms=max(latencies),
            intel_challenge_budget_certified=False,
        ),
    )
    if out is not None:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def audit_published_peer_replay(replay, checkpoint, trace):
    """Re-execute every recorded prefix row; require exact float32 predictions, not saved metrics."""
    saved = json.loads(Path(replay).read_text())
    if (
        not isinstance(saved, dict)
        or saved.get("abi") != ABI
        or saved.get("scope") != SCOPE
        or saved.get("claims") != CLAIMS
        or saved.get("auxiliary_is_calibrated_risk") is not False
    ):
        raise ValueError("Published replay scope/claim mismatch")
    if not isinstance(saved.get("peer"), dict) or not isinstance(saved.get("trace"), dict):
        raise ValueError("Published replay peer/trace manifest missing")
    actual = replay_published_peer(
        saved["peer"].get("peer"), checkpoint, trace, limit=saved["trace"].get("limit")
    )
    for key in ("peer", "trace", "implementation_sha256", "prediction_float32_sha256"):
        if saved.get(key) != actual[key]:
            raise ValueError(f"Published replay {key} mismatch")
    if saved.get("runtime") != actual["runtime"]:
        raise ValueError(
            "Exact replay requires the recorded runtime/host; cross-host equivalence is not certified"
        )
    rows = saved.get("rows")
    if not isinstance(rows, list) or len(rows) != len(actual["rows"]):
        raise ValueError("Published replay row count mismatch")
    for a, b in zip(rows, actual["rows"], strict=True):
        if (
            not isinstance(a, dict)
            or type(a.get("index")) is not int
            or any(a.get(k) != b[k] for k in ("index", "bandwidth_bps", "auxiliary_output"))
        ):
            raise ValueError("Published replay prediction/index mismatch")
        value = a.get("act_latency_ms")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not np.isfinite(value)
            or value < 0
        ):
            raise ValueError("Invalid saved latency")
    times = [x["act_latency_ms"] for x in rows]
    latency = dict(
        scope=actual["latency"]["scope"],
        median_ms=float(np.median(times)),
        p99_ms=float(np.quantile(times, 0.99)),
        max_ms=max(times),
        intel_challenge_budget_certified=False,
    )
    if saved.get("latency") != latency:
        raise ValueError("Published replay latency summary mismatch")
    return dict(
        abi=ABI,
        audited_rows=len(rows),
        exact_predictions=True,
        scope=SCOPE,
        claims=CLAIMS.copy(),
        timing_truth_verified=False,
    )
