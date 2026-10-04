import numpy as np
import pytest

from media_rl import native_failure_evidence_replay as base
from media_rl import native_failure_snapshot as snapshot
from media_rl import native_failure_snapshot_replay as replay
from media_rl.native_protocol import read_json


def test_role_metadata_only_adapter_preserves_every_factual_array_and_original_collector_role():
    state = np.arange(736)
    cohort = dict(
        role="train",
        state=state,
        weight=12,
        cap=300000,
        utility=0.3,
        miss=0.7,
        window_start_ms=1800,
        window_end_ms=2200,
    )
    d = dict(
        late_credit=dict(cohorts=[cohort], requests=12),
        early_reference=dict(cohorts=[cohort]),
        quality=dict(actual=True),
    )
    r = replay.diagnostic_cohort_metadata(d, "diagnostic")
    for field in ("late_credit", "early_reference"):
        c = r[field]["cohorts"][0]
        assert c["role"] == "diagnostic" and c["original_hardcoded_collector_role"] == "train"
        assert all(c[k] is v for k, v in cohort.items() if k != "role")
    assert d["late_credit"]["cohorts"][0]["role"] == "train" and r["quality"] is d["quality"]


def test_train_role_not_allowed_to_use_diagnostic_metadata_adapter():
    with pytest.raises(ValueError):
        replay.diagnostic_cohort_metadata({}, "train")


@pytest.mark.parametrize("role", ["diagnostic", "calibration", None])
def test_only_exact_legacy_hardcoded_role_can_be_corrected(role):
    d = dict(late_credit=dict(cohorts=[dict(role=role)]), early_reference=dict(cohorts=[]))
    with pytest.raises(ValueError):
        replay.diagnostic_cohort_metadata(d, "diagnostic")


def test_actual_atomic_snapshot_source_role_and_replay_bytecode_scope_unchanged():
    cfg = read_json("configs/native_failure_snapshot_diagnostic_v2.json")
    p = snapshot.validate_plan(cfg)
    assert p["stage"] == p["episodes"][0]["role"] == "diagnostic" and len(p["episodes"]) == 1
    assert (
        replay.replay.__code__ is base.replay.__code__
        and replay.audit_replay.__code__ is base.audit_replay.__code__
    )
    assert replay._NS["inspect_source"].__code__ is base.inspect_source.__code__
    assert replay._capture.RAW_PEER is replay._raw_peer
