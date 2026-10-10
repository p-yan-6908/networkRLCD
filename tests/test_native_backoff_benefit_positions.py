"""B1 addendum: the split of holds by position in the schedule. Invented rows only."""

import json

import pytest

from media_rl import native_backoff_benefit as benefit
from media_rl import native_backoff_benefit_panel as b1
from media_rl import native_backoff_benefit_positions as positions

PLAN = benefit.Plan()


def test_every_hold_with_a_predecessor_has_one_position():
    assert [positions.kind("queue-building", e) for e in range(1, 6)] == [
        "before_drop",
        "drop",
        "after_drop",
        "late_drop_schedules",
        "late_drop_schedules",
    ]
    assert (
        positions.kind("collapse-recovery", 2) == "drop"
        and positions.kind("near-capacity", 2) == "near_capacity"
    )
    assert {positions.kind("underutilized", e) for e in range(1, 6)} == {"room"}
    assert {positions.kind(g, e) for g in b1.REGIMES for e in range(1, 6)} == set(positions.KINDS)
    with pytest.raises(ValueError, match="unknown schedule"):
        positions.kind("elsewhere", 2)


def invented(sources=6, peers=6, planted="drop", gain=3.0):
    """Holds as the flag would hand them over: backing off pays only in holds of one kind."""
    held = []
    for s in range(sources):
        for regime in b1.REGIMES:
            for p in range(peers):
                for epoch in range(1, 6):
                    arm = (p + epoch + s) % 3
                    here = positions.kind(regime, epoch)
                    value = 25.0 + 0.1 * s + (gain if here == planted and arm < 2 else 0.0)
                    held.append(
                        dict(
                            source=f"s{s}",
                            regime=regime,
                            trial_id=f"s{s}-{regime}-{p}",
                            epoch=epoch,
                            arm=arm,
                            flagged=(p + epoch) % 2 == 0,
                            complete=True,
                            utility=value,
                            ontime_fraction=0.8,
                            following=None,
                        )
                    )
    return held


def test_split_finds_a_benefit_planted_in_the_drop_hold_and_nowhere_else():
    held, names = invented(), [f"s{s}" for s in range(6)]
    made = positions.table(held, names, PLAN)
    assert set(made) == set(positions.KINDS) and sum(v["holds"] for v in made.values()) == len(held)
    assert sum(v["share_of_flagged_holds"] for v in made.values()) == pytest.approx(1.0)
    drop = made["drop"]["utility"]
    assert drop["flagged"]["mean"] == pytest.approx(3.0) and drop["all_holds"]["mean"] == pytest.approx(3.0)
    assert drop["flagged"]["sources"] == 6 and made["room"]["utility"]["flagged"]["mean"] == pytest.approx(
        0.0
    )
    assert made["drop"]["ontime_fraction"]["flagged"]["mean"] == pytest.approx(0.0)
    said = positions.reading(made)
    assert said["sits_in_the_hold_of_the_drop"] and said["helps_in_the_drop_hold_whatever_the_flag"]
    assert not said["flag_finds_a_usable_state"] and said["intervals_not_corrected_for_the_number_of_kinds"]
    assert said["benefit_among_flagged_holds"] == {k: k == "drop" for k in positions.KINDS}
    elsewhere = positions.reading(positions.table(invented(planted="after_drop"), names, PLAN))
    assert elsewhere["flag_finds_a_usable_state"] and not elsewhere["sits_in_the_hold_of_the_drop"]
    assert not elsewhere["helps_in_the_drop_hold_whatever_the_flag"]
    # Sources outside the registered analysis are left out, and a cell needs every arm.
    fewer = positions.table(held, names[:4], PLAN)
    assert fewer["drop"]["utility"]["flagged"]["sources"] == 4
    thin = [
        h
        for h in held
        if not (h["source"] == "s0" and positions.kind(h["regime"], h["epoch"]) == "drop" and h["arm"] == 2)
    ]
    assert positions.table(thin, names, PLAN)["drop"]["utility"]["flagged"]["sources"] == 5


def test_addendum_runs_after_the_registered_final_and_changes_nothing(tmp_path, capsys):
    b1.dry_run(tmp_path / "dry", "benefit_above_the_gate", seed=3)
    protocol, final = tmp_path / "dry/plan/protocol.json", tmp_path / "dry/final.json"
    roots = [tmp_path / "dry/block-one", tmp_path / "dry/block-two"]
    before = final.read_bytes()
    report = positions.positions(protocol, roots, final)
    assert report["addendum"] and report["part_of_the_registration"] is False and report["mock"] is True
    assert report["changes_the_registered_outcome"] is False and final.read_bytes() == before
    assert report["registered_outcome"] == json.loads(before)["outcome"]
    assert report["analysed_sources"] == len(json.loads(before)["sources"])
    kinds = report["kinds"]
    assert kinds["before_drop"]["holds"] == kinds["drop"]["holds"] == kinds["after_drop"]["holds"]
    assert sum(v["share_of_flagged_holds"] for v in kinds.values()) == pytest.approx(1.0)
    assert set(report["reading"]["benefit_among_flagged_holds"]) == set(positions.KINDS)
    with pytest.raises(ValueError, match="registered final report comes first"):
        positions.positions(protocol, roots, protocol)
    out = tmp_path / "positions.json"
    args = ["--protocol", str(protocol), "--final", str(final), "--out", str(out)]
    for root in roots:
        args += ["--capture", str(root)]
    positions.main(args)
    assert (
        json.loads(out.read_text())["abi"] == positions.ABI
        and "flag_finds_a_usable_state" in capsys.readouterr().out
    )
    with pytest.raises(SystemExit):
        positions.main(args)
