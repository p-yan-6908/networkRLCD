"""Where a hold's frames and time go: the encoder, the relay and the receiver, by requested ratio.

Exploratory description of the Native Phase N1 stage-one capture. It reads what the auditor
recorded per capture request (was the frame read back, how old was it, was that in time), the
browser's own counters, the encoded-frame meter, the relay's packet events and the page's
snapshot at the close of each capacity phase. It reads no PSNR. The quantities are listed in
docs/NATIVE_PHASE_N1_DELIVERY.md, which was committed before any of them was computed by
ratio. Nothing here is confirmatory, no model is fitted and no controller is evaluated.
"""

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import native_actuator_qualification as qualification
from .native_actuator_control import DEADLINE_MS
from .native_actuator_qualification_dynamics import (
    DROP_EPOCH,
    DROP_REGIMES,
    above_zero,
    by_arm,
    capacity_at,
    read_relay,
)
from .native_actuator_qualification_explore import load, summary
from .native_actuator_qualification_panel import REGIMES
from .native_protocol import require

ABI = qualification.ABI + "_delivery"
WINDOWS = dict(outcome=(1800, 2600), hold=(0, 3000))  # ms of capture time from the acknowledgement
PROPAGATION_MS = 25.0  # one way through the relay
FATES = ("never_encoded", "encoded_not_shown", "shown_late", "on_time")
AGES = ("age_median_ms", "age_p90_ms")
PARTS = ("encode_ms", "pacer_ms", "relay_ms", "rest_ms", "frame_wire_ms")
RECEIVER = ("jitter_buffer_ms", "jitter_target_ms", "decoded_share", "freezes")
COUNTERS = ("frames_encoded", "total_encode_s", "packets_sent", "total_packet_send_delay_s")
SPAN = qualification.RATIOS[-1] - qualification.RATIOS[0]
MINIMUM_CELL = 3  # peers of one source, schedule and phase position for a slope


def _column(items, key):
    values = [x.get(key) for x in items]
    return np.array([math.nan if v is None else v for v in values], dtype=float)


def read_labels(path):
    """Per labelled capture request: when it was made, its frame's age at readback, and on time or not."""
    labels = json.loads(Path(path).read_text())["quality"]["source_labels"]
    return dict(
        at=_column(labels, "capture_request_ms"),
        age=_column(labels, "readback_age_ms"),
        ontime=np.array([x["identifiable_ontime"] is True for x in labels], dtype=bool),
    )


def read_sender(path):
    """The browser's cumulative counters at each poll and the encoded frames, on the page's clock."""
    sender = json.loads(Path(path).read_text())
    polls, frames = sender["decisions"], sender["encoded_meter"]["events"]
    raw = [p["observation"]["raw_source"] for p in polls]
    return dict(
        start=float(sender["measurement_start_ms"]),
        cutoff=float(sender["measurement_cutoff_ms"]),
        sample=np.array([p["observation"]["sample_ms"] for p in polls], dtype=float),
        encoded_at=np.array([f["at_ms"] for f in frames], dtype=float),
        encoded_bytes=np.array([f["byte_length"] for f in frames], dtype=float),
        **{name: _column(raw, name) for name in COUNTERS},
    )


def read_phases(path):
    """The receiver during each capacity phase.

    The page's snapshots are cumulative from the start of the connection, so a phase is the
    difference between two of them. Decoded frames stand in for the frames the jitter buffer
    emitted, which the snapshot does not keep.
    """
    phases, before = [], dict(decoded=0.0, encoded=0.0, delay=0.0, target=0.0, freezes=0.0)
    for snapshot in json.loads(Path(path).read_text())["snapshots"]:
        decoded = float(snapshot["frames_decoded"])
        delay, target = (
            math.nan if snapshot[name] is None else float(snapshot[name]) * decoded
            for name in ("mean_native_jitter_buffer_s", "mean_native_jitter_buffer_target_s")
        )
        now = dict(
            decoded=decoded,
            encoded=float(snapshot["frames_encoded"]),
            delay=delay,
            target=target,
            freezes=float(snapshot["freeze_count"] or 0),
        )
        shown, made = now["decoded"] - before["decoded"], now["encoded"] - before["encoded"]
        phases.append(
            dict(
                jitter_buffer_ms=1000 * (now["delay"] - before["delay"]) / shown if shown > 0 else math.nan,
                jitter_target_ms=1000 * (now["target"] - before["target"]) / shown if shown > 0 else math.nan,
                decoded_share=shown / made if made > 0 else math.nan,
                freezes=now["freezes"] - before["freezes"],
            )
        )
        before = now
    return phases


