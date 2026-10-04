import json
import shutil
import subprocess
from copy import deepcopy

import numpy as np
import pytest
from native_study_helpers import bundle

from media_rl.native_calibration import accepted_native_samples, fit_selected_native_calibration
from media_rl.native_learning import NativePolicy
from media_rl.native_protocol import asset_directory


def samples():
    rng = np.random.default_rng(83)
    return [
        dict(
            group="g" + str(i % 3),
            episode_id="e" + str(i % 6),
            step_id=i,
            state=rng.uniform(0, 1, 64).tolist(),
            action=i % 7,
            miss_fraction=0.1 if i % 3 == 0 else 0.8,
            label_count=10,
        )
        for i in range(30)
    ]


def test_selected_calibration_is_monotonic_and_only_platt_changes():
    source = bundle()
    before = deepcopy(source)
    candidate, report = fit_selected_native_calibration(source, samples())
    assert source == before
    assert {k: v for k, v in candidate.items() if k != "platt"} == {
        k: v for k, v in source.items() if k != "platt"
    }
    assert candidate["platt"][0] > 0 and candidate["platt"] != source["platt"]
    assert report["factual_source_requests"] == 300 and report["independent_source_groups"] == 3
    assert report["fitted"]["in_sample_not_selected_policy_validation"]
    assert report["policy_improved"] is False and report["SOTA_achieved"] is False
    assert report["fitted"]["frame_brier"] >= 0


@pytest.mark.parametrize("mutation", ["one-group", "no-misses", "no-deliveries", "bool-count", "nan-label"])
def test_inadequate_or_corrupt_factual_calibration_rejects(mutation):
    data = samples()
    if mutation == "one-group":
        for x in data:
            x["group"] = "g"
    elif mutation in ("no-misses", "no-deliveries"):
        for x in data:
            x["miss_fraction"] = 0 if mutation == "no-misses" else 1
    elif mutation == "bool-count":
        data[0]["label_count"] = True
    else:
        data[0]["miss_fraction"] = float("nan")
    with pytest.raises(ValueError):
        fit_selected_native_calibration(bundle(), data)


def test_fallback_and_inflight_labels_excluded_not_reassigned_to_future():
    decisions = []
    labels = []
    for i in range(3):
        decisions.append(
            dict(
                observation=dict(features=[0] * 16),
                ack_ms=10 + i * 100,
                changed=False,
                actuation_readback=dict(encoder_max_bitrate_bps=300000, receiver_jitter_buffer_target_ms=0),
                policy_decision=dict(
                    action_index=1,
                    encoder_max_bitrate_bps=300000,
                    predicted_frame_miss=[0.2] * 7,
                    risk_disagreement=[0.1] * 7,
                    fallback=i == 1,
                ),
            )
        )
        labels.append(
            dict(
                action_transition_inflight=i == 2,
                decision_id=i,
                capture_request_ms=30 + i * 100,
                encoder_cap_bps=300000,
                receiver_target_ms=0,
                identifiable_ontime=False,
                ontime_sampled_psnr_contribution=0,
            )
        )
    selected, excluded = accepted_native_samples(
        dict(decisions=decisions), dict(source_labels=labels), "e", "g"
    )
    assert len(selected) == 1 and selected[0]["step_id"] == 0 and selected[0]["action"] == 1
    assert excluded == dict(transition=1, unassociated=0, fallback_source_requests=1)
    decisions[0]["policy_decision"]["action_index"] = 3
    with pytest.raises(ValueError, match="selected action"):
        accepted_native_samples(dict(decisions=decisions), dict(source_labels=labels), "e", "g")


def test_recalibrated_real_weights_have_portable_js_python_parity(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("Node required for portable policy probe")
    candidate, _ = fit_selected_native_calibration(bundle(), samples())
    states = [x["state"] for x in samples()]
    for cutoff in (0.0, 0.5, 1.0):
        candidate["risk_cutoff"] = cutoff
        candidate["disagreement_cutoff"] = 1.0 if cutoff == 1 else 0.2
        path = tmp_path / "input.json"
        path.write_text(json.dumps(dict(bundle=candidate, states=states)))
        module = (asset_directory() / "native_policy.mjs").as_uri()
        program = (
            "import {readFileSync} from 'node:fs';"
            + "import {validateNativePolicy,decideNativeHistory} from "
            + json.dumps(module)
            + ";"
            + "const x=JSON.parse(readFileSync(process.argv[1],'utf8'));validateNativePolicy(x.bundle);"
            + "console.log(JSON.stringify(x.states.map(s=>decideNativeHistory(x.bundle,s))));"
        )
        actual = json.loads(
            subprocess.run(
                ["node", "--input-type=module", "--eval", program, str(path)],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
        )
        policy = NativePolicy(candidate)
        for state, row in zip(states, actual, strict=True):
            expected = policy.decide(state)
            assert row["action_index"] == expected["action_index"] and row["fallback"] is expected["fallback"]
            for key in ("q_values", "predicted_frame_miss", "risk_disagreement"):
                np.testing.assert_allclose(row[key], expected[key], atol=1e-10, rtol=0)
