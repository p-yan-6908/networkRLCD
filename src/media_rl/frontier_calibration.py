"""Separate post-selection calibration for packet capture-cohort safety targets.

Does not change the frozen V6 ID/one-step calibration API or any policy/risk weights.
"""

from dataclasses import asdict, dataclass, replace

import numpy as np

from .calibration import Calibrator, risk_features
from .config import split_seed
from .controllers import make_controller
from .environment import action_space
from .experiment import validate_bundle
from .training import id_environment


@dataclass(frozen=True)
class FrontierCalibrationProtocol:
    episodes: int = 30
    split_namespace: str = "frontier_calibration_v12"

    def validate(self, config, bundle, seed):
        config.validate()
        validate_bundle(bundle, config, seed)
        if type(self.episodes) is not int or self.episodes < 1:
            raise ValueError("frontier calibration needs a positive integer episode count")
        if self.split_namespace != "frontier_calibration_v12":
            raise ValueError("frontier calibration requires its dedicated seed namespace")
        if config.simulator.backend != "packet_v2" or config.training.safety_horizon_steps <= 1:
            raise ValueError("frontier calibration requires a deadline-resolved packet cohort target")
        if config.gate.shield_top_k != len(action_space(config.simulator)):
            raise ValueError("frontier calibration requires the full action search")
        return self


def collect_frontier_samples(config, seed, bundle, protocol):
    """Collect only accepted source-screen actions, never proposal/fallback score proxies.

    Labels describe fixed-action continuation through actual newly captured deadlines;
    terminal labels are censored. Changed online continuation is not certified.
    """
    protocol.validate(config, bundle, seed)
    scores, labels, records = [], [], []
    accepted, censored = 0, 0
    horizon = config.training.safety_horizon_steps
    for episode in range(protocol.episodes):
        env = id_environment(config, seed, protocol.split_namespace, episode)
        controller = make_controller(
            "shielded_uncertainty", bundle, env.actions, config.gate, config.simulator.dt_s
        )
        obs = env.reset()
        for step in range(config.simulator.steps):
            decision = controller.act(obs)
            if not decision.fallback:
                accepted += 1
                target = env.safety_preview(decision.action, horizon)
                if target.get("label_censored", False):
                    censored += 1
                else:
                    p, _ = bundle.safety.predict(risk_features(obs, env.actions[decision.action]))
                    score = float(np.asarray(p).reshape(-1)[0])
                    if not np.isfinite(score) or not 0 <= score <= 1:
                        raise ValueError("frontier safety model returned an invalid probability")
                    scores.append(score)
                    labels.append(int(target["safe"]))
                    records.append(
                        dict(
                            model_seed=seed,
                            episode=episode,
                            step=step,
                            scenario=env.trace.name,
                            trace_seed=split_seed(seed, protocol.split_namespace, episode),
                            proposal=decision.proposal,
                            action=decision.action,
                            raw_probability=score,
                            source_calibrated_probability=decision.action_confidence,
                            safe=int(target["safe"]),
                            label_horizon_steps=horizon,
                        )
                    )
            obs, _, _, _ = env.step(decision.action)
    if not scores:
        raise ValueError("no accepted uncensored source-frontier calibration samples")
    return (
        np.asarray(scores),
        np.asarray(labels, dtype=int),
        records,
        dict(accepted=accepted, censored_excluded=censored),
    )


def recalibrate_frontier_bundle(config, seed, bundle, protocol):
    """One-pass monotonic calibration; actor, ensemble, scaler and single calibrator stay frozen."""
    raw, labels, rows, counts = collect_frontier_samples(config, seed, bundle, protocol)
    calibrator = Calibrator.fit(raw, labels, config.gate.calibration)
    metadata = dict(bundle.metadata)
    metadata["split_trace_seeds"] = dict(bundle.metadata["split_trace_seeds"])
    metadata["split_trace_seeds"][protocol.split_namespace] = [
        split_seed(seed, protocol.split_namespace, e) for e in range(protocol.episodes)
    ]
    metadata["frontier_calibration"] = dict(
        protocol=asdict(protocol),
        samples=len(labels),
        positive_rate=float(labels.mean()),
        **counts,
        source_calibrator=asdict(bundle.calibrator),
        scope="accepted source-frontier actions under fixed candidate continuation",
        changed_selection_distribution_not_certified=True,
    )
    return replace(bundle, calibrator=calibrator, metadata=metadata), rows
