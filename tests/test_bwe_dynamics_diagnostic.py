"""Causal feature boundaries, grouped fitting, fair weighting and factual replay."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from media_rl import bwe_dynamics_diagnostic as diagnostic

ROOT = Path(__file__).resolve().parents[1]


def test_future_observations_and_caps_never_enter_current_features():
    bwe, cap = [300.0, 600.0, 900.0], [150.0, 390.0, 585.0]
    original = diagnostic.features(bwe, cap, 1)
    bwe[2], cap[2] = 9e8, 4e6
    assert diagnostic.features(bwe, cap, 1) == original
    cap[1] = 200.0
    changed = diagnostic.features(bwe, cap, 1)
    assert changed[:4] == original[:4] and changed[4] != original[4]
    assert diagnostic.features(bwe, cap, 0)[1:4] == [0.0, 0.0, 0.0]


def invented_rows():
    rows = []
    for source in range(4):
        for regime in range(3):
            for arm in range(2):
                for epoch in range(3):
                    rows.append(
                        dict(
                            source=f"s{source}",
                            regime=f"r{regime}",
                            arm=f"a{arm}",
                            trial=f"s{source}-r{regime}-a{arm}",
                            epoch=epoch,
                            x=[float(source + regime), 0.1 * epoch, -0.4 * arm, float(epoch > 0), -0.4 * arm],
                            y=0.1 * source - 0.2 * regime + 0.02 * epoch + 0.05 * arm,
                        )
                    )
    return rows


def test_weighting_gives_equal_cells_and_does_not_reward_more_epochs():
    rows = invented_rows()
    w = diagnostic.weights(rows)
    assert w.sum() == pytest.approx(1.0)
    assert len(set(np.round(w, 12))) == 1
    duplicated = rows + [r for r in rows if r["trial"] == rows[0]["trial"]]
    original, repeated = diagnostic.fit(rows, 0.01), diagnostic.fit(duplicated, 0.01)
    for model in ("state_ridge", "cap_ridge"):
        assert repeated["models"][model]["mean"] == pytest.approx(original["models"][model]["mean"])
        assert repeated["models"][model]["coef"] == pytest.approx(original["models"][model]["coef"])


@pytest.mark.parametrize("key", ["source", "regime"])
def test_group_folds_exclude_the_entire_group_and_normalize_only_training(key):
    rows = invented_rows()
    predictions, fits = diagnostic.cross_validate(rows, key, 0.01)
    assert set(predictions) == set(diagnostic.MODELS)
    assert all(np.isfinite(v).all() and len(v) == len(rows) for v in predictions.values())
    for held, fit in fits.items():
        assert held not in fit["training_sources" if key == "source" else "training_regimes"]
        train = [r for r in rows if r[key] != held]
        expected = diagnostic.weights(train) @ np.array([r["x"][:4] for r in train])
        assert fit["models"]["state_ridge"]["mean"] == pytest.approx(expected)


@pytest.fixture(scope="module")
def factual_sessions():
    return json.loads((ROOT / "results/native-range-pilot-v1-report/sessions.json").read_text())


def test_native_cap_aliasing_and_one_factual_outcome_per_observed_epoch(factual_sessions):
    rows, aliases = diagnostic.read_rows(factual_sessions, "range", 12, 240)
    assert len(rows) == 1200
    assert aliases["consecutive_nominal_action_changes"] == 0
    assert aliases["alias_share_by_arm"]["0.25"] == pytest.approx(0.6701388888888888)
    assert aliases["alias_share_by_arm"]["0.65"] == 0
    first = rows[0]
    original = factual_sessions[0]
    assert first["y"] == pytest.approx(np.log(original["estimate_kbps"][1] / original["estimate_kbps"][0]))
    # Receiver quality and schedule metadata are absent from the numerical features.
    modified = copy.deepcopy(factual_sessions)
    for session in modified:
        session["session"]["utility"] = -1e9
        session["jitter_buffer_ms"] = [1e9] * len(session["jitter_buffer_ms"])
    changed, _ = diagnostic.read_rows(modified, "range", 12, 240)
    assert [r["x"] for r in changed] == [r["x"] for r in rows]
    assert [r["y"] for r in changed] == [r["y"] for r in rows]


@pytest.mark.parametrize("damage", ["incomplete", "nonfinite", "cap", "ceiling"])
def test_invalid_factual_sequences_fail_closed(factual_sessions, damage):
    sessions = copy.deepcopy(factual_sessions)
    if damage == "incomplete":
        sessions[0] = copy.deepcopy(sessions[1])
    elif damage == "nonfinite":
        sessions[0]["estimate_kbps"][0] = float("nan")
    elif damage == "cap":
        sessions[0]["requested_kbps"][0] += 1.0
    else:
        ceiling = next(s for s in sessions if s["level"] == 4)
        ceiling["requested_kbps"][0] = 2000.0
    with pytest.raises(ValueError):
        diagnostic.read_rows(sessions, "range", 12, 240)


def test_saved_full_fit_replays_all_transfer_predictions():
    path = ROOT / "reports/bwe-dynamics-diagnostic-v1"
    if not path.exists():
        pytest.skip("completed development diagnostic not bundled")
    models = json.loads((path / "models.json").read_text())
    with np.load(path / "predictions.npz", allow_pickle=False) as data:
        for panel in ("ladder_transfer", "margin_transfer"):
            rows = [{"x": list(x)} for x in data[panel + "__x"]]
            predictions = diagnostic.predict(models["full_range_fit"], rows)
            for name, values in predictions.items():
                assert values == pytest.approx(data[panel + "__" + name], rel=1e-12, abs=1e-12)
