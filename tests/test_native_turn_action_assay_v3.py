import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC_PATH = Path(__file__).resolve().parents[1] / "configs/native_turn_probe_v3_action_replication.json"
MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/native_turn_action_assay_v3.py"
MODULE_SPEC = importlib.util.spec_from_file_location("native_turn_action_assay_v3", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
V3_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(V3_MODULE)
verify_v3_trials = V3_MODULE.verify_v3_trials


def registered_spec():
    return json.loads(SPEC_PATH.read_text())


def test_v3_registration_has_full_crossing_and_action_support():
    spec = registered_spec()
    verify_v3_trials(spec)
    assert len(spec["trials"]) == 64
    assert spec["analysis"]["p_adjustment"] == "Holm across all six two-sided endpoint-by-contrast tests"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda spec: spec["trials"][0].update(exploration_seed=1), "peer identity or assignment seed"),
        (lambda spec: spec["trials"].reverse(), "capture order changed"),
        (lambda spec: spec["design"].update(scene_seeds=list(range(201, 209))), "crossed panel or randomized"),
    ],
)
def test_v3_registration_rejects_seed_schedule_changes(mutate, message):
    spec = copy.deepcopy(registered_spec())
    mutate(spec)
    with pytest.raises(ValueError, match=message):
        verify_v3_trials(spec)
