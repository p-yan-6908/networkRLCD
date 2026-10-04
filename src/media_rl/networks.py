"""Small NumPy MLP with Adam; explicit gradients keep CPU experiments lightweight."""

import numpy as np


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -40, 40)))


class MLP:
    def __init__(self, inputs, hidden, outputs, rng):
        self.params = [
            rng.normal(0, np.sqrt(2 / inputs), (inputs, hidden)),
            np.zeros(hidden),
            rng.normal(0, np.sqrt(1 / hidden), (hidden, outputs)),
            np.zeros(outputs),
        ]
        self.m = [np.zeros_like(p) for p in self.params]
        self.v = [np.zeros_like(p) for p in self.params]
        self.updates = 0

    def __call__(self, x):
        w, b, v, c = self.params
        return np.maximum(np.asarray(x) @ w + b, 0) @ v + c

    def train(self, x, output_gradient, lr):
        w, b, v, _ = self.params
        hidden = np.maximum(x @ w + b, 0)
        dh = (output_gradient @ v.T) * (hidden > 0)
        grads = [x.T @ dh, dh.sum(axis=0), hidden.T @ output_gradient, output_gradient.sum(axis=0)]
        norm = np.sqrt(sum(np.sum(g * g) for g in grads))
        self.updates += 1
        for i, g in enumerate(grads):
            g = g * min(1.0, 10 / max(norm, 1e-12))
            self.m[i] = 0.9 * self.m[i] + 0.1 * g
            self.v[i] = 0.999 * self.v[i] + 0.001 * g * g
            mh = self.m[i] / (1 - 0.9**self.updates)
            vh = self.v[i] / (1 - 0.999**self.updates)
            self.params[i] -= lr * mh / (np.sqrt(vh) + 1e-8)

    def to_dict(self):
        return [p.tolist() for p in self.params]

    @classmethod
    def from_dict(cls, data):
        params = [np.asarray(p, dtype=float) for p in data]
        model = cls(params[0].shape[0], params[0].shape[1], params[2].shape[1], np.random.default_rng(0))
        model.params = params
        return model

    def copy_from(self, other):
        self.params = [p.copy() for p in other.params]
