"""Reject future encoded output, forged causal features and unacknowledged caps."""

import copy

import pytest

from media_rl.native_observations import FEATURE_NAMES, NATIVE_OBSERVATION_ABI, NativeSenderObservationEncoder
from media_rl.native_turn_audit import audit_sender


def peer():
    raw = dict(
        stream_key="tx:1",
        bwe_bps=300000,
        rtcp_rtt_s=None,
        rtcp_rtt_measurements=None,
        bytes_sent=10,
        frames_encoded=1,
        total_encode_s=0.01,
        packets_sent=1,
        total_packet_send_delay_s=0,
        encoder_cap_bps=300000,
        receiver_target_ms=0,
    )
    encoder = NativeSenderObservationEncoder()
    rows = []
    for i, at in enumerate((10, 110)):
        own = dict(raw, encoder_cap_bps=300000 if i == 0 else 195000)
        rows.append(
            dict(
                step_id=i,
                observation=dict(
                    observation_abi=NATIVE_OBSERVATION_ABI,
                    sample_ms=at,
                    raw_source=own,
                    feature_names=list(FEATURE_NAMES),
                    features=encoder.observe(own, at),
                ),
                encoded_snapshot=dict(
                    abi="native_encoded_payload_meter_v1",
                    status="active",
                    sample_ms=at,
                    total_bytes=10,
                    total_frames=1,
                ),
                assignment=dict(requested_bps=195000) if i == 0 else None,
                actuation_readback=dict(encoder_max_bitrate_bps=195000, receiver_jitter_buffer_target_ms=0)
                if i == 0
                else None,
                ack_ms=11 if i == 0 else None,
                encoder_response=dict(fields=dict(qpSum=dict(status="absent", value=None))),
            )
        )
    return dict(
        measurement_start_ms=1,
        measurement_cutoff_ms=120,
        decisions=rows,
        encoded_meter=dict(
            events=[
                dict(at_ms=5, total_bytes=10, total_frames=1),
                dict(at_ms=115, total_bytes=20, total_frames=2),
            ]
        ),
    )


def test_reconstructs_causal_features_and_excludes_future_encoded_frame():
    result = audit_sender(peer())
    assert result["encoded_snapshots_replayed"] == 2
    assert result["rtt_present_samples"] == 0
    assert result["encoder_field_present_counts"]["qpSum"] == 0


@pytest.mark.parametrize("kind", ["feature", "future-frame", "cap", "ack", "receiver", "oracle", "clock"])
def test_rejects_causal_forgeries(kind):
    forged = copy.deepcopy(peer())
    first, second = forged["decisions"]
    if kind == "feature":
        second["observation"]["features"][0] += 0.1
    elif kind == "future-frame":
        second["encoded_snapshot"].update(total_bytes=20, total_frames=2)
    elif kind == "cap":
        second["observation"]["raw_source"]["encoder_cap_bps"] = 300000
        second["observation"]["features"][7] = 300000 / 4e6
    elif kind == "ack":
        first["ack_ms"] = 111
    elif kind == "receiver":
        first["actuation_readback"]["receiver_jitter_buffer_target_ms"] = 10
    elif kind == "oracle":
        second["observation"]["raw_source"]["capacity_mbps"] = 4
    else:
        second["observation"]["sample_ms"] = 121
    with pytest.raises(ValueError):
        audit_sender(forged)
