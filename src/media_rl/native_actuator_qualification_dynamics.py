"""Inside a hold: how the encoder, the estimate and the relay queue respond to the requested ratio.

Exploratory description of the Native Phase N1 stage-one capture from its raw per-peer logs.
Mechanism only: it reads the sender's polls, the encoded-frame meter and the relay's packet
events, and no quality or on-time label. The quantities are listed in
docs/NATIVE_PHASE_N1_DYNAMICS.md, which was committed before any of them was computed. Nothing
here is confirmatory, no model is fitted and no controller is evaluated.
"""

import argparse
import gzip
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import native_actuator_qualification as qualification
from .native_actuator_qualification_explore import REFERENCE, load, summary
from .native_actuator_qualification_panel import REGIMES
from .native_protocol import require

ABI = qualification.ABI + "_dynamics"
BIN_MS, BINS = 200, 15  # the 3 s after a request is acknowledged
ARMS = range(len(qualification.RATIOS))
CURVES = ("encoder", "target", "estimate", "sent", "estimate_over_capacity", "sojourn_ms")
BYTES = ("offered", "dropped")
WINDOWS = dict(
    early=(200, 600), middle=(800, 1200), late=(1800, 2200), outcome=(1800, 2600), end=(2800, 3000)
)
DROP_REGIMES = ("queue-building", "collapse-recovery")  # capacity falls just before the third hold
DROP_EPOCH, RECOVERY_EPOCH = 2, 4


def read_relay(path):
    """The capacity phases and every packet offered in the media direction, on the relay's clock."""
    phases, offers, done = [], defaultdict(list), {}
    with gzip.open(path, "rt") as stream:
        for line in stream:
            if '"kind":"service"' in line:  # queue service ticks: nine in ten lines, not needed
                continue
            event = json.loads(line)
            kind = event["kind"]
            if kind == "phase":
                phases.append((float(event["at_ms"]), float(event["capacity_mbps"])))
            elif kind == "offer":
                offers[event["direction"]].append(
                    (event["at_ms"], event["wire_bytes"], bool(event["dropped"]), event["packet"])
                )
            elif kind == "forward":
                done[event["packet"]] = event["serialization_done_ms"]
    require(phases and offers, "relay log without phases or packets")
    media = max(
        offers, key=lambda direction: sum(o[1] for o in offers[direction])
    )  # media outweighs feedback
    at, wire, dropped, packet = (np.array(column) for column in zip(*offers[media], strict=True))
    served = np.array([done.get(p, np.nan) for p in packet], dtype=float)
    return phases, dict(
        at=at.astype(float), wire=wire.astype(float), dropped=dropped.astype(bool), sojourn=served - at
    )


def _number(value):
    return (
        float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else math.nan
    )


def read_sender(path):
    """The sender's polls and its encoded frames, on the page's clock."""
    sender = json.loads(Path(path).read_text())
    polls, frames = sender["decisions"], sender["encoded_meter"]["events"]
    targets = [p["encoder_response"]["fields"]["targetBitrate"] for p in polls]
    return dict(
        start=float(sender["measurement_start_ms"]),
        cutoff=float(sender["measurement_cutoff_ms"]),
        sample=np.array([p["observation"]["sample_ms"] for p in polls], dtype=float),
        estimate=np.array([_number(p["observation"]["raw_source"]["bwe_bps"]) for p in polls]),
        target=np.array([_number(t["value"]) if t["status"] == "present" else math.nan for t in targets]),
        encoded_at=np.array([f["at_ms"] for f in frames], dtype=float),
        encoded_bytes=np.array([f["byte_length"] for f in frames], dtype=float),
    )


def _sums(times, start, weights=None):
    edges = start + BIN_MS * np.arange(BINS + 1)
    return np.histogram(times, bins=edges, weights=weights)[0].astype(float)


