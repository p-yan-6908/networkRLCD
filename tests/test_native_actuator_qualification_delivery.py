"""Where a hold's frames and time go: the reader, on invented peers. Nothing here is native evidence."""

import gzip
import json
import math

import numpy as np
import pytest

from media_rl import native_actuator_qualification_delivery as delivery

START, OFFSET = 1000.0, 500.0
SPACING = 3100  # ms between holds, a little over the 3 s of a hold, as natively
FRAME_MS, PACKET_MS = 40.0, 20.0
AGE, LATE_AGE = (80.0, 90.0, 110.0), 170.0  # invented readback age per arm, and of a late frame
SOJOURN = (5.0, 5.0, 30.0)  # invented relay sojourn per arm
FRAME_BYTES = (2000.0, 3000.0, 4000.0)
ENCODE_S, PACER_S = 0.002, 0.003
CAPACITY = 2.0
RATIOS = (0.65, 0.85, 1.05)
ROTATIONS = ([0, 1, 2, 0, 1, 2], [2, 0, 1, 2, 0, 1], [1, 2, 0, 1, 2, 0])


def fate(arm, index):
    """Invented: the lowest arm's encoder skips every fifth frame; the top arm loses every tenth
    after encoding and shows every fourth late."""
    if arm == 0 and index % 5 == 0:
        return "skipped"
    if arm == 2 and index % 10 == 1:
        return "lost"
    if arm == 2 and index % 4 == 0:
        return "late"
    return "on_time"


def buffer_s(ratio):
    return 0.010 + 0.05 * (ratio - RATIOS[0])  # invented: 20 ms more from the lowest to the top ratio


