"""Phase N1: estimator, blinded rule, planner and the capture-to-verdict path on test doubles.

Nothing here is native evidence. Collector and raw auditor are replaced by doubles, and every
rate is invented.
"""

import gzip
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from media_rl import native_actuator_qualification_panel as n1
from media_rl.native_actuator_qualification import (
    HETEROGENEOUS,
    Capture,
    Plan,
    Registration,
    Scenario,
    analyse,
    blinded_interim,
    decide,
    load_registration,
    operating_characteristics,
    power_report,
    required_sources,
    rule_table,
    simulate,
    source_contrasts,
    support,
)
from media_rl.native_protocol import read_json, write_json

PLAN = Plan().validate()
STRATA = np.arange(12) % 3


def cohorts(sources, lower=0.10, upper=0.10, plan=PLAN, seed=0, noise=0.0):
    """Balanced assigned cohorts: every source x regime x arm cell has the same count."""
    rng = np.random.default_rng(seed)
    rows = []
    for index, source in enumerate(sources):
        shift = 0.01 * (index % 4)  # sources differ, so contrast variances are not zero
        for regime in range(plan.regimes):
            for arm in range(3):
                for _ in range(plan.minimum_cell_cohorts + 1):
                    level = 0.5 + (arm >= 1) * (lower + shift) + (arm == 2) * (upper - shift)
                    value = (level + rng.normal(0, noise)) * 1e6
                    row = dict(source=source, regime=regime, arm=arm, base_bwe_bps=1e6, encoder_bps=value)
                    rows.append(dict(row, complete=True))
    return rows


def test_registration_matches_the_coded_plan_and_rejects_inconsistent_ones():
    registration = load_registration(n1.REGISTRATION)
    assert registration.plan == PLAN and registration.capture == Capture()
    assert len(registration.scenarios) >= 8 and registration.scenarios[0].name == "n2_assumptions"
    assert PLAN.first_stage_sources == 12 and PLAN.maximum_sources == 24 and PLAN.margin == 0.03
    assert PLAN.peers_per_regime == 10 and PLAN.alpha == 0.025  # full level per contrast, no Bonferroni
    for change in (
        dict(margin=0.12),  # margin above the design effect
        dict(design_effect=0.3),  # more than the requested step
        dict(first_stage_sources=13),  # not whole stratum-balanced blocks
        dict(maximum_sources=9),
        dict(abi="native_actuator_source_panel_v2"),  # N2 is a different study
    ):
        with pytest.raises(ValueError):
            replace(PLAN, **change).validate()


def test_source_contrasts_weight_regimes_equally_and_refuse_thin_cells():
    rows = cohorts(["a", "b"], lower=0.12, upper=0.07)
    contrasts, unevaluable = source_contrasts(rows, PLAN)
    assert unevaluable == [] and contrasts["a"] == pytest.approx([0.12, 0.07])
    assert contrasts["b"] == pytest.approx([0.13, 0.06])
    doubled = rows + [r for r in rows if r["regime"] == 0]  # more cohorts in one regime, same cell means
    assert source_contrasts(doubled, PLAN)[0]["a"] == pytest.approx(contrasts["a"])
    incomplete = [
        dict(r, complete=not (r["source"] == "b" and r["regime"] == 2 and r["arm"] == 1)) for r in rows
    ]
    contrasts, unevaluable = source_contrasts(incomplete, PLAN)
    assert unevaluable == ["b"] and set(contrasts) == {"a"}  # never estimated from the cells that remain
    send = [dict(r, send_bps=2 * r["encoder_bps"]) for r in rows]
    assert source_contrasts(send, PLAN, key="send_bps")[0]["a"] == pytest.approx([0.24, 0.14])
    assert source_contrasts(rows, PLAN, regime=3)[0]["a"] == pytest.approx([0.12, 0.07])


