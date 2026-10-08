"""Instrument provenance, physical feedback distinction and staged causal gates."""

import json
import subprocess

import numpy as np
import pytest

from media_rl import native_actuator_control as control
from media_rl import native_actuator_statistics as stats
from media_rl import native_actuator_study as study
from media_rl.native_protocol import asset_directory


def snapshot(now, cap=300000, bwe=600000, total=1000, frames=1):
    raw = dict(stream_key="sender:1", bwe_bps=bwe, rtcp_rtt_s=0.1, encoder_cap_bps=cap, bytes_sent=total)
    observation = dict(
        sample_ms=now, raw_source=raw, features=[0.0] * 16, content_features=dict(features=[0.3, 0.4])
    )
    observation["features"][11] = 1
    encoder = dict(
        fields={
            k: dict(status="present", value=v)
            for k, v in dict(targetBitrate=230000, framesEncoded=frames, qpSum=frames * 20).items()
        }
    )
    meter = dict(
        abi="native_encoded_payload_meter_v1",
        status="active",
        sample_ms=now,
        total_bytes=total,
        total_frames=frames,
    )
    link = dict(loss_fraction=dict(status="absent", value=None), jitter_ms=dict(status="present", value=3.0))
    return observation, encoder, meter, link


def test_full_support_and_not_permutation():
    draws = [control.assigned_arm(seed, i) for seed in range(150) for i in range(6)]
    assert set(draws) == {0, 1, 2}
    assert all(200 < draws.count(a) < 400 for a in range(3))
    assert any(control.assigned_arm(s, 0) == control.assigned_arm(s, 1) for s in range(40))
    with pytest.raises(ValueError):
        control.assigned_arm(-1, 0)


def test_python_node_parity_history_and_exact_known_probability():
    inputs = []
    sampler = control.InstrumentSampler(391)
    expected = []
    cap = 300000
    for index, now in enumerate((0, 100, 2999, 3100, 6200, 9300, 12400, 15500, 19000)):
        sample = snapshot(now, cap=cap, bwe=600000 + index * 10000, total=index * 7000, frames=index)
        sample[0]["raw_source"]["rtcp_rtt_s"] = 0.1 - index * 0.001
        assignment = sampler.observe(*sample)
        cap = assignment["requested_bps"]
        ack = now + 100
        sampler.acknowledge(ack, cap)
        inputs.append(dict(sample=sample, ack=ack, cap=cap))
        expected.append(assignment)
    module = (asset_directory() / "actuator_control.mjs").as_uri()
    code = f"import {{InstrumentSampler}} from {json.dumps(module)}; const s=new InstrumentSampler(391),r=[];"
    code += f"for(const x of {json.dumps(inputs)}){{r.push(await s.observe(...x.sample));s.acknowledge(x.ack,x.cap);}} console.log(JSON.stringify(r));"
    result = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True
        ).stdout
    )
    study.donor.dense._close(result, expected)
    assert [r["epoch"] for r in expected] == [0, 0, 0, 1, 2, 3, 4, 5, 5]
    assert all(r["propensities"] == [1 / 3] * 3 for r in expected)
    assert expected[3]["state"]["rtt_trend_ms"]["value"] < 0
    assert expected[3]["base_bwe_bps"] == 630000
    assert expected[1]["base_bwe_bps"] == 600000


def test_missing_bwe_never_guessed_and_aliases_not_excluded():
    sampler = control.InstrumentSampler(5)
    assert sampler.observe(*snapshot(0, bwe=None)) is None
    assignment = sampler.observe(*snapshot(100, bwe=20e6))
    assert assignment["candidates_bps"] == [4000000] * 3
    assert assignment["clipped_or_aliased"] is True
    assert assignment["propensity"] == 1 / 3
    sampler.acknowledge(101, 4000000)
    assert sampler.observe(*snapshot(200, cap=4000000))["epoch"] == 0
    with pytest.raises(ValueError):
        sampler.observe(*snapshot(199))


