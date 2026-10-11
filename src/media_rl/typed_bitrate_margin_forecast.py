"""The simulator's forecast of the long-session native pilot, committed before its capture (synthetic).

The simulator runs with the receiver layer exactly as it was fitted on the range pilot, with no
refit, on mirrors of the long-session pilot's four schedules, and the pilot's rule runs through
the class that will audit the native sessions. The forecast is written before any session of
the pilot exists; after the capture it is judged by the rule fixed in
docs/NATIVE_MARGIN_PILOT_V1.md. Nothing here is native evidence and nothing is promoted.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from . import native_margin_pilot as margin
from . import typed_bitrate_native_receiver as receiver
from .native_protocol import read_json
from .typed_bitrate import TypedConfig, split_seed
from .typed_bitrate_b1_forecast import load_settings, mirror

STUDY = "typed_bitrate_margin_forecast_v1"
SPANS = ("session", "after_startup")  # the whole session is the span of the reading and of the verdict
ARM_POLICIES = {name: dict(policy, arm=arm) for arm, (name, policy) in enumerate(margin.ARMS)}
PAIRS = tuple(f"{a} minus {b}" for a, b in margin.PAIRS)
RULE_AGAINST_TUNED = tuple(f"{c} minus {name}" for c in margin.CANDIDATES for name in margin.TUNED)
REGIMES = margin.REGIMES


def simulator():
    """The typed simulator as built, with an episode as long as one of the pilot's sessions."""
    config = TypedConfig(name=STUDY)
    length = {sum(ms for _, _, ms in schedule) for schedule in REGIMES.values()}
    if len(length) != 1:
        raise ValueError("the pilot's schedules differ in length")
    return TypedConfig(name=STUDY, steps=int(length.pop() / config.dt_ms)).validate()


def simulate(config, settings, layer, path=None):
    """Every arm under every schedule, on the relay's mirror or, with ``path``, with path noise."""
    made = {name: {} for name in ARM_POLICIES}
    for regime, schedule in REGIMES.items():
        trace = mirror(schedule, config, settings["relay"], path)
        for name, policy in ARM_POLICIES.items():
            session = receiver.run(config, trace, policy, layer, replay=margin.PolicyReplay)
            made[name][regime] = dict(
                receiver.summarise(session, schedule, margin.PHASE_MS, margin.SESSION_PHASES),
                assignments=[
                    dict(at_s=a["at_ms"] / 1000, decision=a["decision"], ratio=a["ratio"])
                    for a in session["assignments"]
                ],
            )
    return made


def over_schedules(made, span, quantity):
    """Per arm the mean over the pilot's four schedules, weighted equally as in its report."""
    return {
        name: float(np.mean([own[regime][span][quantity] for regime in REGIMES]))
        for name, own in made.items()
    }


def differences(made, span):
    """The pilot's six differences of the endpoint, over all schedules and under each."""
    everywhere = over_schedules(made, span, "utility")
    return (
        {f"{a} minus {b}": everywhere[a] - everywhere[b] for a, b in margin.PAIRS},
        {
            regime: {
                f"{a} minus {b}": made[a][regime][span]["utility"] - made[b][regime][span]["utility"]
                for a, b in margin.PAIRS
            }
            for regime in REGIMES
        },
    )


def forecast(layer, config, settings):
    """What the simulator with the fitted layer says the pilot will show."""
    made = simulate(config, settings, layer)
    out = dict(spans={})
    for span in SPANS:
        everywhere, by_schedule = differences(made, span)
        out["spans"][span] = dict(
            levels={
                quantity: {
                    name: dict(
                        all_schedules=over_schedules(made, span, quantity)[name],
                        by_schedule={regime: made[name][regime][span][quantity] for regime in REGIMES},
                    )
                    for name in margin.NAMES
                }
                for quantity in ("utility", "on_time", "encoder_over_capacity")
            },
            differences_over_all_schedules=everywhere,
            differences_under_each_schedule=by_schedule,
        )
    out["what_the_rule_does"] = {
        name: {regime: made[name][regime]["assignments"] for regime in REGIMES} for name in margin.CANDIDATES
    }
    out["timeline"] = {
        name: {
            regime: {
                key: [b[key] for b in made[name][regime]["bins"]]
                for key in ("utility", "on_time", "age_median_ms", "ratio", "requested_kbps")
            }
            | dict(jitter_buffer_ms=[p["jitter_buffer_ms"] for p in made[name][regime]["phases"]])
            for regime in REGIMES
        }
        for name in margin.NAMES
    }
    out["robustness"] = robustness(layer, config, settings)
    return out


