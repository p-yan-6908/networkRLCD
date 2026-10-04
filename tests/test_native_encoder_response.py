import copy
from pathlib import Path

import pytest

from media_rl.native_encoder_response import (
    ABI,
    FIELDS,
    NUMERIC_FIELDS,
    project_encoder_collector,
    summarize_encoder_sidecars,
    validate_encoder_sidecar,
)


def fixture():
    fields = {k: dict(status="present", value=0 if k in NUMERIC_FIELDS else "none") for k in FIELDS}
    fields["targetBitrate"]["value"] = 450000
    s = dict(
        abi=ABI,
        used_by_controller=False,
        stream_key="tx:7",
        stats_id="tx",
        ssrc="7",
        codec_id="c",
        mime_type="video/VP8",
        stats_timestamp_ms=1000,
        sample_ms=100,
        time_origin_epoch_ms=100000,
        capture_cost_ms=0,
        fields=fields,
    )
    obs = dict(
        sample_ms=100,
        raw_source=dict(
            stream_key="tx:7", bytes_sent=0, frames_encoded=0, total_encode_s=0, encoder_cap_bps=450000
        ),
    )
    return s, obs


@pytest.mark.parametrize(
    "kind", ["stream", "sample", "origin", "bool", "absent-padded", "actor", "counter", "timestamp", "fields"]
)
def test_invalid_sidecar(kind):
    s, o = fixture()
    if kind == "stream":
        s["ssrc"] = "8"
    elif kind == "sample":
        s["sample_ms"] = 1
    elif kind == "origin":
        s["time_origin_epoch_ms"] = 1
    elif kind == "bool":
        s["fields"]["qpSum"]["value"] = True
    elif kind == "absent-padded":
        s["fields"]["qpSum"]["status"] = "absent"
    elif kind == "actor":
        s["used_by_controller"] = True
    elif kind == "counter":
        s["fields"]["bytesSent"]["value"] = 1
    elif kind == "timestamp":
        s["stats_timestamp_ms"] = -1
    else:
        s["fields"].pop("totalEncodedBytesTarget")
    with pytest.raises(ValueError):
        validate_encoder_sidecar(s, o, 100000)


@pytest.mark.parametrize("kind", ["absent", "reset", "impossible"])
def test_optional_retransmission_counter_does_not_block_qp_or_fake_zero(kind):
    sender, frames = pair()
    first, second = [r["encoder_response"] for r in sender["decisions"]]
    if kind == "absent":
        second["fields"]["retransmittedBytesSent"].update(status="absent", value=None)
    elif kind == "reset":
        first["fields"]["retransmittedBytesSent"]["value"] = 10
    else:
        second["fields"]["retransmittedBytesSent"]["value"] = 1001
    interval = summarize_encoder_sidecars(sender, frames)["valid_intervals"][0]
    assert interval["mean_vp8_qp"] == 20
    assert interval["sent_nonretransmitted_payload_mbps"] is None


def test_projection_only_auxiliary_data_and_fail_closed():
    old = Path("benchmarks/native_rtc/excitation_episode.mjs").read_text()
    new = project_encoder_collector(old)
    assert "encoder_response,feedback_input" in new
    policy = "const policyInput={observation_abi:observation.observation_abi,feature_names:observation.feature_names,features:observation.features};"
    assert old.count(policy) == new.count(policy) == 1
    with pytest.raises(ValueError):
        project_encoder_collector(new)


def pair():
    s, o = fixture()
    t, p = copy.deepcopy((s, o))
    t["sample_ms"] = p["sample_ms"] = 200
    t["stats_timestamp_ms"] = 1100
    t["fields"]["qpSum"]["value"] = 60
    t["fields"]["framesEncoded"]["value"] = 3
    t["fields"]["bytesSent"]["value"] = 1000
    p["raw_source"].update(frames_encoded=3, bytes_sent=1000)
    return dict(
        learned_policy=False,
        decisions=[
            dict(step_id=0, observation=o, encoder_response=s),
            dict(step_id=1, observation=p, encoder_response=t),
        ],
    ), dict(time_origin_epoch_ms=100000)


def test_real_delta_units_zero_frames_no_mutation():
    sender, frames = pair()
    before = copy.deepcopy(sender)
    r = summarize_encoder_sidecars(sender, frames)
    v = r["valid_intervals"][0]
    assert v["mean_vp8_qp"] == 20 and v["sent_payload_mbps"] == 0.08
    assert not r["encoder_response_lag_established"] and not r["SOTA_achieved"] and sender == before
    sender["decisions"][1]["observation"]["raw_source"]["frames_encoded"] = 0
    sender["decisions"][1]["encoder_response"]["fields"]["framesEncoded"]["value"] = 0
    assert summarize_encoder_sidecars(sender, frames)["valid_intervals"][0]["mean_vp8_qp"] is None


@pytest.mark.parametrize(
    "reason",
    ["qpSum_missing", "qpSum_reset", "stats_timestamp_missing_or_stale", "cap_change", "sample_interval"],
)
def test_invalid_intervals_not_used(reason):
    sender, frames = pair()
    row = sender["decisions"][1]
    s = row["encoder_response"]
    if reason == "qpSum_missing":
        s["fields"]["qpSum"].update(status="absent", value=None)
    elif reason == "qpSum_reset":
        sender["decisions"][0]["encoder_response"]["fields"]["qpSum"]["value"] = 100
    elif reason == "stats_timestamp_missing_or_stale":
        s["stats_timestamp_ms"] = 1000
    elif reason == "cap_change":
        row["observation"]["raw_source"]["encoder_cap_bps"] = 300000
    else:
        s["sample_ms"] = row["observation"]["sample_ms"] = 100
    r = summarize_encoder_sidecars(sender, frames)
    assert not r["valid_intervals"] and r["dropped_intervals"][reason] == 1
