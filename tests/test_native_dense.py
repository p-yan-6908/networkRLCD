"""Software-only scalar control/provenance tests; not native or learned efficacy."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from native_study_helpers import bundle

from media_rl.native_dense_control import (
    CONFIG,
    RepairPolicy,
    executed_learned_action,
    exploration_cap,
    scalar_cap,
)
from media_rl.native_dense_study import (
    BEHAVIORS,
    RECIPE,
    _report,
    audit_dense_study,
    plan_dense_study,
    run_dense_study,
    trial_schedule,
    validate_dense_protocol,
)
from media_rl.native_protocol import DEFAULT_LIMITS, digest
from media_rl.native_repair5_study import _close
from media_rl.native_video import VIDEO_ABI

ROOT = Path(__file__).resolve().parents[1]


def features(bwe=550000, cap=467500):
    f = [0.0] * 16
    f[0], f[1], f[7], f[9], f[10] = bwe / 4e6, 0.4, cap / 4e6, 1, 1
    return f


def fixture(tmp_path):
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"artificial movie fixture, NOT native evidence")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            dict(
                source_abi=VIDEO_ABI,
                path=str(movie),
                sha256=digest(movie),
                duration_ms=300000,
                attribution="synthetic test",
                license_url="https://example.invalid/license",
                source_url="https://example.invalid/source",
                rights_asserted_by_importer=True,
                not_representative_corpus=True,
            )
        )
    )
    model = tmp_path / "model.json"
    model.write_text(json.dumps(bundle()))
    path = tmp_path / "plan.json"
    p = plan_dense_study(model, catalog, path, results_directory=tmp_path / "results")
    return p, path


def test_continuous_bwe_fills_dead_zone_without_changing_headroom():
    f = features()
    assert exploration_cap("bwe", 0, 1, f) == 300000
    assert exploration_cap("bwe-continuous", 0, 1, f) == 467500
    assert 467500 < CONFIG["bwe_headroom"] * 550000
    assert exploration_cap("fixed450", 0, 1, f) == 450000
    assert exploration_cap("gcc", 0, 1, f) == 4000000
    for bw in np.linspace(180000, 6000000, 301):
        f = features(float(bw))
        rate = exploration_cap("bwe-continuous", 0, 1, f)
        assert 150000 <= rate <= 4000000
        assert rate <= 0.85 * bw + 1e-9


def test_unavailable_bwe_preserves_legacy_minimum_not_a_learned_decision():
    f = features()
    f[9] = 0
    assert exploration_cap("bwe-continuous", 0, 1, f) == 150000
    assert executed_learned_action({"reason": "learned"}, 450000, "repair") is False


@pytest.mark.parametrize("value", [True, 149999, 4000001, 450000.5, float("inf"), float("nan"), "450000"])
def test_scalar_domain_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        scalar_cap(value)


def test_shadow_projection_is_explicit_and_never_mutates_actual_features():
    p = RepairPolicy()
    obs = dict(sample_ms=0, features=features(), content_features=[0.0, 0.0, 0.0])
    old = deepcopy(obs)
    d = p.observe(obs)
    assert obs == old
    assert d["shadow_only"] and d["fallback"] and not d["learned_departure"]
    assert d["actual_scalar_cap_bps"] == 467500
    assert d["shadow_projected_cap_bps"] == 300000
    assert d["history"][-23 + 7] == 300000 / 4e6
    assert obs["features"][7] == 467500 / 4e6
    p.acknowledge(467500, 10)
    with pytest.raises(ValueError):
        RepairPolicy({})
    with pytest.raises(ValueError):
        p.observe(dict(obs, sample_ms=-1))


def test_python_js_control_and_shadow_state_parity():
    rows = [
        dict(
            sample_ms=i * 100,
            features=features(300000 + i * 3900, 300000 if i < 2 else 467500),
            content_features=[0.2, 0.1, 1.0],
        )
        for i in range(45)
    ]
    p = RepairPolicy()
    expected = []
    for row in rows:
        expected.append(p.observe(row, None))
        p.acknowledge(round(row["features"][7] * 4e6), row["sample_ms"] + 1)
    node = "const p=await import(process.argv[1]),rows=JSON.parse(process.argv[2]),a=new p.RepairPolicy(),ds=[];for(const r of rows){ds.push(a.observe(r,null));a.acknowledge(Math.round(r.features[7]*4e6),r.sample_ms+1);}console.log(JSON.stringify({ds,caps:rows.map(r=>p.BEHAVIORS.map(b=>p.explorationCap(b,0,1,r)))}));"
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            node,
            (ROOT / "benchmarks/native_rtc/dense_control.mjs").as_uri(),
            json.dumps(rows),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    got = json.loads(result.stdout)
    _close(got["ds"], expected)
    assert got["caps"] == [[exploration_cap(b, 0, 1, r["features"]) for b in BEHAVIORS] for r in rows]


def test_prospective_plan_only_allows_complete_diagnostic_controls(tmp_path):
    p, _ = fixture(tmp_path)
    assert p["stage"] == "diagnostic" and p["repair_model"] is None and p["learner"] is None
    assert p["limits"] == DEFAULT_LIMITS and p["measurement_recipe"] == RECIPE
    assert len(trial_schedule(p)) == 8
    assert set(p["conditions"]) == set(BEHAVIORS)
    assert p["groups"][0]["orders"][0] != p["groups"][0]["orders"][1]
    for key, value in [
        ("stage", "train"),
        ("repair_model", {}),
        ("learner", {}),
        ("limits", dict(DEFAULT_LIMITS, inference_p99_ms=20)),
        ("conditions", {"bwe": p["conditions"]["bwe"]}),
    ]:
        bad = deepcopy(p)
        bad[key] = value
        with pytest.raises(ValueError):
            validate_dense_protocol(bad)


def test_reservations_include_existing_dense_and_v5_roles(tmp_path):
    p, path = fixture(tmp_path)
    existing = tmp_path / "results" / "old"
    existing.mkdir(parents=True)
    (existing / "protocol.json").write_text(json.dumps(p))
    newer = plan_dense_study(
        p["models"]["source"]["path"],
        tmp_path / "catalog.json",
        tmp_path / "next.json",
        results_directory=tmp_path / "results",
    )
    assert newer["groups"][0]["video_segment"] == [80000, 100000]
    assert digest(existing / "protocol.json") in newer["excluded_inputs_sha256"].values()
    changed = deepcopy(p)
    changed["source_kind"] = "recorded_video_repair_v5"
    (existing / "protocol.json").write_text(json.dumps(changed))
    newest = plan_dense_study(
        p["models"]["source"]["path"],
        tmp_path / "catalog.json",
        tmp_path / "third.json",
        results_directory=tmp_path / "results",
    )
    assert newest["groups"][0]["video_segment"] == [80000, 100000]
    assert path.exists()


def test_partial_capture_retained_and_never_recollected(tmp_path, monkeypatch):
    import media_rl.native_dense_study as m

    _, path = fixture(tmp_path)
    calls = []

    def fail(args, timeout, log):
        child = Path(args[2])
        child.mkdir()
        (child / "partial.txt").write_text("retained failed prefix")
        calls.append(str(child))
        raise ValueError("synthetic capture failure")

    monkeypatch.setattr(m, "_collect", fail)
    monkeypatch.setattr(m, "_recover_cleanup_capture", lambda *args: None)
    out = tmp_path / "capture"
    with pytest.raises(FileNotFoundError):
        run_dense_study(path, out)
    assert json.loads((out / "failure.json").read_text())["all_partial_evidence_preserved"]
    assert Path(calls[0], "partial.txt").read_text() == "retained failed prefix"
    with pytest.raises(FileExistsError):
        run_dense_study(path, out)
    assert len(calls) == 1
    with pytest.raises((ValueError, FileNotFoundError)):
        audit_dense_study(out)


def test_complete_summary_is_not_policy_qualification(tmp_path):
    p, _ = fixture(tmp_path)
    rows = [
        dict(t, utility=30.0 if t["condition"] == "bwe" else 31.0, ontime_fraction=0.9, inference_p99_ms=1.0)
        for t in trial_schedule(p)
    ]
    report = _report(rows, p)
    assert report["actual_executed_learned_steps"] == 0 and not report["dense_learned_policy_present"]
    assert report["mechanism_probe_not_policy_qualification"] and not report["SOTA_achieved"]
    assert report["paired_group_contrasts_vs_legacy_bwe"]["bwe-continuous"]["utility"]["ci95"] is None
    with pytest.raises(ValueError):
        _report(rows[:-1], p)


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "m", "--video-source", "v", "--out", "o"]),
        ("study", ["--config", "c", "--out", "o"]),
        ("audit", ["--run", "r"]),
    ],
)
def test_public_diagnostic_commands_dispatch(command, flags, monkeypatch):
    import media_rl.native_dense_cli as m
    from media_rl.cli import main

    calls = []
    monkeypatch.setattr(m, "run", lambda args: calls.append(args))
    main(["native-dense-" + command, *flags])
    assert calls[0].command == "native-dense-" + command
