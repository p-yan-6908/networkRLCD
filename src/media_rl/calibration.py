"""Binary probability of a proposed action satisfying next-interval constraints."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .networks import MLP, sigmoid


def risk_features(observation, action):
    x = observation.vector()
    return np.r_[
        x,
        action.bitrate_mbps / 4,
        action.fec,
        float(action.low_latency),
        action.wire_mbps / max(observation.throughput_mbps, 0.05) / 5,
    ]


def logit(p):
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return np.log(p / (1 - p))


@dataclass
class Calibrator:
    slope: float = 1.0
    bias: float = 0.0
    method: str = "identity"

    def predict(self, p):
        return sigmoid(self.slope * logit(np.asarray(p)) + self.bias)

    @classmethod
    def fit(cls, p, labels, method="platt"):
        p, y = np.asarray(p), np.asarray(labels)
        if (
            p.ndim != 1
            or p.size == 0
            or p.shape != y.shape
            or not np.all(np.isfinite(p))
            or np.any((p < 0) | (p > 1))
            or not np.all(np.isin(y, [0, 1]))
        ):
            raise ValueError("invalid calibration samples")
        if method not in {"platt", "temperature"}:
            raise ValueError("unknown calibration method")
        if len(np.unique(y)) == 1:
            # Finite smoothed prior for a degenerate held-out set, explicitly recorded.
            prior = (y.sum() + 1) / (len(y) + 2)
            return cls(0, float(logit(prior)), "constant_single_class")
        z = logit(p)

        def objective(theta):
            a = np.exp(theta[0])
            b = theta[1] if len(theta) == 2 else 0
            logits = a * z + b
            return np.mean(np.logaddexp(0, logits) - y * logits)

        n = 2 if method == "platt" else 1
        initial = np.zeros(n)
        result = minimize(
            objective, initial, method="L-BFGS-B", bounds=[(-5, 5)] + ([(-15, 15)] if n == 2 else [])
        )
        if not result.success or result.fun > objective(initial):
            return cls(method="identity_optimization_failed")
        return cls(float(np.exp(result.x[0])), float(result.x[1]) if n == 2 else 0, method)


class SafetyEnsemble:
    def __init__(self, models, mean, scale, support_limit):
        self.models, self.mean, self.scale = models, np.asarray(mean), np.asarray(scale)
        self.support_limit = float(support_limit)

    def normalized(self, x):
        return np.clip((np.asarray(x) - self.mean) / self.scale, -12, 12)

    def support_score(self, x):
        # Telemetry-only diagonal standardized distance, separate from probability.
        z = (np.asarray(x)[..., :10] - self.mean[:10]) / self.scale[:10]
        return np.sqrt(np.mean(z * z, axis=-1))

    def predict(self, x, single=False):
        z = self.normalized(x)
        models = self.models[:1] if single else self.models
        probabilities = np.stack([sigmoid(m(z)[..., 0]) for m in models])
        return probabilities.mean(axis=0), probabilities.std(axis=0)

    @classmethod
    def fit(cls, x, y, episodes, config, gate, rng):
        x, y, episodes = np.asarray(x), np.asarray(y), np.asarray(episodes)
        mean, scale = x.mean(axis=0), np.maximum(x.std(axis=0), 0.05)
        z = np.clip((x - mean) / scale, -12, 12)
        support = np.sqrt(np.mean(((x[:, :10] - mean[:10]) / scale[:10]) ** 2, axis=1))
        models = []
        ids = np.unique(episodes)
        for _ in range(config.ensemble_size):
            model = MLP(x.shape[1], config.hidden, 1, rng)
            # Bootstrap whole episodes, not correlated time steps.
            indices = np.concatenate(
                [np.flatnonzero(episodes == i) for i in rng.choice(ids, len(ids), replace=True)]
            )
            for _ in range(config.risk_epochs):
                rng.shuffle(indices)
                for start in range(0, len(indices), config.batch_size):
                    idx = indices[start : start + config.batch_size]
                    prediction = sigmoid(model(z[idx])[:, 0])
                    grad = ((prediction - y[idx]) / len(idx))[:, None]
                    model.train(z[idx], grad, config.learning_rate)
            models.append(model)
        return cls(models, mean, scale, np.quantile(support, gate.ood_quantile))

    def to_dict(self):
        return dict(
            models=[m.to_dict() for m in self.models],
            mean=self.mean.tolist(),
            scale=self.scale.tolist(),
            support_limit=self.support_limit,
        )

    @classmethod
    def from_dict(cls, data):
        return cls(
            [MLP.from_dict(m) for m in data["models"]], data["mean"], data["scale"], data["support_limit"]
        )
