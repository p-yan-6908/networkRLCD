"""Paper evidence for the simulator's receiver layer, from invented fits and tests. Not native evidence."""

import hashlib
import json
import re

import pytest

from media_rl import native_ladder_pilot as ladder
from media_rl import typed_bitrate_native_receiver as receiver
from media_rl import typed_bitrate_native_receiver_report as report


def invented():
    def level(simulated, native):
        return dict(simulated=simulated, native=native)

    fitted = dict(
        study=receiver.STUDY + "_layer",
        layer=dict(e0_bps=744_000.0, b0=14.31, gu=55.2, gq=0.278, tau_s=35.1, return_ms=28.3),
        stages=dict(buffer=dict(rms_ms=14.8), age=dict(rms_ms=16.9)),
        beside_the_range_pilot=dict(
            comparisons=dict(agrees=7, disagrees=0, unclear=13),
            schedules_with_the_same_best_level=2,
            levels={
                key: {name: level(0.5 + 0.01 * i, 0.4 + 0.01 * i) for i, name in enumerate(receiver.LEVELS)}
                for key in ("utility", "on_time", "encoder_over_capacity")
            },
        ),
    )
    pairs = [f"{a} minus {b}" for a, b in receiver.PAIRS]

    def judged(pair, verdict):
        return dict(simulated=-1.25, native=-2.0, native_interval95=[-3.0, -1.0], verdict=verdict)

    everywhere = {pair: judged(pair, "agrees") for pair in pairs}
    everywhere[report.FAST] = dict(
        simulated=0.03, native=1.37, native_interval95=[0.17, 2.58], verdict="flat"
    )
    everywhere["0.25 minus 0.65"]["verdict"] = "not established"
    levels = {
        key: {
            name: dict(simulated=20.0 + i, native=21.0 + i, native_interval95=[15.0 + i, 27.0 + i])
            for i, name in enumerate(ladder.NAMES)
        }
        for key in ("utility", "on_time")
    }
    seen = dict(
        levels=levels,
        differences_over_all_schedules=everywhere,
        established_over_all_schedules=8,
        agreeing_over_all_schedules=7,
        established_under_the_schedules=22,
        share_agreeing_under_the_schedules=19 / 22,
        endpoints_inside_the_native_interval=5,
    )
    held = {pair: judged(pair, "disagrees" if "0.25" in pair else "agrees") for pair in pairs}
    made = dict(
        study=receiver.STUDY + "_test",
        synthetic=True,
        native_evidence=False,
        learned_controller_promoted=False,
        verdict="the layer does not predict the controller pilot",
        spans={receiver.SPANS[0]: seen},
        ablations=dict(buffer_held_at_its_base=dict(differences_over_all_schedules=held)),
        robustness=dict(
            replicates=48,
            share_of_replicates_agreeing={
                pair: 0.5625 if pair == report.FAST else 0.979 for pair in pairs[:-1]
            },
        ),
    )
    return fitted, made


def test_macros_carry_the_verdict_the_counts_and_the_layer():
    rows = report.macros(*invented())
    assert all(re.fullmatch(r"ReceiverLayer[A-Za-z]+", name) for name in rows)
    assert rows["ReceiverLayerVerdict"] == "the layer does not predict the controller pilot"
    assert (rows["ReceiverLayerEstablished"], rows["ReceiverLayerAgreeing"]) == ("8", "7")
    assert (rows["ReceiverLayerLocalEstablished"], rows["ReceiverLayerLocalAgreeing"]) == ("22", "19")
    assert rows["ReceiverLayerFastSim"] == "$+$0.03" and rows["ReceiverLayerFastNative"] == "$+$1.37"
    assert rows["ReceiverLayerFastJudged"] == "flat" and rows["ReceiverLayerInside"] == "5"
    assert (rows["ReceiverLayerStart"], rows["ReceiverLayerBase"], rows["ReceiverLayerFall"]) == (
        "744",
        "14.3",
        "35",
    )
    assert rows["ReceiverLayerPerQueue"] == "0.28" and rows["ReceiverLayerInUnclear"] == "13"
    assert rows["ReceiverLayerSimLadder"] == "20.0" and rows["ReceiverLayerNativeTop"] == "25.0"
    assert rows["ReceiverLayerHeldDisagree"] == "4"  # the invented ablation reverses the four pairs with 0.25
    assert rows["ReceiverLayerRobustMin"] == "98" and rows["ReceiverLayerRobustFast"] == "56"


def test_tables_set_the_simulator_beside_the_pilots():
    fitted, made = invented()
    levels = report.table_levels(fitted)
    assert levels.count("\\\\") == 2 + 5 and "ceiling & 0.5 & 0.4 & 54.0 & 44.0 & 54.0 & 44.0" in levels
    arms = report.table_arms(made)
    assert arms.count("\\\\") == 2 + 5 and "ladder & 20.0 & 21.0 & [15.0, 27.0] & 2000.0 & 2100.0" in arms
    differences = report.table_differences(made)
    assert differences.count("\\\\") == 1 + 10
    assert "fast ladder $-$ ladder & $+$0.03 & $+$1.37 [$+$0.17, $+$2.58] & flat" in differences
    assert "0.25 $-$ 0.65 & $-$1.25 & $-$2.00 [$-$3.00, $-$1.00] & not established" in differences


def test_export_writes_evidence_and_refuses_other_records(tmp_path):
    fitted, made = invented()

    def write(first, second, bind=True):
        paths = tmp_path / "layer.json", tmp_path / "report.json"
        paths[0].write_text(json.dumps(first))
        sha = hashlib.sha256(paths[0].read_bytes()).hexdigest()
        paths[1].write_text(json.dumps(dict(second, layer_sha256=sha if bind else "0" * 64)))
        return paths

    out = tmp_path / "generated"
    result = report.export(*write(fitted, made), out)
    assert result["verdict"].startswith("the layer does not") and result["macros"] == len(
        report.macros(fitted, made)
    )
    assert {p.name for p in out.iterdir()} == {
        "evidence.tex",
        "provenance.json",
        "receiver_layer_levels.tex",
        "receiver_layer_arms.tex",
        "receiver_layer_differences.tex",
    }
    assert "\\newcommand{\\ReceiverLayerAgreeing}{7}" in (out / "evidence.tex").read_text()
    for wrong, bind, match in (
        ((dict(fitted, study="other"), made), True, "fitted layer"),
        ((fitted, dict(made, study="other")), True, "fitted layer"),
        ((fitted, dict(made, native_evidence=True)), True, "no native evidence"),
        ((fitted, dict(made, learned_controller_promoted=True)), True, "nothing is promoted"),
        ((fitted, made), False, "another layer"),
    ):
        with pytest.raises(ValueError, match=match):
            report.export(*write(*wrong, bind=bind), tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    with pytest.raises(SystemExit):
        report.main(
            ["--layer", str(tmp_path / "none.json"), "--report", str(tmp_path / "no.json"), "--out", str(out)]
        )
