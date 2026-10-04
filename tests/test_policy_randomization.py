import json
from pathlib import Path

import pytest

from media_rl.policy_randomization import METHODS, PolicyRandomizationProtocol, select_policy_candidate
from media_rl.scenarios import SCENARIOS


def protocol(**overrides):
    settings = dict(
        name="test-v4",
        base_config="paper.json",
        model_seeds=[11],
        validation_seeds=[4601],
        test_seeds=[5601],
        policy_training_scenarios=["steady", "collapse"],
        max_id_qoe_drop=0.03,
        max_id_violation_increase=0.01,
        max_stress_violation_increase=0.02,
        max_stress_scenario_violation_increase=0.03,
        risk_penalty=5.0,
        minimum_score_gain=0.005,
        bootstrap_samples=100,
    )
    settings.update(overrides)
    return PolicyRandomizationProtocol(**settings).validate()


def validation_rows(*, candidate_id_qoe=0.75, candidate_stress_qoe=0.50, candidate_stress_violation=0.08):
    rows = []
    for scenario, domain in SCENARIOS.items():
        for method in ["calibrated_v1", "calibrated"]:
            is_candidate = method == "calibrated"
            stress = domain == "ood"
            rows.append(
                dict(
                    method=method,
                    scenario=scenario,
                    domain=domain,
                    qoe=(
                        (candidate_id_qoe if is_candidate else 0.75)
                        if not stress
                        else (candidate_stress_qoe if is_candidate else 0.40)
                    ),
                    violation_rate=(
                        0.01 if not stress else (candidate_stress_violation if is_candidate else 0.10)
                    ),
                )
            )
    return rows


def test_frozen_protocol_schedule_and_registered_method_panel():
    root = Path(__file__).resolve().parents[1]
    settings = json.loads((root / "configs/policy_randomization_v4.json").read_text())
    p = PolicyRandomizationProtocol(**settings).validate()
    assert METHODS == ["safe", "heuristic", "gcc", "rl", "calibrated_v1", "calibrated", "uncalibrated"]
    assert set(name for name, domain in SCENARIOS.items() if domain == "ood") <= set(
        p.policy_training_scenarios
    )
    assigned = [p.policy_training_scenarios[i % len(p.policy_training_scenarios)] for i in range(160)]
    assert sum(SCENARIOS[name] == "id" for name in assigned) == 104
    assert sum(SCENARIOS[name] == "ood" for name in assigned) == 56
    assert p.validation_seeds == list(range(4601, 4611))
    assert p.test_seeds == list(range(5601, 5611))


def test_promotion_is_validation_only_and_requires_every_safety_constraint():
    p = protocol()
    selected = select_policy_candidate(validation_rows(), p)
    assert selected["selection_split"] == "validation"
    assert selected["selected_controller"] == "calibrated"
    assert selected["candidate_promoted"] is True
    assert selected["score_gain"] > p.minimum_score_gain

    rejected = select_policy_candidate(validation_rows(candidate_id_qoe=0.70), p)
    assert rejected["candidate_feasible"] is False
    assert rejected["selected_controller"] == "calibrated_v1"
    assert rejected["test_seeds"] == p.test_seeds

    scenario_rejected_rows = validation_rows()
    next(
        row for row in scenario_rejected_rows if row["method"] == "calibrated" and row["scenario"] == "outage"
    )["violation_rate"] = 0.14
    scenario_rejected = select_policy_candidate(scenario_rejected_rows, p)
    assert scenario_rejected["candidate_feasible"] is False
    with pytest.raises(ValueError, match="missing scenarios"):
        select_policy_candidate(
            [
                row
                for row in validation_rows()
                if not (row["method"] == "calibrated" and row["scenario"] == "steady")
            ],
            p,
        )

    no_gain = select_policy_candidate(
        validation_rows(candidate_stress_qoe=0.40, candidate_stress_violation=0.10), p
    )
    assert no_gain["candidate_feasible"] is True
    assert no_gain["candidate_promoted"] is False
    assert no_gain["selected_controller"] == "calibrated_v1"


def test_protocol_rejects_overlap_and_bad_schedule():
    with pytest.raises(ValueError, match="overlap"):
        protocol(test_seeds=[4601])
    with pytest.raises(ValueError, match="scenario names"):
        protocol(policy_training_scenarios=["steady", "invented"])
    with pytest.raises(ValueError, match="both ID and stress"):
        protocol(policy_training_scenarios=["steady", "wifi"])
