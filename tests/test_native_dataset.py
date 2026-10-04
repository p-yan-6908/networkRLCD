import numpy as np
import pytest

from media_rl.native_dataset import factual_transitions, history_matrix, n_step_arrays


def test_history_is_only_past_normalized_sender_features_with_zero_padding():
    features = np.arange(5 * 16).reshape(5, 16)
    h = history_matrix(features)
    assert h.shape == (5, 64)
    np.testing.assert_array_equal(h[0, :48], 0)
    np.testing.assert_array_equal(h[0, 48:], features[0])
    np.testing.assert_array_equal(h[4], features[1:5].ravel())
    with pytest.raises(ValueError):
        history_matrix(np.ones((2, 14)))


def transition(i, reward=1, terminal=False, episode="a"):
    return dict(
        episode_id=episode,
        step_id=i,
        state=np.zeros(64),
        next_state=np.ones(64) * i,
        action=0,
        reward=reward,
        terminal=terminal,
    )


def test_native_three_step_return_discount_and_terminal():
    rows = [transition(i, terminal=i == 3) for i in range(4)]
    data = n_step_arrays(rows, gamma=0.5, n=3)
    assert data["returns"].tolist() == [1.75, 1.75, 1.5, 1]
    assert data["bootstrap_discounts"].tolist() == [0.125, 0, 0, 0]


def test_gaps_and_episodes_never_create_fictitious_n_step_transition():
    rows = [transition(0), transition(2), transition(1, episode="other", terminal=True)]
    d = n_step_arrays(rows, gamma=0.5, n=3)
    assert d["returns"].tolist() == [1, 1, 1]
    assert d["bootstrap_discounts"].tolist() == [0, 0, 0]


def fixture():
    decisions = [
        dict(
            observation=dict(features=[0] * 16),
            ack_ms=10 + i * 100,
            actuation_readback=dict(encoder_max_bitrate_bps=300000, receiver_jitter_buffer_target_ms=0),
            changed=False,
        )
        for i in range(3)
    ]
    labels = [
        dict(
            action_transition_inflight=False,
            decision_id=0,
            capture_request_ms=30,
            encoder_cap_bps=300000,
            receiver_target_ms=0,
            identifiable_ontime=False,
            ontime_sampled_psnr_contribution=0,
        ),
        dict(
            action_transition_inflight=False,
            decision_id=0,
            capture_request_ms=50,
            encoder_cap_bps=300000,
            receiver_target_ms=0,
            identifiable_ontime=True,
            ontime_sampled_psnr_contribution=40,
        ),
    ]
    config = dict(on_time_sampled_psnr_divisor=100, miss_penalty=0.2, switch_penalty=0.005)
    return dict(decisions=decisions), dict(source_labels=labels), config


def test_missing_and_delivered_labels_remain_in_factual_reward_denominator():
    sender, q, c = fixture()
    rows, rejected = factual_transitions(sender, q, "a", c)
    assert len(rows) == 1 and rows[0]["terminal"]
    assert rows[0]["reward"] == pytest.approx(0.1)
    assert rows[0]["miss_fraction"] == 0.5 and rows[0]["label_count"] == 2
    assert rejected == dict(transition=0, unassociated=0)


def test_transition_unknown_and_future_assignment_are_not_clean_training_labels():
    s, q, c = fixture()
    q["source_labels"][0]["action_transition_inflight"] = True
    q["source_labels"][1]["decision_id"] = None
    rows, rejected = factual_transitions(s, q, "a", c)
    assert not rows and rejected == dict(transition=1, unassociated=1)
    s, q, c = fixture()
    q["source_labels"][0]["decision_id"] = 1
    with pytest.raises(ValueError):
        factual_transitions(s, q, "a", c)
