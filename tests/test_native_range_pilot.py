"""The wide-range development pilot: its level rule, plan, capture loop and report, on invented
sessions. Nothing here is native evidence."""

import json

import pytest
from test_native_actuator_qualification_delivery import buffer_s, make_peer

from media_rl import native_range_pilot as pilot
from media_rl.native_protocol import asset_directory, read_json, seal_directory

SHOWS = (0, 1, 1, 1, 2)  # which invented behaviour a level shows: skips at the encoder, clean, late
PSNR = (35.0, 34.0, 36.0, 38.0, 40.0)
ON_TIME = (0.8, 1.0, 1.0, 1.0, 0.65)


def test_episode_script_is_the_frozen_one_with_the_listed_changes_only():
    frozen = (asset_directory() / pilot.FROZEN_EPISODE).read_text()
    made = pilot.episode_source()
    assert (asset_directory() / "range_episode.mjs").read_text() == made
    undone = made
    for old, new in pilot.EPISODE_CHANGES:
        assert frozen.count(old) == 1 and undone.count(new) == 1
        undone = undone.replace(new, old)
    assert undone == frozen
    assert "InstrumentSampler" not in made and "LevelSampler(nativeConfig.level)" in made


def test_a_level_is_a_ratio_inside_the_cap_domain_or_the_ceiling():
    assert pilot.LEVELS == (0.25, 0.65, 0.85, 1.05, None) and pilot.NAMES[pilot.REFERENCE] == "1.05"
    assert pilot.requested_bps(0, 400000) == 150000  # a quarter would be 100 kbit/s: the floor
    assert pilot.requested_bps(1, 400000) == 260000
    assert pilot.requested_bps(2, 300001) == 255001  # rounds half up, as the page does
    assert pilot.requested_bps(3, 3_900_000) == 4_000_000
    assert pilot.requested_bps(4, 123456) == 4_000_000
    for level, estimate in ((5, 400000), (1, 0), (1.0, 400000), (1, None)):
        with pytest.raises(ValueError):
            pilot.requested_bps(level, estimate)
    control = (asset_directory() / "range_control.mjs").read_text()
    assert "LEVELS=Object.freeze([0.25,0.65,0.85,1.05,null])" in control
    assert f"ABI='{pilot.ABI}'" in control


