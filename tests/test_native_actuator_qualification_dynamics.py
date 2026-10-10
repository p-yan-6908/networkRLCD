"""Inside a hold: the reader of raw per-peer logs, on invented peers. Nothing here is native evidence."""

import gzip
import json
import math

import numpy as np
import pytest

from media_rl import native_actuator_qualification_dynamics as dynamics

LEVEL = (0.6, 0.75, 0.9)  # invented encoder share of the frozen estimate per arm
START, OFFSET, FROZEN = 1000.0, 500.0, 1_000_000.0
SPACING = 3100  # ms between holds, a little over the 3 s that is binned, as natively


def make_peer(capture, trial, source, regime, arms, *, congested=None, cutoff=None, drop_to=None):
    """One invented peer: six holds, polls every 100 ms, frames every 40 ms, packets every 20 ms.

    ``congested`` names a hold in which the top arm meets a long queue and loses a fifth of its
    packets. ``drop_to`` lowers the relay capacity just before the third hold.
    """
    root = capture / trial
    root.mkdir(parents=True)
    cutoff = START + 6 * SPACING + 100 if cutoff is None else cutoff
    rows = [
        dict(
            trial_id=trial,
            epoch=epoch,
            arm=arm,
            assignment_ms=START + SPACING * epoch,
            ack_ms=START + SPACING * epoch + 2,
            base_bwe_bps=FROZEN,
            cluster_id=source,
            network_regime=regime,
            complete=True,
        )
        for epoch, arm in enumerate(arms)
    ]

    def hold_of(t):
        return min(int((t - START) // SPACING), 5)

    decisions, frames, events = [], [], []
    for t in np.arange(START, cutoff, 100.0):
        epoch = hold_of(t)
        into = (t - START - SPACING * epoch) / 1000
        decisions.append(
            dict(
                observation=dict(
                    sample_ms=float(t), raw_source=dict(bwe_bps=FROZEN * (1 + 0.1 * into * (arms[epoch] + 1)))
                ),
                encoder_response=dict(
                    fields=dict(targetBitrate=dict(status="present", value=LEVEL[arms[epoch]] * FROZEN))
                ),
            )
        )
    for t in np.arange(START + 1, cutoff, 40.0):
        frames.append(dict(at_ms=float(t), byte_length=LEVEL[arms[hold_of(t)]] * FROZEN * 0.04 / 8))
    events.append(dict(kind="phase", at_ms=START + OFFSET, capacity_mbps=2.0))
    if drop_to is not None:
        events.append(dict(kind="phase", at_ms=START + OFFSET + 2 * SPACING - 100, capacity_mbps=drop_to))
    packet = 0
    for t in np.arange(START + 3, cutoff, 20.0):
        epoch = hold_of(t)
        hard = congested == epoch and arms[epoch] == 2
        lost = hard and packet % 5 == 0
        wire = LEVEL[arms[epoch]] * FROZEN * 0.02 / 8
        at = float(t) + OFFSET  # the relay's clock runs ahead of the page's
        events.append(
            dict(kind="offer", direction="a_to_b", at_ms=at, wire_bytes=wire, dropped=lost, packet=packet)
        )
        events.append(dict(kind="service", direction="a_to_b", at_ms=at, queue_after_wire_bytes=0))
        if not lost:
            done = at + (60.0 if hard else 5.0)
            events.append(
                dict(
                    kind="forward",
                    direction="a_to_b",
                    packet=packet,
                    at_ms=done + 25,
                    serialization_done_ms=done,
                )
            )
        packet += 1
        events.append(
            dict(kind="offer", direction="b_to_a", at_ms=at, wire_bytes=80, dropped=False, packet=packet)
        )
        events.append(
            dict(
                kind="forward", direction="b_to_a", packet=packet, at_ms=at + 26, serialization_done_ms=at + 1
            )
        )
        packet += 1
    sender = dict(
        measurement_start_ms=START,
        measurement_cutoff_ms=cutoff,
        decisions=decisions,
        encoded_meter=dict(events=frames),
    )
    (root / "sender_observations.json").write_text(json.dumps(sender))
    (root / "cohorts.json").write_text(json.dumps(rows))
    with gzip.open(root / "events.jsonl.gz", "wt") as stream:
        stream.write("\n".join(json.dumps(e) for e in events) + "\n")
    return rows


def test_relay_reader_keeps_the_media_direction_and_times_each_packet(tmp_path):
    make_peer(tmp_path, "t", "s", "queue-building", [2, 2, 2, 0, 1, 2], congested=2, drop_to=0.6)
    phases, packets = dynamics.read_relay(tmp_path / "t/events.jsonl.gz")
    assert phases == [(START + OFFSET, 2.0), (START + OFFSET + 2 * SPACING - 100, 0.6)]
    assert set(np.round(packets["wire"])) == {
        round(LEVEL[a] * FROZEN * 0.02 / 8) for a in (0, 1, 2)
    }  # no feedback
    assert packets["dropped"].sum() > 0 and np.isnan(packets["sojourn"][packets["dropped"]]).all()
    assert set(np.round(packets["sojourn"][~packets["dropped"]])) == {5.0, 60.0}
    assert (
        dynamics.capacity_at(phases, START) == 2.0
        and dynamics.capacity_at(phases, START + OFFSET + 2 * SPACING) == 0.6
    )


def test_hold_curves_are_over_the_frozen_estimate_and_on_the_pages_clock(tmp_path):
    arms = [2, 0, 2, 1, 0, 2]
    rows = make_peer(
        tmp_path,
        "t",
        "s",
        "queue-building",
        arms,
        congested=2,
        drop_to=0.6,
        cutoff=START + 5 * SPACING + 2502,
    )
    holds = dynamics.peer_holds(tmp_path / "t", rows)
    assert [h["epoch"] for h in holds] == list(range(6)) and {h["relay_offset_ms"] for h in holds} == {OFFSET}
    for h in holds[:5]:
        level = LEVEL[h["arm"]]
        assert np.allclose(h["encoder"], level, rtol=0.05) and np.allclose(h["target"], level)
        assert np.allclose(h["sent"], level, rtol=0.11)  # ten packets per bin, give or take one at an edge
        assert h["estimate"][0] < h["estimate"][-1] and h["estimate"][0] == pytest.approx(1.0, abs=0.05)
    assert (
        holds[0]["estimate"][-1] > holds[1]["estimate"][-1]
    )  # the invented estimate grows faster at the top arm
    hit, calm = holds[2], holds[3]
    assert np.allclose(hit["sojourn_ms"], 60.0) and np.allclose(calm["sojourn_ms"], 5.0)
    assert dynamics.dropped_share(hit) == pytest.approx(0.2, abs=0.01) and dynamics.dropped_share(calm) == 0.0
    assert dynamics.peak(hit["sojourn_ms"]) == pytest.approx(60.0)
    # Capacity fell to 0.6 Mbit/s 100 ms before the third hold: the estimate is far above it there.
    assert hit["estimate_over_capacity"][0] == pytest.approx(1.0 / 0.6, rel=0.05)
    assert holds[1]["estimate_over_capacity"][0] == pytest.approx(1.0 / 2.0, rel=0.05)
    last = holds[5]  # the measurement ends 2.5 s into the last hold
    assert np.isfinite(last["encoder"][:12]).all() and np.isnan(last["encoder"][12:]).all()
    assert math.isnan(dynamics.window(last["estimate"], dynamics.WINDOWS["end"]))
    assert dynamics.window(last["encoder"], dynamics.WINDOWS["outcome"]) == pytest.approx(LEVEL[2], rel=0.05)


def test_raw_logs_must_belong_to_the_audited_rows(tmp_path):
    rows = make_peer(tmp_path, "t", "s", "near-capacity", [0, 1, 2, 0, 1, 2])
    with pytest.raises(ValueError, match="do not belong to the audited rows"):
        dynamics.peer_holds(tmp_path / "t", [dict(rows[0], arm=1), *rows[1:]])
    with pytest.raises(ValueError, match="no raw logs"):
        dynamics.collect(tmp_path, [dict(r, trial_id="missing") for r in rows])


def panel(capture, sources=4, peers=6):
    """Invented sources: the top arm meets a queue and drops in the hold of the capacity drop only."""
    rows = []
    for s in range(sources):
        for regime in dynamics.REGIMES:
            for p in range(peers):
                arms = [(p + epoch) % 3 for epoch in range(6)]
                trial = f"s{s}-{regime}-p{p}"
                planted = dynamics.DROP_EPOCH if regime in dynamics.DROP_REGIMES else None
                drop = 0.6 if regime in dynamics.DROP_REGIMES else None
                rows += make_peer(
                    capture, trial, f"source-{s}", regime, arms, congested=planted, drop_to=drop
                )
    return rows


def test_tables_recover_a_planted_mechanism_and_nothing_where_none_was_planted(tmp_path):
    rows = panel(tmp_path)
    report, holds = dynamics.study(tmp_path, rows)
    assert (
        report["exploratory"]
        and report["mechanism_only"]
        and report["quality_or_ontime_labels_read"] is False
    )
    assert (
        report["peers"] == 4 * 4 * 6
        and report["holds"] == len(holds) == 4 * 4 * 6 * 6
        and report["sources"] == 4
    )
    assert report["relay_clock_minus_page_clock_ms"]["median"] == OFFSET
    tables = report["tables"]
    for regime in dynamics.DROP_REGIMES:
        hit = tables["capacity_drop"][regime]
        assert hit["mechanism_present"] and hit["visible_in_the_outcome_window"]
        assert hit["peak_sojourn_ms"]["top_minus_lower"]["mean"] == pytest.approx(55.0, abs=1.0)
        assert hit["dropped_share"]["1.05"]["mean"] == pytest.approx(0.2, abs=0.02)
        assert hit["dropped_share"]["0.65"]["mean"] == 0.0 and hit["peak_sojourn_ms"]["1.05"]["sources"] == 4
    steady = tables["steady_constraint"]
    assert not steady["mechanism_present"] and not steady["visible_in_the_outcome_window"]
    settled = tables["encoder_settling"]["encoder"]
    assert [round(settled["outcome"][k]["mean"], 2) for k in ("0.65", "0.85", "1.05")] == [0.6, 0.75, 0.9]
    room = tables["estimate_with_room"]
    assert set(room) == {"first hold", "later holds"} and set(room["later holds"]) == {
        "middle",
        "late",
        "end",
    }
    assert (
        room["later holds"]["end"]["top_minus_lower"]["mean"] > 0
    )  # the invented estimate grows with the arm
    assert set(tables["recovery"]) == {"estimate_at_end", "encoder_in_outcome_window"}
    key = "queue-building|2|1.05"
    curve = report["curves"][key]
    assert curve["sources"] == 4 and len(curve["sojourn_ms"]) == dynamics.BINS
    assert (
        curve["dropped_share"][5] == pytest.approx(0.2, abs=0.05)
        and report["curves"]["queue-building|2|0.65"]["dropped_share"][5] == 0
    )
    json.dumps(report, allow_nan=False)  # empty bins are written as null, never NaN


def test_cli_writes_the_report_and_per_hold_curves_once(tmp_path, capsys):
    capture = tmp_path / "capture"
    rows = panel(capture, sources=2, peers=3)
    path = tmp_path / "rows.json.gz"
    path.write_bytes(gzip.compress(json.dumps(rows).encode()))
    out = tmp_path / "out"
    dynamics.main(["--rows", str(path), "--capture", str(capture), "--out", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["peers"] == 2 * 4 * 3 and set(printed["capacity_drop"]) == set(dynamics.DROP_REGIMES)
    report = json.loads((out / "report.json").read_text())
    assert len(report["rows_sha256"]) == 64 and report["models_fitted"] == 0
    kept = json.loads(gzip.open(out / "holds.json.gz", "rt").read())
    assert len(kept) == report["holds"] and len(kept[0]["encoder"]) == dynamics.BINS
    assert {"source", "regime", "epoch", "arm", "offered", "dropped", "sojourn_ms"} <= set(kept[0])
    with pytest.raises(SystemExit):
        dynamics.main(["--rows", str(path), "--capture", str(capture), "--out", str(out)])


def test_window_and_dropped_share_skip_empty_bins():
    values = [math.nan] * 4 + [2.0, 4.0] + [math.nan] * 9
    assert dynamics.window(values, (800, 1200)) == 3.0 and math.isnan(dynamics.window(values, (0, 800)))
    assert math.isnan(dynamics.peak([math.nan] * 15)) and dynamics.peak(values) == 4.0
    hold = dict(offered=[100.0] * 15, dropped=[0.0] * 9 + [50.0] * 4 + [0.0] * 2)
    assert dynamics.dropped_share(hold) == pytest.approx(200 / 1500)
    assert dynamics.dropped_share(hold, dynamics.WINDOWS["outcome"]) == 0.5
    assert math.isnan(dynamics.dropped_share(dict(offered=[0.0] * 15, dropped=[0.0] * 15)))
