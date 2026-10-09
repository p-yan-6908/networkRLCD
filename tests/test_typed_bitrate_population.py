import hashlib
import json

import numpy as np
import pytest

from media_rl.typed_bitrate import TypedConfig, load_config
from media_rl.typed_bitrate_baselines import audit
from media_rl.typed_bitrate_experiment import main, run, transfer
from media_rl.typed_bitrate_families import FAMILIES, TEST_FAMILIES, TRAIN_FAMILIES, family_trace
from media_rl.typed_bitrate_population import (
    EVENTS,
    PANELS,
    SEALED,
    SEED,
    SHAPES,
    names,
    parameters,
    table_hash,
)

TINY = dict(
    steps=120,
    tune_episodes=4,
    train_episodes=8,
    rounds=2,
    calibration_episodes=4,
    hidden=8,
    epochs=3,
    batch_size=32,
    model_seeds=[0],
    validation_seeds=[1],
    test_seeds=[2],
    scenarios=["steady", "collapse"],
    bootstrap_samples=50,
    workers=1,
)
# The population as registered on 2026-10-08. A change here changes every registered panel.
REGISTERED = "fbfb8da06b15443679e4da1bb46a030d46be9a55caeafcca257df7ab5fdd679c"


def test_population_is_the_registered_one_and_its_panels_are_disjoint():
    assert (SEED, PANELS) == (20261008, dict(r=48, s=48, d=64))
    assert table_hash() == REGISTERED
    members = [name for panel in PANELS for name in names(panel)]
    assert len(set(members)) == len(members) == 160 and set(members) <= set(FAMILIES)
    assert SEALED == set(names("r")) | set(names("s")) and SEALED <= set(TEST_FAMILIES)
    assert not set(names("d")) & set(TEST_FAMILIES) and not set(members) & set(TRAIN_FAMILIES)
    assert parameters("r", 0) == parameters("r", 0) != parameters("s", 0)
    with pytest.raises(ValueError):
        parameters("r", 48)


def test_population_parameters_stay_inside_the_declared_ranges():
    for panel, count in PANELS.items():
        for index in range(count):
            p = parameters(panel, index)
            assert p["shape"] in SHAPES and set(p["events"]) <= set(EVENTS)
            assert 0.12 <= p["level"] <= 1.3 and 20 <= p["rtt"] <= 180 and 0.25 <= p["buffer"] <= 10
            assert 0.2 <= p["low"] <= 0.6 < 1.0 <= p["high"] <= 1.6
            assert p["loss"] is None or 0.02 <= p["loss"] <= 0.045
            for name in ("feedback_gap", "outage"):
                if name in p["events"]:
                    count_, longest = p["events"][name]
                    assert count_ * longest <= 0.4  # the events cannot cover the whole episode


def test_population_traces_show_what_their_parameters_declare():
    for panel in PANELS:
        for index in range(0, PANELS[panel], 5):
            p, name = parameters(panel, index), names(panel)[index]
            trace = family_trace(name, 360, 11)  # Trace validates ranges, shapes and finiteness
            assert trace.base_rtt.min() >= 0.4 * 0.85 * p["rtt"] - 1e-9
            assert np.all(trace.buffer_scale == p["buffer"])
            assert ("outage" in p["events"]) == bool(np.any(trace.capacity == 0))
            assert ("feedback_gap" in p["events"]) == (not trace.feedback.all())
            assert np.all(trace.capacity[trace.capacity > 0] >= 0.2)
            if p["loss"] is not None and "loss_episode" not in p["events"]:
                assert trace.loss[trace.capacity > 0].min() >= 0.02 * 0.85


def test_sealed_panels_cannot_be_fitted_on_but_the_development_pool_can():
    for sealed in ("pop_r00", "pop_s47"):
        with pytest.raises(ValueError):
            TypedConfig(train_scenarios=["steady", sealed]).validate()
        with pytest.raises(ValueError):
            TypedConfig(development_scenarios=[sealed]).validate()
        TypedConfig(scenarios=[sealed]).validate()
    TypedConfig(train_scenarios=["steady", "pop_d00"], development_scenarios=["pop_d63"]).validate()


def registration(run_dir, **changes):
    config = load_config(run_dir / "config.json")
    record = dict(
        name="tiny-transfer",
        source=config.name,
        base_ratio=config.base_ratio,
        panel="d",  # unit tests never run a controller on a sealed panel
        test_seeds=[5],
        population_seed=SEED,
        population_hash=table_hash(),
        models={
            f"model_seed_{s}.json": hashlib.sha256(
                (run_dir / f"model_seed_{s}.json").read_bytes()
            ).hexdigest()
            for s in config.model_seeds
        },
    )
    return {**record, **changes}


def test_transfer_evaluates_frozen_models_once_on_a_registered_panel(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(TINY))
    run(load_config(path), tmp_path / "run", splits=("validation",))
    source = tmp_path / "run"
    record = tmp_path / "registration.json"
    for bad in (
        dict(source="another-run"),
        dict(base_ratio=0.123),
        dict(population_hash="0" * 64),
        dict(models={"model_seed_0.json": "0" * 64}),
    ):
        record.write_text(json.dumps(registration(source, **bad)))
        with pytest.raises(ValueError):
            transfer(source, tmp_path / "refused", record)
        assert not (tmp_path / "refused").exists()  # nothing runs under a broken registration
    best = audit(source, tmp_path / "source-audit", samples=20)["tuning"]["selected"]["rule_best"]["spec"]
    record.write_text(json.dumps(registration(source, rule_best=best, sensitive_margin=0.02)))
    report = transfer(source, tmp_path / "panel", record)
    out = tmp_path / "panel"
    assert (out / "model_seed_0.json").read_bytes() == (source / "model_seed_0.json").read_bytes()
    assert report["base_tuning"] == json.loads((source / "report.json").read_text())["base_tuning"]
    assert report["transfer"]["registration"]["panel"] == "d"
    config = load_config(out / "config.json")
    assert config.scenarios == names("d") and config.test_seeds == [5]
    assert config.train_scenarios == load_config(source / "config.json").train_scenarios
    assert set(report["panels"]) == {"test"} and set(report["panels"]["test"]) == {"ood", "all"}
    assert len(report["panels"]["test"]["all"]["scenarios"]) == 64
    with pytest.raises(FileExistsError):
        transfer(source, out, record)
    with pytest.raises(SystemExit):
        main(["transfer", "--run", str(source), "--registration", str(record), "--out", str(out)])
    rules = audit(out, tmp_path / "panel-audit", samples=20)  # the registered comparator and subset
    assert rules["tuning"]["selected"]["rule_best"]["spec"] == best
    panels = rules["panels"]["test"]["panels"]
    assert rules["panels"]["test"]["pairing_max_difference"] == 0
    by_family = panels["all"]["by_family"]
    headroom = np.subtract(
        by_family["oracle"]["utility"], by_family[f"fixed_{config.base_ratio:.2f}"]["utility"]
    )
    assert panels["sensitive"]["families"] == [
        f for f, h in zip(panels["all"]["families"], headroom) if h >= 0.02
    ]
    changed = json.loads((out / "report.json").read_text())
    changed["transfer"]["registration"]["rule_best"] = dict(kind="backoff", high=1.0, low=0.6, hold_ms=1)
    (out / "report.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        audit(out, tmp_path / "wrong-rule")  # a comparator other than the registered one is refused
