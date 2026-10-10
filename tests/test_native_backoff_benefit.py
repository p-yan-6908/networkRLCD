"""Phase B1: flag, estimator, outcomes, planner and the capture-to-outcome path on test doubles.

Nothing here is native evidence. Collector and raw auditor are replaced by doubles, and every
value is invented.
"""

import gzip
import json
import subprocess
import tomllib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from media_rl import native_backoff_benefit as benefit
from media_rl import native_backoff_benefit_panel as b1
from media_rl.native_protocol import read_json, write_json

PLAN = benefit.Plan().validate()
STRATA = np.arange(30) % 3


def hold(source, trial, epoch, arm, bwe, utility=25.0, complete=True, **more):
    row = dict(source=source, trial_id=trial, epoch=epoch, arm=arm, base_bwe_bps=bwe, utility=utility)
    return dict(row, complete=complete, ontime_fraction=0.8, jitter_ms=5.0, rtt_ms=50.0, **more)


def test_registration_matches_the_coded_plan_and_rejects_inconsistent_ones():
    registration = benefit.load_registration(b1.REGISTRATION)
    assert registration.plan == PLAN and registration.capture == benefit.Capture()
    assert registration.secondary_flags == dict(jitter_ms=12.0, rtt_ms=57.0)
    assert PLAN.growth_limit == 1.05 and PLAN.weights == [0.5, 0.5, -1.0]
    assert PLAN.practical_gate == 1.0 and PLAN.minimum_sources == 30 and PLAN.alpha == 0.025
    assert {s.name for s in registration.scenarios} >= {"benefit_at_the_gate", "no_benefit"}
    for bad in (
        dict(weights=[1.0, 0.0, -0.5]),
        dict(weights=[-1.0, 0.0, 1.0]),
        dict(minimum_sources=31),
        dict(minimum_sources=3),
        dict(alpha=0.6),
        dict(abi="other"),
        dict(maximum_skipped_share=1.0),
    ):
        with pytest.raises(ValueError):
            replace(PLAN, **bad).validate()


def test_flag_compares_consecutive_frozen_estimates_of_one_peer():
    rows = [
        hold("s", "a", 0, 0, 1000.0),
        hold("s", "a", 1, 1, 1049.0),  # grew by less than 5%: flagged
        hold("s", "a", 2, 2, 1101.5),  # exactly 1.05 times is not below the limit
        hold("s", "a", 3, 0, 900.0),  # fell: flagged
        hold("s", "b", 0, 2, 500.0),
        hold("s", "b", 2, 1, 400.0),  # its predecessor is missing: left out
    ]
    held = benefit.flag_rows(rows, PLAN)
    assert [(r["trial_id"], r["epoch"], r["flagged"]) for r in held] == [
        ("a", 1, True),
        ("a", 2, False),
        ("a", 3, True),
    ]
    assert held[0]["following"]["epoch"] == 2 and held[2]["following"] is None
    assert [r["previous_arm"] for r in held] == [0, 1, 2]
    # The previous hold's estimate is used whether or not that hold was complete.
    censored = [dict(rows[0], complete=False), *rows[1:]]
    assert [r["flagged"] for r in benefit.flag_rows(censored, PLAN)] == [True, False, True]
    loud = [dict(r, jitter_ms=None if r["epoch"] == 1 else 20.0 * r["epoch"]) for r in rows]
    marked = benefit.flag_rows(loud, PLAN, "jitter_ms", 45.0)
    assert [(r["epoch"], r["flagged"]) for r in marked] == [
        (2, False),
        (3, True),
    ]  # absent values are left out


