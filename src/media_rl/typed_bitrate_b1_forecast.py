"""What the typed simulator predicts Native Phase B1 will find (synthetic forecast, no model).

Native Phase B1 asks whether backing off helps in holds flagged beforehand by a stalled
estimate. This module runs B1's protocol in the fluid simulator before any B1 data exist: three
requested ratios of the estimate frozen at the start of each 3 s hold, IID per hold, six holds
per fresh sender, on mirrors of the four native capacity schedules, scored with B1's own
registered flag and estimator. The output is a forecast to compare with B1's outcome, next to a
comparison of the simulator with what N1 measured.

No model is trained or evaluated, no controller acts, and nothing here is native evidence.
"""

import argparse
import itertools
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import native_backoff_benefit as benefit
from .config import SimulatorConfig
from .environment import MediaEnvironment
from .native_actuator_panel import REGIMES
from .scenarios import ID_SCENARIOS, Trace
from .typed_bitrate import Link, TypedConfig, split_seed

STUDY = "typed_bitrate_b1_forecast_v1"
ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "configs/native_backoff_benefit_b1.json"
FREEZE = ROOT / "configs/native_backoff_benefit_b1_freeze.json"
ENCODER_SHARE = 0.90  # mean output of the simulated encoder over its target
HOLD_MS = 3000
ARMS = range(len(benefit.RATIOS))
CLASSES = ("helps", "hurts", "no_clear_benefit")
DEFAULTS = dict(
    name="typed-b1-forecast-v1",
    seed=261011,
    relay=dict(rtt_ms=50.0, queue_mbit=0.24),  # 25 ms each way and a 30 kB queue, as the native relay
    window_ms=[1800, 2600],  # B1's outcome window inside a hold
    replicates=48,  # sampled panel: each has ten random senders per schedule, as one native source has
    n1_reference=dict(  # published N1 figures the simulator is set beside; none is fitted to
        source="docs/NATIVE_PHASE_N1_EXPLORATORY.md and results/native-phase-b1-sizing.json",
        encoder_over_bwe={
            "all": [0.588, 0.732, 0.825],
            "underutilized": [0.602, 0.777, 0.922],
            "near-capacity": [0.611, 0.762, 0.822],
            "queue-building": [0.585, 0.738, 0.782],
            "collapse-recovery": [0.556, 0.651, 0.776],
        },
        estimate_log_growth={
            "all": [0.123, 0.128, 0.310],
            "underutilized": [0.165, 0.216, 0.693],
            "near-capacity": [0.209, 0.141, 0.213],
            "queue-building": [0.090, 0.161, 0.158],
            "collapse-recovery": [0.029, -0.008, 0.174],
        },
        flagged_share=0.339,
        flagged_share_by_previous_arm=[0.514, 0.229, 0.275],
    ),
)


def load_settings(path=None):
    settings = {**DEFAULTS, **(json.loads(Path(path).read_text()) if path else {})}
    if set(settings) != set(DEFAULTS):
        raise ValueError("unknown forecast setting")
    low, high = settings["window_ms"]
    if (
        not 0 <= low < high <= HOLD_MS
        or type(settings["replicates"]) is not int
        or settings["replicates"] < 2
    ):
        raise ValueError("the window must lie inside a hold and at least two replicates are needed")
    if set(settings["relay"]) != {"rtt_ms", "queue_mbit"} or any(v <= 0 for v in settings["relay"].values()):
        raise ValueError("relay delay and queue must be positive")
    return settings


def variants(settings):
    """Requested ratios per description of the actuator.

    ``as_built`` requests B1's three ratios and lets the simulated encoder follow them, also above
    the estimate. ``n1_realised`` requests what makes the simulated encoder's mean output equal
    the levels N1's encoder realised, so the top arm stays below the estimate as it did natively.
    """
    realised = settings["n1_reference"]["encoder_over_bwe"]["all"]
    return dict(as_built=list(benefit.RATIOS), n1_realised=[r / ENCODER_SHARE for r in realised])