def _means(times, values, start):
    keep = np.isfinite(values)
    count, total = _sums(times[keep], start), _sums(times[keep], start, values[keep])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def capacity_at(phases, relay_ms):
    """The relay capacity in force, in Mbit/s. Before the first phase it is the first phase's."""
    current = phases[0][1]
    for at, capacity in phases:
        if at <= relay_ms:
            current = capacity
    return current


def hold_curves(row, sender, phases, packets, offset):
    """One hold in bins from its acknowledgement. Rates are over the hold's frozen estimate.

    ``offset`` is the relay's clock minus the page's. Bins that end after the measurement cutoff
    are left empty.
    """
    start, frozen = float(row["ack_ms"]), float(row["base_bwe_bps"])
    inside = start + BIN_MS * np.arange(1, BINS + 1) <= sender["cutoff"]
    rate = 8000 / BIN_MS / frozen
    at = packets["at"] - offset
    offered = _sums(at, start, packets["wire"])
    lost = packets["dropped"]
    middle = start + BIN_MS * (np.arange(BINS) + 0.5)
    capacity = np.array([capacity_at(phases, t + offset) for t in middle]) * 1e6
    estimate = _means(sender["sample"], sender["estimate"], start)
    with np.errstate(invalid="ignore", divide="ignore"):
        over_capacity = np.where(capacity > 0, estimate / capacity, np.nan)
    curves = dict(
        encoder=_sums(sender["encoded_at"], start, sender["encoded_bytes"]) * rate,
        target=_means(sender["sample"], sender["target"], start) / frozen,
        estimate=estimate / frozen,
        sent=offered * rate,
        estimate_over_capacity=over_capacity,
        sojourn_ms=_means(at, packets["sojourn"], start),
        offered=offered,
        dropped=_sums(at[lost], start, packets["wire"][lost]),
    )
    return {name: np.where(inside, values, np.nan) for name, values in curves.items()}


def peer_holds(root, rows):
    """Every hold of one peer, bound to its audited rows."""
    root = Path(root)
    own = {r["epoch"]: r for r in json.loads((root / "cohorts.json").read_text())}
    for r in rows:
        mine = own.get(r["epoch"])
        require(
            mine is not None
            and all(mine[k] == r[k] for k in ("trial_id", "arm", "ack_ms", "base_bwe_bps", "cluster_id")),
            f"{root.name}: raw logs do not belong to the audited rows",
        )
    sender = read_sender(root / "sender_observations.json")
    phases, packets = read_relay(root / "events.jsonl.gz")
    offset = phases[0][0] - sender["start"]  # the page opens the first phase as its measurement starts
    return [
        dict(
            source=r["cluster_id"],
            regime=r["network_regime"],
            trial_id=r["trial_id"],
            epoch=r["epoch"],
            arm=r["arm"],
            base_bwe_bps=r["base_bwe_bps"],
            relay_offset_ms=offset,
            **hold_curves(r, sender, phases, packets, offset),
        )
        for r in sorted(rows, key=lambda r: r["epoch"])
    ]


def collect(capture, rows):
    """Every hold of every peer in the capture."""
    peers = defaultdict(list)
    for r in rows:
        peers[r["trial_id"]].append(r)
    holds = []
    for trial, own in sorted(peers.items()):
        root = Path(capture) / trial  # a peer's directory carries its trial's name
        require(root.is_dir(), f"no raw logs for {trial}")
        holds += peer_holds(root, own)
    return holds


def window(values, bounds):
    """Mean of a curve over the bins of ``bounds`` (ms from the acknowledgement)."""
    low, high = (int(v / BIN_MS) for v in bounds)
    chunk = np.asarray(values, dtype=float)[low:high]
    return float(np.mean(chunk[np.isfinite(chunk)])) if np.isfinite(chunk).any() else math.nan


def peak(values):
    values = np.asarray(values, dtype=float)
    return float(np.max(values[np.isfinite(values)])) if np.isfinite(values).any() else math.nan