def test_benefit_is_a_contrast_of_arm_means_over_flagged_holds_and_needs_every_arm():
    rows, level = [], {0: 27.0, 1: 26.0, 2: 24.0}
    for peer in range(9):
        arm = peer % 3
        rows += [hold("s", f"p{peer}", 0, 0, 1000.0), hold("s", f"p{peer}", 1, arm, 1000.0, level[arm])]
        rows += [hold("s", f"p{peer}", 2, 0, 2000.0, 30.0 + arm)]  # not flagged; scored as the next hold
    held = benefit.flag_rows(rows, PLAN)
    values, thin = benefit.source_benefits(held, PLAN)
    assert thin == [] and values["s"] == pytest.approx((27.0 + 26.0) / 2 - 24.0)
    assert benefit.source_benefits(held, PLAN, weights=[1.0, 0.0, -1.0])[0]["s"] == pytest.approx(3.0)
    assert benefit.source_benefits(held, PLAN, following=True)[0]["s"] == pytest.approx(0.5 - 2.0)
    assert benefit.source_benefits(held, PLAN, flagged=False)[1] == ["s"]  # the other holds are all at arm 0
    assert benefit.source_benefits(held, replace(PLAN, minimum_flagged_cell=4))[1] == ["s"]
    incomplete = [dict(r, complete=False) if r["epoch"] == 1 and r["arm"] == 2 else r for r in rows]
    assert benefit.source_benefits(benefit.flag_rows(incomplete, PLAN), PLAN)[1] == ["s"]
    support = benefit.flagged_support(held, PLAN)
    assert support["holds_with_a_predecessor"] == 18 and support["flagged_share"] == 0.5
    assert support["smallest_flagged_cell"] == 3
    assert support["share_of_flagged_holds_after_the_top_ratio"] == 0.0  # every flagged hold follows arm 0


def test_four_outcomes_follow_the_two_registered_statements():
    wobble = np.tile([-1.0, 0.0, 1.0], 10)
    cases = (
        (2.5, 2.0, benefit.OUTCOMES[0]),  # clearly helps, and may exceed the gate
        (0.4, 0.3, benefit.OUTCOMES[1]),  # helps, and the whole interval is below the gate
        (0.0, 0.5, benefit.OUTCOMES[2]),  # nothing shown, and anything larger than the gate is excluded
        (0.5, 3.0, benefit.OUTCOMES[3]),  # too noisy for either statement
        (-1.0, 2.0, benefit.OUTCOMES[2]),  # backing off hurts: no relevant benefit
    )
    for mean, spread, expected in cases:
        result = benefit.analyse(mean + spread * wobble, STRATA, PLAN)
        assert result["outcome"] == expected, (mean, spread, result)
        assert result["backing_off_helps"] == (result["lower_bound"] > 0)
        assert result["benefit_below_practical_gate"] == (result["upper_bound"] < 1.0)
        assert result["sources"] == 30 and result["degrees_of_freedom"] == 29
    with pytest.raises(ValueError, match="equal numbers of sources"):
        benefit.analyse(np.ones(30), np.r_[np.zeros(11), np.ones(9), 2 * np.ones(10)], PLAN)
    with pytest.raises(ValueError, match="at least two sources per stratum"):
        benefit.analyse(np.ones(3), np.arange(3), PLAN)


def test_power_table_is_planning_only_and_matches_the_registered_figures():
    registration = benefit.load_registration(b1.REGISTRATION)
    table = benefit.power_table(PLAN, registration.planning)
    assert table["planning_only"] is True
    row = next(r for r in table["rows"] if r["sources"] == 42 and r["per_source_sd"] == 2.27)
    assert row["power"]["1"] == pytest.approx(0.80, abs=0.01) and row["power"]["1.5"] > 0.98
    assert row["interval_half_width"] == pytest.approx(0.71, abs=0.01)
    assert benefit.power(30, 1.0, 2.27) < benefit.power(42, 1.0, 2.27) < benefit.power(42, 1.5, 2.27)