def test_support_gates_ignore_outcomes():
    rows = cohorts([f"s{i}" for i in range(12)])
    assert support(rows, PLAN)["passed"]
    shifted = [dict(r, encoder_bps=r["encoder_bps"] * (3 if r["arm"] == 2 else 1)) for r in rows]
    assert support(shifted, PLAN) == support(rows, PLAN)
    lossy = [dict(r, complete=not (r["arm"] == 2 and i % 4 == 0)) for i, r in enumerate(rows)]
    assert not support(lossy, PLAN)["passed"]  # one arm loses far more cohorts than the others
    aliased = [dict(r, clipped_or_aliased=i % 5 == 0) for i, r in enumerate(rows)]
    assert not support(aliased, PLAN)["passed"]


def test_blinded_rule_depends_on_variances_only_and_can_only_add_sources():
    table = rule_table(PLAN)
    assert [row["total"] for row in table["rows"]] == [12, 15, 18, 21, 24] and table[
        "degrees_of_freedom"
    ] == 11
    previous = 0
    for sd in (0.01, 0.05, 0.065, 0.07, 0.078, 0.084, 0.12, 0.15):
        rule = required_sources([sd**2, 0.0001], PLAN)
        assert 12 <= rule["total"] <= 24 and rule["total"] % 3 == 0 and rule["total"] >= previous
        assert rule["total"] == required_sources([0.0001, sd**2], PLAN)["total"]  # the worse contrast decides
        assert not rule["precision_futility"]
        previous = rule["total"]
    for row in table["rows"]:
        assert (
            required_sources([row["largest_first_stage_sd"] ** 2 * 0.999] * 2, PLAN)["total"] == row["total"]
        )
    futile = required_sources([(table["precision_futility_above_sd"] * 1.01) ** 2] * 2, PLAN)
    assert (
        futile["total"] == 12 and futile["precision_futility"]
    )  # too imprecise to pursue, nothing about the effect


def test_interim_exposes_only_the_total_and_seals_the_variances():
    sources = [f"s{i}" for i in range(12)]
    small = blinded_interim(cohorts(sources, lower=0.04, upper=0.04, noise=0.01), sources, PLAN)
    large = blinded_interim(cohorts(sources, lower=0.19, upper=0.19, noise=0.01), sources, PLAN)
    # Same noise draws, different separation: neither part moves.
    assert small["public"] == large["public"]
    assert small["sealed"]["contrast_variances"] == pytest.approx(
        large["sealed"]["contrast_variances"], rel=1e-9
    )
    public = small["public"]
    assert set(public) == {"abi", "first_stage_sources", "prescribed_total_sources", "support", "released"}
    assert public["prescribed_total_sources"] == 12 and "variance" not in json.dumps(public)
    assert set(small["sealed"]) >= {"contrast_variances", "precision_futility", "uncapped_sources"}
    wide = [
        dict(r, encoder_bps=r["encoder_bps"] + 5e5 * (int(r["source"][1:]) % 3 - 1) * (r["arm"] == 2))
        for r in cohorts(sources)
    ]
    spread = blinded_interim(wide, sources, PLAN)
    assert spread["sealed"]["precision_futility"] and spread["public"]["prescribed_total_sources"] == 12
    # A total of twelve reads the same whether precision was ample or futile.
    assert {k for k in spread["public"]} == set(public)
    with pytest.raises(ValueError, match="not evaluable"):
        blinded_interim(cohorts(sources[:11]), sources, PLAN)