def dropped_share(hold, bounds=(0, BIN_MS * BINS)):
    """Share of the offered wire bytes that the relay's queue dropped."""
    low, high = (int(v / BIN_MS) for v in bounds)
    offered = np.nansum(np.asarray(hold["offered"], dtype=float)[low:high])
    lost = np.nansum(np.asarray(hold["dropped"], dtype=float)[low:high])
    return float(lost / offered) if offered > 0 else math.nan


def source_values(holds, value, where):
    """Per source: the mean of ``value`` over the selected holds, with schedules weighted equally."""
    cells = defaultdict(list)
    for h in holds:
        if where(h):
            v = value(h)
            if math.isfinite(v):
                cells[(h["source"], h["regime"])].append(v)
    grouped = defaultdict(list)
    for (source, _), values in cells.items():
        grouped[source].append(float(np.mean(values)))
    return {source: float(np.mean(values)) for source, values in grouped.items()}


def by_arm(holds, value, where):
    """Mean over sources per requested ratio, and the top ratio minus the mean of the two lower ones."""
    per = [source_values(holds, value, lambda h, arm=arm: h["arm"] == arm and where(h)) for arm in ARMS]
    out = {f"{qualification.RATIOS[arm]:.2f}": summary(list(per[arm].values())) for arm in ARMS}
    shared = sorted(set(per[0]) & set(per[1]) & set(per[2]))
    out["top_minus_lower"] = summary([per[2][s] - (per[0][s] + per[1][s]) / 2 for s in shared])
    return out


def above_zero(entry):
    return entry["interval95"] is not None and entry["interval95"][0] > 0


def congestion(holds, where):
    """Queueing and drops by arm in one state, and whether the top ratio carries more of either."""
    table = dict(
        peak_sojourn_ms=by_arm(holds, lambda h: peak(h["sojourn_ms"]), where),
        outcome_sojourn_ms=by_arm(holds, lambda h: window(h["sojourn_ms"], WINDOWS["outcome"]), where),
        dropped_share=by_arm(holds, dropped_share, where),
        outcome_dropped_share=by_arm(holds, lambda h: dropped_share(h, WINDOWS["outcome"]), where),
        estimate_over_capacity_at_end=by_arm(
            holds, lambda h: window(h["estimate_over_capacity"], WINDOWS["end"]), where
        ),
    )
    table["mechanism_present"] = bool(
        above_zero(table["peak_sojourn_ms"]["top_minus_lower"])
        or above_zero(table["dropped_share"]["top_minus_lower"])
    )
    table["visible_in_the_outcome_window"] = bool(
        above_zero(table["outcome_sojourn_ms"]["top_minus_lower"])
        or above_zero(table["outcome_dropped_share"]["top_minus_lower"])
    )
    return table


def describe(holds):
    """The tables fixed in advance."""

    def later(h):
        return h["epoch"] >= 1

    def steady(h):
        return (h["regime"] == "near-capacity" and h["epoch"] >= DROP_EPOCH) or (
            h["regime"] in DROP_REGIMES and h["epoch"] == DROP_EPOCH + 1
        )

    def recovering(h):
        return h["regime"] == "collapse-recovery" and h["epoch"] == RECOVERY_EPOCH

    groups = (("first hold", lambda h: h["epoch"] == 0), ("later holds", later))
    return dict(
        encoder_settling={
            name: {
                span: by_arm(holds, lambda h, name=name, span=span: window(h[name], WINDOWS[span]), later)
                for span in ("early", "middle", "outcome")
            }
            for name in ("encoder", "target")
        },
        estimate_with_room={
            label: {
                span: by_arm(
                    holds,
                    lambda h, span=span: window(h["estimate"], WINDOWS[span]),
                    lambda h, chosen=chosen: h["regime"] == REFERENCE and chosen(h),
                )
                for span in ("middle", "late", "end")
            }
            for label, chosen in groups
        },
        capacity_drop={
            regime: congestion(
                holds, lambda h, regime=regime: h["regime"] == regime and h["epoch"] == DROP_EPOCH
            )
            for regime in DROP_REGIMES
        },
        recovery=dict(
            estimate_at_end=by_arm(holds, lambda h: window(h["estimate"], WINDOWS["end"]), recovering),
            encoder_in_outcome_window=by_arm(
                holds, lambda h: window(h["encoder"], WINDOWS["outcome"]), recovering
            ),
        ),
        steady_constraint=congestion(holds, steady),
    )