def test_observed_zero_is_not_missing_and_RTP_is_not_target():
    sampler = control.InstrumentSampler(1)
    a = sampler.observe(*snapshot(0, total=0, frames=0))
    sampler.acknowledge(1, a["requested_bps"])
    sample = snapshot(3100, total=0, frames=0)
    sampler.observe(*sample)
    sampler.acknowledge(3101, sampler.current["requested_bps"])
    sample = snapshot(6200, total=0, frames=0)
    sampler.observe(*sample)
    # Long absent intervals correctly remain unknown.
    assert sampler.current["state"]["actual_encoder_bps"]["value"] is None
    sample = snapshot(6300, total=0, frames=0)
    sampler.observe(*sample)
    sampler.acknowledge(6301, sampler.current["requested_bps"])
    sample = snapshot(9301, total=0, frames=0)
    sampler.observe(*sample)
    # Separate direct probe of the causal interval calculation.
    s = control.InstrumentSampler(8)
    s.observe(*snapshot(0, total=0, frames=0))
    s.acknowledge(1, s.current["requested_bps"])
    s.observe(*snapshot(3001, total=100, frames=0))
    s.acknowledge(3002, s.current["requested_bps"])
    s.observe(*snapshot(5902, total=100, frames=0))
    s.observe(*snapshot(6002, total=100, frames=0))
    assert s.current["state"]["actual_encoder_bps"] == dict(status="present", value=0)
    assert s.current["state"]["encoder_target_bps"]["value"] == 230000


def test_clock_only_censoring_and_zero_output_nonresponse_kept(monkeypatch):
    assignments = [
        dict(
            epoch=i,
            arm=i,
            ratio=control.RATIOS[i],
            seed=1,
            ack_ms=i * 3000,
            assignment_ms=i * 3000,
            first_step_id=i,
            base_bwe_bps=600000,
            requested_bps=400000,
            propensity=1 / 3,
            propensities=[1 / 3] * 3,
            state={},
            candidates_bps=[390000, 510000, 630000],
            clipped_or_aliased=False,
            abi=control.ABI,
        )
        for i in range(3)
    ]
    monkeypatch.setattr(study, "replay_assignments", lambda sender, trial: ([], assignments))
    decisions = []
    for time in range(0, 8100, 100):
        obs, encoder, _, _ = snapshot(time, total=time)
        decisions.append(dict(observation=obs, encoder_response=encoder))
    sender = dict(decisions=decisions, encoded_meter=dict(events=[]))
    quality = dict(
        source_labels=[
            dict(
                source_id=i,
                capture_request_ms=1900 + i * 3000,
                ontime_sampled_psnr_contribution=0,
                identifiable_ontime=False,
            )
            for i in range(3)
        ]
    )
    rows = study.build_cohorts(
        sender,
        dict(measurement_cutoff_ms=8100),
        quality,
        dict(block_id="owned", role="discovery", id="trial"),
    )
    assert len(rows) == 3  # all randomized assignments, not just successful arms
    assert rows[0]["complete"] and rows[0]["encoder_bps"] == 0 and rows[0]["utility"] == 0
    assert not rows[0]["plateau_observed"]
    assert not rows[2]["complete"] and rows[2]["utility"] is None
    assert rows[2]["censor_reason"] == "window_or_deadline_crosses_cutoff_or_next_assignment"
    assert all(r["non_plateau_is_not_exclusion"] for r in rows)


def test_failed_capture_prefix_is_preserved_and_cannot_be_overwritten(tmp_path, monkeypatch):
    cfg = dict(runtimes={"one": dict(episodes=[dict(id="owned", role="discovery")])})
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(cfg))
    monkeypatch.setattr(study, "verify_seal", lambda *args: None)
    monkeypatch.setattr(study, "validate_plan", lambda p: p)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["node"], stderr="encoded output unavailable")

    monkeypatch.setattr(study.subprocess, "run", fail)
    out = tmp_path / "capture"
    with pytest.raises(subprocess.CalledProcessError):
        study.run_study(protocol, out)
    failed = json.loads((out / "failure.json").read_text())
    assert failed["collector_stderr"] == "encoded output unavailable"
    assert failed["rerun_requires_fresh_path"]
    assert (out / "protocol.json").exists()
    with pytest.raises(ValueError, match="fresh"):
        study.run_study(protocol, out)


