import pytest

from media_rl.native_context import NativeContextSwitch


def features(bwe=2, offered=1, rtt=40, delay=0):
    f = [0.0] * 16
    f[0] = bwe / 4
    f[1] = rtt / 150
    f[3] = offered / 4
    f[6] = delay / 150
    f[7] = 1
    f[8:15] = [1] * 7
    f[15] = 1
    return f


def test_steady_link_defaults_to_short_model():
    c = NativeContextSwitch()
    for i in range(30):
        assert c.observe(features(), i * 100, "s")["selected_model"] == "base"


def test_bwe_drop_requires_valid_offered_load_and_two_samples():
    c = NativeContextSwitch()
    c.observe(features(), 0, "s")
    assert c.observe(features(1.5, 1.6), 100, "s")["selected_model"] == "base"
    assert c.observe(features(1.5, 1.6), 200, "s")["selected_model"] == "long"
    c = NativeContextSwitch()
    c.observe(features(), 0, "s")
    for i in [100, 200]:
        assert c.observe(features(1.5, 0.5), i, "s")["selected_model"] == "base"


@pytest.mark.parametrize("signal", ["rtt", "delay"])
def test_separate_sender_alarm_and_exact_causal_recovery(signal):
    c = NativeContextSwitch()
    c.observe(features(), 0, "s")
    f = features(rtt=80) if signal == "rtt" else features(delay=30)
    c.observe(f, 100, "s")
    assert c.observe(f, 200, "s")["selected_model"] == "long"
    for i in range(300, 2200, 100):
        assert c.observe(features(), i, "s")["selected_model"] == "long"
    assert c.observe(features(), 2200, "s")["selected_model"] == "base"


def test_invalid_signals_do_not_count_as_clean_recovery():
    c = NativeContextSwitch()
    c.observe(features(delay=30), 0, "s")
    c.observe(features(delay=30), 100, "s")
    f = features()
    f[9:15] = [0] * 6
    for i in range(200, 3100, 100):
        assert c.observe(f, i, "s")["selected_model"] == "long"


@pytest.mark.parametrize("reset", ["stream", "gap"])
def test_stream_and_large_clock_gap_reset_context(reset):
    c = NativeContextSwitch()
    c.observe(features(delay=30), 0, "s")
    c.observe(features(delay=30), 100, "s")
    assert (
        c.observe(features(), 200 if reset == "stream" else 1200, "other" if reset == "stream" else "s")[
            "selected_model"
        ]
        == "base"
    )


@pytest.mark.parametrize("attack", ["time", "boolean", "length", "flag", "nonfinite"])
def test_invalid_or_extra_neural_features_and_clock_reject(attack):
    c = NativeContextSwitch()
    c.observe(features(), 100, "s")
    f = features()
    now = 200
    if attack == "time":
        now = 100
    elif attack == "boolean":
        f[0] = True
    elif attack == "length":
        f.append(1)
    elif attack == "flag":
        f[9] = 0.5
    else:
        f[0] = float("nan")
    with pytest.raises(ValueError):
        c.observe(f, now, "s")