def robustness(layer, config, settings):
    """With the path noise of the simulator's own families: each difference's mean, and how often it
    is at least the counting size on either side."""
    seen = {pair: [] for pair in PAIRS}
    for replicate in range(settings["replicates"]):
        path = np.random.default_rng(split_seed(settings["seed"], "margin-forecast-path", replicate))
        everywhere, _ = differences(simulate(config, settings, layer, path), SPANS[0])
        for pair, value in everywhere.items():
            seen[pair].append(value)
    return dict(
        replicates=settings["replicates"],
        differences={
            pair: dict(
                mean=float(np.mean(values)),
                share_positive=float(np.mean([v >= receiver.MINIMUM for v in values])),
                share_negative=float(np.mean([v <= -receiver.MINIMUM for v in values])),
            )
            for pair, values in seen.items()
        },
    )


def judged(made, native):
    """The forecast against the pilot's report, by the rule fixed in the pilot's design."""
    out = dict(spans={})
    for span in SPANS:
        own, theirs = made["spans"][span], native["all_schedules"][span]["utility"]
        everywhere = {
            pair: receiver.judge(own["differences_over_all_schedules"][pair], theirs["contrasts"][pair])
            for pair in PAIRS
        }
        by_schedule = {
            regime: {
                pair: receiver.judge(
                    own["differences_under_each_schedule"][regime][pair],
                    native["by_schedule"][regime][span]["utility"]["contrasts"][pair],
                )
                for pair in PAIRS
            }
            for regime in REGIMES
        }
        decided = receiver.decide(everywhere, by_schedule, RULE_AGAINST_TUNED)
        decided["verdict"] = VERDICTS[decided["verdict"]]
        levels = {
            name: dict(
                forecast=own["levels"]["utility"][name]["all_schedules"],
                native=theirs["arms"][name]["level"]["mean"],
                native_interval95=theirs["arms"][name]["level"]["interval95"],
            )
            for name in margin.NAMES
        }
        out["spans"][span] = dict(
            levels=levels,
            endpoints_inside_the_native_interval=sum(
                e["native_interval95"] is not None
                and e["native_interval95"][0] <= e["forecast"] <= e["native_interval95"][1]
                for e in levels.values()
            ),
            differences_over_all_schedules=everywhere,
            differences_under_each_schedule=by_schedule,
            **decided,
        )
    out["verdict"] = out["spans"][SPANS[0]]["verdict"]
    return out


VERDICTS = {  # the receiver layer's three verdicts, in this design's words
    "the layer predicts the controller pilot": "the layer forecast the pilot",
    "the layer predicts the order only": "the layer forecast the order only",
    "the layer does not predict the controller pilot": "the layer did not forecast the pilot",
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    writer = commands.add_parser("forecast", help="write the forecast, before the capture")
    writer.add_argument("--layer", required=True, type=Path)
    judge = commands.add_parser("judge", help="set the committed forecast against the pilot's report")
    judge.add_argument("--forecast", required=True, type=Path)
    judge.add_argument("--pilot", required=True, type=Path, help="the long-session pilot's report")
    for command in (writer, judge):
        command.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output file required\n")
    if args.command == "forecast":
        fitted = read_json(args.layer)
        if fitted.get("study") != receiver.STUDY + "_layer":
            parser.exit(2, "error: the fitted receiver layer is required\n")
        layer = receiver.Layer(
            **{k: tuple(v) if isinstance(v, list) else v for k, v in fitted["layer"].items()}
        )
        result = dict(
            study=STUDY,
            synthetic=True,
            native_evidence=False,
            written_before_the_capture=True,
            learned_controller_promoted=False,
            layer_sha256=_sha(args.layer),
            schedules={
                regime: [capacity for capacity, _, _ in schedule] for regime, schedule in REGIMES.items()
            },
            arms=list(margin.NAMES),
            **forecast(layer, simulator(), load_settings()),
        )
        shown = {
            name: round(e["all_schedules"], 2)
            for name, e in result["spans"][SPANS[0]]["levels"]["utility"].items()
        }
    else:
        made, native = read_json(args.forecast), read_json(args.pilot)
        if made.get("study") != STUDY or native.get("abi") != margin.ABI + "_report":
            parser.exit(2, "error: the committed forecast and the long-session pilot's report are required\n")
        result = dict(
            study=STUDY + "_judged",
            synthetic=True,
            forecast_sha256=_sha(args.forecast),
            pilot_report_sha256=_sha(args.pilot),
            **judged(made, native),
        )
        shown = dict(verdict=result["verdict"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(shown, indent=1))


if __name__ == "__main__":
    main()