def simulator():
    """The typed simulator as built, with an episode as long as a native capacity schedule."""
    lengths = {sum(ms for _, _, ms in schedule) for schedule in REGIMES.values()}
    if len(lengths) != 1:
        raise ValueError("native schedules differ in length")
    config = TypedConfig(name=STUDY)
    return TypedConfig(name=STUDY, steps=int(lengths.pop() / config.dt_ms)).validate()


def mirror(schedule, config, relay, rng=None):
    """A native capacity schedule as a simulator trace.

    Without ``rng`` it mirrors the relay: fixed delay, the relay's queue, no random loss or
    jitter. With ``rng`` it adds the path noise the simulator's own families draw: a capacity
    scale, a base delay, a small random loss and jitter.
    """
    steps = config.steps
    capacity = np.concatenate([np.full(int(ms / config.dt_ms), float(mbps)) for mbps, _, ms in schedule])
    rtt, loss, jitter = relay["rtt_ms"], 0.0, np.zeros(steps)
    if rng is not None:
        capacity = capacity * rng.uniform(0.85, 1.15)
        rtt, loss = rng.uniform(35, 65), rng.uniform(0.002, 0.012)
        jitter = np.abs(rng.normal(0, 2, steps))
    return Trace(
        "b1-mirror",
        capacity,
        np.full(steps, rtt),
        np.full(steps, loss),
        jitter,
        np.ones(steps, dtype=bool),
        np.zeros(steps),
        np.full(steps, relay["queue_mbit"] / SimulatorConfig().queue_mbit),
    )


def session(config, trace, ratios, arms, window_ms, tag):
    """One fresh sender through its holds: one row per hold, in the shape B1's estimator reads.

    The request is the arm's ratio of the estimate frozen at the start of the hold and stays put
    for the hold, as the native cap does. The synthetic governor is not in the loop. The endpoint
    is the simulator's delivered on-time quality term, averaged over the outcome window.
    """
    link = Link(config, ID_SCENARIOS[0], 0)
    link.env = MediaEnvironment(link.env.config, trace)
    limits, hold = config.residual, int(HOLD_MS / config.dt_ms)
    low, high = (int(v / config.dt_ms) for v in window_ms)
    rows = []
    for epoch, arm in enumerate(arms):
        kept = []
        for k in range(hold):
            sample = link.sample()
            if k == 0:
                frozen = sample.bwe_bps
                rate = float(np.clip(ratios[arm] * frozen, limits.min_bps, limits.max_bps))
            o = link.advance(rate)
            if low <= k < high:
                ontime = (1 - o["residual_loss"]) * (1 - o["deadline_miss"])
                quality = math.log1p(o["bitrate_mbps"] / 0.15) * (0.82 if o["low_latency"] else 1.0)
                kept.append((quality * ontime, o["qoe"], 1 - o["deadline_miss"], link.actual_bps))
        quality, qoe, ontime, sent = np.mean(kept, axis=0)
        rows.append(
            dict(
                trial_id=tag,
                epoch=epoch,
                arm=int(arm),
                base_bwe_bps=float(frozen),
                utility=float(quality),
                qoe=float(qoe),
                ontime_fraction=float(ontime),
                encoder_over_bwe=float(sent / frozen),
                complete=True,
            )
        )
    return rows


def exact_panel(config, settings, ratios, holds):
    """Every arm sequence on the relay's mirror: the randomisation distribution, with no sampling."""
    rows = []
    for regime, schedule in REGIMES.items():
        trace = mirror(schedule, config, settings["relay"])
        for arms in itertools.product(ARMS, repeat=holds):
            tag = f"{regime}:{''.join(map(str, arms))}"
            made = session(config, trace, ratios, arms, settings["window_ms"], tag)
            rows += [dict(r, source="exact", regime=regime) for r in made]
    return rows