def test_exact_projection_and_no_mutation_of_legacy_auditor_globals():
    assets = asset_directory()
    assert (
        study.project_collector((assets / "encoder_response_episode.mjs").read_text())
        == (assets / "actuator_episode.mjs").read_text()
    )
    assert study.donor.dense.audit_dense_episode.__globals__["STUDY_ABI"] != study.ABI
    assert study.donor.dense.audit_dense_episode.__globals__["RECIPE"] != study.RECIPE
    with pytest.raises(ValueError):
        study.project_collector("changed")
    assert "controller.enqueue(frame)" in (assets / "actuator_meter.mjs").read_text()
    assert "createEncodedStreams" in (assets / "actuator_meter.mjs").read_text()


def test_encoded_meter_identity_and_future_snapshot_filter():
    module = (asset_directory() / "actuator_meter.mjs").as_uri()
    code = f"import {{installEncodedMeter}} from {json.dumps(module)};"
    code += """
let clock=0,writer,seen=[];
const readable=new ReadableStream({start(c){writer=c;}}),writable=new WritableStream({write(f){seen.push(f);}});
const meter=installEncodedMeter({createEncodedStreams(){return {readable,writable};}},()=>clock);
const frames=[{data:new ArrayBuffer(10),timestamp:1,type:'key'},{data:new ArrayBuffer(20),timestamp:2,type:'delta'}];
clock=10;writer.enqueue(frames[0]);await new Promise(r=>setTimeout(r,0));
clock=20;writer.enqueue(frames[1]);await new Promise(r=>setTimeout(r,0));
const old=meter.snapshot(10),now=meter.snapshot(20),evidence=meter.evidence(0,20);
if(seen[0]!==frames[0]||seen[1]!==frames[1])throw Error('frame identity mutated');
let rejected=false;try{installEncodedMeter({});}catch{rejected=true;}
console.log(JSON.stringify({old,now,evidence,rejected}));
"""
    result = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-e", code], check=True, capture_output=True, text=True
        ).stdout
    )
    assert result["rejected"]
    assert result["old"]["total_bytes"] == 10
    assert result["now"]["total_bytes"] == 30
    assert result["evidence"]["events"][-1]["total_frames"] == 2
    assert result["evidence"]["unit"] == "encoded_video_payload_bytes_before_RTP_packetization"


def test_meter_substitution_and_future_counter_rejected():
    sample = snapshot(0, total=0, frames=0)
    sampler = control.InstrumentSampler(5)
    a = sampler.observe(*sample)
    cap = a["requested_bps"]
    row = dict(
        step_id=0,
        observation=sample[0],
        encoder_response=sample[1],
        encoded_snapshot=sample[2],
        instrument_link=sample[3],
        actuator_assignment=a,
        ack_ms=1,
        actuation_readback=dict(encoder_max_bitrate_bps=cap),
        instrument_compute_ms=0,
        total_inference_ms=1,
    )
    sender = dict(
        measurement_start_ms=0,
        measurement_cutoff_ms=5000,
        decisions=[row],
        encoded_meter=dict(
            abi="native_encoded_payload_meter_v1",
            owner="unique_owned_video_sender",
            measurement_start_ms=0,
            measurement_cutoff_ms=5000,
            started_ms=0,
            error=None,
            ended_ms=None,
            pass_through_no_frame_mutation=True,
            unit="encoded_video_payload_bytes_before_RTP_packetization",
            events=[],
        ),
    )
    assert len(study.replay_assignments(sender, dict(exploration_seed=5))[1]) == 1
    sender["decisions"][0]["encoded_snapshot"]["total_bytes"] = 1
    with pytest.raises(ValueError, match="future or substituted"):
        study.replay_assignments(sender, dict(exploration_seed=5))
    sender["decisions"][0]["encoded_snapshot"]["total_bytes"] = 0
    sender["encoded_meter"]["unit"] = "encoder_target_bytes"
    with pytest.raises(ValueError, match="actual encoded"):
        study.replay_assignments(sender, dict(exploration_seed=5))


