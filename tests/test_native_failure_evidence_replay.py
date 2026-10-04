import pytest

from media_rl import native_failure_evidence as capture
from media_rl import native_failure_evidence_replay as replay


def test_legacy_summary_projection_preserves_null_omits_object_undefined_and_nulls_array_nonfinites():
    source = dict(
        nullable=None,
        missing={capture.TAG: "undefined"},
        values=[
            {capture.TAG: "undefined"},
            {capture.TAG: "NaN"},
            {capture.TAG: "+Infinity"},
            {capture.TAG: "-Infinity"},
            0.003,
        ],
    )
    assert replay.legacy_json(source) == dict(nullable=None, values=[None, None, None, None, 0.003])
    assert source["missing"] == {capture.TAG: "undefined"}


def test_exact_summary_numeric_payload_unchanged_only_actual_counter_phases_may_grow():
    raw = dict(raw_event_count=39148, native_result=dict(meaning="original native return", count=294))
    summary = dict(meaning="original native return", count=294, raw_event_count=39152)
    assert replay.verify_summary(raw, summary, 39152) == 39152
    assert raw["raw_event_count"] == 39148 and summary["raw_event_count"] == 39152


@pytest.mark.parametrize("case", ["pre-after-final", "wrong-gzip", "changed-native-field", "invented-field"])
def test_actual_counter_or_native_payload_mismatch_rejected_not_blanket_comparison_relaxation(case):
    raw = dict(raw_event_count=100, native_result=dict(count=294))
    summary = dict(count=294, raw_event_count=104)
    events = 104
    if case == "pre-after-final":
        raw["raw_event_count"] = 105
    elif case == "wrong-gzip":
        events = 103
    elif case == "changed-native-field":
        summary["count"] = 295
    else:
        summary["invented"] = True
    with pytest.raises(ValueError):
        replay.verify_summary(raw, summary, events)
