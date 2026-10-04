import numpy as np
import pytest

from media_rl import native_action_atomic_diagnosis as diagnosis
from media_rl.networks import sigmoid


def test_group_uniform_population_surrogate_preserves_group_not_row_mass():
    group = np.asarray(["a", "a", "b", "b", "b"])
    weight = np.full(5, 12)
    q = diagnosis.group_population_weights(weight, group)
    assert np.isclose(q[group == "a"].sum(), 0.5) and np.isclose(q[group == "b"].sum(), 0.5)
    assert not np.array_equal(q, weight / weight.sum())
    assert "not exact finite_batch" in diagnosis.CONTRACT["gradient_measure"]


def test_shared_head_gradient_norm_cosine_match_independent_finite_differences():
    x = np.asarray([[0.3, 0.2, 0.1], [0.1, 0.4, 0.2], [0.2, 0.1, 0.3]])
    w = np.asarray([[0.1, 0.2], [0.2, 0.1], [0.1, 0.1]])
    b = np.asarray([0.3, 0.4])
    v = np.asarray([[0.2, -0.1], [0.1, 0.3]])
    c = np.asarray([0.1, -0.2])
    target = np.asarray([[0.7, 0.3], [0.2, 0.8], [0.4, 0.2]])
    q = np.asarray([0.2, 0.3, 0.5])
    gradients = []
    for head in (0, 1):

        def loss(matrix):
            logits = np.maximum(x @ matrix + b, 0) @ v + c
            p = sigmoid(logits)
            return np.sum(
                q
                * (
                    (p[:, 0] - target[:, 0]) ** 2
                    if head == 0
                    else np.logaddexp(0, logits[:, 1]) - target[:, 1] * logits[:, 1]
                )
            )

        g = np.zeros_like(w)
        for i, j in np.ndindex(w.shape):
            a = w.copy()
            z = w.copy()
            a[i, j] += 1e-6
            z[i, j] -= 1e-6
            g[i, j] = (loss(a) - loss(z)) / 2e-6
        gradients.append(g)
    r = diagnosis.shared_gradients(x, [w, b, v, c], target, q)
    a, z = gradients
    assert r["utility_shared_gradient_l2"] == pytest.approx(np.linalg.norm(a), abs=1e-9)
    assert r["risk_shared_gradient_l2"] == pytest.approx(np.linalg.norm(z), abs=1e-9)
    assert r["shared_gradient_cosine"] == pytest.approx(
        float(np.sum(a * z) / (np.linalg.norm(a) * np.linalg.norm(z))), abs=1e-8
    )


@pytest.mark.parametrize(
    "cv",
    [
        "results/native-action-balanced-matrix-v2",
        "results/native-failure-snapshot-replay-v3",
        "results/native-action-late-validation-v3",
    ],
)
def test_actual_partial_diagnostic_validation_inputs_never_enter_diagnosis(cv, tmp_path):
    out = tmp_path / "no-diagnosis"
    with pytest.raises((ValueError, FileNotFoundError)):
        diagnosis.diagnose(cv, out)
    assert not out.exists()


def test_error_contributions_exact_additive_physical_and_film_decomposition():
    d = dict(
        weight=np.asarray([2, 3, 4]),
        targets=np.asarray([[0.2, 0], [0.4, 0], [0.8, 0]]),
        film=np.asarray(["a", "a", "b"]),
        group=np.asarray(["x", "y", "y"]),
    )
    o = dict(
        conditional=np.asarray([[0.1, 0], [0.6, 0], [0.5, 0]]),
        blind=np.asarray([[0.3, 0], [0.5, 0], [0.7, 0]]),
    )
    r = diagnosis.error_contributions(d, o)
    for kind in ("film", "physical_group"):
        assert sum(
            x["weighted_conditional_minus_blind_utility_SSE"] for x in r["strata"] if x["kind"] == kind
        ) == pytest.approx(r["total_weighted_conditional_minus_blind_utility_SSE"])
    assert all(x["not_causal_attribution"] for x in r["strata"])