def invented_sender(level, estimates, *, applied=None):
    """Polls every 100 ms; the estimate appears at the second poll; the page acknowledges 4 ms later."""
    rows, current, ack = [], None, None
    for step in range(70):
        now = 100.0 * step
        bwe = None if step == 0 else estimates[min(len(estimates) - 1, int(now // 3100))]
        epoch = 0 if current is None else current["epoch"] + 1
        if bwe and (current is None or (ack is not None and now >= ack + 3000)) and epoch < 6:
            ratio, asked = pilot.LEVELS[level], pilot.requested_bps(level, bwe)
            current = dict(
                abi=pilot.ABI,
                level=level,
                epoch=epoch,
                arm=level,
                ratio=ratio,
                assignment_ms=now,
                base_bwe_bps=bwe,
                requested_bps=asked,
                clipped=ratio is not None and asked != round(ratio * bwe),
            )
            ack = None
        cap = 300000 if current is None else current["requested_bps"]
        rows.append(
            dict(
                step_id=step,
                observation=dict(sample_ms=now, raw_source=dict(bwe_bps=bwe)),
                actuator_assignment=None if current is None else dict(current),
                ack_ms=now + 4,
                actuation_readback=dict(encoder_max_bitrate_bps=cap if applied is None else applied),
            )
        )
        if current is not None and ack is None:
            ack = now + 4
    meter = dict(
        abi="native_encoded_payload_meter_v1",
        owner="unique_owned_video_sender",
        pass_through_no_frame_mutation=True,
        error=None,
        unit="encoded_video_payload_bytes_before_RTP_packetization",
        measurement_start_ms=0.0,
        measurement_cutoff_ms=7000.0,
        started_ms=0.0,
        ended_ms=None,
        events=[],
    )
    return dict(decisions=rows, encoded_meter=meter, measurement_start_ms=0.0, measurement_cutoff_ms=7000.0)


def test_replay_recomputes_every_hold_and_refuses_a_record_that_disagrees():
    sender = invented_sender(1, [400000, 900000, 200000])
    caps, assignments = pilot.replay_assignments(sender, 1)
    assert caps[0] == 300000 and caps[1] == 260000  # the initial cap, then 0.65 of the first estimate
    assert [a["epoch"] for a in assignments] == [0, 1, 2]
    assert [a["requested_bps"] for a in assignments] == [260000, 585000, 150000]  # the last one at the floor
    assert [a["clipped"] for a in assignments] == [False, False, True]
    assert assignments[1]["assignment_ms"] == 3200 and assignments[1]["ack_ms"] == 3204  # 3 s after the ack
    assert all(a["arm"] == 1 and a["ratio"] == 0.65 for a in assignments)
    ceiling = invented_sender(4, [400000, 900000])
    caps, assignments = pilot.replay_assignments(ceiling, 4)
    assert set(caps[1:]) == {4_000_000} and assignments[0]["ratio"] is None
    with pytest.raises(ValueError):  # recorded under another level
        pilot.replay_assignments(sender, 2)
    with pytest.raises(ValueError, match="acknowledgment"):  # another cap was applied
        pilot.replay_assignments(invented_sender(1, [400000], applied=300000), 1)


def invented_plan(tmp_path, sources=("a", "b")):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not a video")
    chosen, runtimes = [], {}
    for name in sources:
        chosen.append(dict(clip_id=name, cluster_id="source-" + name))
        episodes = [
            dict(
                id=f"n1-{name}-{regime}-p{position}-r0-instrument",
                network_regime=regime,
                position=position,
                condition="instrument",
                role="discovery",
                cluster_id="source-" + name,
                scene_seed=0,
                exploration_seed=7,
            )
            for regime in pilot.REGIMES
            for position in range(2)
        ]
        runtimes["n1-" + name] = dict(
            panel_abi="native_actuator_identification_v1",
            stage="discovery",
            video_source=dict(path=str(video)),
            extra_source_sha256={"assets/actuator_episode.mjs": "0" * 64},
            conditions=dict(instrument=dict(controller="explore", behavior="instrument", model="source")),
            measurement_recipe={},
            episodes=episodes,
        )
    return chosen, runtimes


def test_plan_runs_every_level_on_the_same_content_in_one_shuffled_order(tmp_path):
    chosen, runtimes = invented_plan(tmp_path)
    made = pilot.plan_from(chosen, runtimes, "f" * 64)
    assert made["development_pilot"] is True and made["confirmatory"] is False
    assert made["levels"] == list(pilot.NAMES) and made["reference_level"] == "1.05"
    assert len(made["order"]) == 2 * 4 * 5 and len({tuple(o) for o in made["order"]}) == 40
    assert made["order"] == pilot.plan_from(chosen, runtimes, "f" * 64)["order"]  # the same shuffle again
    assert made["order"] != sorted(made["order"])
    runtime = made["runtimes"]["rp-a"]
    assert runtime["panel_abi"] == pilot.ABI and runtime["stage"] == "discovery"
    assert runtime["measurement_recipe"]["instrument_ratios"] == [0.25, 0.65, 0.85, 1.05, None]
    assert runtime["conditions"]["level4"] == dict(
        controller="explore", behavior="level", level=4, model="source"
    )
    assert set(runtime["extra_source_sha256"]) == {
        "assets/actuator_episode.mjs",
        "assets/range_control.mjs",
        "assets/range_episode.mjs",
    }
    cell = [e for e in runtime["episodes"] if e["network_regime"] == "near-capacity"]
    assert [e["condition"] for e in cell] == [f"level{i}" for i in range(5)]
    assert {(e["position"], e["scene_seed"], e["role"]) for e in cell} == {
        (0, 0, "discovery")
    }  # N1's first peer
    assert runtimes["n1-a"]["panel_abi"] == "native_actuator_identification_v1"  # N1's runtime is not touched
    runtimes["n1-b"]["video_source"]["path"] = str(tmp_path / "absent.mp4")
    with pytest.raises(ValueError, match="not on this machine"):
        pilot.plan_from(chosen, runtimes, "f" * 64)


def sealed_plan(tmp_path):
    chosen, runtimes = invented_plan(tmp_path, sources=("a",))
    made = pilot.plan_from(chosen, runtimes, "f" * 64)
    root = tmp_path / "plan"
    root.mkdir()
    (root / "protocol.json").write_text(json.dumps(made))
    seal_directory(root, ["protocol.json"], pilot.PLAN_STAGE)
    return root / "protocol.json", made


def test_capture_resumes_keeps_failures_and_retries_each_once(tmp_path):
    path, made = sealed_plan(tmp_path)
    broken, hopeless = made["order"][3][1], made["order"][7][1]
    calls = []

    def run(child, runtime_path, runtime, trial):
        calls.append(trial["id"])
        assert read_json(runtime_path) == runtime and trial["role"] == "discovery"
        child.mkdir()
        (child / "raw.json").write_text("{}")
        if trial["id"] == hopeless or (trial["id"] == broken and calls.count(broken) == 1):
            raise RuntimeError("the browser did not connect")
        seal_directory(child, ["raw.json"], pilot.PEER_STAGE)

    out = tmp_path / "capture"
    first = pilot.capture(path, out, limit=5, run=run)
    assert first == dict(planned=20, sealed=4, failed_attempts=[broken + "-1"])
    assert (out / "failed" / (broken + "-1") / "raw.json").exists()  # the failed attempt is kept whole
    assert "did not connect" in (out / "failed" / (broken + "-1") / "pilot_failure.json").read_text()
    done = pilot.capture(path, out, run=run)
    assert done["sealed"] == 19 and done["failed_attempts"] == [
        broken + "-1",
        hopeless + "-1",
        hopeless + "-2",
    ]
    assert calls.count(broken) == 2 and calls.count(hopeless) == 2
    assert max(calls.count(t) for _, t in made["order"] if t not in (broken, hopeless)) == 1
    before = len(calls)
    assert pilot.capture(path, out, run=run) == done and len(calls) == before  # nothing is run again
    other = dict(made, order_seed=1)
    (out / "protocol.json").write_text(json.dumps(other))
    with pytest.raises(ValueError, match="another plan"):
        pilot.capture(path, out, run=run)


def make_session(capture, source, regime, level):
    """One invented sealed session at one level, in the shape the audit leaves behind."""
    trial = f"rp-{source}-{regime}-l{level}"
    rows = make_peer(capture, trial, source, regime, [SHOWS[level]] * 6)
    root = capture / trial
    rows = [dict(r, arm=level, clipped=level == 0, requested_bps=150000 + 1000 * level) for r in rows]
    (root / "cohorts.json").write_text(json.dumps(rows))
    derived = json.loads((root / "native_derived.json").read_text())
    labels = derived["quality"]["source_labels"]
    for x in labels:
        x["psnr_db"] = PSNR[level] if x["readback_age_ms"] is not None else None
        x["ontime_sampled_psnr_contribution"] = PSNR[level] if x["identifiable_ontime"] else 0
    (root / "native_derived.json").write_text(json.dumps(derived))
    native = dict(
        id=trial,
        cluster_id=source,
        network_regime=regime,
        utility=sum(x["ontime_sampled_psnr_contribution"] for x in labels) / len(labels),
        ontime_fraction=sum(x["identifiable_ontime"] for x in labels) / len(labels),
    )
    (root / "native_row.json").write_text(json.dumps(native))
    seal_directory(root, sorted(f.name for f in root.iterdir()), pilot.PEER_STAGE)
    return ["rp-" + source, trial]


def invented_capture(tmp_path, skip=()):
    capture = tmp_path / "capture"
    capture.mkdir()
    order = [
        make_session(capture, source, regime, level)
        for source in ("s0", "s1", "s2")
        for regime in ("underutilized", "queue-building")
        for level in range(5)
        if (source, regime, level) not in skip
    ]
    (capture / "protocol.json").write_text(json.dumps(dict(order=order)))
    return capture


def test_a_session_is_read_over_its_whole_length_and_from_the_second_hold_on(tmp_path):
    capture = invented_capture(tmp_path)
    low = pilot.session_outcomes(capture / "rp-s0-underutilized-l0")
    assert (low["level"], low["source"], low["regime"]) == (0, "s0", "underutilized")
    assert low["holds"] == 6 and low["clipped_holds"] == 6 and low["requested_kbps"] == [150.0] * 6
    assert low["session"]["on_time"] == pytest.approx(0.8, abs=0.01)
    assert low["session"]["never_encoded"] == pytest.approx(0.2, abs=0.01)
    assert low["session"]["utility"] == pytest.approx(0.8 * 35, abs=0.3)
    assert low["session"]["psnr_on_time_db"] == pytest.approx(35)
    assert low["after_startup"]["requests"] < low["session"]["requests"]
    assert low["after_startup"]["encoder_kbps"] == pytest.approx(0.8 * 2000 * 8 / 40, rel=0.02)
    assert low["after_startup"]["encoder_over_capacity"] == pytest.approx(
        0.8 * 2000 * 8 / 40 / 2000, rel=0.02
    )
    assert low["jitter_buffer_after_startup_ms"] == pytest.approx(1000 * buffer_s(0.65))
    top = pilot.session_outcomes(capture / "rp-s0-underutilized-l4")
    assert top["after_startup"]["shown_late"] == pytest.approx(0.25, abs=0.01)
    native = capture / "rp-s1-underutilized-l1" / "native_row.json"
    record = json.loads(native.read_text())
    native.write_text(json.dumps(dict(record, utility=record["utility"] + 1)))
    with pytest.raises(ValueError, match="do not reproduce the audited session"):
        pilot.session_outcomes(capture / "rp-s1-underutilized-l1")


def test_a_request_captured_exactly_a_deadline_before_the_cutoff_belongs_to_the_session(tmp_path):
    capture = invented_capture(tmp_path)
    root = capture / "rp-s0-underutilized-l1"
    before = pilot.session_outcomes(root)
    sender = json.loads((root / "sender_observations.json").read_text())
    derived = json.loads((root / "native_derived.json").read_text())
    labels = derived["quality"]["source_labels"]
    edge = dict(
        labels[-1], capture_request_ms=sender["measurement_cutoff_ms"] - 150
    )  # as the audit labels it
    labels.append(edge)
    (root / "native_derived.json").write_text(json.dumps(derived))
    native = json.loads((root / "native_row.json").read_text())
    native.update(
        utility=sum(x["ontime_sampled_psnr_contribution"] for x in labels) / len(labels),
        ontime_fraction=sum(x["identifiable_ontime"] for x in labels) / len(labels),
    )
    (root / "native_row.json").write_text(json.dumps(native))
    after = pilot.session_outcomes(root)  # the reader's own check passes: the edge request is counted
    assert after["session"]["requests"] == before["session"]["requests"] + 1 == len(labels)
    assert after["after_startup"]["requests"] == before["after_startup"]["requests"] + 1


def test_report_compares_every_level_with_the_reference_within_source_and_schedule(tmp_path):
    capture = invented_capture(tmp_path, skip={("s2", "queue-building", 0)})
    sessions, made = pilot.collect(capture)
    assert len(sessions) == 29
    report = pilot.analyse(sessions, planned=30)
    assert report["development_pilot"] is True and report["confirmatory"] is False
    assert report["sessions_by_level"] == {"0.25": 5, "0.65": 6, "0.85": 6, "1.05": 6, "ceiling": 6}
    assert (
        report["clipped_holds_by_level"]["0.25"] == [30, 30]
        and report["clipped_holds_by_level"]["1.05"][0] == 0
    )
    seen = report["all_schedules"]["after_startup"]
    assert seen["on_time"]["1.05"]["level"]["mean"] == pytest.approx(1)
    assert seen["on_time"]["1.05"]["minus_reference"]["mean"] == 0
    assert seen["on_time"]["0.25"]["minus_reference"]["mean"] == pytest.approx(-0.2, abs=0.01)
    assert (
        seen["on_time"]["0.25"]["sessions"] == 5
        and seen["on_time"]["0.25"]["minus_reference"]["sources"] == 3
    )
    assert seen["utility"]["0.65"]["minus_reference"]["mean"] == pytest.approx(34 - 38)
    assert seen["utility"]["ceiling"]["minus_reference"]["mean"] == pytest.approx(0.65 * 40 - 38, abs=0.4)
    assert seen["jitter_buffer_ms"]["0.25"]["minus_reference"]["mean"] == pytest.approx(
        1000 * (buffer_s(0.65) - buffer_s(0.85))
    )
    read = report["reading"]
    assert read["moves_on_time"] == {"0.25": True, "0.65": False, "0.85": False, "ceiling": True}
    assert read["pays_on_the_endpoint"] == dict.fromkeys(("0.25", "0.65", "0.85", "ceiling"), False)
    assert read["costs_on_the_endpoint"] == dict.fromkeys(("0.25", "0.65", "0.85", "ceiling"), True)
    assert read["empties_the_receiver_buffer"] == {"0.25": True, "0.65": False, "0.85": False}
    assert read["the_ceiling_is_worst"] is True
    assert set(report["by_schedule"]) == set(pilot.REGIMES)
    empty = report["by_schedule"]["near-capacity"]
    assert empty["session"]["utility"]["ceiling"]["sessions"] == 0
    assert empty["reading"]["the_ceiling_is_worst"] is False  # nothing is claimed where there is no data
    assert not any(empty["reading"]["moves_on_time"].values())


def test_command_writes_the_report_and_refuses_to_overwrite(tmp_path, capsys):
    capture = invented_capture(tmp_path)
    out = tmp_path / "report"
    pilot.main(["analyse", "--capture", str(capture), "--out", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["sessions"] == 30 and printed["reading"]["the_ceiling_is_worst"] is True
    report = json.loads((out / "report.json").read_text())
    assert report["abi"] == pilot.ABI + "_report" and len(report["plan_sha256"]) == 64
    assert len(json.loads((out / "sessions.json").read_text())) == 30
    with pytest.raises(SystemExit):
        pilot.main(["analyse", "--capture", str(capture), "--out", str(out)])
    pilot.main(["status", "--capture", str(capture)])
    assert json.loads(capsys.readouterr().out)["sealed"] == 30
