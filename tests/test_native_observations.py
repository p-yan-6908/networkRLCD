import pytest

from media_rl.native_observations import NativeSenderObservationEncoder


def raw():
    return dict(
        stream_key="s",
        bwe_bps=2000000,
        rtcp_rtt_s=0.05,
        rtcp_rtt_measurements=1,
        bytes_sent=1000,
        frames_encoded=3,
        total_encode_s=0.003,
        packets_sent=5,
        total_packet_send_delay_s=0.002,
        encoder_cap_bps=1600000,
        receiver_target_ms=0,
    )


def test_independent_native_units_and_first_sample_masks():
    e = NativeSenderObservationEncoder()
    r = raw()
    first = e.observe(r, 100)
    assert len(first) == 16 and first[12:15] == [0, 0, 0]
    r.update(
        bytes_sent=51000,
        frames_encoded=6,
        total_encode_s=0.006,
        packets_sent=10,
        total_packet_send_delay_s=0.008,
    )
    a = e.observe(r, 200)
    assert a[3:5] == [1, 1]
    assert a[5] == pytest.approx(0.03)
    assert a[6] == pytest.approx(1.2 / 150)
    assert a[7:9] == [0.4, 1]


def test_rtcp_age_requires_observed_counter_advance_not_query_time():
    e = NativeSenderObservationEncoder()
    r = raw()
    assert e.observe(r, 100)[11] == 0
    assert e.observe(r, 200)[11] == 0
    r["rtcp_rtt_measurements"] = 2
    assert e.observe(r, 300)[11] == 1
    assert e.observe(r, 500)[2] == 0.2
    r["rtcp_rtt_measurements"] = 1
    assert e.observe(r, 600)[11] == 0


def test_stream_change_long_gap_and_counter_reset_invalidate_rates():
    e = NativeSenderObservationEncoder()
    r = raw()
    e.observe(r, 100)
    r["bytes_sent"] = 0
    assert e.observe(r, 200)[12] == 0
    r["stream_key"] = "other"
    assert e.observe(r, 300)[12] == 0
    r["bytes_sent"] = 999
    assert e.observe(r, 2000)[12] == 0


@pytest.mark.parametrize(
    "bad",
    [{"capacity": 2}, {"bytes_sent": float("nan")}, {"packets_sent": True}, {"receiver_target_ms": False}],
)
def test_oracle_and_nonfinite_boolean_fields_reject(bad):
    r = raw()
    r.update(bad)
    with pytest.raises(ValueError):
        NativeSenderObservationEncoder().observe(r, 100)


def test_zero_rtcp_count_and_missing_bwe_do_not_fake_valid_feedback():
    r = raw()
    r.update(bwe_bps=None, rtcp_rtt_measurements=0)
    a = NativeSenderObservationEncoder().observe(r, 100)
    assert a[9:12] == [0, 0, 0]


def test_sender_time_reversal_rejects():
    e = NativeSenderObservationEncoder()
    e.observe(raw(), 200)
    with pytest.raises(ValueError):
        e.observe(raw(), 100)