def test_three_outcomes_and_the_two_stage_standard_error():
    wobble = np.tile([-0.02, 0.0, 0.02, 0.0], 3)[:, None]
    clear = decide(0.12 + wobble * [1, -1], STRATA, PLAN)
    assert (
        clear["verdict"] == "qualified" and clear["designation"] is None and clear["degrees_of_freedom"] == 11
    )
    assert clear["separating_sources"] == 12
    assert clear["separating_share_lower_bound"] == pytest.approx(0.025 ** (1 / 12))
    assert clear["realised_share_of_requested_step"] == pytest.approx([0.6, 0.6])
    assert decide(0.0 + wobble * [1, -1], STRATA, PLAN)["verdict"] == "not_separable_at_threshold"
    assert decide(0.035 + wobble * [1, -1], STRATA, PLAN)["verdict"] == "inconclusive"
    one_low = np.column_stack([0.12 + wobble[:, 0], 0.0 + wobble[:, 0]])
    assert (
        decide(one_low, STRATA, PLAN)["verdict"] == "not_separable_at_threshold"
    )  # either contrast suffices
    with pytest.raises(ValueError, match="prescribed 12"):
        decide(0.12 + np.tile(wobble, (2, 1)) * [1, -1], np.arange(24) % 3, PLAN)
    with pytest.raises(ValueError, match="equal numbers"):
        analyse(0.12 + wobble * [1, -1], np.array([0] * 6 + [1] * 3 + [2] * 3), PLAN)
    rng = np.random.default_rng(5)
    first = 0.10 + rng.normal(0, 0.07, (12, 2))
    total = required_sources(first.var(axis=0, ddof=1), PLAN)["total"]
    assert total > 12
    strata = np.arange(total) % 3
    calm = decide(np.vstack([first, np.full((total - 12, 2), 0.10)]), strata, PLAN)
    swing = np.tile([[0.3, -0.3], [-0.3, 0.3]], (total, 1))[: total - 12]
    wild = decide(np.vstack([first, 0.10 + swing]), strata, PLAN)
    width = lambda r: np.subtract(r["upper_bounds"], r["lower_bounds"])  # noqa: E731
    assert width(calm) == pytest.approx(width(wild))  # second-stage spread never enters the standard error