def _between(times, low, high):
    return (times >= low) & (times < high)


def _per(sender, total, count, low, high):
    """Growth of one counter per unit of another over a window, from the polls at its two edges."""
    keep = np.isfinite(sender[total]) & np.isfinite(sender[count])
    sample = sender["sample"][keep]
    first, last = (int(i) - 1 for i in np.searchsorted(sample, [low, high], side="right"))
    if first < 0 or last <= first:
        return math.nan
    units = sender[count][keep][last] - sender[count][keep][first]
    return float((sender[total][keep][last] - sender[total][keep][first]) / units) if units > 0 else math.nan


def window_delivery(row, bounds, labels, sender, phases, packets, offset):
    """One window of one hold: what became of its frames and where the time of the shown ones went.

    ``offset`` is the relay's clock minus the page's. Requests in the last ``DEADLINE_MS`` of the
    measurement carry no label, so the window is cut there.
    """
    low = float(row["ack_ms"]) + bounds[0]
    high = min(float(row["ack_ms"]) + bounds[1], sender["cutoff"] - DEADLINE_MS)
    asked = _between(labels["at"], low, high)
    requests = int(asked.sum())
    if requests == 0:
        return dict.fromkeys(("requests", *FATES, *AGES, *PARTS, "relay_dropped_share"), math.nan)
    age = labels["age"][asked]
    age = age[np.isfinite(age)]
    made = _between(sender["encoded_at"], low, high)
    encoded, shown, timely = int(made.sum()), len(age), int(labels["ontime"][asked].sum())
    arrived = _between(packets["at"] - offset, low, high)
    wait = packets["sojourn"][arrived]
    wait = wait[np.isfinite(wait)]
    offered = float(packets["wire"][arrived].sum())
    lost = float(packets["wire"][arrived & packets["dropped"]].sum())
    encode = 1000 * _per(sender, "total_encode_s", "frames_encoded", low, high)
    pacer = 1000 * _per(sender, "total_packet_send_delay_s", "packets_sent", low, high)
    relay = float(wait.mean()) + PROPAGATION_MS if len(wait) else math.nan
    capacity = capacity_at(phases, (low + high) / 2 + offset) * 1e6
    return dict(
        requests=requests,
        never_encoded=(requests - encoded) / requests,
        encoded_not_shown=(encoded - shown) / requests,
        shown_late=(shown - timely) / requests,
        on_time=timely / requests,
        age_median_ms=float(np.median(age)) if shown else math.nan,
        age_p90_ms=float(np.sort(age)[math.ceil(0.9 * shown) - 1]) if shown else math.nan,
        encode_ms=encode,
        pacer_ms=pacer,
        relay_ms=relay,
        rest_ms=float(age.mean()) - encode - pacer - relay if shown else math.nan,
        frame_wire_ms=float(sender["encoded_bytes"][made].mean()) * 8000 / capacity if encoded else math.nan,
        relay_dropped_share=lost / offered if offered > 0 else math.nan,
    )


