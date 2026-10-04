"""Validation-locked evaluation of an ensemble-disagreement action screen."""

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from .config import load_config
from .experiment import dump_json, evaluate_experiment, manifest, sha256
from .improvement import audit_directory, complete_evaluation
from .reporting import build_report, read_episodes
from .shield_selection import (
    UNCERTAINTY_CANDIDATE_METHOD,
    UNCERTAINTY_REFERENCE_METHOD,
    UNCERTAINTY_TEST_METHODS,
    ShieldProtocol,
    _evaluation_config,
    _identity,
    select_shield_candidate,
    write_shield_diagnostics,
)


def run_uncertainty_shield(settings_path, models, out, plots=True):
    """Compare V6's calibrated screen with a disagreement-gated V7 screen.

    Both methods use the same frozen checkpoints, action ranking, probability
    threshold, support gate, and fallback. The candidate adds only a fixed
    ensemble-standard-deviation cutoff, selected on validation traces.
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
        base,
        protocol,
        protocol.validation_seeds,
        "validation",
        [UNCERTAINTY_REFERENCE_METHOD, UNCERTAINTY_CANDIDATE_METHOD],
    )
    validation = out / "validation"
    complete_evaluation(validation_config, models, validation, "validation", plots=False)
    selection = select_shield_candidate(
        read_episodes(validation / "episodes.csv"),
        protocol,
        reference_method=UNCERTAINTY_REFERENCE_METHOD,
        candidate_method=UNCERTAINTY_CANDIDATE_METHOD,
    )
    selection["validation_manifest_sha256"] = sha256(validation / "manifest.json")
    selection["baseline_model_sha256"] = identity["model_sha256"]
    selection["candidate_model_sha256"] = identity["model_sha256"]
    selection_path = out / "selection.json"
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != selection:
            raise ValueError("locked uncertainty-screen selection changed; do not overwrite it")
    else:
        dump_json(selection_path, selection)
    print(
        f"LOCKED uncertainty-screen decision={selection['selected_controller']} "
        f"promote_candidate={selection['candidate_promoted']} before fresh-test evaluation",
        flush=True,
    )

    final_config = _evaluation_config(base, protocol, protocol.test_seeds, "test", UNCERTAINTY_TEST_METHODS)
    final = out / "test"
    if final.exists():
        final_manifest = audit_directory(final, "complete")
        if not final_config.digest_matches(final_manifest["config_sha256"]):
            raise ValueError("final uncertainty-screen test does not match the locked protocol")
        if final_manifest.get("evaluation_split") != "test":
            raise ValueError("final uncertainty-screen run is not a fresh test evaluation")
        if sha256(final / "selection.json") != sha256(selection_path):
            raise ValueError("final test does not retain the locked validation selection")
    else:
        evaluate_experiment(final_config, models, final, split="test")
        (final / "selection.json").write_bytes(selection_path.read_bytes())
        build_report(final, plots=plots)
        write_shield_diagnostics(final, method=UNCERTAINTY_CANDIDATE_METHOD)
        extra = {
            "selection_sha256": sha256(selection_path),
            "campaign_sha256": sha256(out / "campaign.json"),
        }
        resume_provenance = out / "resume_provenance.json"
        if resume_provenance.is_file():
            extra["resume_provenance_sha256"] = sha256(resume_provenance)
        manifest(final, final_config, "complete", extra=extra)
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


def resume_uncertainty_shield(settings_path, models, out, resume_from, plots=True):
    """Reuse a complete validation lock after a timed-out test, never its outcomes.

    Experiment/controller/dependency hashes, checkpoints, settings and validation
    artifacts must match the original campaign. CLI/orchestration/paper-exporter and
    other non-runtime drift is recorded; the incomplete test is hashed and untouched.
    """
    settings_path = Path(settings_path).resolve()
    models, out, resume_from = Path(models).resolve(), Path(out).resolve(), Path(resume_from).resolve()
    protocol = ShieldProtocol(**json.loads(settings_path.read_text())).validate()
    if out.exists() or out == resume_from:
        raise FileExistsError("resume output must be a new directory distinct from the source campaign")
    original = json.loads((resume_from / "campaign.json").read_text())
    current = _identity(protocol, settings_path, models)
    for key in [
        "protocol",
        "settings_sha256",
        "source_config_sha256",
        "source_manifest_sha256",
        "model_sha256",
    ]:
        if original.get(key) != current.get(key):
            raise ValueError(f"resume source campaign changed its {key}")

    old_impl, new_impl = original["implementation_sha256"], current["implementation_sha256"]
    orchestration = {"src/media_rl/cli.py", "src/media_rl/evidence.py", "src/media_rl/uncertainty_shield.py"}
    runtime_paths = {
        name
        for name in set(old_impl) | set(new_impl)
        if (name.startswith("src/media_rl/") and name not in orchestration)
        or name in {"pyproject.toml", "uv.lock", ".python-version"}
    }
    mismatches = sorted(name for name in runtime_paths if old_impl.get(name) != new_impl.get(name))
    if mismatches:
        raise ValueError(f"resume is unsafe after runtime/dependency changes: {mismatches}")
    nonruntime_changes = sorted(
        name for name in set(old_impl) | set(new_impl) if old_impl.get(name) != new_impl.get(name)
    )

    validation = resume_from / "validation"
    validation_audit = audit_directory(validation, "complete")
    validation_manifest = json.loads((validation / "manifest.json").read_text())
    validation_sources = validation_manifest.get("source_sha256", {})
    validation_source_mismatches = sorted(
        name for name in runtime_paths if validation_sources.get(name) != old_impl.get(name)
    )
    validation_nonruntime_changes = sorted(
        name
        for name in set(old_impl) | set(validation_sources)
        if name not in runtime_paths and old_impl.get(name) != validation_sources.get(name)
    )
    if validation_source_mismatches:
        raise ValueError(
            "validation source snapshot differs from the original runtime lock: "
            f"{validation_source_mismatches}"
        )
    expected_validation = _evaluation_config(
        load_config(models / "config.json"),
        protocol,
        protocol.validation_seeds,
        "validation",
        [UNCERTAINTY_REFERENCE_METHOD, UNCERTAINTY_CANDIDATE_METHOD],
    )
    if validation_manifest.get("evaluation_split") != "validation" or not expected_validation.digest_matches(
        validation_manifest.get("config_sha256")
    ):
        raise ValueError("source campaign validation does not match the frozen V7 protocol")
    selection_path = resume_from / "selection.json"
    selection = json.loads(selection_path.read_text())
    if (
        selection.get("selection_split") != "validation"
        or selection.get("validation_manifest_sha256") != sha256(validation / "manifest.json")
        or selection.get("protocol") != asdict(protocol)
        or selection.get("validation_seeds") != protocol.validation_seeds
        or selection.get("test_seeds") != protocol.test_seeds
        or selection.get("baseline_model_sha256") != current["model_sha256"]
        or selection.get("candidate_model_sha256") != current["model_sha256"]
    ):
        raise ValueError("source campaign selection is not bound to its audited validation/model panel")

    partial_test = resume_from / "test"
    if (partial_test / "manifest.json").exists():
        raise ValueError("source campaign already has a complete test; do not duplicate it through resume")
    partial_artifacts = (
        {
            str(path.relative_to(partial_test)): sha256(path)
            for path in sorted(partial_test.rglob("*"))
            if path.is_file()
        }
        if partial_test.exists()
        else {}
    )

    out.mkdir(parents=True)
    dump_json(out / "campaign.json", current)
    (out / "settings.json").write_bytes(settings_path.read_bytes())
    (out / "base_config.json").write_bytes((models / "config.json").read_bytes())
    shutil.copytree(validation, out / "validation")
    shutil.copy2(selection_path, out / "selection.json")
    dump_json(
        out / "resume_provenance.json",
        dict(
            source_campaign=str(resume_from),
            source_campaign_sha256=sha256(resume_from / "campaign.json"),
            source_selection_sha256=sha256(selection_path),
            validation_manifest_sha256=sha256(validation / "manifest.json"),
            validation_artifacts_verified=len(validation_audit["artifacts_sha256"]),
            runtime_paths_verified=sorted(runtime_paths),
            validation_nonruntime_source_changes=validation_nonruntime_changes,
            nonruntime_source_changes=nonruntime_changes,
            preserved_partial_test_artifacts=partial_artifacts,
        ),
    )
    return run_uncertainty_shield(settings_path, models, out, plots=plots)