def make_peer(capture, trial, source, regime, arms, *, cutoff=None):
    """One invented peer: six holds, a request every 40 ms, a poll every 100 ms, a packet every 20 ms."""
    root = capture / trial
    root.mkdir(parents=True)
    cutoff = START + 6 * SPACING + 200 if cutoff is None else cutoff

    def hold_of(t):
        return min(int((t - START) // SPACING), 5)

    requests = [(index, float(t)) for index, t in enumerate(np.arange(START + 5, cutoff, FRAME_MS))]
    labels, frames = [], []
    for index, t in requests:
        arm = arms[hold_of(t)]
        what = fate(arm, index)
        if what != "skipped":
            frames.append(dict(at_ms=t + 2, byte_length=FRAME_BYTES[arm]))
        if t < cutoff - 150:  # later requests are censored
            shown = what in ("late", "on_time")
            labels.append(
                dict(
                    source_id=index,
                    capture_request_ms=t,
                    identifiable_ontime=what == "on_time",
                    readback_age_ms=(LATE_AGE if what == "late" else AGE[arm]) if shown else None,
                    psnr_db=None,
                )
            )
    packets = [float(t) for t in np.arange(START + 3, cutoff, PACKET_MS)]
    decisions = []
    for t in np.arange(START, cutoff, 100.0):
        made = sum(1 for f in frames if f["at_ms"] <= t)
        sent = sum(1 for p in packets if p <= t)
        decisions.append(
            dict(
                observation=dict(
                    sample_ms=float(t),
                    raw_source=dict(
                        frames_encoded=made,
                        total_encode_s=ENCODE_S * made,
                        packets_sent=sent,
                        total_packet_send_delay_s=PACER_S * sent,
                    ),
                )
            )
        )
    events = [dict(kind="phase", at_ms=START + OFFSET, capacity_mbps=CAPACITY)]
    for number, t in enumerate(packets):
        at = t + OFFSET  # the relay's clock runs ahead of the page's
        events.append(
            dict(kind="offer", direction="a_to_b", at_ms=at, wire_bytes=500, dropped=False, packet=2 * number)
        )
        events.append(dict(kind="service", direction="a_to_b", at_ms=at, queue_after_wire_bytes=0))
        done = at + SOJOURN[arms[hold_of(t)]]
        events.append(
            dict(
                kind="forward",
                direction="a_to_b",
                packet=2 * number,
                at_ms=done + 25,
                serialization_done_ms=done,
            )
        )
        events.append(
            dict(
                kind="offer",
                direction="b_to_a",
                at_ms=at,
                wire_bytes=80,
                dropped=False,
                packet=2 * number + 1,
            )
        )
    rows = []
    for epoch, arm in enumerate(arms):
        ack = START + SPACING * epoch + 2
        inside = [index for index, t in requests if ack + 1800 <= t < ack + 2600]
        rows.append(
            dict(
                trial_id=trial,
                epoch=epoch,
                arm=arm,
                ack_ms=ack,
                base_bwe_bps=1_000_000.0,
                cluster_id=source,
                network_regime=regime,
                complete=True,
                ontime_fraction=sum(fate(arm, i) == "on_time" for i in inside) / len(inside),
            )
        )
    snapshots, encoded, decoded, delay = [], 0, 0, 0.0
    for phase in range(3):  # cumulative from the start of the connection, as the page records them
        opens = START + 2 * SPACING * phase
        close = START + 2 * SPACING * (phase + 1) if phase < 2 else math.inf
        own = [(i, t) for i, t in requests if opens <= t < close]
        made = sum(fate(arms[hold_of(t)], i) != "skipped" for i, t in own)
        seen = sum(fate(arms[hold_of(t)], i) in ("late", "on_time") for i, t in own)
        encoded, decoded = encoded + made, decoded + seen
        delay += buffer_s((RATIOS[arms[2 * phase]] + RATIOS[arms[2 * phase + 1]]) / 2) * seen
        snapshots.append(
            dict(
                frames_encoded=encoded,
                frames_decoded=decoded,
                mean_native_jitter_buffer_s=delay / decoded,
                mean_native_jitter_buffer_target_s=0.02,
                freeze_count=phase,  # one more in each later phase
            )
        )
    (root / "native_derived.json").write_text(json.dumps(dict(quality=dict(source_labels=labels))))
    (root / "sender_observations.json").write_text(
        json.dumps(
            dict(
                measurement_start_ms=START,
                measurement_cutoff_ms=cutoff,
                decisions=decisions,
                encoded_meter=dict(events=frames),
            )
        )
    )
    (root / "summary.json").write_text(json.dumps(dict(snapshots=snapshots)))
    (root / "cohorts.json").write_text(json.dumps(rows))
    with gzip.open(root / "events.jsonl.gz", "wt") as stream:
        stream.write("\n".join(json.dumps(e) for e in events) + "\n")
    return rows


def panel(capture):
    """Three sources under two schedules, three peers each, every arm in every phase position."""
    rows = []
    for source in ("s0", "s1", "s2"):
        for regime in ("underutilized", "queue-building"):
            for number, arms in enumerate(ROTATIONS):
                rows += make_peer(capture, f"{source}-{regime}-{number}", source, regime, arms)
    return rows


def test_a_window_splits_its_frames_by_fate_and_its_time_by_place(tmp_path):
    rows = make_peer(tmp_path, "t", "s", "underutilized", ROTATIONS[0])
    holds, _ = delivery.peer_delivery(tmp_path / "t", rows)
    low, middle, top = (holds[epoch]["outcome"] for epoch in (3, 4, 5))  # arms 0, 1 and 2
    for seen in (low, middle, top):
        assert seen["requests"] == 20  # 0.8 s of a request every 40 ms
        assert sum(seen[name] for name in delivery.FATES) == pytest.approx(1)
        assert seen["encode_ms"] == pytest.approx(1000 * ENCODE_S)
        assert seen["pacer_ms"] == pytest.approx(1000 * PACER_S)
        assert seen["relay_dropped_share"] == 0
    assert (low["never_encoded"], low["encoded_not_shown"], low["shown_late"]) == pytest.approx((0.2, 0, 0))
    assert (middle["never_encoded"], middle["on_time"]) == pytest.approx((0, 1))
    assert (
        top["never_encoded"],
        top["encoded_not_shown"],
        top["shown_late"],
        top["on_time"],
    ) == pytest.approx((0, 0.1, 0.25, 0.65))
    assert (middle["age_median_ms"], middle["age_p90_ms"]) == (90, 90)
    assert (top["age_median_ms"], top["age_p90_ms"]) == (110, 170)  # 13 frames at 110 ms, 5 at 170 ms
    assert middle["relay_ms"] == pytest.approx(5 + 25)
    assert middle["rest_ms"] == pytest.approx(90 - 2 - 3 - 30)
    assert top["rest_ms"] == pytest.approx((13 * 110 + 5 * 170) / 18 - 2 - 3 - (30 + 25))
    assert middle["frame_wire_ms"] == pytest.approx(3000 * 8 / (CAPACITY * 1e6) * 1000)
    assert holds[4]["hold"]["requests"] == 75  # 3 s
    assert holds[4]["hold"]["on_time"] == pytest.approx(1)


def test_a_window_is_cut_where_the_labels_stop(tmp_path):
    cutoff = START + 5 * SPACING + 2 + 2600 + 150  # the last registered window just fits
    rows = make_peer(tmp_path, "t", "s", "underutilized", ROTATIONS[1], cutoff=cutoff)
    holds, _ = delivery.peer_delivery(tmp_path / "t", rows)
    last = holds[5]
    assert last["outcome"]["requests"] == 20
    assert last["hold"]["requests"] == 65  # 2.6 s of labels, not 3 s
    assert sum(last["hold"][name] for name in delivery.FATES) == pytest.approx(1)
    assert last["hold"]["never_encoded"] == pytest.approx(0)  # frames encoded after the cut are not counted


def test_a_phase_is_the_difference_between_two_cumulative_snapshots(tmp_path):
    arms = ROTATIONS[0]
    make_peer(tmp_path, "t", "s", "underutilized", arms)
    phases = delivery.read_phases(tmp_path / "t/summary.json")
    assert len(phases) == 3
    for index, phase in enumerate(phases):
        ratio = (RATIOS[arms[2 * index]] + RATIOS[arms[2 * index + 1]]) / 2
        assert phase["jitter_buffer_ms"] == pytest.approx(1000 * buffer_s(ratio))
        assert phase["jitter_target_ms"] == pytest.approx(20)
        assert 0 < phase["decoded_share"] <= 1
    assert [p["freezes"] for p in phases] == [0, 1, 1]
    assert phases[2]["decoded_share"] < 1  # the top arm loses frames after encoding


def test_a_phase_without_decoded_frames_or_buffer_figures_is_left_empty(tmp_path):
    snapshots = [
        dict(
            frames_encoded=10,
            frames_decoded=0,
            mean_native_jitter_buffer_s=None,
            mean_native_jitter_buffer_target_s=None,
            freeze_count=None,
        ),
        dict(
            frames_encoded=30,
            frames_decoded=20,
            mean_native_jitter_buffer_s=0.03,
            mean_native_jitter_buffer_target_s=0.02,
            freeze_count=2,
        ),
    ]
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(dict(snapshots=snapshots)))
    first, second = delivery.read_phases(path)
    assert math.isnan(first["jitter_buffer_ms"]) and first["decoded_share"] == 0
    assert math.isnan(second["jitter_buffer_ms"])  # the earlier total is unknown, so the difference is too
    assert second["decoded_share"] == 1 and second["freezes"] == 2


def test_reader_refuses_raw_logs_that_do_not_match_the_audited_rows(tmp_path):
    rows = make_peer(tmp_path, "t", "s", "underutilized", ROTATIONS[0])
    wrong = [dict(r, ontime_fraction=0.5) if r["epoch"] == 4 else r for r in rows]
    with pytest.raises(ValueError, match="do not reproduce the audited on-time fraction of hold 4"):
        delivery.peer_delivery(tmp_path / "t", wrong)
    other = [dict(r, arm=(r["arm"] + 1) % 3) for r in rows]
    with pytest.raises(ValueError, match="do not belong to the audited rows"):
        delivery.peer_delivery(tmp_path / "t", other)
    with pytest.raises(ValueError, match="no raw logs"):
        delivery.collect(tmp_path, [dict(rows[0], trial_id="absent")])


def test_tables_by_ratio_and_the_statements_fixed_in_advance(tmp_path):
    holds, spans = delivery.collect(tmp_path, panel(tmp_path))
    report = delivery.summarise(holds, spans)
    assert (report["peers"], report["holds"], report["phases"], report["sources"]) == (18, 108, 54, 3)
    assert report["psnr_read"] is False and report["exploratory"] is True
    seen = report["tables"]["all_schedules"]
    never = seen["outcome"]["never_encoded"]
    assert [never[arm]["mean"] for arm in ("0.65", "0.85", "1.05")] == pytest.approx([0.2, 0, 0])
    assert never["top_minus_lower"]["mean"] == pytest.approx(-0.1)
    assert seen["outcome"]["shown_late"]["top_minus_lower"]["mean"] == pytest.approx(0.25)
    assert seen["outcome"]["rest_ms"]["top_minus_lower"]["mean"] == pytest.approx(
        (13 * 110 + 5 * 170) / 18 - 60 - (45 + 55) / 2
    )
    assert seen["a_lower_cap_costs_frames_at_the_encoder"] is True
    assert seen["a_higher_cap_costs_time_after_the_relay"] is True
    assert seen["it_reaches_the_deadline"] is True
    assert set(report["tables"]["by_schedule"]) == set(delivery.REGIMES)
    empty = report["tables"]["by_schedule"]["near-capacity"]
    assert empty["outcome"]["on_time"]["top_minus_lower"]["sources"] == 0
    assert empty["it_reaches_the_deadline"] is False  # nothing is claimed where there is no data
    drop = report["tables"]["capacity_drop"]["queue-building"]
    assert drop["hold"]["on_time"]["0.85"]["mean"] == pytest.approx(1)
    receiver = report["tables"]["receiver_per_phase"]
    slope = receiver["all_phases"]["jitter_buffer_ms"]["slope_per_span_of_ratio"]
    assert slope["sources"] == 3 and slope["mean"] == pytest.approx(20)  # the invented 20 ms
    assert receiver["all_phases"]["a_higher_cap_fills_the_receiver_buffer"] is True
    assert receiver["all_phases"]["jitter_target_ms"]["slope_per_span_of_ratio"]["mean"] == pytest.approx(0)
    assert set(receiver["by_phase_position"]) == {"1", "2", "3"}
    assert receiver["by_schedule"]["near-capacity"]["a_higher_cap_fills_the_receiver_buffer"] is False
    level = receiver["all_phases"]["jitter_buffer_ms"]["level"]["mean"]
    assert level == pytest.approx(1000 * buffer_s(0.85))  # every peer's phases average to the middle ratio


def test_a_slope_needs_three_peers_and_more_than_one_ratio():
    def span(source, ratio, value, phase=0):
        return dict(source=source, regime="underutilized", phase=phase, ratio=ratio, jitter_buffer_ms=value)

    two = [span("a", 0.65, 10), span("a", 1.05, 30)]
    assert delivery.source_slopes(two, "jitter_buffer_ms", lambda s: True) == []
    flat = [span("a", 0.85, v) for v in (10, 20, 30)]
    assert delivery.source_slopes(flat, "jitter_buffer_ms", lambda s: True) == []
    three = [*two, span("a", 0.85, 20)]
    assert delivery.source_slopes(three, "jitter_buffer_ms", lambda s: True) == pytest.approx([20])


def test_command_writes_the_report_and_refuses_to_overwrite(tmp_path, capsys):
    capture = tmp_path / "capture"
    rows = panel(capture)
    table = tmp_path / "rows.json"
    table.write_text(json.dumps(rows))
    out = tmp_path / "out"
    delivery.main(["--capture", str(capture), "--rows", str(table), "--out", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["peers"] == 18 and printed["a_higher_cap_fills_the_receiver_buffer"] is True
    report = json.loads((out / "report.json").read_text())
    assert report["abi"].endswith("_delivery") and len(report["rows_sha256"]) == 64
    kept = json.loads(gzip.decompress((out / "holds.json.gz").read_bytes()))
    assert len(kept["holds"]) == 108 and len(kept["phases"]) == 54
    with pytest.raises(SystemExit):
        delivery.main(["--capture", str(capture), "--rows", str(table), "--out", str(out)])