def peer_delivery(root, rows):
    """Every hold and every capacity phase of one peer, bound to its audited rows."""
    root = Path(root)
    own = {r["epoch"]: r for r in json.loads((root / "cohorts.json").read_text())}
    for r in rows:
        mine = own.get(r["epoch"])
        require(
            mine is not None
            and all(mine[k] == r[k] for k in ("trial_id", "arm", "ack_ms", "base_bwe_bps", "cluster_id")),
            f"{root.name}: raw logs do not belong to the audited rows",
        )
    labels = read_labels(root / "native_derived.json")
    sender = read_sender(root / "sender_observations.json")
    phases, packets = read_relay(root / "events.jsonl.gz")
    offset = phases[0][0] - sender["start"]  # the page opens the first phase as its measurement starts
    rows = sorted(rows, key=lambda r: r["epoch"])
    holds = []
    for r in rows:
        hold = dict(
            source=r["cluster_id"],
            regime=r["network_regime"],
            trial_id=r["trial_id"],
            epoch=r["epoch"],
            arm=r["arm"],
        )
        for name, bounds in WINDOWS.items():
            hold[name] = window_delivery(r, bounds, labels, sender, phases, packets, offset)
        require(
            abs(hold["outcome"]["on_time"] - r["ontime_fraction"]) < 1e-9,
            f"{root.name}: the labels do not reproduce the audited on-time fraction of hold {r['epoch']}",
        )
        holds.append(hold)
    ratio = {r["epoch"]: qualification.RATIOS[r["arm"]] for r in rows}
    spans = [
        dict(
            source=rows[0]["cluster_id"],
            regime=rows[0]["network_regime"],
            trial_id=rows[0]["trial_id"],
            phase=index,
            ratio=(ratio[2 * index] + ratio[2 * index + 1]) / 2,
            **receiver,
        )
        for index, receiver in enumerate(read_phases(root / "summary.json"))
        if 2 * index in ratio and 2 * index + 1 in ratio  # a phase holds two holds
    ]
    return holds, spans


def collect(capture, rows):
    """Every hold and phase of every peer in the capture."""
    peers = defaultdict(list)
    for r in rows:
        peers[r["trial_id"]].append(r)
    holds, spans = [], []
    for trial, own in sorted(peers.items()):
        root = Path(capture) / trial  # a peer's directory carries its trial's name
        require(root.is_dir(), f"no raw logs for {trial}")
        peer_holds, peer_spans = peer_delivery(root, own)
        holds += peer_holds
        spans += peer_spans
    return holds, spans


def below_zero(entry):
    return entry["interval95"] is not None and entry["interval95"][1] < 0


def state(holds, where):
    """One state by requested ratio in both windows, and the statements fixed in advance."""
    table = {
        span: {
            name: by_arm(holds, lambda h, span=span, name=name: h[span][name], where)
            for name in (*FATES, "relay_dropped_share", *AGES, *PARTS)
        }
        for span in WINDOWS
    }
    seen = table["outcome"]
    table["a_lower_cap_costs_frames_at_the_encoder"] = bool(
        below_zero(seen["never_encoded"]["top_minus_lower"])
    )
    table["a_higher_cap_costs_time_after_the_relay"] = bool(above_zero(seen["rest_ms"]["top_minus_lower"]))
    table["it_reaches_the_deadline"] = bool(above_zero(seen["shown_late"]["top_minus_lower"]))
    return table


def source_levels(spans, name, where):
    """Per source: the mean of a phase quantity, with schedules weighted equally."""
    cells = defaultdict(list)
    for s in spans:
        if where(s) and math.isfinite(s[name]):
            cells[(s["source"], s["regime"])].append(s[name])
    grouped = defaultdict(list)
    for (source, _), values in cells.items():
        grouped[source].append(float(np.mean(values)))
    return [float(np.mean(values)) for _, values in sorted(grouped.items())]


def source_slopes(spans, name, where):
    """Per source: the slope of a phase quantity on the mean requested ratio of the phase's two holds.

    Least squares within source, schedule and phase position, cells averaged within source,
    scaled to the distance between the lowest and the top ratio.
    """
    cells = defaultdict(list)
    for s in spans:
        if where(s) and math.isfinite(s[name]):
            cells[(s["source"], s["regime"], s["phase"])].append((s["ratio"], s[name]))
    grouped = defaultdict(list)
    for (source, _, _), points in cells.items():
        x, y = (np.array(column, dtype=float) for column in zip(*points, strict=True))
        spread = float(((x - x.mean()) ** 2).sum())
        if len(points) >= MINIMUM_CELL and spread > 1e-12:
            grouped[source].append(float(((x - x.mean()) * (y - y.mean())).sum() / spread) * SPAN)
    return [float(np.mean(values)) for _, values in sorted(grouped.items())]


