"""GCC-deferring config conversion, NOT a new actor/risk fit."""

from pathlib import Path

from .native_protocol import digest, read_json, require, write_json
from .native_repair3_policy import validate_repair_bundle as validate_source
from .native_repair4_policy import CONFIG, rebase_repair_bundle, validate_repair_bundle


def rebase_repair_model(source_model, out):
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "rebase output already exists")
    source_model = Path(source_model).resolve()
    source = validate_source(read_json(source_model))
    candidate = rebase_repair_bundle(source)
    require(
        {k: v for k, v in source.items() if k not in ("model_abi", "config")}
        == {k: v for k, v in candidate.items() if k not in ("model_abi", "config")},
        "rebasing changed weights/probability/support",
    )
    source_sha = digest(source_model)
    candidate["gcc_rebase"] = dict(
        abi="native_gcc_config_rebase_v4",
        source_model=str(source_model),
        source_model_sha256=source_sha,
        implementation_sha256=digest(__file__),
        policy_source_sha256=digest(Path(__file__).with_name("native_repair4_policy.py")),
        weights_changed=False,
        labels_fitted=False,
        fresh_selected_policy_calibration_required=True,
    )
    validate_repair_bundle(candidate)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", candidate)
    report = dict(
        source_model_sha256=source_sha,
        model_sha256=digest(out / "model.json"),
        weights_and_probabilities_unchanged=True,
        actor_risk_refitted=False,
        labels_used=False,
        controller_config=CONFIG,
        fresh_selected_calibration_required=True,
        native_gcc_ceiling_not_requested_send_rate=True,
        learned_risk_support_budget_gates_unchanged=True,
        old_bwe_and_native_gcc_comparisons_required=True,
        original_five_percent_bwe_departure_gate_unchanged=True,
        SOTA_achieved=False,
    )
    write_json(out / "report.json", report)
    return report
