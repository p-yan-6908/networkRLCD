"""Post-hoc calibration on actions selected by the top-k safety screen."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .calibration import Calibrator, risk_features
from .config import load_config, split_seed
from .controllers import make_controller
from .environment import MediaEnvironment, action_space
from .experiment import dump_json, initialize, manifest, sha256, validate_bundle, write_csv
from .improvement import audit_directory
from .scenarios import ID_SCENARIOS, make_trace
from .training import ModelBundle


@dataclass(frozen=True)
class ActionCalibrationProtocol:
    name: str
    episodes: int
    split_namespace: str
    top_k: int
    threshold: float
    calibration: str

    def validate(self, config):
        if not self.name or type(self.episodes) is not int or self.episodes < 1:
            raise ValueError("action calibration requires a name and positive episode count")
        if self.split_namespace != "action_calibration_v6":
            raise ValueError("v6 action calibration must use the frozen action_calibration_v6 namespace")
        if self.top_k != config.gate.shield_top_k or self.threshold != config.gate.threshold:
            raise ValueError("calibration screen top_k/threshold must match the source model configuration")
        if self.calibration != config.gate.calibration:
            raise ValueError("calibration method must match the source model configuration")
        if not np.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("calibration threshold must be a finite probability")
        return self


def collect_selected_action_samples(config, seed, bundle, protocol):
    """Collect raw scores and outcomes from the frozen screen's ID closed-loop rollouts."""
    raw_scores, labels, records = [], [], []
    actions = action_space(config.simulator)
    for episode in range(protocol.episodes):
        scenario = ID_SCENARIOS[episode % len(ID_SCENARIOS)]
        trace_seed = split_seed(seed, protocol.split_namespace, episode)
        env = MediaEnvironment(config.simulator, make_trace(scenario, config.simulator.steps, trace_seed))
        controller = make_controller(
            "shielded", bundle, actions, config.gate, config.simulator.dt_s, threshold=protocol.threshold
        )
        obs = env.reset()
        for step in range(config.simulator.steps):
            decision = controller.act(obs)
            preview = env.preview(decision.action)
            old_obs = obs
            obs, _, _, info = env.step(decision.action)
            if preview["safe"] != info["safe"]:
                raise RuntimeError("preview and executed one-step safety labels disagree")
            if decision.action_confidence is not None:
                features = risk_features(old_obs, env.actions[decision.action])
                probability, _ = bundle.safety.predict(features)
                score = float(np.asarray(probability).reshape(-1)[0])
                label = int(bool(info["safe"]))
                if not np.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError("selected-action safety model returned an invalid probability")
                raw_scores.append(score)
                labels.append(label)
                records.append(
                    dict(
                        model_seed=seed,
                        episode=episode,
                        step=step,
                        scenario=scenario,
                        trace_seed=trace_seed,
                        proposal=decision.proposal,
                        action=decision.action,
                        old_calibrated_confidence=decision.action_confidence,
                        raw_probability=score,
                        safe=label,
                    )
                )
    if not raw_scores:
        raise ValueError(f"selected-action calibration collected no accepted actions for seed {seed}")
    return np.asarray(raw_scores), np.asarray(labels, dtype=int), records


