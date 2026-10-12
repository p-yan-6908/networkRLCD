"""Factual summary verification and fail-closed evidence export, with no simulator calls."""

import copy
import json
from pathlib import Path

import pytest

from media_rl import native_margin_pilot_report as evidence

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def records():
    spec = json.loads((ROOT / "configs/native_margin_validation_v1.json").read_text())
    data = {role: json.loads((ROOT / e["path"]).read_text()) for role, e in spec["inputs"].items()}
    return spec, data


def validate(spec, data):
    return evidence.validate(
        data["report"], data["sessions"], data["forecast"], spec, spec["inputs"]["layer"]["sha256"]
    )


def test_complete_report_recomputes_without_simulator_or_raw_replay(records, monkeypatch):
    spec, data = records

    def forbidden(*args, **kwargs):
        raise AssertionError("native forecast validation must not run counterfactuals")

    monkeypatch.setattr(evidence.forecast, "simulate", forbidden)
    monkeypatch.setattr(evidence.forecast.receiver, "run", forbidden)
    judged = validate(spec, data)
    primary = judged["spans"]["session"]
    assert judged["verdict"] == "the layer did not forecast the pilot"
    assert (primary["agreeing_over_all_schedules"], primary["established_over_all_schedules"]) == (3, 4)
    assert primary["differences_over_all_schedules"]["margin minus 0.65"]["verdict"] == "flat"
    description = evidence.trajectories(data["report"], data["forecast"])
    assert (
        description["added_after_native_report_was_read"] and not description["causal_mechanism_identified"]
    )
    assert description["by_schedule"]["one-drop"]["native_requested_kbps"] == pytest.approx(376.63, abs=0.01)
    assert description["by_schedule"]["one-drop"]["forecast_requested_kbps"] == pytest.approx(158.119)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "nan", "report", "flag", "schedule"])
def test_incomplete_forged_or_nonfactual_evidence_is_rejected(records, damage):
    spec, original = records
    data = copy.deepcopy(original)
    if damage == "missing":
        data["sessions"].pop()
    elif damage == "duplicate":
        data["sessions"][0] = copy.deepcopy(data["sessions"][1])
    elif damage == "nan":
        data["sessions"][0]["session"]["utility"] = float("nan")
    elif damage == "report":
        data["report"]["all_schedules"]["session"]["utility"]["contrasts"]["margin minus 0.65"]["mean"] += 0.1
    elif damage == "flag":
        data["report"]["confirmatory"] = True
    elif damage == "schedule":
        data["forecast"]["schedules"]["one-drop"][1] = 0.85
    with pytest.raises(ValueError):
        validate(spec, data)


def test_library_rounding_tolerated_but_not_boolean_substitution():
    evidence.compare({"a": 1.0, "b": float("nan")}, {"a": 1.0 + 1e-13, "b": float("nan")})
    with pytest.raises(ValueError):
        evidence.compare({"a": False}, {"a": 0})
    with pytest.raises(ValueError):
        evidence.compare({"a": 1.0}, {"a": 1.01})


def test_holm_adjustment_and_paired_source_sensitivity(records):
    adjusted = evidence.holm({"one": 0.01, "two": 0.02, "three": 0.5})
    assert adjusted == pytest.approx({"one": 0.03, "two": 0.04, "three": 0.5})
    _, data = records
    check = evidence.sensitivity(data["report"], data["sessions"])
    assert check["added_after_native_report_was_read"] and not check["selection_or_promotion"]
    assert len(check["holm"]) == 6
    omitted = check["leave_one_source_out"]["omitted_sources"]
    assert len(omitted) == 12 and all(e["sources"] == 11 for e in omitted.values())


def test_pinned_input_drift_and_existing_output_fail_before_writing(records, tmp_path):
    spec, _ = records
    spec = copy.deepcopy(spec)
    for e in spec["inputs"].values():
        e["path"] = str(ROOT / e["path"])
    changed = tmp_path / "changed.json"
    changed.write_text("{}")
    spec["inputs"]["report"]["path"] = str(changed)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    out, paper = tmp_path / "report", tmp_path / "paper"
    with pytest.raises(ValueError, match="changed pinned report"):
        evidence.run(path, out, paper)
    assert not out.exists() and not paper.exists()
    out.mkdir()
    with pytest.raises(ValueError, match="fresh"):
        evidence.run(path, out, paper)
