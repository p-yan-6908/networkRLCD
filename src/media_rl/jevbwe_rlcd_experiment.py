"""Isolated factual-bandit RLCD study; supervised JevBWE bytes are never rewritten."""

import gzip
import hashlib
import itertools
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.stats import beta

from .jevbwe import RATIOS, STATE_DIM, CausalHistory, JevBWE, ResidualModel, clipped_rate
from .jevbwe_credit import SettledCredit
from .jevbwe_experiment import Episode, dump, dump_gzip
from .jevbwe_experiment import source_hashes as baseline_sources
from .jevbwe_rlcd import (
    ABI,
    BEHAVIOR,
    ROLES,
    NumericModel,
    RLCDPolicy,
    calibrate_binary,
    calibrate_choice,
    calibrated_forecasts,
    fit_policy,
    forecasts,
    split_seed,
)
from .networks import MLP
from .scenarios import ID_SCENARIOS, SCENARIOS

SOURCES = ("jevbwe_rlcd.py", "jevbwe_rlcd_experiment.py", "jevbwe_rlcd_cli.py", "jevbwe_laya.py")
SCENARIO_ORDER = tuple(SCENARIOS)
METHODS = ("fallback_only", "supervised", "numeric_rlcd")


def sources():
    root = Path(__file__).parent
    return {
        **baseline_sources(),
        **{name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES},
    }


def seal(path):
    artifacts = {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.rglob("*"))
        if p.is_file() and p != path / "manifest.json"
    }
    dump(path / "manifest.json", dict(abi=ABI, artifacts=artifacts, synthetic_only=True))


