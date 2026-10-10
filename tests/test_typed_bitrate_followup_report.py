import hashlib
import json
import re

import pytest

from media_rl.typed_bitrate import load_config
from media_rl.typed_bitrate_audit import audit
from media_rl.typed_bitrate_baselines import audit as rule_audit
from media_rl.typed_bitrate_experiment import rescore, run, transfer
from media_rl.typed_bitrate_factual import study
from media_rl.typed_bitrate_followup_report import export, headroom_macros, rule_name, table_headroom
from media_rl.typed_bitrate_headroom import load_settings as headroom_settings
from media_rl.typed_bitrate_headroom import measure
from media_rl.typed_bitrate_population import SEED, table_hash

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
    validation_seeds=[1, 3],
    test_seeds=[2],
    scenarios=["steady", "collapse"],
    bootstrap_samples=50,
    workers=1,
)
SMALL = dict(
    blocks=[40, 120],
    control_blocks=40,
    seeds=[0, 1],
    max_updates=60,
    min_epochs=1,
    check_every=20,
    patience=2,
)


def test_rule_names_read_as_prose():
    name = rule_name(dict(kind="delay", high=1.05, low=0.8, on_ms=15, off_ms=5))
    assert "1.05 and 0.80" in name and "15\\,ms" in name and "5\\,ms" in name
    assert (
        rule_name(dict(kind="backoff", high=1.0, low=0.7, hold_ms=2000))
        == "backoff (high 1, low 0.7, hold ms 2000)"
    )


def test_followup_evidence_is_generated_from_the_summaries(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(TINY))
    source = tmp_path / "run"
    run(load_config(path), source)
    rules = rule_audit(source, tmp_path / "rules", samples=20)
    config = load_config(source / "config.json")
    record = dict(
        name="tiny-transfer",
        source=config.name,
        base_ratio=config.base_ratio,
        panel="d",  # unit tests never run a controller on a sealed panel
        test_seeds=[5],
        population_seed=SEED,
        population_hash=table_hash(),
        models={"model_seed_0.json": hashlib.sha256((source / "model_seed_0.json").read_bytes()).hexdigest()},
        rule_best=rules["tuning"]["selected"]["rule_best"]["spec"],
        sensitive_margin=0.02,
    )
    (tmp_path / "registration.json").write_text(json.dumps(record))
    panel = tmp_path / "panel"
    transfer(source, panel, tmp_path / "registration.json")
    audit(panel, samples=20)
    rule_audit(panel, tmp_path / "panel-rules", samples=20)
    with pytest.raises(ValueError):  # the paper states that the panel replays exactly
        export(tmp_path / "early", tmp_path / "rules", panel, tmp_path / "panel-rules")
    rescore(panel)
    audit(panel, samples=20)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SMALL))
    study(source, tmp_path / "factual", settings, samples=20)
    out = tmp_path / "paper"
    written = export(out, tmp_path / "rules", panel, tmp_path / "panel-rules", tmp_path / "factual")
    lines = (out / "evidence.tex").read_text().splitlines()
    macros = dict(re.fullmatch(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}", line).groups() for line in lines[1:])
    assert written["macros"] == len(macros) == len(lines) - 1  # letters only, no duplicates
    assert not any("nan" in value.lower().replace("n/a", "") for value in macros.values())
    for name in (
        "TypedRuleCandidates",
        "TypedRuleBestName",
        "TypedRuleValRuleVsFixedT",
        "TypedRepGain",
        "TypedRepGainT",
        "TypedRepGainVsRuleFamily",
        "TypedRepEce",
        "TypedRepUnsafeFamily",
        "TypedRepCriteriaMet",
        "TypedRepOracleShare",
        "TypedFactOneGain",
        "TypedFactOneGainT",
        "TypedFactOneControlGain",
        "TypedFactOnePrice",
        "TypedFactTwoGain",
        "TypedFactLastHours",
        "TypedFactIdentifiedBudgets",
        "TypedFactRefRegress",
    ):
        assert name in macros, name
    assert "TypedFactTwoControlGain" not in macros  # beyond the control's budget
    assert macros["TypedRepFamilies"] == "64" and macros["TypedRepTraceSeeds"] == "1"
    assert macros["TypedFactOneBlocks"] == "40" and macros["TypedFactBudgets"] == "2"
    assert {macros[f"TypedRepMet{k}"] for k in ("Gain", "Rule", "Calibration", "Constraints")} <= {
        "met",
        "not met",
    }
    audited = json.loads((panel / "audit_test.json").read_text())
    ece = audited["calibration"]["choice_rlcd_bayes"]["all"]["ece"]
    assert macros["TypedRepMetCalibration"] == ("met" if ece <= 0.05 else "not met")
    assert float(macros["TypedRepEce"]) == pytest.approx(ece, abs=5e-4)
    for table in ("followup_rules.tex", "followup_replication.tex", "followup_factual.tex"):
        text = (out / table).read_text()
        assert text.startswith("\\begin{tabular}") and text.rstrip().endswith("\\end{tabular}")
    assert "Population panel (registered) & 64" in (out / "followup_rules.tex").read_text()
    assert "not run" in (out / "followup_factual.tex").read_text()
    assert (out / "followup_factual.pdf").stat().st_size > 1000
    provenance = json.loads((out / "provenance.json").read_text())
    assert len(provenance) == 5
    for name, digest in provenance.items():
        assert hashlib.sha256(open(name, "rb").read()).hexdigest() == digest
    partial = export(tmp_path / "rules-only", tmp_path / "rules")
    assert (
        partial["macros"] < written["macros"]
        and not (tmp_path / "rules-only" / "followup_factual.tex").exists()
    )
    with pytest.raises(ValueError):
        export(tmp_path / "broken", tmp_path / "rules", panel)  # a replication needs its rule audit


def test_headroom_evidence_names_sets_and_panels(tmp_path):
    config = load_config_from(TINY)
    settings = headroom_settings()
    settings.update(samples=50)
    panels = {"r": (["steady", "collapse"], [11, 12]), "s": (["steady", "ramp"], [13, 14])}
    report = dict(
        synthetic_only=True,
        models_trained=0,
        families={"r": 2, "s": 2},
        sets=measure(config, settings, panels),
    )
    made = headroom_macros(report)
    assert (
        made["TypedHeadRefTop"] == "1.05"
        and made["TypedHeadCapTop"] == "1.00"
        and made["TypedHeadLowTop"] == "0.90"
    )
    assert "TypedHeadRefRepShare" not in made and made["TypedHeadCapSealReading"] in (
        "below",
        "above",
        "mixed",
    )
    assert all(re.fullmatch(r"[A-Za-z]+", name) for name in made)
    table = table_headroom(report)
    assert table.count("\\\\") == 1 + 6 and "replication" in table and "sealed" in table
    with pytest.raises(ValueError, match="three option sets"):
        headroom_macros(dict(report, sets=report["sets"][:2]))
    json.dumps(report, allow_nan=False)  # a panel without reference headroom has no share, not a NaN


def load_config_from(values):
    from media_rl.typed_bitrate import TypedConfig

    return TypedConfig(**{**values, "train_scenarios": ["steady", "collapse"]}).validate()