def test_allocation_is_seeded_balanced_without_reserve_and_excludes_touched_clusters():
    clips = b1.n1.mock_clips(12)
    sources = b1.allocate(clips, [], PLAN, seed=5)
    assert len(sources) == 36 and [s["b1_order"] for s in sources] == list(range(36))
    assert [s["complexity_stratum"] for s in sources] == list(b1.STRATA) * 12
    assert len({s["cluster_id"] for s in sources}) == 36 and sources == b1.allocate(clips, [], PLAN, seed=5)
    assert [s["cluster_id"] for s in sources] != [s["cluster_id"] for s in b1.allocate(clips, [], PLAN, 6)]
    touched = sources[0]
    again = b1.allocate(clips, [dict(sha256=touched["source_sha256"], segment=[0, 1])], PLAN, seed=5)
    assert (
        touched["cluster_id"] not in {s["cluster_id"] for s in again} and len(again) == 33
    )  # a whole block goes
    with pytest.raises(ValueError, match="B1 needs 10 fresh independent"):
        b1.allocate(b1.n1.mock_clips(9), [], PLAN, seed=5)


def test_plan_checks_randomisation_balance_cell_minima_and_independence():
    sources = b1.allocate(b1.n1.mock_clips(10), [], PLAN, seed=5)
    runtimes = {b1.PREFIX + s["clip_id"]: b1.mock_runtime(s, i, PLAN, 5) for i, s in enumerate(sources)}
    checks = b1.verify_plan(sources, runtimes, PLAN)
    assert checks["planned_peers"] == 30 * 4 * 10 and checks["planned_cohorts"] == 7200
    assert checks["smallest_planned_cell"] >= PLAN.minimum_cell_cohorts
    planned = b1.n1.planned_assignments(runtimes)
    assert all(a["arm"] == b1.control.assigned_arm(a["seed"], a["epoch"]) for a in planned)
    assert all(t["id"].startswith("b1-") for r in runtimes.values() for t in r["episodes"])
    key = b1.PREFIX + sources[0]["clip_id"]
    reused = dict(
        runtimes, **{key: dict(episodes=[dict(t, exploration_seed=7) for t in runtimes[key]["episodes"]])}
    )
    with pytest.raises(ValueError, match="own assignment seed"):
        b1.verify_plan(sources, reused, PLAN)
    with pytest.raises(ValueError, match="below the minimum"):
        b1.verify_plan(sources, runtimes, replace(PLAN, minimum_cell_cohorts=40))
    with pytest.raises(ValueError, match="stratum-balanced blocks"):
        b1.verify_plan([sources[1], sources[0], *sources[2:]], runtimes, PLAN)
    with pytest.raises(ValueError, match="at least the registered minimum"):
        b1.verify_plan(sources[:27], runtimes, PLAN)