def test_complexity_is_a_diagnostic_with_uncertainty_not_a_gate():
    wobble = np.tile([-0.02, 0.0, 0.02, 0.0], 3)
    low_stratum_flat = np.column_stack([0.12 + wobble, np.where(STRATA == 0, 0.02, 0.11) + wobble / 4])
    mixed = decide(low_stratum_flat, STRATA, PLAN)
    assert mixed["verdict"] == "qualified" and mixed["designation"] == HETEROGENEOUS
    detail = mixed["complexity"]
    assert detail["diagnostic_only"] and detail["no_flag_is_not_evidence_of_uniformity"]
    assert detail["sources_per_stratum"] == 4 and len(detail["intervals95"]) == 3
    assert all(
        low < mean < high
        for row, means in zip(detail["intervals95"], detail["means"])
        for (low, high), mean in zip(row, means)
    )
    assert detail["heterogeneity_p_values"][1] < 0.001 < detail["heterogeneity_p_values"][0]
    # One noisy tercile mean below the margin is not a finding: no flag without evidence that strata differ.
    per_stratum = [[-0.10, 0.12, -0.02, 0.08], [0.02, 0.18, 0.10, 0.06], [0.15, 0.01, 0.11, 0.09]]
    noisy = np.column_stack([0.12 + wobble, [per_stratum[i % 3][i // 3] for i in range(12)]])
    assert noisy[STRATA == 0, 1].mean() < PLAN.margin  # the low tercile's mean sits below the margin
    result = analyse(noisy, STRATA, PLAN)
    assert not result["complexity"]["heterogeneous_by_complexity"] and result["designation"] is None
    assert "uniform" not in json.dumps({k: v for k, v in result.items() if k != "complexity"})


def test_two_stage_test_holds_its_level_at_the_margin():
    """Normal per-source contrasts with the mean exactly at the margin: false qualification stays near alpha."""
    rng = np.random.default_rng(11)
    for sd in (0.03, 0.07, 0.11):
        draws, passed, failed, extended = 6000, 0, 0, 0
        samples = PLAN.margin + rng.normal(0, sd, (draws, PLAN.maximum_sources, 2))
        samples[:, :, 1] += 0.2  # only the lower contrast sits at the margin, the hardest case
        for sample in samples:
            total = required_sources(sample[:12].var(axis=0, ddof=1), PLAN)["total"]
            verdict = decide(sample[:total], np.arange(total) % 3, PLAN)["verdict"]
            passed += verdict == "qualified"
            failed += verdict == "not_separable_at_threshold"
            extended += total > 12
        assert 0.017 <= passed / draws <= 0.033, (sd, passed / draws)
        assert failed / draws <= 0.02  # the other verdict is held to the same level
        assert (extended > 0) == (sd > 0.05)


def test_simulation_reproduces_its_scenario_and_the_report_is_marked_as_planning():
    scenario = Scenario(
        "check", 0.10, 0.16, 0.03, 0.08, 0.1, saturating_strata=1, saturation=0.0, dead_regimes=1
    )
    x = simulate(np.random.default_rng(1), 300, 12, scenario, PLAN)
    assert x.shape == (300, 12, 2)
    assert x[:, :, 0].mean() == pytest.approx(0.75 * 0.10, abs=0.004)  # one of four regimes is dead
    assert x[:, 0::3, 1].mean() == pytest.approx(0.0, abs=0.006)  # the saturating stratum
    assert x[:, 1::3, 1].mean() == pytest.approx(0.75 * 0.16, abs=0.006)
    strong = operating_characteristics(
        Scenario("strong", 0.15, 0.15, 0.02, 0.08, 0.08), PLAN, draws=200, fixed=(6, 12)
    )
    assert (
        strong["designs"]["adaptive"]["qualified"] > 0.99
        and strong["designs"]["adaptive"]["mean_sources"] == 12
    )
    assert set(strong["designs"]) == {"adaptive", "fixed_6", "fixed_12"}
    absent = operating_characteristics(Scenario("absent", 0.0, 0.0, 0.02, 0.08, 0.08), PLAN, draws=200)
    assert absent["designs"]["adaptive"]["not_separable_at_threshold"] > 0.9
    assert absent["designs"]["adaptive"]["qualified"] == 0
    report = power_report(
        PLAN, load_registration(n1.REGISTRATION).scenarios[:1], draws=100, seed=3, fixed=(12,)
    )
    assert report["native_data_collected"] is False and report["models_fitted"] == 0
    assert (
        report["planning_assumptions_not_measurements"] is True and report["rule"]["degrees_of_freedom"] == 11
    )


# Planner and pipeline -----------------------------------------------------------------------


def test_allocation_is_seeded_stratum_balanced_and_excludes_touched_clusters():
    clips = n1.mock_clips(8)
    sources = n1.allocate(clips, [], PLAN, seed=5)
    assert len(sources) == 24 and [s["n1_order"] for s in sources] == list(range(24))
    assert [s["complexity_stratum"] for s in sources] == list(n1.STRATA) * 8  # 4/4/4 then 5/5/5 ... 8/8/8
    assert len({s["cluster_id"] for s in sources}) == 24
    assert sources == n1.allocate(clips, [], PLAN, seed=5)
    assert [s["cluster_id"] for s in sources] != [
        s["cluster_id"] for s in n1.allocate(clips, [], PLAN, seed=6)
    ]
    touched = sources[0]
    again = n1.allocate(clips, [dict(sha256=touched["source_sha256"], segment=[0, 1])], PLAN, seed=5)
    assert (
        touched["cluster_id"] not in {s["cluster_id"] for s in again} and len(again) == 21
    )  # a whole block goes
    assert (
        len(n1.allocate(n1.mock_clips(5), [], PLAN, seed=5)) == 15
    )  # one reserve block is all the pool allows
    with pytest.raises(ValueError, match="N1 needs 4 fresh independent"):
        n1.allocate(n1.mock_clips(3), [], PLAN, seed=5)
    twin = dict(clips[1], source_title=clips[0]["source_title"])  # same title filed under another cluster
    with pytest.raises(ValueError, match="pseudo-replication"):
        n1.allocate([clips[0], twin, *clips[2:]], [], PLAN, seed=5)


def test_plan_checks_randomisation_balance_cell_minima_and_independence():
    sources = n1.allocate(n1.mock_clips(8), [], PLAN, seed=5)
    runtimes = {"n1-" + s["clip_id"]: n1.mock_runtime(s, i, PLAN, 5) for i, s in enumerate(sources)}
    checks = n1.verify_plan(sources, runtimes, PLAN)
    assert checks["planned_peers"] == 24 * 4 * 10 and checks["planned_cohorts"] == 5760
    assert checks["smallest_planned_cell"] >= PLAN.minimum_cell_cohorts and checks["reserve_blocks"] == 4
    assert sum(checks["planned_arm_counts"]) == 5760 and checks["planned_arm_share_p_value"] >= 0.001
    planned = n1.planned_assignments(runtimes)
    assert all(
        a["arm"] == n1.control.assigned_arm(a["seed"], a["epoch"]) for a in planned
    )  # IID, never rebalanced
    key = "n1-" + sources[0]["clip_id"]
    reused = dict(
        runtimes, **{key: dict(episodes=[dict(t, exploration_seed=7) for t in runtimes[key]["episodes"]])}
    )
    with pytest.raises(ValueError, match="own assignment seed"):
        n1.verify_plan(sources, reused, PLAN)
    short = dict(runtimes, **{key: dict(episodes=runtimes[key]["episodes"][:-1])})
    with pytest.raises(ValueError, match="registered number of peers"):
        n1.verify_plan(sources, short, PLAN)
    with pytest.raises(ValueError, match="below the minimum"):
        n1.verify_plan(sources, runtimes, replace(PLAN, minimum_cell_cohorts=40))
    with pytest.raises(ValueError, match="stratum-balanced blocks"):
        n1.verify_plan([sources[1], sources[0], *sources[2:]], runtimes, PLAN)
    with pytest.raises(ValueError, match="whole stratum-balanced blocks"):
        n1.verify_plan(sources[:10], runtimes, PLAN)


@pytest.fixture
def native(tmp_path, monkeypatch):
    """A small N1 study on doubles: the real planner and runtime builder, a fake collector and auditor."""
    small = replace(PLAN, first_stage_sources=6, maximum_sources=12, peers_per_regime=6)
    template = tmp_path / "template.json"
    conditions = {"random-hold-a": dict(model="frozen")}
    write_json(template, dict(conditions=conditions, repair_model=None, learner=None, order_seed=10))
    capture = Capture(seed=19, template=str(template), reservation_root=str(tmp_path / "results"))
    registration = Registration(small, capture, load_registration(n1.REGISTRATION).scenarios)
    clips = n1.mock_clips(4)
    pool = dict(clips=clips, catalogs={c["source_sha256"]: dict(sha256=c["source_sha256"]) for c in clips})
    real_seal = n1.verify_seal
    monkeypatch.setattr(n1.qualification, "load_registration", lambda path: registration)
    monkeypatch.setattr(n1, "verify_freeze", lambda *a: dict(files=4, sha256="f" * 64, verified=True))
    monkeypatch.setattr(n1.assets, "verify_controller_freeze", lambda *a: dict(verified=True))
    monkeypatch.setattr(n1.physical.donor, "compatible_engines", lambda p: True)
    monkeypatch.setattr(n1.panel, "_screen", lambda path: pool)
    parent = n1.physical.donor.PARENT_SEAL
    monkeypatch.setattr(
        n1, "verify_seal", lambda root, stage=None: {} if stage == parent else real_seal(root, stage)
    )
    (tmp_path / "results").mkdir()
    (tmp_path / "screen.json").write_text("{}")
    state = dict(spread=0.0, censored=set())

    def collector(args, **kwargs):
        child = Path(args[2])
        child.mkdir()
        with gzip.open(child / "events.jsonl.gz", "wt") as stream:
            stream.write(json.dumps(dict(kind="phase", capacity_mbps=0.6)) + "\n")
        return subprocess.CompletedProcess(args, 0)

    def auditor(child, runtime, trial):
        rng = np.random.default_rng(trial["exploration_seed"])
        shift = state["spread"] * ((int(trial["cluster_id"][-4:], 16) % 9) - 4) / 4
        scenario = Scenario("double", 0.12, 0.12, 0.0, 0.01, 0.02)
        rows = n1.synthetic_cohorts(trial, (0.12 + shift, 0.12 - shift), scenario, rng)
        rows = [{k: v for k, v in r.items() if k != "mock"} for r in rows]
        for r in rows:
            if (trial["cluster_id"], trial["network_regime"], r["arm"]) in state["censored"]:
                r.update(complete=False, censor_reason="double", encoder_bps=None, send_bps=None)
        return dict(id=trial["id"]), dict(wire=dict(fifo_capacity_accounting_verified=True)), rows

    monkeypatch.setattr(n1.subprocess, "run", collector)
    monkeypatch.setattr(n1.physical, "audit_peer", auditor)
    protocol = n1.plan_study(tmp_path / "screen.json", tmp_path / "results/n1-plan", "Test Custodian")
    return dict(
        root=tmp_path, path=tmp_path / "results/n1-plan/protocol.json", protocol=protocol, state=state
    )


def test_planner_seals_a_plan_that_reuses_the_unchanged_runtime_and_reserves_its_sources(native):
    protocol, root = native["protocol"], native["root"]
    assert protocol["checks"]["sources"] == 12 and protocol["checks"]["reserve_blocks"] == 2
    assert protocol["interim_custodian"] == "Test Custodian" and protocol["outcomes_observed"] is False
    for runtime in protocol["runtimes"].values():
        assert runtime["stage"] == n1.RUNTIME_STAGE and runtime["measurement_recipe"] == n1.physical.RECIPE
        assert runtime["panel_abi"] == n1.physical.ABI and len(runtime["episodes"]) == 24
        assert {t["network_regime"] for t in runtime["episodes"]} == set(n1.REGIMES)
    assert n1.sealed_protocol(native["path"]) == protocol  # re-derived from its inputs, identical
    # The existing reservation scan now excludes every N1 source, so N2 cannot reuse one.
    excluded, inputs = n1.physical.reservations.reservations(root / "results")
    assert {e["sha256"] for e in excluded} == {s["source_sha256"] for s in protocol["sources"]}
    assert str(native["path"].resolve()) in inputs
    with pytest.raises(ValueError, match="name the interim custodian"):
        n1.plan_study(root / "screen.json", root / "results/other", "  ")
    # A second plan cannot draw the same sources: the first plan already reserved them.
    with pytest.raises(ValueError, match="0 available"):
        n1.plan_study(root / "screen.json", root / "results/again", "Test Custodian")
    forged = dict(protocol, sources=protocol["sources"][::-1])
    with pytest.raises(ValueError, match="assignments/runtime mismatch"):
        n1.validate_plan(forged)


def test_capture_analyses_nothing_and_the_blinded_path_reaches_a_verdict(native):
    root, path = native["root"], native["path"]
    done = n1.capture(path, root / "results/stage-one", 0, 6)
    assert done == dict(native_peers=144, assigned_cohorts=864, sources=6)
    names = {p.name for p in (root / "results/stage-one").iterdir() if p.is_file()}
    assert "report.json" not in names and "cohorts.json" in names  # collecting unblinds no one
    manifest = read_json(root / "results/stage-one/manifest.json")
    assert manifest["stage"] == n1.CAPTURE_STAGE and manifest["outcome_statistics_computed"] is False
    with pytest.raises(ValueError, match="fresh N1 capture path"):
        n1.capture(path, root / "results/stage-one", 0, 6)
    with pytest.raises(ValueError, match="whole stratum-balanced blocks"):
        n1.capture(path, root / "results/odd", 0, 5)
    roots = [root / "results/stage-one"]
    progress = n1.status(path, roots)
    assert progress["interim_can_run"] and progress["outcome_free"] and progress["planned_cohorts"] == 864
    public = n1.interim(path, roots, root / "public.json", root / "custodian-sealed.json")
    assert public["prescribed_total_sources"] == 6 and public["interim_custodian"] == "Test Custodian"
    assert "contrast_variances" not in public and "precision_futility" not in public
    sealed = read_json(root / "custodian-sealed.json")
    assert len(sealed["contrast_variances"]) == 2 and sealed["precision_futility"] is False
    assert sealed["input_manifests_sha256"] == public["input_manifests_sha256"] and sealed["protocol_sha256"]
    assert set(sealed["n1_code_and_registration_sha256"]) == set(n1.FROZEN)
    report = n1.final(path, roots, root / "public.json", root / "custodian-sealed.json", root / "final.json")
    assert report["verdict"] == "qualified" and report["mock"] is False and report["QoE_claims"] is False
    assert report["primary"]["mean_contrasts"] == pytest.approx([0.12, 0.12], abs=0.01)
    assert report["interim"]["precision_futility_is_not_evidence_about_the_effect"] is True
    secondary = report["secondary"]
    assert secondary["send_rate"]["verdict"] == "qualified" and set(secondary["regime_map"]) == set(
        n1.REGIMES
    )
    assert secondary["first_stage_strength"]["encoder"]["cluster_F"] > 10
    assert all(len(v["holm_p_values"]) == 2 for v in secondary["regime_map"].values())
    # The sealed record is bound to the public one, and rows are bound to the planned randomisation.
    tampered = dict(sealed, contrast_variances=[0.0, 0.0])
    write_json(root / "forged-sealed.json", tampered)
    with pytest.raises(ValueError, match="sealed interim record changed"):
        n1.final(path, roots, root / "public.json", root / "forged-sealed.json", root / "other.json")
    rows = read_json(root / "results/stage-one/cohorts.json")
    with pytest.raises(ValueError, match="planned randomisation"):
        n1.estimator_rows([dict(rows[0], arm=(rows[0]["arm"] + 1) % 3), *rows[1:]], native["protocol"])
    with pytest.raises(ValueError, match="forged propensity"):
        n1.estimator_rows([dict(rows[0], propensity=0.5), *rows[1:]], native["protocol"])
    with pytest.raises(ValueError, match="outside the sealed plan or duplicated"):
        n1.estimator_rows([rows[0], *rows], native["protocol"])


def test_extension_and_skipped_sources_follow_the_pre_drawn_order(native):
    root, path, state = native["root"], native["path"], native["state"]
    state["spread"] = 0.09  # sources disagree, so the blinded rule asks for more of them
    sources = native["protocol"]["sources"]
    state["censored"] = {(sources[1]["cluster_id"], n1.REGIMES[0], 2)}  # one stage-one source loses a cell
    n1.capture(path, root / "results/a", 0, 6)
    progress = n1.status(path, [root / "results/a"])
    assert progress["not_evaluable_sources"] == [sources[1]["cluster_id"]] and not progress["interim_can_run"]
    assert "capture the next planned block" in progress["blocker"]
    with pytest.raises(ValueError, match="capture the next planned block"):
        n1.interim(path, [root / "results/a"], root / "p.json", root / "s.json")
    n1.capture(path, root / "results/b", 6, 9)
    roots = [root / "results/a", root / "results/b"]
    public = n1.interim(path, roots, root / "public.json", root / "sealed.json")
    sealed = read_json(root / "sealed.json")
    assert public["skipped_sources"] == 1 and sources[1]["cluster_id"] not in sealed["first_stage_sources"]
    assert sources[7]["cluster_id"] in sealed["first_stage_sources"]  # the next source of the same tercile
    total = public["prescribed_total_sources"]
    assert total > 6 and total % 3 == 0
    with pytest.raises(ValueError, match="capture the next planned block"):
        n1.final(path, roots, root / "public.json", root / "sealed.json", root / "early.json")
    n1.capture(path, root / "results/c", 9, 12)
    roots.append(root / "results/c")
    if total <= 9:  # every planned source is captured; the fixed order decides which enter
        report = n1.final(path, roots, root / "public.json", root / "sealed.json", root / "final.json")
        assert report["primary"]["sources"] == total and report["support"]["skipped_sources"] == 1
        assert report["sources"][:6] == sealed["first_stage_sources"]
    else:  # the rule wants more evaluable sources than this small pool drew: nothing is improvised
        with pytest.raises(ValueError, match="evaluable"):
            n1.final(path, roots, root / "public.json", root / "sealed.json", root / "final.json")
    with pytest.raises(ValueError, match="captured once"):
        n1.status(path, [root / "results/a", root / "results/a"])


def test_dry_run_goes_from_plan_to_verdict_on_mock_rows_only(tmp_path, native):
    summary = n1.dry_run(tmp_path / "dry", seed=3)
    assert summary["mock"] and summary["proves_nothing_about_the_native_stack"]
    assert summary["plan_checks"]["sources"] == 12 and summary["status_before_interim"]["interim_can_run"]
    assert "contrast_variances" not in summary["interim_public_keys"]
    assert summary["verdict_on_mock_rows"] in ("qualified", "inconclusive", "not_separable_at_threshold")
    report = read_json(tmp_path / "dry/final.json")
    assert report["mock"] is True and report["primary"]["sources"] == summary["prescribed_total_sources"]
    # Mock rows and native plans never mix, in either direction.
    with pytest.raises(ValueError, match="mock plan cannot drive a native capture"):
        n1.capture(tmp_path / "dry/plan/protocol.json", tmp_path / "dry/native", 0, 6)
    scenario = Scenario("x", 0.1, 0.1, 0.0, 0.01, 0.02)
    with pytest.raises(ValueError, match="only follow a mock plan"):
        n1.mock_capture(native["path"], tmp_path / "fake", 0, 6, scenario, 1)
    with pytest.raises(ValueError, match="different sealed plan"):
        n1.status(native["path"], [tmp_path / "dry/stage-one"])


def test_freeze_binds_registration_and_implementation(tmp_path):
    record = n1.freeze_record()
    assert set(record["files"]) == set(n1.FROZEN) and record["native_data_collected"] is False
    assert record["controller_freeze_sha256"] == n1.digest(
        n1.assets.FREEZE
    )  # the controller freeze is only read
    path = tmp_path / "freeze.json"
    assert n1.write_freeze(path) == record and n1.verify_freeze(path)["verified"]
    with pytest.raises(FileExistsError):
        n1.write_freeze(path)  # a changed registration needs a visible new record, never a silent rewrite
    drifted = tmp_path / "drifted.json"
    write_json(drifted, dict(record, files=dict(record["files"], **{n1.FROZEN[0]: "0" * 64})))
    with pytest.raises(ValueError, match="changed after it was frozen"):
        n1.verify_freeze(drifted)


def test_rule_maximum_is_what_the_sealed_plan_holds():
    from dataclasses import asdict

    sources = n1.allocate(n1.mock_clips(5), [], PLAN, seed=5)  # one reserve block only
    protocol = dict(plan=asdict(PLAN), sources=sources)
    capped = n1.effective_plan(protocol)
    assert capped.maximum_sources == 15 and capped.first_stage_sources == 12
    assert required_sources([0.10**2] * 2, capped)["total"] == 15  # the registered plan would have said 24
    assert required_sources([0.10**2] * 2, PLAN)["total"] == 24
    assert required_sources([0.14**2] * 2, capped)["precision_futility"]  # judged against the lower cap
    full = dict(plan=asdict(PLAN), sources=n1.allocate(n1.mock_clips(8), [], PLAN, seed=5))
    assert n1.effective_plan(full) == PLAN


def test_acquisition_queue_orders_candidates_without_verifying_anything(tmp_path):
    records = []
    for i in range(9):
        records.append(
            dict(
                asset_id=f"a{i}",
                source_cluster_id=f"candidate-{i // 2}",  # two files of one cluster count once
                planning_candidate=i != 8,
                previously_exposed_title=i == 6,
                source_title=f"title {i}",
                license_type="CC-BY-4.0",
                duration_seconds=100.0,
                source_uri=f"https://example.invalid/{i}",
                representations=[dict(uri="u", approximate_bytes=1000 * (i + 1))],
                blocking_reasons=["native_media_probe_not_performed"],
            )
        )
    path = tmp_path / "inventory.json"
    write_json(path, dict(records=records))
    queue = n1.acquisition_queue(path, seed=1, count=3)
    assert queue["candidate_clusters"] == 4 and len(queue["queue"]) == 3
    assert len({q["source_cluster_id"] for q in queue["queue"]}) == 3
    assert queue["media_downloaded"] is False and queue["rights_reviewed"] is False
    assert queue["verified_eligible_sources"] == 0 and queue["estimated_bytes"] > 0
    assert queue == n1.acquisition_queue(path, seed=1, count=3)