def audit(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("abi") != ABI or not manifest.get("artifacts"):
        raise ValueError("RLCD artifact ABI/inventory required")
    actual = {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in path.rglob("*")
        if p.is_file() and p != path / "manifest.json"
    }
    if actual != manifest["artifacts"]:
        raise ValueError("RLCD artifact hash/inventory mismatch")
    return dict(artifacts=len(actual), synthetic_only=True)


def collect(config, role):
    c = config.study
    cohorts, samples = [], []
    interval = int(c.hold_ms / c.dt_ms)
    for episode in range(getattr(c, f"{role}_episodes")):
        seed = split_seed(c.seed, role, episode)
        runtime = Episode(c, ID_SCENARIOS[episode % len(ID_SCENARIOS)], seed)
        history = CausalHistory(c.residual)
        tracker = SettledCredit(c.credit_window_ms, switch_weight=c.switch_weight)
        assignment_seed = split_seed(seed, "assignment")
        rng = np.random.default_rng(assignment_seed)  # independent of the exogenous trace RNG
        for step in range(c.steps):
            sample = runtime.sample()
            state, _ = history.observe(sample)
            request = sample.requested_bps
            if step % interval == 0:
                action = int(rng.integers(6))  # IID, not a without-replacement permutation!
                ceiling = min(c.residual.max_bps, RATIOS[-1] * sample.bwe_bps)
                candidates = [clipped_rate(r, sample.bwe_bps, ceiling, c.residual) for r in RATIOS]
                request = candidates[action]
                old = tracker.begin(
                    now_ms=sample.sample_ms,
                    action_index=action,
                    state=state.tolist(),
                    requested_bps=request,
                    previous_bps=sample.requested_bps,
                    network_delay_ms=sample.rtt_ms / 2,
                    role=role,
                    episode=episode,
                    scenario=ID_SCENARIOS[episode % len(ID_SCENARIOS)],
                    trace_seed=seed,
                    base_bps=sample.bwe_bps,
                    identifiable=sum(abs(v - request) <= 1 for v in candidates) == 1,
                    behavior=BEHAVIOR,
                    behavior_seed=assignment_seed,
                    behavior_probabilities=[1 / 6] * 6,
                    behavior_probability=1 / 6,
                )
                if old is not None:
                    cohorts.append(old)
            outcome = runtime.advance(request)
            row = tracker.observe(
                now_ms=runtime.now,
                interval_ms=c.dt_ms,
                encoder_target_bps=runtime.encoder.target_bps,
                delivered_qoe=outcome["qoe"],
                unsafe=1 - outcome["safe"],
            )
            if row is not None:
                cohorts.append(row)
            samples.append(
                dict(
                    role=role,
                    episode=episode,
                    step=step,
                    sample=asdict(sample),
                    command_bps=request,
                    encoder_target_bps=runtime.encoder.target_bps,
                    delivered_qoe=outcome["qoe"],
                    unsafe=1 - outcome["safe"],
                )
            )
        tail = tracker.finish()
        if tail is not None:
            cohorts.append(tail)
    return cohorts, samples


def inspect_data(data):
    """Do not retrofit 1/6 into legacy marginal-uniform, without-replacement logs."""
    report = {}
    for role, rows in data.items():
        unknown = nonpositive = invalid = 0
        counts = [0] * 6
        for row in rows:
            if (
                row.get("role") != role
                or len(row.get("state", [])) != STATE_DIM
                or not np.isfinite(np.asarray(row.get("state", []), dtype=float)).all()
                or type(row.get("action_index")) is not int
                or not 0 <= row["action_index"] < 6
            ):
                invalid += 1
                continue
            counts[row["action_index"]] += 1
            if row.get("behavior") != BEHAVIOR or "behavior_probabilities" not in row:
                unknown += 1
                continue
            mu = np.asarray(row["behavior_probabilities"], dtype=float)
            if (
                mu.shape != (6,)
                or not np.isfinite(mu).all()
                or abs(mu.sum() - 1) > 1e-10
                or not np.allclose(mu, [1 / 6] * 6, rtol=0, atol=1e-12)
                or row.get("behavior_probability") != float(mu[row["action_index"]])
            ):
                invalid += 1
            if mu.shape == (6,) and np.any(mu <= 0):
                nonpositive += 1
        for episode in {r.get("episode") for r in rows}:
            ordered = sorted(
                [r for r in rows if r.get("episode") == episode], key=lambda r: r.get("command_ms", -1)
            )
            if not ordered or ordered[0].get("behavior") != BEHAVIOR:
                continue
            trace_seed, behavior_seed = ordered[0].get("trace_seed"), ordered[0].get("behavior_seed")
            if (
                type(trace_seed) is not int
                or type(behavior_seed) is not int
                or behavior_seed != split_seed(trace_seed, "assignment")
            ):
                invalid += len(ordered)
                continue
            rng = np.random.default_rng(behavior_seed)
            for r in ordered:
                if r.get("behavior_seed") != behavior_seed or r.get("action_index") != int(rng.integers(6)):
                    invalid += 1
        report[role] = dict(
            cohorts=len(rows),
            action_counts=counts,
            unknown_propensities=unknown,
            nonpositive_support=nonpositive,
            invalid_contracts=invalid,
            censored=sum(r.get("censored", True) for r in rows),
            changed=sum(r.get("changed_action", False) for r in rows),
            aliased=sum(not r.get("identifiable", False) for r in rows),
        )
    identified = bool(report) and all(
        r["cohorts"]
        and min(r["action_counts"]) > 0
        and not (r["unknown_propensities"] or r["nonpositive_support"] or r["invalid_contracts"])
        for r in report.values()
    )
    return dict(
        known_randomization_and_positivity=identified,
        no_outcome_dependent_censoring=all(r["censored"] == 0 for r in report.values()),
        roles=report,
        target="uniform-intervention success-conditional Choice; not an optimal-action label",
        limitation="randomization identifies factual arm event probabilities; predictive skill and control superiority are separate checks",
    )


def arrays(rows, target, config):
    x = np.asarray([r["state"] for r in rows])
    a = np.asarray([r["action_index"] for r in rows], dtype=int)
    y = np.asarray([int(r[target] >= config.success_qoe) for r in rows])
    mu = np.asarray([r["behavior_probability"] for r in rows])
    return x, a, y, mu


def calibrate(net, rows, mean, scale, target, config, *, blind=False):
    x, a, y, mu = arrays(rows, target, config)
    logits = net(np.clip((x - mean) / scale, -12, 12))
    if blind:
        logits = np.repeat(logits.mean(axis=-1, keepdims=True), 6, axis=-1)
    binary = calibrate_binary(logits[np.arange(len(a)), a], y, mu)
    _, p, _ = forecasts(binary["slope"] * logits + binary["bias"])
    return dict(binary=binary, choice=calibrate_choice(p, a, y, mu))


def cluster_interval(values, seed, config, *, alpha=None):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        return None
    rng = np.random.default_rng(seed)
    boots = rng.choice(values, (config.bootstrap_samples, len(values)), replace=True).mean(axis=1)
    alpha = config.alpha if alpha is None else alpha
    return np.quantile(boots, [alpha / 2, 1 - alpha / 2]).tolist()


def skill(rows, conditional, blind, mean, scale, cal, blind_cal, target, config):
    selected = [r for r in rows if r["changed_action"] and r["identifiable"]]
    folds, gains = [], []
    for fold in (None, 0, 1):
        subset = [r for r in selected if fold is None or r["episode"] % 2 == fold]
        if not subset:
            folds.append(dict(fold=fold, rows=0, skill=None))
            continue
        x, a, y, mu = arrays(subset, target, config)
        _, p = calibrated_forecasts(conditional, x, mean, scale, cal)
        # Scores only the observed Bernoulli arm; no dense one-hot outcome matrix.
        z = np.clip((x - mean) / scale, -12, 12)
        raw, raw_blind = conditional(z), blind(z).mean(axis=-1)
        chosen = cal["binary"]["slope"] * raw[np.arange(len(a)), a] + cal["binary"]["bias"]
        chosen_blind = blind_cal["binary"]["slope"] * raw_blind + blind_cal["binary"]["bias"]
        losses = np.logaddexp(0, chosen) - y * chosen
        blind_losses = np.logaddexp(0, chosen_blind) - y * chosen_blind
        weights = 1 / (6 * mu)
        conditional_loss, blind_loss = (
            float(np.average(losses, weights=weights)),
            float(np.average(blind_losses, weights=weights)),
        )
        folds.append(
            dict(
                fold=fold,
                rows=len(subset),
                conditional_log_loss=conditional_loss,
                blind_log_loss=blind_loss,
                skill=1 - conditional_loss / blind_loss if blind_loss > 1e-12 else None,
                observed_successes=int(y.sum()),
                success_conditional_log_loss=float(
                    np.average(-np.log(p[y == 1, a[y == 1]]), weights=weights[y == 1])
                )
                if y.any()
                else None,
            )
        )
        if fold is None:
            for episode in sorted({r["episode"] for r in subset}):
                mask = np.asarray([r["episode"] == episode for r in subset])
                gains.append(float(np.average(blind_losses[mask] - losses[mask], weights=weights[mask])))
    interval = cluster_interval(gains, split_seed(config.study.seed, "bootstrap", 0), config)
    counts = [sum(r["action_index"] == a for r in selected) for a in range(6)]
    passed = (
        len(selected) >= 24
        and min(counts) >= 2
        and len(gains) >= 4
        and all(f["skill"] is not None and f["skill"] >= 0.01 for f in folds)
        and interval is not None
        and interval[0] > 0
    )
    return dict(
        passed=passed,
        threshold=0.01,
        action_counts=counts,
        folds=folds,
        episode_gain_interval=interval,
        comparison="calibrated factual arm event log loss vs identical arm-blind forecast",
    )


def choice_skill(rows, probabilities, config):
    p = np.asarray(probabilities, dtype=float)
    if (
        p.shape != (len(rows), 6)
        or not np.isfinite(p).all()
        or np.any(p <= 0)
        or not np.allclose(p.sum(axis=1), 1)
    ):
        return dict(passed=False, folds=[], episode_gain_interval=None, reason="invalid_choice_support")
    selected = [
        (r, p[i])
        for i, r in enumerate(rows)
        if r["changed_action"] and r["identifiable"] and r["reward"] >= config.success_qoe
    ]
    folds, gains = [], []
    for fold in (None, 0, 1):
        subset = [(r, v) for r, v in selected if fold is None or r["episode"] % 2 == fold]
        if not subset:
            folds.append(dict(fold=fold, rows=0, skill=None))
            continue
        weights = np.asarray([1 / (6 * r["behavior_probability"]) for r, _ in subset])
        loss = np.asarray([-np.log(v[r["action_index"]]) for r, v in subset])
        brier = [1 - 2 * v[r["action_index"]] + np.sum(v * v) for r, v in subset]
        nll = float(np.average(loss, weights=weights))
        folds.append(
            dict(
                fold=fold,
                rows=len(subset),
                log_loss=nll,
                uniform_log_loss=float(np.log(6)),
                brier=float(np.average(brier, weights=weights)),
                skill=1 - nll / np.log(6),
            )
        )
        if fold is None:
            for episode in sorted({r["episode"] for r, _ in subset}):
                mask = np.asarray([r["episode"] == episode for r, _ in subset])
                gains.append(float(np.average(np.log(6) - loss[mask], weights=weights[mask])))
    interval = cluster_interval(gains, split_seed(config.study.seed, "bootstrap", 4), config)
    counts = [sum(r["action_index"] == a for r, _ in selected) for a in range(6)]
    passed = (
        len(selected) >= 24
        and min(counts) >= 2
        and len(gains) >= 4
        and interval is not None
        and interval[0] > 0
        and all(f["skill"] is not None and f["skill"] >= 0.01 for f in folds)
    )
    return dict(
        passed=bool(passed),
        action_counts=counts,
        folds=folds,
        episode_gain_interval=interval,
        target="factual arm conditional on success under uniform intervention; NOT best-action labels",
    )


def train(config, baseline_model, out, *, data_run=None):
    config.validate()
    baseline_model, out = Path(baseline_model), Path(out)
    original = baseline_model.read_bytes()
    baseline = json.loads(original)
    ResidualModel(baseline)
    if baseline.get("source_sha256") != baseline_sources() or baseline.get("synthetic_only") is not True:
        raise ValueError("frozen supervised baseline source/domain mismatch")
    if baseline["config"] != asdict(config.study.residual):
        raise ValueError("RLCD must preserve the baseline physical constraints")
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(out / "config.json", config.to_dict())
    (out / "baseline_model.json").write_bytes(original)
    data = {}
    for role in ROLES:
        if data_run is None:
            data[role], samples = collect(config, role)
            dump_gzip(out / f"{role}_samples.json.gz", samples)
        else:
            data[role] = json.loads(
                gzip.decompress((Path(data_run) / f"{role}_cohorts.json.gz").read_bytes())
            )
        dump_gzip(out / f"{role}_cohorts.json.gz", data[role])
    readiness = inspect_data(data)
    dump(out / "data_support.json", readiness)
    if not readiness["known_randomization_and_positivity"]:
        seal(out)
        raise ValueError(
            "factual data lacks the known conditional randomization/positivity contract; support report saved, no counterfactual labels or model fitted"
        )
    complete = {role: [r for r in rows if not r["censored"]] for role, rows in data.items()}
    if any(not rows for rows in complete.values()):
        seal(out)
        raise ValueError("no settled outcomes in a required role; censored evidence retained")
    x = np.asarray([r["state"] for r in complete["train"]])
    mean, scale = x.mean(axis=0), np.maximum(x.std(axis=0), 0.05)
    models, calibrations, qualifications = {}, {}, {}
    for target in ("reward", "delivered_reward"):
        x, a, y, mu = arrays(complete["train"], target, config)
        z = np.clip((x - mean) / scale, -12, 12)
        seed = split_seed(config.study.seed, "optimizer", 0)
        conditional = fit_policy(z, a, y, mu, config, seed)
        blind = fit_policy(z, a, y, mu, config, seed, blind=True)
        cal = calibrate(conditional, complete["calibration"], mean, scale, target, config)
        blind_cal = calibrate(blind, complete["calibration"], mean, scale, target, config, blind=True)
        models[target] = dict(conditional=conditional.to_dict(), blind=blind.to_dict())
        calibrations[target] = dict(conditional=cal, blind=blind_cal)
        qualifications[target] = skill(
            complete["qualification"], conditional, blind, mean, scale, cal, blind_cal, target, config
        )
    actor = MLP.from_dict(models["reward"]["conditional"])
    _, qp = calibrated_forecasts(
        actor,
        [r["state"] for r in complete["qualification"]],
        mean,
        scale,
        calibrations["reward"]["conditional"],
    )
    qualifications["choice"] = choice_skill(complete["qualification"], qp, config)
    passed = (
        readiness["no_outcome_dependent_censoring"]
        and all(q["passed"] for q in qualifications.values())
        and calibrations["reward"]["conditional"]["binary"]["method"] == "ipw_platt"
    )
    cal_rows = [r for r in complete["calibration"] if r["reward"] >= config.success_qoe]
    artifact = dict(
        abi=ABI,
        ratios=list(RATIOS),
        policy_weights=models["reward"]["conditional"],
        mean=mean.tolist(),
        scale=scale.tolist(),
        calibration=calibrations["reward"]["conditional"],
        qualification_controls=models,
        qualification_calibration=calibrations,
        action_value_passed=passed,
        supports_causal_discrimination=passed,
        calibration_rows=[sum(r["action_index"] == a for r in cal_rows) for a in range(6)],
        calibration_episodes=[
            len({r["episode"] for r in cal_rows if r["action_index"] == a}) for a in range(6)
        ],
        baseline_bundle=baseline,
        baseline_model_sha256=hashlib.sha256(original).hexdigest(),
        fitting_hash=config.fitting_hash(),
        evaluation_hash=config.evaluation_hash(),
        source_sha256=sources(),
        inference_budget_ms=config.study.dt_ms,
        promoted=False,
        synthetic_only=True,
    )
    NumericModel(artifact)
    dump(out / "model.json", artifact)
    report = dict(
        abi=ABI,
        data_support=readiness,
        qualification=qualifications,
        supports_causal_discrimination=passed,
        calibrated_choice_target="uniform-intervention action conditional on a factual QoE-success event",
        label_semantics="only factual binary QoE event; never an optimal-action label or unobserved-arm negative",
        training="Gaussian REINFORCE, leave-one-out group baseline, IPW strictly proper binary log + success-conditional log/spherical reward",
        parameter_count=sum(np.asarray(p).size for p in artifact["policy_weights"]),
        risk_weights_changed=False,
        supervised_weights_changed=False,
        promoted=False,
    )
    dump(out / "training_report.json", report)
    snapshot = out / "source"
    snapshot.mkdir()
    for name in sources():
        (snapshot / name).write_bytes((Path(__file__).parent / name).read_bytes())
    assert baseline_model.read_bytes() == original
    seal(out)
    return report


def control_episode(config, numeric, baseline, scenario, seed, split, method):
    c = config.study
    runtime = Episode(c, scenario, split_seed(seed, split, SCENARIO_ORDER.index(scenario)))
    if method == "supervised":
        policy = JevBWE(ResidualModel(baseline))
    elif method == "fallback_only":
        frozen = dict(baseline)
        frozen.update(action_value_passed=True, calibration_rows=[0] * 6, calibration_episodes=[0] * 6)
        policy = JevBWE(ResidualModel(frozen))  # unchanged 0.85 headroom, no neural eligibility
    else:
        policy = RLCDPolicy(numeric)
    tracker = SettledCredit(c.credit_window_ms, switch_weight=c.switch_weight)
    rows, cohorts = [], []
    for step in range(c.steps):
        sample = runtime.sample()
        decision = policy.observe(sample)
        request = decision["requested_bps"]
        changed = abs(request - sample.requested_bps) > 1
        switch = c.switch_weight * abs(np.log(request / sample.requested_bps)) if changed else 0
        if changed:
            old = tracker.finish("superseded")
            if old is not None:
                cohorts.append(old)
            if decision["learned_executed"]:
                tracker.begin(
                    now_ms=sample.sample_ms,
                    action_index=decision["proposal_index"],
                    state=decision["history"],
                    requested_bps=request,
                    previous_bps=sample.requested_bps,
                    network_delay_ms=sample.rtt_ms / 2,
                    neural=True,
                    seed=seed,
                    scenario=scenario,
                    method=method,
                )
            policy.acknowledge(request, sample.sample_ms)
        outcome = runtime.advance(request)
        cohort = tracker.observe(
            now_ms=runtime.now,
            interval_ms=c.dt_ms,
            encoder_target_bps=runtime.encoder.target_bps,
            delivered_qoe=outcome["qoe"],
            unsafe=1 - outcome["safe"],
        )
        if cohort is not None:
            cohorts.append(cohort)
        rows.append(
            dict(
                step=step,
                sample=asdict(sample),
                decision=decision,
                changed=changed,
                encoder_target_bps=runtime.encoder.target_bps,
                actual_bps=runtime.actual_bps,
                utility=outcome["qoe"] - switch,
                unsafe=1 - outcome["safe"],
                deadline_miss=outcome["deadline_miss"],
                latency_ms=outcome["latency_ms"],
                raw_loss=outcome["raw_loss"],
            )
        )
        if method == "laya":
            queried = decision["action_probabilities"] is not None
            rows[-1].update(
                laya_request=numeric.backend.last_request if queried else None,
                laya_response=numeric.backend.last_response if queried else None,
            )
    tail = tracker.finish()
    if tail is not None:
        cohorts.append(tail)
    return rows, cohorts


def control_checks(rows, config):
    last_change = rows[0]["sample"]["sample_ms"]
    rate_errors = dwell_errors = 0
    for r in rows:
        d, s = r["decision"], r["sample"]
        rate = d["requested_bps"]
        rate_errors += int(
            not (
                0 <= rate <= d["safe_bps"] + 1e-6
                and rate >= min(config.study.residual.min_bps, d["safe_bps"]) - 1e-6
            )
        )
        if r["changed"]:
            dwell_errors += int(rate > s["requested_bps"] + 1 and s["sample_ms"] - last_change < 1800)
            last_change = s["sample_ms"]
    return dict(
        rate_violations=rate_errors,
        dwell_violations=dwell_errors,
        inference_overruns=sum(r["decision"].get("inference_overrun", False) for r in rows),
    )


def summarize(rows, cohorts, config):
    return dict(
        utility=float(np.mean([r["utility"] for r in rows])),
        unsafe=float(np.mean([r["unsafe"] for r in rows])),
        deadline_miss=float(np.mean([r["deadline_miss"] for r in rows])),
        latency_p95_ms=float(np.quantile([r["latency_ms"] for r in rows], 0.95)),
        neural_steps=sum(r["decision"]["learned_executed"] for r in rows),
        neural_complete_cohorts=sum(not r["censored"] for r in cohorts),
        neural_censored_cohorts=sum(r["censored"] for r in cohorts),
        checks=control_checks(rows, config),
        reasons=dict(Counter(r["decision"]["reason"] for r in rows)),
    )


def paired_significance(effects, config):
    effects = np.asarray(effects, dtype=float)
    if not len(effects) or not np.isfinite(effects).all():
        raise ValueError("finite paired seed effects required")
    # Two candidates x two frozen panels: predeclared Bonferroni family, even if Laya is not run.
    adjusted = config.alpha / 4
    observed = float(effects.mean())
    if len(effects) <= 16:
        means = np.asarray(
            [np.mean(effects * signs) for signs in itertools.product((-1, 1), repeat=len(effects))]
        )
        p = float(np.mean(means >= observed - 1e-12))
    else:
        rng = np.random.default_rng(split_seed(config.study.seed, "bootstrap", 2))
        means = (rng.choice([-1, 1], (10000, len(effects))) * effects).mean(axis=1)
        p = float((1 + np.sum(means >= observed)) / (len(means) + 1))
    interval = cluster_interval(
        effects, split_seed(config.study.seed, "bootstrap", 1), config, alpha=2 * adjusted
    )
    passed = len(effects) >= 8 and observed > 0 and p <= adjusted and interval[0] > 0
    return dict(
        paired_seed_mean=observed,
        seed_clusters=len(effects),
        one_sided_sign_flip_p=p,
        family_adjusted_alpha=adjusted,
        interval=interval,
        significant=bool(passed),
    )


def promotion_panel(episodes, cohorts, method, config):
    candidate = [e for e in episodes if e["method"] == method]
    fallback = {(e["seed"], e["scenario"]): e for e in episodes if e["method"] == "fallback_only"}
    seeds = sorted({e["seed"] for e in candidate})
    effects, safety = [], []
    for seed in seeds:
        group = [e for e in candidate if e["seed"] == seed]
        effects.append(
            float(np.mean([e["utility"] - fallback[(seed, e["scenario"])]["utility"] for e in group]))
        )
        safety.append(
            max(
                e[metric] - fallback[(seed, e["scenario"])][metric]
                for e in group
                for metric in ("unsafe", "deadline_miss")
            )
        )
    significance = paired_significance(effects, config)
    complete = [r for r in cohorts if r["method"] == method and not r["censored"]]
    rates = [
        max(r["unsafe"] for r in complete if r["seed"] == seed)
        for seed in seeds
        if any(r["seed"] == seed for r in complete)
    ]
    # An all-zero bootstrap falsely gives upper risk zero. Treat a seed's ANY
    # unsafe settled neural outcome as one conservative Bernoulli cluster and
    # use an exact one-sided bound; correlated cohorts are not independent trials.
    n, k = len(rates), sum(rates)
    risk_interval = (
        [0.0, float(beta.ppf(1 - config.alpha / 4, k + 1, n - k)) if k < n else 1.0] if n else None
    )
    risk_passed = (
        len(complete) >= config.min_neural_cohorts
        and len(rates) >= 8
        and not any(r["method"] == method and r["censored"] for r in cohorts)
        and risk_interval is not None
        and risk_interval[1] <= config.study.residual.risk_limit
    )
    constraints = all(not any(e["checks"].values()) for e in candidate)
    safety_ok = bool(safety) and max(safety) <= 1e-12 and risk_passed
    return dict(
        qoe_vs_fallback=significance,
        hard_and_timing_constraints=constraints,
        no_seed_scenario_safety_regression=bool(safety) and max(safety) <= 1e-12,
        settled_neural_cohorts=len(complete),
        settled_neural_risk_interval=risk_interval,
        selected_risk_seed_clusters=n,
        risk_interval_method="exact one-sided seed-cluster any-unsafe bound; zero-event bootstrap not used",
        censoring_free=not any(r["method"] == method and r["censored"] for r in cohorts),
        settled_risk_supported=bool(risk_passed),
        eligible=bool(significance["significant"] and constraints and safety_ok),
    )


def evaluate(config, model_path, out, *, laya_model=None):
    config.validate()
    model_path, out = Path(model_path), Path(out)
    original = model_path.read_bytes()
    artifact = json.loads(original)
    if (
        artifact.get("source_sha256") != sources()
        or artifact.get("fitting_hash") != config.fitting_hash()
        or artifact.get("evaluation_hash") != config.evaluation_hash()
    ):
        raise ValueError("RLCD frozen source/fitting/predeclared-panel contract drift")
    numeric = NumericModel(artifact)
    baseline = artifact["baseline_bundle"]
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(out / "config.json", config.to_dict())  # predeclare both panels before outcomes
    (out / "model.json").write_bytes(original)
    if laya_model is not None:
        dump(out / "laya_model.json", laya_model.artifact)
    methods = (*METHODS, "laya") if laya_model is not None else METHODS
    episodes, all_cohorts, promotion = [], [], {}
    for split, seeds in (("validation", config.validation_seeds), ("test", config.study.test_seeds)):
        panel, panel_cohorts = [], []
        for scenario in config.study.scenarios:
            for seed in seeds:
                for method in methods:
                    active = laya_model if method == "laya" else numeric
                    rows, cohorts = control_episode(config, active, baseline, scenario, seed, split, method)
                    name = f"{split}_{scenario}_{seed}_{method}"
                    dump_gzip(out / f"{name}_decisions.json.gz", rows)
                    dump_gzip(out / f"{name}_settled_cohorts.json.gz", cohorts)
                    panel.append(
                        dict(
                            split=split,
                            scenario=scenario,
                            seed=seed,
                            method=method,
                            **summarize(rows, cohorts, config),
                        )
                    )
                    panel_cohorts.extend(cohorts)
        promotion[split] = {
            m: promotion_panel(panel, panel_cohorts, m, config)
            for m in methods
            if m in ("numeric_rlcd", "laya")
        }
        episodes.extend(panel)
        all_cohorts.extend(panel_cohorts)
    eligibility = {
        m: bool(
            (laya_model.artifact["action_value_passed"] if m == "laya" else artifact["action_value_passed"])
            and (m != "laya" or laya_model.backend.identity.get("kind") == "local_pretrained_laya")
            and promotion["validation"][m]["eligible"]
            and promotion["test"][m]["eligible"]
        )
        for m in promotion["validation"]
    }
    report = dict(
        abi=ABI,
        synthetic_only=True,
        promoted=False,
        promotion_eligible=eligibility,
        qualification=artifact["supports_causal_discrimination"],
        panels=promotion,
        episodes=episodes,
        optional_laya="not_run"
        if laya_model is None
        else laya_model.backend.identity.get("kind", "unverified_backend"),
        limitations=[
            "no observed optimal-action labels",
            "hypothetical encoder/QP physics, not native proof",
            "frozen randomized-hold risk gate is not certified selected-live-policy safety",
            "no automatic model promotion, even if the statistical gates pass",
        ],
    )
    dump(out / "evaluation_report.json", report)
    dump_gzip(out / "all_settled_cohorts.json.gz", all_cohorts)
    assert model_path.read_bytes() == original
    seal(out)
    return report


def run(config, baseline_model, out):
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(out / "config.json", config.to_dict())
    training = train(config, baseline_model, out / "training")
    evaluation = evaluate(config, out / "training" / "model.json", out / "evaluation")
    seal(out)
    return dict(
        training=training,
        promotion_eligible=evaluation["promotion_eligible"],
        panels=evaluation["panels"],
        optional_laya="not_run",
        promoted=False,
    )
