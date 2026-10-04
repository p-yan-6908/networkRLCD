import csv
import gzip

from media_rl.scenarios import SCENARIOS
from media_rl.shield_selection import ShieldProtocol, select_shield_candidate, write_shield_diagnostics


def protocol():
    return ShieldProtocol(
        name="shield-test",
        model_seeds=[11, 22],
        validation_seeds=[101, 102],
        test_seeds=[201, 202],
        top_k=5,
        threshold=0.9,
        max_id_qoe_drop=0.03,
        max_id_violation_increase=0.01,
        max_stress_violation_increase=0.02,
        max_stress_scenario_violation_increase=0.03,
        risk_penalty=5,
        minimum_score_gain=0.005,
    )


def rows(candidate_family_unsafe=None):
    result = []
    for method in ["calibrated_v1", "shielded"]:
        candidate = method == "shielded"
        for scenario, domain in SCENARIOS.items():
            qoe = (
                2.1 if candidate and domain == "id" else 2.0 if domain == "id" else 1.2 if candidate else 1.0
            )
            violation = 0.005 if domain == "id" else 0.08 if candidate else 0.10
            if candidate and scenario == candidate_family_unsafe:
                violation = 0.15
            result.append(
                dict(
                    method=method,
                    scenario=scenario,
                    domain=domain,
                    qoe=qoe,
                    violation_rate=violation,
                )
            )
    return result


def test_shield_selection_promotes_only_validation_candidate_meeting_every_bound():
    selected = select_shield_candidate(rows(), protocol().validate())
    assert selected["candidate_feasible"]
    assert selected["candidate_promoted"]
    assert selected["selected_controller"] == "shielded"
    assert selected["selection_split"] == "validation"

    rejected = select_shield_candidate(rows("bufferbloat"), protocol().validate())
    assert not rejected["candidate_feasible"]
    assert not rejected["candidate_promoted"]
    assert rejected["selected_controller"] == "calibrated_v1"
    assert rejected["stress_scenario_violation_deltas"]["bufferbloat"] > 0.03


def test_uncertainty_cutoff_selector_compares_the_v7_screen_to_v6_on_validation_only():
    result = []
    for method in ["shielded", "shielded_uncertainty"]:
        candidate = method == "shielded_uncertainty"
        for scenario, domain in SCENARIOS.items():
            result.append(
                dict(
                    method=method,
                    scenario=scenario,
                    domain=domain,
                    qoe=2.1
                    if candidate and domain == "id"
                    else 2.0
                    if domain == "id"
                    else 1.2
                    if candidate
                    else 1.0,
                    violation_rate=0.005 if domain == "id" else 0.08 if candidate else 0.10,
                )
            )
    selection = select_shield_candidate(
        result,
        protocol().validate(),
        reference_method="shielded",
        candidate_method="shielded_uncertainty",
    )
    assert selection["candidate_promoted"]
    assert selection["selected_controller"] == "shielded_uncertainty"
    assert selection["reference_method"] == "shielded"
    assert selection["selection_split"] == "validation"


def test_shield_protocol_rejects_overlapping_or_invalid_panels():
    import pytest

    with pytest.raises(ValueError, match="overlap"):
        ShieldProtocol(**{**protocol().__dict__, "test_seeds": [101, 202]}).validate()
    with pytest.raises(ValueError, match="top_k"):
        ShieldProtocol(**{**protocol().__dict__, "top_k": 0}).validate()
    with pytest.raises(ValueError, match="max_ensemble_std"):
        ShieldProtocol(**{**protocol().__dict__, "max_ensemble_std": 0.51}).validate()


def test_shield_diagnostics_stream_step_logs_by_model_seed(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    rows = [
        dict(
            method="shielded",
            domain="id",
            model_seed=11,
            reason="shielded_action",
            proposal_safe=False,
            safe=True,
        ),
        dict(
            method="shielded",
            domain="id",
            model_seed=11,
            reason="no_safe_candidate",
            proposal_safe=True,
            safe=False,
        ),
        dict(
            method="calibrated", domain="id", model_seed=11, reason="accepted", proposal_safe=True, safe=True
        ),
    ]
    with gzip.open(run / "steps.csv.gz", "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_shield_diagnostics(run)
    with (run / "shield_diagnostics.csv").open(newline="") as stream:
        output = list(csv.DictReader(stream))
    assert len(output) == 1
    assert float(output[0]["intervention_rate"]) == 0.5
    assert float(output[0]["proposal_violation_rate"]) == 0.5
    assert float(output[0]["executed_violation_rate"]) == 0.5
    assert float(output[0]["intervention_proposal_violation_rate"]) == 1.0
    assert float(output[0]["intervention_executed_violation_rate"]) == 0.0
