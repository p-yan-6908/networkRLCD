from pathlib import Path

import pytest


ARTIFACT_DEPENDENT_MODULES = {
    "test_native_action_atomic_diagnosis_v2.py",
    "test_native_action_atomic_matrix.py",
    "test_native_action_atomic_portable_audit.py",
    "test_native_action_balanced_hold.py",
    "test_native_action_balanced_matrix.py",
    "test_native_action_hold_response_diagnosis.py",
    "test_native_action_ordered_projection.py",
    "test_native_context_replay.py",
}


def pytest_collection_modifyitems(config, items):
    repository = Path(__file__).resolve().parents[1]
    evidence = repository / "results/native-action-atomic-value-cv-v4/train_rows.npz"
    if evidence.is_file():
        return

    skip = pytest.mark.skip(
        reason="Requires generated research artifacts omitted from the public source repository."
    )
    for item in items:
        if Path(str(item.fspath)).name in ARTIFACT_DEPENDENT_MODULES:
            item.add_marker(skip)