@pytest.fixture
def native(tmp_path, monkeypatch):
    """A small B1 study on doubles: the real planner and runtime builder, a fake collector and auditor."""
    small = replace(PLAN, minimum_sources=6, peers_per_regime=6)
    template = tmp_path / "template.json"
    conditions = {"random-hold-a": dict(model="frozen")}
    write_json(template, dict(conditions=conditions, repair_model=None, learner=None, order_seed=10))
    capture = benefit.Capture(seed=23, template=str(template), reservation_root=str(tmp_path / "results"))
    registered = benefit.load_registration(b1.REGISTRATION)
    registration = benefit.Registration(
        small, capture, registered.secondary_flags, registered.planning, registered.scenarios
    )
    clips = b1.n1.mock_clips(3)
    pool = dict(clips=clips, catalogs={c["source_sha256"]: dict(sha256=c["source_sha256"]) for c in clips})
    real_seal = b1.verify_seal
    monkeypatch.setattr(b1.benefit, "load_registration", lambda path: registration)
    monkeypatch.setattr(b1, "verify_freeze", lambda *a: dict(files=4, sha256="f" * 64, verified=True))
    monkeypatch.setattr(b1.assets, "verify_controller_freeze", lambda *a: dict(verified=True))
    monkeypatch.setattr(b1.physical.donor, "compatible_engines", lambda p: True)
    monkeypatch.setattr(b1.panel, "_screen", lambda path: pool)
    parent = b1.physical.donor.PARENT_SEAL
    monkeypatch.setattr(
        b1, "verify_seal", lambda root, stage=None: {} if stage == parent else real_seal(root, stage)
    )
    (tmp_path / "results").mkdir()
    (tmp_path / "screen.json").write_text("{}")
    state = dict(unflaggable=set())

    def collector(args, **kwargs):
        child = Path(args[2])
        child.mkdir()
        with gzip.open(child / "events.jsonl.gz", "wt") as stream:
            stream.write(json.dumps(dict(kind="phase", capacity_mbps=0.6)) + "\n")
        return subprocess.CompletedProcess(args, 0)

    def auditor(child, runtime, trial):
        rng = np.random.default_rng(trial["exploration_seed"])
        scenario = benefit.Scenario("double", 2.0, -0.5, 0.0, 0.2)
        rows = b1.synthetic_cohorts(trial, 0.0, scenario, small, rng)
        rows = [{k: v for k, v in r.items() if k != "mock"} for r in rows]
        if trial["cluster_id"] in state["unflaggable"]:  # an estimate that always doubles is never flagged
            for r in rows:
                r["base_bwe_bps"] = 1e5 * 2 ** r["epoch"]
        return dict(id=trial["id"]), dict(wire=dict(fifo_capacity_accounting_verified=True)), rows

    monkeypatch.setattr(b1.subprocess, "run", collector)
    monkeypatch.setattr(b1.physical, "audit_peer", auditor)
    protocol = b1.plan_study(tmp_path / "screen.json", tmp_path / "results/b1-plan")
    return dict(
        root=tmp_path, path=tmp_path / "results/b1-plan/protocol.json", protocol=protocol, state=state
    )


def test_planner_seals_a_plan_that_reuses_the_unchanged_runtime_and_reserves_its_sources(native):
    protocol, root = native["protocol"], native["root"]
    assert protocol["checks"]["sources"] == 9 and protocol["outcomes_observed"] is False
    assert (
        protocol["secondary_flags"] == dict(jitter_ms=12.0, rtt_ms=57.0)
        and "interim_custodian" not in protocol
    )
    for runtime in protocol["runtimes"].values():
        assert runtime["stage"] == b1.RUNTIME_STAGE and runtime["measurement_recipe"] == b1.physical.RECIPE
        assert runtime["panel_abi"] == b1.physical.ABI and len(runtime["episodes"]) == 24
        assert {t["network_regime"] for t in runtime["episodes"]} == set(b1.REGIMES)
    assert b1.sealed_protocol(native["path"]) == protocol  # re-derived from its inputs, identical
    excluded, inputs = b1.physical.reservations.reservations(root / "results")
    assert {e["sha256"] for e in excluded} == {s["source_sha256"] for s in protocol["sources"]}
    assert str(native["path"].resolve()) in inputs
    with pytest.raises(ValueError, match="the thinnest has 0"):  # the first plan already reserved them
        b1.plan_study(root / "screen.json", root / "results/again")
    with pytest.raises(ValueError, match="assignments/runtime mismatch"):
        b1.validate_plan(dict(protocol, sources=protocol["sources"][::-1]))