def sampled_panel(config, settings, ratios, holds, peers):
    """Replicates shaped like a native source: ``peers`` random senders per schedule, noisy paths.

    Arm sequences and path noise depend on the seed only, so every variant sees the same ones.
    """
    rows = []
    for replicate in range(settings["replicates"]):
        path = np.random.default_rng(split_seed(settings["seed"], "b1-forecast-path", replicate))
        for index, (regime, schedule) in enumerate(REGIMES.items()):
            trace = mirror(schedule, config, settings["relay"], path)
            for peer in range(peers):
                seed = split_seed(settings["seed"], "b1-forecast-arms", replicate, index, peer)
                arms = np.random.default_rng(seed).integers(len(ARMS), size=holds).tolist()
                tag = f"r{replicate}:{regime}:{peer}"
                made = session(config, trace, ratios, arms, settings["window_ms"], tag)
                rows += [dict(r, source=f"r{replicate}", regime=regime) for r in made]
    return rows


def contrasts(held, plan):
    """B1's primary and secondary contrasts per source, by its registered estimator."""
    top = len(benefit.RATIOS) - 1

    def pick(rows=held, **options):
        return benefit.source_benefits(rows, plan, **options)[0]

    out = dict(
        primary=pick(),
        lower_065=pick(weights=[1.0, 0.0, -1.0]),
        lower_085=pick(weights=[0.0, 1.0, -1.0]),
        other_holds=pick(flagged=False),
        next_hold=pick(following=True),
        simulator_qoe=pick(key="qoe"),
        ontime_fraction=pick(key="ontime_fraction"),
        after_top=pick([r for r in held if r["previous_arm"] == top]),
        after_lower=pick([r for r in held if r["previous_arm"] != top]),
    )
    for regime in REGIMES:
        out[f"regime:{regime}"] = pick([r for r in held if r["regime"] == regime])
    primary, other, following = out["primary"], out["other_holds"], out["next_hold"]
    out["flagged_minus_other"] = {s: primary[s] - other[s] for s in primary if s in other}
    out["immediate_plus_next"] = {s: primary[s] + following[s] for s in primary if s in following}
    return out


def flag_shares(held):
    """How often the flag marks a hold: overall, by schedule and by the arm of the hold before."""
    by_regime, by_previous = defaultdict(list), defaultdict(list)
    for r in held:
        by_regime[r["regime"]].append(r["flagged"])
        by_previous[r["previous_arm"]].append(r["flagged"])
    return dict(
        all=float(np.mean([r["flagged"] for r in held])),
        by_regime={regime: float(np.mean(by_regime[regime])) for regime in REGIMES},
        by_previous_arm=[float(np.mean(by_previous[arm])) for arm in ARMS],
    )


def levels(rows):
    """Per schedule and arm: encoder over the frozen estimate, and the estimate's log growth to the next hold."""
    peers = defaultdict(dict)
    for r in rows:
        peers[r["trial_id"]][r["epoch"]] = r
    rate, growth = defaultdict(list), defaultdict(list)
    for holds in peers.values():
        for epoch, r in holds.items():
            rate[(r["regime"], r["arm"])].append(r["encoder_over_bwe"])
            if epoch + 1 in holds:
                grown = math.log(holds[epoch + 1]["base_bwe_bps"] / r["base_bwe_bps"])
                growth[(r["regime"], r["arm"])].append(grown)

    def table(cells):
        out = {regime: [float(np.mean(cells[(regime, arm)])) for arm in ARMS] for regime in REGIMES}
        out["all"] = [float(np.mean([out[regime][arm] for regime in REGIMES])) for arm in ARMS]
        return out

    return dict(encoder_over_bwe=table(rate), estimate_log_growth=table(growth))


def arm_means(held, flagged):
    cells = defaultdict(list)
    for r in held:
        if r["flagged"] is flagged:
            cells[r["arm"]].append(r["utility"])
    return [float(np.mean(cells[arm])) if cells[arm] else None for arm in ARMS]


def sign(interval):
    """The forecast class of an interval over replicates."""
    if interval is None:
        return CLASSES[2]
    return CLASSES[0] if interval[0] > 0 else CLASSES[1] if interval[1] < 0 else CLASSES[2]