def _mean(stack):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # a bin that no hold reaches stays empty
        return np.nanmean(np.asarray(stack, dtype=float), axis=0)


def _plain(values, digits=5):
    return [
        None if not math.isfinite(v) else float(f"{v:.{digits}g}") for v in np.asarray(values, dtype=float)
    ]


def mean_curves(holds):
    """Per schedule, hold position and arm: the mean curve over sources, one curve per source first."""
    cells = defaultdict(list)
    for h in holds:
        cells[(h["regime"], h["epoch"], h["arm"], h["source"])].append(h)
    grouped = defaultdict(list)
    for (regime, epoch, arm, _), members in cells.items():
        own = {name: _mean([m[name] for m in members]) for name in CURVES}
        offered = np.nansum([m["offered"] for m in members], axis=0)
        lost = np.nansum([m["dropped"] for m in members], axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            own["dropped_share"] = np.where(offered > 0, lost / offered, np.nan)
        grouped[(regime, epoch, arm)].append(own)
    out = {}
    for (regime, epoch, arm), sources in sorted(grouped.items()):
        entry = dict(sources=len(sources))
        for name in (*CURVES, "dropped_share"):
            entry[name] = _plain(_mean([s[name] for s in sources]))
        out[f"{regime}|{epoch}|{qualification.RATIOS[arm]:.2f}"] = entry
    return out


def study(capture, rows):
    holds = collect(capture, rows)
    offsets = np.array([h["relay_offset_ms"] for h in holds])
    report = dict(
        abi=ABI,
        exploratory=True,
        mechanism_only=True,
        quality_or_ontime_labels_read=False,
        models_fitted=0,
        peers=len({h["trial_id"] for h in holds}),
        holds=len(holds),
        sources=len({h["source"] for h in holds}),
        bin_ms=BIN_MS,
        bins=BINS,
        windows_ms=WINDOWS,
        schedules=list(REGIMES),
        relay_clock_minus_page_clock_ms=dict(
            minimum=float(offsets.min()), median=float(np.median(offsets)), maximum=float(offsets.max())
        ),
        tables=describe(holds),
        curves=mean_curves(holds),
    )
    return report, holds


def headline(report):
    tables = report["tables"]
    drop = {
        regime: {
            k: tables["capacity_drop"][regime][k]
            for k in ("mechanism_present", "visible_in_the_outcome_window")
        }
        for regime in DROP_REGIMES
    }
    steady = tables["steady_constraint"]
    return dict(
        peers=report["peers"],
        holds=report["holds"],
        capacity_drop=drop,
        steady_constraint={k: steady[k] for k in ("mechanism_present", "visible_in_the_outcome_window")},
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inside a hold: exploratory description of the N1 raw logs")
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output directory required\n")
    rows, digest = load(args.rows)
    report, holds = study(args.capture, rows)
    report["rows_sha256"] = digest
    args.out.mkdir(parents=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    kept = [{k: _plain(v) if isinstance(v, np.ndarray) else v for k, v in h.items()} for h in holds]
    with gzip.open(
        args.out / "holds.json.gz", "wt"
    ) as stream:  # per-hold curves, so the raw logs are not needed again
        json.dump(kept, stream)
    print(json.dumps(headline(report), indent=1))


if __name__ == "__main__":
    main()