def recalibrate_screen_models(settings_path, source_models, out):
    """Write immutable derived checkpoints with a calibrator fitted on selected ID actions."""
    settings_path, source_models, out = (
        Path(settings_path).resolve(),
        Path(source_models).resolve(),
        Path(out).resolve(),
    )
    if out == source_models or out.is_relative_to(source_models) or source_models.is_relative_to(out):
        raise ValueError("derived calibration run and source model run must be disjoint directories")
    protocol = ActionCalibrationProtocol(**json.loads(settings_path.read_text()))
    config = load_config(source_models / "config.json")
    protocol.validate(config)
    source_manifest = audit_directory(source_models, "trained")
    seeds = config.seeds
    if any(f"models/seed_{seed}.json" not in source_manifest["artifacts_sha256"] for seed in seeds):
        raise ValueError("source model run is missing a declared seed checkpoint")
    checkpoint_hashes = {str(seed): sha256(source_models / "models" / f"seed_{seed}.json") for seed in seeds}
    identity = dict(
        protocol=asdict(protocol),
        protocol_sha256=sha256(settings_path),
        source_model_run=str(source_models),
        source_manifest_sha256=sha256(source_models / "manifest.json"),
        source_config_sha256=sha256(source_models / "config.json"),
        source_checkpoint_sha256=checkpoint_hashes,
        config_sha256=config.digest(),
    )
    identity_path = out / "calibration_identity.json"
    if out.exists() and any(out.iterdir()):
        if not identity_path.is_file() or json.loads(identity_path.read_text()) != identity:
            raise ValueError(
                "calibration output exists with different or incomplete provenance; use a new path"
            )
        audit_directory(out, "trained")
        return dict(output=str(out), resumed=True, model_seeds=seeds)

    initialize(out, config)
    (out / "models").mkdir(exist_ok=True)
    (out / "action_calibration_protocol.json").write_bytes(settings_path.read_bytes())
    dump_json(identity_path, identity)
    summary, records = [], []
    for seed in seeds:
        source_path = source_models / "models" / f"seed_{seed}.json"
        bundle = ModelBundle.load(source_path)
        validate_bundle(bundle, config, seed)
        raw, labels, rows = collect_selected_action_samples(config, seed, bundle, protocol)
        calibrator = Calibrator.fit(raw, labels, protocol.calibration)
        from .metrics import calibration_metrics

        before = calibration_metrics(bundle.calibrator.predict(raw), labels)
        after = calibration_metrics(calibrator.predict(raw), labels)
        metadata = dict(bundle.metadata)
        metadata["selected_action_calibration"] = dict(
            protocol=protocol.name,
            protocol_sha256=identity["protocol_sha256"],
            source_bundle_sha256=checkpoint_hashes[str(seed)],
            split_namespace=protocol.split_namespace,
            trace_seeds=[
                split_seed(seed, protocol.split_namespace, episode) for episode in range(protocol.episodes)
            ],
            episodes=protocol.episodes,
            samples=len(labels),
            positive_rate=float(labels.mean()),
            threshold=protocol.threshold,
            top_k=protocol.top_k,
            calibration_method=calibrator.method,
            fit_ece_before=float(before["ece"]),
            fit_ece_after=float(after["ece"]),
            fit_brier_before=float(before["brier"]),
            fit_brier_after=float(after["brier"]),
            fit_metrics_are_in_sample=True,
        )
        candidate = ModelBundle(bundle.policy, bundle.safety, calibrator, bundle.single_calibrator, metadata)
        if (
            candidate.policy.to_dict() != bundle.policy.to_dict()
            or candidate.safety.to_dict() != bundle.safety.to_dict()
        ):
            raise RuntimeError("selected-action recalibration changed policy or safety-model weights")
        candidate.save(out / "models" / f"seed_{seed}.json")
        for row, calibrated in zip(rows, calibrator.predict(raw)):
            records.append(dict(**row, new_calibrated_probability=float(calibrated)))
        summary.append(
            dict(
                model_seed=seed,
                episodes=protocol.episodes,
                selected_action_samples=len(labels),
                unsafe_rate=float(1 - labels.mean()),
                calibrator_method=calibrator.method,
                fit_ece_before=before["ece"],
                fit_ece_after=after["ece"],
                fit_brier_before=before["brier"],
                fit_brier_after=after["brier"],
            )
        )
    write_csv(out / "selected_calibration_summary.csv", summary)
    write_csv(out / "selected_calibration_samples.csv", records)
    source_provenance = json.loads((source_models / "manifest.json").read_text())
    dump_json(
        out / "manifest.json",
        {
            "training_provenance": source_provenance.get(
                "training_provenance", source_provenance["source_sha256"]
            )
        },
    )
    manifest(
        out,
        config,
        "trained",
        extra=dict(
            derivation="selected-action-only post-hoc Platt recalibration; policy/safety weights frozen",
            source_model_run=str(source_models),
            source_manifest_sha256=identity["source_manifest_sha256"],
            action_calibration_protocol_sha256=identity["protocol_sha256"],
        ),
    )
    return dict(
        output=str(out),
        resumed=False,
        model_seeds=seeds,
        sample_counts={str(row["model_seed"]): row["selected_action_samples"] for row in summary},
    )