def test_capture_analyses_nothing_and_the_final_waits_for_every_planned_source(native):
    root, path = native["root"], native["path"]
    done = b1.capture(path, root / "results/block-1", 0, 6)
    assert done == dict(native_peers=144, assigned_cohorts=864, sources=6)
    names = {p.name for p in (root / "results/block-1").iterdir() if p.is_file()}
    assert "report.json" not in names and "cohorts.json" in names  # collecting unblinds no one
    manifest = read_json(root / "results/block-1/manifest.json")
    assert manifest["stage"] == b1.CAPTURE_STAGE and manifest["outcome_statistics_computed"] is False
    with pytest.raises(ValueError, match="fresh B1 capture path"):
        b1.capture(path, root / "results/block-1", 0, 6)
    with pytest.raises(ValueError, match="whole stratum-balanced blocks"):
        b1.capture(path, root / "results/odd", 0, 5)
    roots = [root / "results/block-1"]
    progress = b1.status(path, roots)
    assert progress["outcome_free"] and not progress["final_can_run"] and progress["captured_sources"] == 6
    assert 0.2 < progress["flag"]["flagged_share"] < 0.8 and progress["support"]["passed"]
    assert not {"mean_benefit", "outcome", "primary"} & set(json.dumps(progress).replace('"', " ").split())
    with pytest.raises(ValueError, match="every planned source must be captured"):
        b1.final(path, roots, root / "early.json")
    assert not (root / "early.json").exists()
    b1.capture(path, root / "results/block-2", 6, 9)
    roots.append(root / "results/block-2")
    assert b1.status(path, roots)["final_can_run"]
    report = b1.final(path, roots, root / "final.json")
    assert report["outcome"] == "helps" and report["mock"] is False and report["capture_support_passed"]
    assert (
        report["primary"]["mean_benefit"] == pytest.approx(2.0, abs=0.3) and report["primary"]["sources"] == 9
    )
    assert report["perceptual_quality_claims"] is False and report["learned_controller_promoted"] is False
    secondary = report["secondary"]
    assert set(secondary["each_lower_ratio"]) == {"0.65 - 1.05", "0.85 - 1.05"}
    assert secondary["other_holds"]["mean"] == pytest.approx(-0.5, abs=0.3)
    assert set(secondary["alternative_flags"]) == {"jitter_ms above 12", "rtt_ms above 57"}
    split = secondary["by_previous_request"]
    assert set(split) == {"previous hold at 1.05", "previous hold at 0.65 or 0.85"}
    assert split["previous hold at 0.65 or 0.85"]["mean"] == pytest.approx(2.0, abs=0.5)
    assert all(v["sources"] <= 9 for v in split.values())
    assert 0 < report["support"]["flag"]["share_of_flagged_holds_after_the_top_ratio"] < 1
    assert set(secondary["by_regime"]) == set(b1.REGIMES) and secondary["none_of_these_changes_the_outcome"]
    assert secondary["actuator_replication"]["0.85 - 0.65"]["mean"] == pytest.approx(0.14, abs=0.01)
    assert set(report["b1_code_and_registration_sha256"]) == set(b1.FROZEN)
    with pytest.raises(ValueError, match="written once"):
        b1.final(path, roots, root / "final.json")
    rows = read_json(root / "results/block-1/cohorts.json")
    with pytest.raises(ValueError, match="planned randomisation"):
        b1.estimator_rows([dict(rows[0], arm=(rows[0]["arm"] + 1) % 3), *rows[1:]], native["protocol"])
    with pytest.raises(ValueError, match="forged propensity"):
        b1.estimator_rows([dict(rows[0], propensity=0.5), *rows[1:]], native["protocol"])
    with pytest.raises(ValueError, match="outside the sealed plan or duplicated"):
        b1.estimator_rows([rows[0], *rows], native["protocol"])
    with pytest.raises(ValueError, match="measured rates and quality"):
        b1.estimator_rows([dict(rows[0], utility=None), *rows[1:]], native["protocol"])
    with pytest.raises(ValueError, match="captured once"):
        b1.status(path, [roots[0], roots[0]])