def receiver(spans, where=lambda s: True):
    """The receiver per capacity phase: level, and slope on the requested ratio."""
    table = {
        name: dict(
            level=summary(source_levels(spans, name, where)),
            slope_per_span_of_ratio=summary(source_slopes(spans, name, where)),
        )
        for name in RECEIVER
    }
    table["a_higher_cap_fills_the_receiver_buffer"] = bool(
        above_zero(table["jitter_buffer_ms"]["slope_per_span_of_ratio"])
    )
    return table


def describe(holds, spans):
    """The tables fixed in advance."""

    def later(h):
        return h["epoch"] >= 1

    return dict(
        all_schedules=state(holds, later),
        by_schedule={
            regime: state(holds, lambda h, regime=regime: h["regime"] == regime and later(h))
            for regime in REGIMES
        },
        capacity_drop={
            regime: state(holds, lambda h, regime=regime: h["regime"] == regime and h["epoch"] == DROP_EPOCH)
            for regime in DROP_REGIMES
        },
        receiver_per_phase=dict(
            all_phases=receiver(spans),
            by_schedule={
                regime: receiver(spans, lambda s, regime=regime: s["regime"] == regime) for regime in REGIMES
            },
            by_phase_position={
                str(index + 1): receiver(spans, lambda s, index=index: s["phase"] == index)
                for index in sorted({s["phase"] for s in spans})
            },
        ),
    )


def summarise(holds, spans):
    """The report for a set of holds and phases, from one capture or from several."""
    return dict(
        abi=ABI,
        exploratory=True,
        labels_read="per request: read back or not, age at readback, within the deadline or not",
        psnr_read=False,
        models_fitted=0,
        peers=len({h["trial_id"] for h in holds}),
        holds=len(holds),
        phases=len(spans),
        sources=len({h["source"] for h in holds}),
        deadline_ms=DEADLINE_MS,
        windows_ms={name: list(bounds) for name, bounds in WINDOWS.items()},
        ratio_span_of_a_slope=SPAN,
        tables=describe(holds, spans),
    )


def headline(report):
    """The few numbers worth printing: the registered window over all schedules, and the receiver."""
    seen = report["tables"]["all_schedules"]
    buffer = report["tables"]["receiver_per_phase"]["all_phases"]
    return dict(
        peers=report["peers"],
        holds=report["holds"],
        registered_window={
            name: {arm: seen["outcome"][name][arm]["mean"] for arm in seen["outcome"][name]}
            for name in (*FATES, "age_median_ms", "age_p90_ms", "rest_ms")
        },
        statements={k: v for k, v in seen.items() if isinstance(v, bool)},
        jitter_buffer_ms=buffer["jitter_buffer_ms"],
        a_higher_cap_fills_the_receiver_buffer=buffer["a_higher_cap_fills_the_receiver_buffer"],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--capture", type=Path, action="append", required=True)
    parser.add_argument(
        "--rows",
        type=Path,
        action="append",
        help="audited rows per capture, in order (default: its cohorts.json)",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output directory required\n")
    sources = args.rows or [capture / "cohorts.json" for capture in args.capture]
    if len(sources) != len(args.capture):
        parser.exit(2, "error: one rows file per capture\n")
    holds, spans, digests = [], [], []
    for capture, source in zip(args.capture, sources, strict=True):
        rows, digest = load(source)
        capture_holds, capture_spans = collect(capture, rows)
        holds += capture_holds
        spans += capture_spans
        digests.append(digest)
    report = summarise(holds, spans)
    report["rows_sha256"] = digests[0] if len(digests) == 1 else digests
    args.out.mkdir(parents=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    with gzip.open(args.out / "holds.json.gz", "wt") as stream:  # the raw logs are not needed again
        json.dump(dict(holds=holds, phases=spans), stream)
    print(json.dumps(headline(report), indent=1))


if __name__ == "__main__":
    main()
