"""Validation-locked delay-evidence budget screening; no refitting or test tuning."""

import json
from pathlib import Path

from .config import load_config
from .experiment import dump_json, evaluate_experiment, manifest, sha256
from .improvement import audit_directory, complete_evaluation
from .reporting import build_report, read_episodes
from .shield_selection import (
    ShieldProtocol,
    _evaluation_config,
    _identity,
    select_shield_candidate,
    write_shield_diagnostics,
)

REFERENCE_METHOD = "shielded_uncertainty"
LOSS_BUDGET_METHOD = "shielded_budget"
CANDIDATE_METHOD = "shielded_delay_budget"
ABLATION_METHOD = "delay_budget_only"
VALIDATION_METHODS = [REFERENCE_METHOD, LOSS_BUDGET_METHOD, CANDIDATE_METHOD]
TEST_METHODS = ["safe", "heuristic", "gcc", "rl", "calibrated", *VALIDATION_METHODS, ABLATION_METHOD]


def run_delay_budget(settings_path, models, out, plots=True):
    """Freeze V9-versus-V7 promotion before opening a disjoint fresh test panel.

    V8 is a paired mechanistic comparator, never an alternative promotion choice.
    V9 removes raw-loss-only backoff from the warm budget AND its fallback;
    RTT excess/trend, probing, FEC preference and all other dynamics stay fixed.
    The ablation removes confidence eligibility only, retaining Q/support guards.
    """
    settings_path = Path(settings_path).resolve()
    protocol = ShieldProtocol(**json.loads(settings_path.read_text())).validate()
    models, out = Path(models).resolve(), Path(out).resolve()
    base = load_config(models / "config.json")
    if not set(protocol.model_seeds) <= set(base.seeds):
        raise ValueError("source checkpoints are missing declared model seeds")
    if (set(protocol.validation_seeds) | set(protocol.test_seeds)) & set(base.test_seeds):
        raise ValueError("validation/test traces must not reuse source-model test traces")
    if protocol.threshold != base.gate.threshold or protocol.top_k != base.gate.shield_top_k:
        raise ValueError("frozen screen threshold/top_k must match the source model configuration")
    identity = _identity(protocol, settings_path, models)
    identity.update(
        reference_method=REFERENCE_METHOD,
        candidate_method=CANDIDATE_METHOD,
        ablation_method=ABLATION_METHOD,
        validation_methods=VALIDATION_METHODS,
        test_methods=TEST_METHODS,
        budget_rule="rtt_excess>35ms or trend>15ms; no loss-only backoff",
    )
    if out.exists():
        marker = out / "campaign.json"
        if not marker.is_file() or json.loads(marker.read_text()) != identity:
            raise ValueError(
                "campaign source/settings changed or output is partial; preserve it and use a new directory"
            )
    else:
        out.mkdir(parents=True)
        dump_json(out / "campaign.json", identity)
        (out / "settings.json").write_bytes(settings_path.read_bytes())
        (out / "base_config.json").write_bytes((models / "config.json").read_bytes())
    validation_config = _evaluation_config(
        base, protocol, protocol.validation_seeds, "validation", VALIDATION_METHODS
    )
    validation = out / "validation"
    complete_evaluation(validation_config, models, validation, "validation", plots=False)
    selection = select_shield_candidate(
        read_episodes(validation / "episodes.csv"),
        protocol,
        reference_method=REFERENCE_METHOD,
        candidate_method=CANDIDATE_METHOD,
    )
    selection.update(
        validation_manifest_sha256=sha256(validation / "manifest.json"),
        baseline_model_sha256=identity["model_sha256"],
        candidate_model_sha256=identity["model_sha256"],
        ablation_method=ABLATION_METHOD,
        mechanistic_comparator=LOSS_BUDGET_METHOD,
    )
    selection_path = out / "selection.json"
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != selection:
            raise ValueError("locked delay-budget selection changed; do not overwrite it")
    else:
        dump_json(selection_path, selection)
    print(
        f"LOCKED delay-budget decision={selection['selected_controller']} "
        f"promote_candidate={selection['candidate_promoted']} before fresh-test evaluation",
        flush=True,
    )
    final_config = _evaluation_config(base, protocol, protocol.test_seeds, "test", TEST_METHODS)
    final = out / "test"
    if final.exists():
        final_manifest = audit_directory(final, "complete")
        if not final_config.digest_matches(final_manifest["config_sha256"]):
            raise ValueError("final delay-budget test does not match the locked protocol")
        if final_manifest.get("evaluation_split") != "test":
            raise ValueError("final delay-budget run is not a fresh test evaluation")
        if (
            sha256(final / "selection.json") != sha256(selection_path)
            or final_manifest.get("selection_sha256") != sha256(selection_path)
            or final_manifest.get("campaign_sha256") != sha256(out / "campaign.json")
        ):
            raise ValueError("final test does not retain the locked validation selection/campaign")
    else:
        evaluate_experiment(final_config, models, final, split="test")
        (final / "selection.json").write_bytes(selection_path.read_bytes())
        build_report(final, plots=plots)
        write_shield_diagnostics(final, method=CANDIDATE_METHOD)
        write_shield_diagnostics(final, method=ABLATION_METHOD, filename="delay_budget_only_diagnostics.csv")
        manifest(
            final,
            final_config,
            "complete",
            extra={
                "selection_sha256": sha256(selection_path),
                "campaign_sha256": sha256(out / "campaign.json"),
            },
        )
    dump_json(
        out / "status.json",
        dict(
            stage="complete",
            selected_controller=selection["selected_controller"],
            selection_sha256=sha256(selection_path),
            final_manifest_sha256=sha256(final / "manifest.json"),
        ),
    )
    return final