def make_rows(strong=True, outcome=True, blocks=16, seed=211):
    rng = np.random.default_rng(seed)
    rows = []
    for role in study.ROLES:
        for block in range(blocks):
            for epoch in range(18):
                arm = int(rng.integers(3))
                base = float(rng.uniform(450000, 750000))
                a = (0.2 + control.RATIOS[arm] * 0.65 if strong else 0.5) + float(rng.normal(0, 0.015))
                q = 20 + (15 * a if outcome else 0) + float(rng.normal(0, 0.5))
                state = {k: dict(status="absent", value=None) for k in stats.COVARIATES}
                state["previous_action"] = None
                state["bwe_bps"] = dict(status="present", value=base)
                rows.append(
                    dict(
                        role=role,
                        block_id=f"{role}-{block}",
                        arm=arm,
                        epoch=epoch,
                        propensity=1 / 3,
                        state=state,
                        base_bwe_bps=base,
                        requested_bps=base * control.RATIOS[arm],
                        encoder_bps=base * a,
                        send_bps=base * (a + rng.normal(0, 0.005)),
                        utility=q,
                        ontime_fraction=0.95,
                        clipped_or_aliased=False,
                        complete=True,
                        plateau_observed=True,
                    )
                )
    return rows


def test_first_stage_weak_defers_qoe_and_ML():
    result = stats.analyze_cohorts(make_rows(strong=False))
    assert not result["stage1"]["qualified"]
    assert result["stage2"]["status"] == "deferred_until_stage1_replicates"
    assert result["stage3"]["status"] == "not_fitted_architecture_frozen"
    assert not result["stage3"]["eligible_next_experiment"]


def test_strong_first_stage_and_iv_assumptions_are_separate():
    rows = make_rows()
    report = stats.analyze_cohorts(rows)
    assert report["stage1"]["qualified"]
    assert report["stage2"]["qualified"]
    assert not report["stage2"]["actual_bitrate_causal_effect_established"]
    assumed = stats.analyze_cohorts(rows, True)
    assert assumed["stage2"]["actual_bitrate_causal_effect_established"]
    assert assumed["stage3"]["eligible_next_experiment"]
    assert not assumed["learned_controller_promoted"]
    for role in study.ROLES:
        ar = assumed["stage2"]["roles"][role]["weak_instrument_robust_AR"]
        assert ar["intervals"] and not ar["unbounded"]
        assert any(x["lower"] < 15 < x["upper"] for x in ar["intervals"])


def test_no_qoe_effect_blocks_stage2_even_when_actuator_is_strong():
    report = stats.analyze_cohorts(make_rows(outcome=False))
    assert report["stage1"]["qualified"]
    assert not report["stage2"]["qualified"]
    assert not report["stage3"]["eligible_next_experiment"]


def test_weak_IV_confidence_set_is_unbounded_not_spuriously_finite():
    rows = [r for r in make_rows(strong=False, outcome=False, blocks=32) if r["role"] == "discovery"]
    design = stats._design(rows)
    a = stats._fit([r["encoder_bps"] / r["base_bwe_bps"] for r in rows], design)
    y = stats._fit([r["utility"] for r in rows], design)
    ar = stats.anderson_rubin_set(a, y, design, 0.05)
    assert ar["unbounded"]
    assert any(x["lower"] is None or x["upper"] is None for x in ar["intervals"])


def test_replication_and_physical_blocks_are_required():
    rows = make_rows()
    assert not stats.analyze_cohorts([r for r in rows if r["role"] == "discovery"])["stage1"]["qualified"]
    assert not stats.analyze_cohorts(make_rows(blocks=2))["stage1"]["qualified"]
    rows[-1]["block_id"] = rows[0]["block_id"]
    with pytest.raises(ValueError, match="role-disjoint"):
        stats.analyze_cohorts(rows)


def test_no_unobserved_negative_labels_or_propensity_invention():
    rows = make_rows()
    rows[0]["propensity"] = 0.0
    with pytest.raises(ValueError, match="factual prospective"):
        stats.analyze_cohorts(rows)
    rows = make_rows()
    for r in rows:
        r["plateau_observed"] = False
    report = stats.analyze_cohorts(rows)
    assert report["stage1"]["qualified"]
    assert all(x["non_plateau_not_excluded"] for x in report["stage1"]["roles"].values())
    assert report["no_counterfactual_outcomes_imputed"]


@pytest.mark.parametrize(
    "field", ["criteria", "recipe", "policy_models_fitted", "native_deployment_qualified"]
)
def test_frozen_scope_rejects_drift(field):
    cfg = dict(
        abi=study.ABI,
        criteria=stats.CRITERIA,
        recipe=study.RECIPE,
        policy_models_fitted=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    cfg[field] = "forged"
    with pytest.raises(ValueError, match="diagnostic-only"):
        study.validate_plan(cfg)