def reading(forecast, outcome):
    """How a forecast class compares with a B1 outcome. Fixed here, before B1 has one."""
    if forecast not in CLASSES or outcome not in benefit.OUTCOMES:
        raise ValueError("unknown forecast class or B1 outcome")
    if outcome == "inconclusive":
        return "not assessed"
    native = outcome in ("helps", "helps_below_practical_gate")
    if (forecast == "helps") == native:
        return "agrees in sign"
    return "simulator overstates the benefit" if forecast == "helps" else "simulator misses the benefit"


def measure(config, settings, ratios, plan, holds, peers):
    """Both panels for one description of the actuator."""
    exact = exact_panel(config, settings, ratios, holds)
    held = benefit.flag_rows(exact, plan)
    values = {name: v.get("exact") for name, v in contrasts(held, plan).items()}
    top = arm_means(held, True)[-1]
    sampled = sampled_panel(config, settings, ratios, holds, peers)
    sampled_held = benefit.flag_rows(sampled, plan)
    spread = {name: benefit.summary(list(v.values())) for name, v in contrasts(sampled_held, plan).items()}
    forecast = sign(spread["primary"]["interval"])
    primary = values["primary"]
    return dict(
        requested_ratios=[float(r) for r in ratios],
        forecast=forecast,
        exact_panel_agrees=primary is not None
        and (forecast == CLASSES[2] or (primary > 0) == (forecast == CLASSES[0])),
        relative_benefit=primary / top if primary is not None and top else None,
        exact=dict(
            sessions=len({r["trial_id"] for r in exact}),
            flag=flag_shares(held),
            flagged_arm_means=arm_means(held, True),
            other_arm_means=arm_means(held, False),
            contrasts=values,
            **levels(exact),
        ),
        sampled=dict(
            replicates=settings["replicates"],
            sessions=len({r["trial_id"] for r in sampled}),
            flag=flag_shares(sampled_held),
            contrasts=spread,
        ),
    )


def study(settings, holds=None, peers=None):
    plan = benefit.load_registration(REGISTRATION).plan
    config, started = simulator(), time.time()
    holds, peers = holds or plan.holds_per_peer, peers or plan.peers_per_regime
    made = {
        name: measure(config, settings, ratios, plan, holds, peers)
        for name, ratios in variants(settings).items()
    }
    return dict(
        study=STUDY,
        synthetic=True,
        native_evidence=False,
        models_trained_or_evaluated=0,
        b1_freeze_sha256=json.loads(FREEZE.read_text())["sha256"],
        flag=f"frozen estimate below {plan.growth_limit:g} times the previous hold's",
        endpoint="simulator's delivered on-time quality term in the outcome window; not the native PSNR proxy",
        holds_per_sender=holds,
        senders_per_schedule=peers,
        settings=settings,
        variants=made,
        readings_fixed_in_advance={
            outcome: {forecast: reading(forecast, outcome) for forecast in CLASSES}
            for outcome in benefit.OUTCOMES
        },
        seconds=time.time() - started,
    )


def headline(report):
    out = {}
    for name, v in report["variants"].items():
        primary = v["sampled"]["contrasts"]["primary"]
        out[name] = dict(
            forecast=v["forecast"],
            exact_benefit=v["exact"]["contrasts"]["primary"],
            sampled_benefit=primary["mean"],
            sampled_interval=primary["interval"],
            relative_benefit=v["relative_benefit"],
            flagged_share=v["exact"]["flag"]["all"],
            encoder_over_bwe=v["exact"]["encoder_over_bwe"]["all"],
        )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Simulator forecast of Native Phase B1 (synthetic)")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output directory required\n")
    settings = load_settings(args.settings)
    report = study(settings)
    args.out.mkdir(parents=True)
    (args.out / "settings.json").write_text(json.dumps(settings, indent=1, sort_keys=True) + "\n")
    (args.out / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(headline(report), indent=1))


if __name__ == "__main__":
    main()
