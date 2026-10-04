"""Primary-spec checks for MMSys receiver observations, NOT an extractor certificate.

A 150-float shape alone does not establish correct units or a faithful receiver.
These checks reject documented aggregate contradictions without inventing missing
packet clock, window-boundary, loss/reordering or payload-classification semantics.
No policy is executed and no observations are padded, normalized or repaired.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ABI = "rtc_receiver_contract_v1"
SCOPE = "documented_aggregate_consistency_not_original_extractor_equivalence"
SOURCE_URL = "https://www.microsoft.com/en-us/research/academic-program/bandwidth-estimation-challenge/data/"
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_ROWS = 4096
WINDOW_MS = (60,) * 5 + (600,) * 5
# Includes a conservative allowance for independent float32 feature rounding.
RTOL = 2e-6
RATE_ATOL_BPS = 0.25
DELAY_ATOL_MS = 0.002
FLOAT32_EPS = float(np.finfo(np.float32).eps)
FEATURES = (
    ("receiving_rate", "bps"),
    ("received_packets", "packet"),
    ("received_bytes", "bytes"),
    ("queuing_delay", "ms"),
    ("delay_minus_200ms", "ms"),
    ("minimum_seen_delay", "ms"),
    ("delay_ratio", "ms/ms"),
    ("average_minus_interval_minimum_delay", "ms"),
    ("packet_interarrival_time", "ms"),
    ("packet_jitter", "ms"),
    ("packet_loss_ratio", "packet/packet"),
    ("lost_packets_conditional_mean", "packet"),
    ("video_packets_proportion", "packet/packet"),
    ("audio_packets_proportion", "packet/packet"),
    ("probing_packets_proportion", "packet/packet"),
)
CLAIMS = dict(
    policy_executed=False,
    closed_loop=False,
    causality_certified=False,
    original_extractor_equivalence=False,
    sota=False,
)
UNRESOLVED = (
    "Authoritative paired RTP packet/150-feature fixtures are not supplied",
    "Packet send/arrival clock normalization, wrap/reset and availability are not verified",
    "Exact within-window order, boundaries, empty defaults and bucket update timing are not verified",
    "Sequence loss, reordering, duplicate/RTX and SSRC semantics are not verified",
    "Negotiated RTP payload/padding classification and byte-accounting semantics are not verified",
    "Original encoder/transport actuation is not verified",
)


def receiver_feature_schema():
    return dict(
        abi=ABI,
        scope=SCOPE,
        source_url=SOURCE_URL,
        feature_count=150,
        windows_ms=list(WINDOW_MS),
        features=[
            dict(
                name=name,
                unit=unit,
                short_indices=list(range(i * 10, i * 10 + 5)),
                long_indices=list(range(i * 10 + 5, i * 10 + 10)),
            )
            for i, (name, unit) in enumerate(FEATURES)
        ],
        tolerances=dict(
            rtol=RTOL,
            rate_atol_bps=RATE_ATOL_BPS,
            delay_atol_ms=DELAY_ATOL_MS,
            probability_count_rounding="4 * float32 epsilon * max(1, packet count)",
        ),
        claims=CLAIMS.copy(),
        unresolved=list(UNRESOLVED),
    )


def _observation(observation):
    raw = np.asarray(observation)
    if raw.shape != (150,) or raw.dtype.kind not in "iuf":
        raise ValueError("Expected exactly 150 numeric receiver features; no native projection")
    data = raw.astype(np.float64, copy=True)
    if not np.isfinite(data).all():
        raise ValueError("Receiver observation contains non-finite values")
    with np.errstate(over="ignore", invalid="ignore"):
        quantized = data.astype(np.float32)
    if not np.isfinite(quantized).all():
        raise ValueError("Receiver observation is outside finite model float32 range")
    return data.reshape(15, 10)


def check_receiver_observation(observation):
    """Return deterministic contradictions only; a pass is NOT original/causal readiness."""
    v = _observation(observation)
    violations = []

    def require(name, good):
        bad = np.flatnonzero(~np.asarray(good, dtype=bool)).tolist()
        if bad:
            violations.append(dict(check=name, windows=bad))

    n, byte_count = v[1], v[2]
    active = n > 0
    require("packet_count_nonnegative_integer", (n >= 0) & (n == np.rint(n)))
    require("received_bytes_nonnegative_integer", (byte_count >= 0) & (byte_count == np.rint(byte_count)))
    require("zero_packet_byte_accounting", (n != 0) | (byte_count == 0))
    expected_rate = byte_count * 8000 / np.asarray(WINDOW_MS)
    require("rate_byte_units", np.isclose(v[0], expected_rate, rtol=RTOL, atol=RATE_ATOL_BPS))

    # Inactive delay/proportion default semantics are deliberately not guessed.
    mean_delay = v[4] + 200
    interval_minimum = mean_delay - v[7]
    require(
        "delay_queue_minimum_identity",
        ~active | np.isclose(v[3], mean_delay - v[5], rtol=RTOL, atol=DELAY_ATOL_MS),
    )
    require(
        "delay_ratio_interval_minimum_identity",
        ~active | np.isclose(v[6] * interval_minimum, mean_delay, rtol=RTOL, atol=DELAY_ATOL_MS),
    )
    require("minimum_seen_not_above_interval_minimum", ~active | (v[5] <= interval_minimum + DELAY_ATOL_MS))
    for i in (3, 7, 8, 9, 11):
        require(FEATURES[i][0] + "_nonnegative", ~active | (v[i] >= -DELAY_ATOL_MS))
    for i in (10, 12, 13, 14):
        require(FEATURES[i][0] + "_range", (v[i] >= 0) & (v[i] <= 1))
    require("zero_loss_zero_conditional_mean", ~active | (v[10] != 0) | (v[11] == 0))
    require("conditional_loss_mean_at_least_one", ~active | (v[10] == 0) | (v[11] >= 1 - RTOL))
    # Actual proportions of observed packets, not arbitrary/fixed corpus priors.
    # Category partition itself is NOT assumed without original RTP classification.
    for i in (12, 13, 14):
        category_count = v[i] * n
        allowance = 4 * FLOAT32_EPS * np.maximum(1, n)
        require(
            FEATURES[i][0] + "_count_consistency",
            ~active | (np.abs(category_count - np.rint(category_count)) <= allowance),
        )
    return dict(
        abi=ABI,
        scope=SCOPE,
        passed=not violations,
        active_windows=int(active.sum()),
        violations=violations,
        claims=CLAIMS.copy(),
    )


def validate_receiver_observation(observation):
    report = check_receiver_observation(observation)
    if not report["passed"]:
        names = ", ".join(x["check"] for x in report["violations"])
        raise ValueError(f"Receiver feature contract contradiction: {names}")
    return report


def audit_receiver_trace(trace, out=None, limit=MAX_ROWS):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"Receiver audit limit must be an integer in [1, {MAX_ROWS}]")
    if out is not None and Path(out).exists():
        raise ValueError("Receiver audit output exists; refusing overwrite")
    with Path(trace).open("rb") as stream:
        data = stream.read(MAX_TRACE_BYTES + 1)
    if len(data) > MAX_TRACE_BYTES:
        raise ValueError("Receiver trace exceeds bounded audit size")
    source = json.loads(data)
    if not isinstance(source, dict) or not isinstance(source.get("observations"), list):
        raise ValueError("Expected a behavior trace object with observations")
    selected = source["observations"][:limit]
    if not selected:
        raise ValueError("No receiver observations to audit")
    observations = []
    active_windows = 0
    minimum_history = []
    for i, row in enumerate(selected):
        try:
            result = validate_receiver_observation(row)
            quantized = _observation(row).astype(np.float32).reshape(150)
            validate_receiver_observation(quantized)
        except ValueError as exc:
            raise ValueError(f"Receiver row {i}: {exc}") from exc
        active_windows += result["active_windows"]
        v = _observation(row)
        observations.append(v.reshape(150))
        if v[1, 0] > 0:
            minimum_history.append(float(v[5, 0]))
    # Characterize this source only. No unsupplied clocks/reset/order assumptions.
    increases = int(np.sum(np.diff(minimum_history) > DELAY_ATOL_MS))
    values = np.asarray(observations, dtype="<f8")
    report = dict(
        abi=ABI,
        scope=SCOPE,
        documented_checks_pass=True,
        original_controller_ready=False,
        claims=CLAIMS.copy(),
        source=dict(
            sha256=hashlib.sha256(data).hexdigest(),
            total_rows=len(source["observations"]),
            audited_rows=len(selected),
            limit=limit,
            model_fields=["observations"],
            ignored_fields=sorted(set(source) - {"observations"}),
            observations_float64_sha256=hashlib.sha256(values.tobytes()).hexdigest(),
        ),
        checked_float64_and_model_float32=True,
        active_monitor_cells=active_windows,
        diagnostics=dict(
            current_short_minimum_delay_increases=increases, temporal_order_and_clock_resets_verified=False
        ),
        schema=receiver_feature_schema(),
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    if out is not None:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="MMSys documented receiver-feature checks, NOT extractor equivalence"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("schema", help="Show original feature groups/units and unresolved extraction semantics")
    audit = sub.add_parser(
        "audit", help="Check raw and model-float32 observation prefixes; never execute a policy"
    )
    audit.add_argument("--trace", type=Path, required=True)
    audit.add_argument("--out", type=Path, required=True)
    audit.add_argument("--limit", type=int, default=MAX_ROWS)
    args = parser.parse_args(argv)
    try:
        report = (
            receiver_feature_schema()
            if args.command == "schema"
            else audit_receiver_trace(args.trace, args.out, args.limit)
        )
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    return report


if __name__ == "__main__":
    main()