def test_a_source_the_flag_never_marks_is_passed_over_and_the_terciles_stay_equal(native):
    root, path, sources = native["root"], native["path"], native["protocol"]["sources"]
    native["state"]["unflaggable"] = {sources[1]["cluster_id"]}
    b1.capture(path, root / "results/all", 0, 9)
    progress = b1.status(path, [root / "results/all"])
    assert progress["not_evaluable_sources"] == [sources[1]["cluster_id"]]
    report = b1.final(path, [root / "results/all"], root / "final.json")
    support = report["support"]
    assert (
        support["skipped_sources"] == 1
        and support["analysed_sources"] == 6
        and support["trimmed_for_balance"] == 2
    )
    assert sources[1]["cluster_id"] not in report["sources"] and len(report["sources"]) == 6
    tercile = {s["cluster_id"]: s["complexity_stratum"] for s in sources}
    assert [tercile[n] for n in report["sources"]] == list(b1.STRATA) * 2
    # One of nine planned sources is more than the registered tenth, so support fails: inconclusive.
    assert report["capture_support_passed"] is False and report["outcome"] == "inconclusive"
    assert (
        report["primary"]["outcome"] == "helps"
    )  # the estimate is reported, the outcome is not taken from it


def test_dry_run_goes_from_plan_to_outcome_on_mock_rows_only(tmp_path, native):
    summary = b1.dry_run(tmp_path / "dry", "benefit_above_the_gate", seed=3)
    assert summary["mock"] and summary["proves_nothing_about_the_native_stack"]
    assert summary["plan_checks"]["sources"] == 12 and summary["outcome_on_mock_rows"] in benefit.OUTCOMES
    assert not summary["status_after_first_block"]["final_can_run"]
    assert summary["status_before_final"]["final_can_run"]
    assert read_json(tmp_path / "dry/final.json")["mock"] is True
    with pytest.raises(ValueError, match="mock plan cannot drive a native capture"):
        b1.capture(tmp_path / "dry/plan/protocol.json", tmp_path / "dry/native", 0, 6)
    scenario = benefit.Scenario("x", 1.0, 0.0, 0.0, 0.1)
    with pytest.raises(ValueError, match="only follow a mock plan"):
        b1.mock_capture(native["path"], tmp_path / "fake", 0, 6, scenario, 1)
    with pytest.raises(ValueError, match="different sealed plan"):
        b1.status(native["path"], [tmp_path / "dry/block-one"])


def test_registered_scenarios_reach_the_outcomes_they_describe(tmp_path):
    expected = dict(
        benefit_above_the_gate="helps",
        small_benefit="helps_below_practical_gate",
        no_benefit="no_practically_relevant_benefit",
    )
    for name, outcome in expected.items():
        assert b1.dry_run(tmp_path / name, name, seed=7)["outcome_on_mock_rows"] == outcome


def test_freeze_binds_registration_implementation_and_the_n1_code_it_reuses(tmp_path):
    record = b1.freeze_record()
    assert set(record["files"]) == set(b1.FROZEN) and record["native_data_collected"] is False
    assert record["controller_freeze_sha256"] == b1.digest(b1.assets.FREEZE)
    assert record["n1_freeze_sha256"] == read_json(b1.n1.FREEZE)["sha256"]
    path = tmp_path / "freeze.json"
    assert b1.write_freeze(path) == record and b1.verify_freeze(path)["verified"]
    with pytest.raises(FileExistsError):
        b1.write_freeze(path)
    drifted = tmp_path / "drifted.json"
    write_json(drifted, dict(record, files=dict(record["files"], **{b1.FROZEN[0]: "0" * 64})))
    with pytest.raises(ValueError, match="changed after it was frozen"):
        b1.verify_freeze(drifted)


def test_committed_freeze_still_matches_the_registration_and_its_code():
    assert b1.verify_freeze() == dict(
        files=len(b1.FROZEN), sha256=read_json(b1.FREEZE)["sha256"], verified=True
    )


def test_public_cli_is_registered():
    scripts = tomllib.loads(Path("pyproject.toml").read_text())["project"]["scripts"]
    assert scripts["media-backoff-benefit"] == "media_rl.native_backoff_benefit_panel:main"
    assert all((b1.ROOT / name).is_file() for name in b1.FROZEN)
