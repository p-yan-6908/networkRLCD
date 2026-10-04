"""Offline application-frame measurement, not a native safety certificate.

Pixel IDs identify source requests; clocks are from one browser document. Missing
identities include encoder/capture skips and instrumentation failures, not solely
network loss. Sink time is pixel readback completion, not physical scan-out.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric timestamp/luminance required")
    return float(value)


def _crc8(values: list[int]) -> int:
    result = 0
    for value in values:
        result ^= value
        for _ in range(8):
            result = ((result << 1) ^ 7) & 255 if result & 128 else (result << 1) & 255
    return result


def _decode(luma: list[float]) -> tuple[int, bool]:
    if len(luma) != 24:
        raise ValueError("24 pixel-marker luminances required")
    samples = [_finite(v) for v in luma]
    if any(v < 0 or v > 255 for v in samples):
        raise ValueError("luminance outside byte range")
    bits = [int(v > 127.5) for v in samples]
    source, check = 0, 0
    for bit in bits[:16]:
        source = (source << 1) | bit
    for bit in bits[16:]:
        check = (check << 1) | bit
    return source, check == _crc8([source >> 8, source & 255])


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    x = (len(ordered) - 1) * q
    lo, hi = math.floor(x), math.ceil(x)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (x - lo)


def summarize_native_frames(evidence: dict[str, Any]) -> dict[str, Any]:
    """Recompute identities, terminal censoring and request-to-readback outcomes.

    150ms is the prototype's predeclared application deadline. Other positive
    deadlines must be declared in the captured protocol, never selected here.
    Qualification is metadata/identity coverage, not controller superiority.
    """
    protocol = evidence["protocol"]
    if (
        protocol["metric"] != "capture_request_to_video_pixel_readback"
        or protocol["clock_domain"] != "single_document_performance_now"
        or protocol["capture_method"] != "canvas_manual_requestFrame"
    ):
        raise ValueError("unsupported measurement/clock/capture semantics")
    if protocol["terminal_censoring"] != "exclude_all_requests_with_deadline_after_cutoff":
        raise ValueError("outcome-dependent terminal censoring is forbidden")
    deadline = _finite(protocol["deadline_ms"])
    coverage_min = _finite(protocol["min_known_marker_coverage"])
    minimum = protocol["min_readbacks"]
    if (
        deadline <= 0
        or not 0 <= coverage_min <= 1
        or not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or minimum < 1
    ):
        raise ValueError("invalid deadline or qualification protocol")
    start = _finite(evidence["measurement_start_ms"])
    cutoff = _finite(evidence["measurement_cutoff_ms"])
    if start < 0 or cutoff < start:
        raise ValueError("invalid measurement window")
    sources: dict[int, dict[str, Any]] = {}
    last = -math.inf
    for row in evidence["sources"]:
        id = row["source_id"]
        born = _finite(row["capture_request_ms"])
        if (
            not isinstance(id, int)
            or isinstance(id, bool)
            or id != len(sources) + 1
            or id > 65535
            or born < last
            or born < 0
            or born > cutoff
        ):
            raise ValueError("nonunique/out-of-order source request")
        sources[id] = row
        last = born
    first: dict[int, float] = {}
    known, unknown, errors, callbacks, duplicates = 0, 0, 0, 0, 0
    last = -math.inf
    for row in evidence["observations"]:
        at = _finite(row["readback_ms"])
        callback = _finite(row["callback_ms"])
        if at < callback or at < last or at > cutoff or callback < 0:
            raise ValueError("nonmonotonic readback clock/window")
        last = at
        in_window = start <= at <= cutoff
        callbacks += int(in_window)
        if "read_error" in row:
            errors += 1
            unknown += int(in_window)
            continue
        candidate, crc_ok = _decode(row["luma"])
        if (
            row["candidate_id"] != candidate
            or row["crc_valid"] is not crc_ok
            or row["source_id"] != (candidate if crc_ok else None)
        ):
            raise ValueError("recorded marker identity differs from raw pixels/CRC")
        is_known = crc_ok and candidate in sources
        if row["known_source"] is not is_known:
            raise ValueError("recorded source membership differs")
        known += int(in_window and is_known)
        unknown += int(in_window and not is_known)
        if is_known:
            if at < sources[candidate]["capture_request_ms"]:
                raise ValueError("pixel source ID points to a future request")
            duplicates += int(candidate in first)
            first.setdefault(candidate, at)
    if errors != evidence["read_errors"]:
        raise ValueError("read-error count mismatch")
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: dict(
            eligible=0, identifiable_ontime=0, identified_late=0, no_identifiable_readback=0, delays=[]
        )
    )
    censored, warmup = 0, 0
    for id, row in sources.items():
        born = row["capture_request_ms"]
        if born < start:
            warmup += 1
            continue
        if born + deadline > cutoff:
            censored += 1
            continue
        bucket = buckets[str(row["phase"])]
        bucket["eligible"] += 1
        if id not in first:
            bucket["no_identifiable_readback"] += 1
        else:
            delay = first[id] - born
            bucket["delays"].append(delay)
            bucket["identifiable_ontime" if delay <= deadline else "identified_late"] += 1
    total = {
        key: sum(v[key] for v in buckets.values())
        for key in ["eligible", "identifiable_ontime", "identified_late", "no_identifiable_readback"]
    }

    def finish(bucket: dict[str, Any]) -> dict[str, Any]:
        result = {key: value for key, value in bucket.items() if key != "delays"}
        n = bucket["eligible"]
        result["identified_readback_delay_p50_ms"] = _percentile(bucket.get("delays", []), 0.5)
        result["identified_readback_delay_p95_ms"] = _percentile(bucket.get("delays", []), 0.95)
        result["identifiable_ontime_rate"] = bucket["identifiable_ontime"] / n if n else None
        return result

    total["delays"] = [x for v in buckets.values() for x in v["delays"]]
    overall = finish(total)
    n = total["eligible"]
    miss = total["identified_late"] + total["no_identifiable_readback"]
    overall["unidentified_or_late_rate"] = miss / n if n else None
    overall["deadline_miss_rate_bounds_allowing_unknown_readbacks"] = (
        [max(0, miss - unknown) / n, miss / n] if n else None
    )
    coverage = known / callbacks if callbacks else 0.0
    return dict(
        measurement_qualified=coverage >= coverage_min and callbacks >= minimum and errors == 0 and n > 0,
        metric=protocol["metric"],
        deadline_ms=deadline,
        total_source_requests=len(sources),
        warmup_excluded=warmup,
        terminal_censored=censored,
        callbacks_in_window=callbacks,
        known_marker_callbacks=known,
        unknown_marker_callbacks=unknown,
        known_marker_coverage=coverage,
        read_errors=errors,
        duplicate_identified_readbacks=duplicates,
        overall=overall,
        by_source_phase={k: finish(v) for k, v in buckets.items()},
        physical_scanout_or_capture_instant_verified=False,
        network_loss_or_controller_SOTA_certified=False,
    )
