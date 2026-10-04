from pathlib import Path

import pytest

from media_rl import native_action_atomic_matrix as matrix
from media_rl import native_action_atomic_portable_audit as adapter
from media_rl import native_action_atomic_value_cv as value
from media_rl.native_protocol import read_json


def test_actual_frozen_plan_portable_view_same_runtime_no_file_or_numeric_change(monkeypatch):
    cfg = read_json("configs/native_action_atomic_matrix_v4.json")
    actual = matrix._dependencies(value)
    relocated = {"/tmp/extracted-wheel/media_rl/" + Path(k).name: v for k, v in actual.items()}
    expected = matrix.validate_plan(cfg)
    monkeypatch.setattr(matrix, "_dependencies", lambda _: relocated)
    assert adapter.validate_plan(cfg) == expected
    assert adapter.portable_dependencies(cfg, relocated) == cfg["dependencies_sha256"]
    assert not hasattr(adapter, "fit_cv") and not hasattr(adapter, "collect_matrix")


@pytest.mark.parametrize("case", ["checksum", "missing", "extra", "same-name-collision"])
def test_portable_view_never_loosens_executing_source_identity(case):
    cfg = read_json("configs/native_action_atomic_matrix_v4.json")
    actual = matrix._dependencies(value)
    key = next(iter(actual))
    if case == "checksum":
        actual[key] = "0" * 64
    elif case == "missing":
        actual.pop(key)
    elif case == "extra":
        actual["/tmp/additional.py"] = "0" * 64
    else:
        actual["/tmp/" + Path(key).name] = actual[key]
    with pytest.raises(ValueError):
        adapter.portable_dependencies(cfg, actual)


def test_portable_public_audits_use_exact_original_validation_and_numerical_bytecode():
    assert adapter.audit_matrix.__code__ is matrix.audit_matrix.__code__
    assert adapter._MATRIX_NS["validate_plan"] is adapter.validate_plan
    assert adapter.audit_cv.__code__.co_code == value.audit_cv.__code__.co_code
    assert adapter.LOAD.__code__ is value.LOAD.__code__
    assert adapter._CV_NS["_report"] is value.REPORT
    assert adapter._CV_NS["evaluate"] is value._NS["evaluate"]
