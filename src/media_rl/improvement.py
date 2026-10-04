"""Locked-validation safety refits; original policy weights and v1 evidence remain untouched."""

import copy
import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .calibration import Calibrator, SafetyEnsemble, risk_features
from .config import load_config, split_seed
from .controllers import DeterministicController
from .environment import MediaEnvironment
from .experiment import dump_json, evaluate_experiment, initialize, manifest, sha256, write_csv
from .metrics import calibration_metrics
from .reporting import build_report, read_episodes
from .scenarios import ID_SCENARIOS, Trace, load_trace, make_trace
from .training import ModelBundle


@dataclass(frozen=True)
class ImprovementConfig:
    name: str
    model_seeds: list[int]
    validation_seeds: list[int]
    test_seeds: list[int]
    safety_episodes: int
    calibration_episodes: int
    stress_fraction: float
    candidates: list[str]
    max_id_qoe_drop: float
    max_id_violation_increase: float
    risk_penalty: float
    minimum_score_gain: float
    bootstrap_samples: int

    def validate(self):
        for seeds in [self.model_seeds, self.validation_seeds, self.test_seeds]:
            if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or s < 0 for s in seeds):
                raise ValueError("invalid campaign seeds")
        if set(self.validation_seeds) & set(self.test_seeds):
            raise ValueError("validation/test seed overlap")
        if self.candidates != ["id_refit", "stress_safe", "stress_gcc"]:
            raise ValueError("candidate set/order must match the frozen protocol")
        if any(type(n) is not int or n < 2 for n in [self.safety_episodes, self.calibration_episodes]):
            raise ValueError("refit requires at least two episodes per split")
        if not np.isfinite(self.stress_fraction) or not 0 < self.stress_fraction < 1:
            raise ValueError("stress fraction must lie strictly between zero and one")
        for value in [
            self.max_id_qoe_drop,
            self.max_id_violation_increase,
            self.risk_penalty,
            self.minimum_score_gain,
        ]:
            if not np.isfinite(value) or value < 0:
                raise ValueError("selection tolerances must be finite and nonnegative")
        if type(self.bootstrap_samples) is not int or self.bootstrap_samples < 20:
            raise ValueError("bootstrap_samples must be >=20")
        return self


def randomized_stress(steps, seed):
    """Training distribution, NOT an evaluation-family generator or replay of test data."""
    if steps < 10:
        raise ValueError("stress traces require >=10 steps")
    rng = np.random.default_rng(seed)
    cuts = np.r_[0, np.sort(rng.choice(np.arange(1, steps), min(5, steps - 1), replace=False)), steps]
    capacity, rtt = np.empty(steps), np.empty(steps)
    loss, burst = np.empty(steps), np.zeros(steps)
    buffer = np.ones(steps)
    for start, end in zip(cuts[:-1], cuts[1:]):
        capacity[start:end] = np.exp(rng.uniform(np.log(0.12), np.log(7.0)))
        rtt[start:end] = rng.uniform(25, 230)
        loss[start:end] = rng.uniform(0.001, 0.025)
        buffer[start:end] = rng.choice([1.0, 2.0, 4.0, 8.0])
    bad = False
    severity = rng.uniform(0.06, 0.4)
    for t in range(steps):
        bad = rng.random() > 0.2 if bad else rng.random() < 0.025
        if bad:
            loss[t], burst[t] = severity, 0.8
    jitter = np.abs(rng.normal(0, rng.uniform(1, 15), steps))
    feedback = np.ones(steps, dtype=bool)
    if rng.random() < 0.5:
        start = int(rng.integers(1, steps))
        feedback[start : min(steps, start + int(rng.integers(3, 16)))] = False
    return Trace("randomized_training", capacity, rtt, loss, jitter, feedback, burst, buffer)


def collect_refit(config, seed, policy, split, episodes, stress_fraction, augment):
    if split not in {"risk_v2", "calibration_v2"}:
        raise ValueError("refit collectors cannot access validation/test namespaces")
    rng = np.random.default_rng(split_seed(seed, split))
    xs, ys, ids, seeds, families = [], [], [], [], []
    id_episode = 0
    for episode in range(episodes):
        trace_seed = split_seed(seed, split, episode)
        # Spread the requested stress fraction evenly rather than confounding family with behavior.
        stress = int((episode + 1) * stress_fraction) > int(episode * stress_fraction)
        if stress:
            trace = randomized_stress(config.simulator.steps, trace_seed)
        else:
            trace = make_trace(
                ID_SCENARIOS[id_episode % len(ID_SCENARIOS)], config.simulator.steps, trace_seed
            )
            id_episode += 1
        seeds.append(trace_seed)
        families.append(trace.name)
        env = MediaEnvironment(config.simulator, trace)
        obs = env.reset()
        baseline = DeterministicController(
            env.actions, "safe" if episode % 3 == 1 else "gcc", config.simulator.dt_s
        )
        for _ in range(config.simulator.steps):
            proposal = int(np.argmax(policy(np.clip(obs.vector(), -12, 12))))
            executed = proposal if episode % 3 == 0 else baseline.act(obs).action
            probe = int(rng.integers(len(env.actions))) if augment else proposal
            if augment and rng.random() < 0.15:
                executed = probe
            # One extra random-action label improves action coverage; deduplicate candidates.
            for candidate in dict.fromkeys([proposal, probe] if augment else [proposal]):
                xs.append(risk_features(obs, env.actions[candidate]))
                ys.append(env.preview(candidate)["safe"])
                ids.append(episode)
            obs, _, _, _ = env.step(executed)
    x, y, ids = np.asarray(xs), np.asarray(ys), np.asarray(ids)
    digest = hashlib.sha256(
        x.astype("<f8").tobytes() + y.astype("<i8").tobytes() + ids.astype("<i8").tobytes()
    ).hexdigest()
    return (
        x,
        y,
        ids,
        dict(
            namespace=split,
            trace_seeds=seeds,
            families=families,
            samples=len(y),
            positive_rate=float(y.mean()),
            data_sha256=digest,
        ),
    )


def audit_directory(path, stage):
    data = json.loads((Path(path) / "manifest.json").read_text())
    if data["stage"] != stage:
        raise ValueError(f"incomplete {path}: expected {stage}; preserve it and use a new campaign directory")
    for name, expected in data["artifacts_sha256"].items():
        if not (Path(path) / name).is_file() or sha256(Path(path) / name) != expected:
            raise ValueError(f"artifact hash mismatch: {path}/{name}")
    return data


def refit_candidates(config, protocol, models, out):
    for candidate in protocol.candidates:
        dest = out / "candidates" / candidate
        if dest.exists():
            audit_directory(dest, "refit_complete")
            continue
        initialize(dest, config)
        (dest / "models").mkdir()
        rows = []
        for seed in config.seeds:
            if candidate == "stress_gcc":
                bundle = ModelBundle.load(out / "candidates/stress_safe/models" / f"seed_{seed}.json")
                bundle.metadata["fallback_kind"] = "gcc"
            else:
                source = models / "models" / f"seed_{seed}.json"
                original = ModelBundle.load(source)
                fraction = 0.0 if candidate == "id_refit" else protocol.stress_fraction
                x, y, ids, risk_info = collect_refit(
                    config, seed, original.policy, "risk_v2", protocol.safety_episodes, fraction, True
                )
                safety = SafetyEnsemble.fit(
                    x,
                    y,
                    ids,
                    config.training,
                    config.gate,
                    np.random.default_rng(split_seed(seed, "risk_v2")),
                )
                cx, cy, cids, cal_info = collect_refit(
                    config,
                    seed,
                    original.policy,
                    "calibration_v2",
                    protocol.calibration_episodes,
                    fraction,
                    False,
                )
                raw, _ = safety.predict(cx)
                single, _ = safety.predict(cx, single=True)
                calibrator = Calibrator.fit(raw, cy, config.gate.calibration)
                single_cal = Calibrator.fit(single, cy, config.gate.calibration)
                metadata = copy.deepcopy(original.metadata)
                metadata.update(
                    fallback_kind="safe",
                    source_checkpoint_sha256=sha256(source),
                    policy_frozen=True,
                    safety_refit=dict(
                        protocol=vars(protocol),
                        candidate=candidate,
                        stress_fraction=fraction,
                        risk=risk_info,
                        calibration=cal_info,
                    ),
                    risk_samples=len(y),
                    risk_positive_rate=float(y.mean()),
                    calibration_samples=len(cy),
                    calibration_positive_rate=float(cy.mean()),
                    split_trace_seeds={
                        "train": original.metadata["split_trace_seeds"]["train"],
                        "risk_v2": risk_info["trace_seeds"],
                        "calibration_v2": cal_info["trace_seeds"],
                    },
                )
                bundle = ModelBundle(original.policy, safety, calibrator, single_cal, metadata)
                rows.extend(
                    dict(
                        seed=seed,
                        episode=int(e),
                        label=int(label),
                        raw=float(p),
                        calibrated=float(q),
                        single_raw=float(sp),
                    )
                    for e, label, p, q, sp in zip(cids, cy, raw, calibrator.predict(raw), single)
                )
            bundle.save(dest / "models" / f"seed_{seed}.json")
            print(f"refit candidate={candidate} seed={seed}", flush=True)
        if rows:
            write_csv(dest / "calibration.csv", rows)
        else:
            shutil.copy2(out / "candidates/stress_safe/calibration.csv", dest / "calibration.csv")
        dump_json(dest / "refit_protocol.json", vars(protocol))
        manifest(dest, config, "refit_complete")


def validation_metrics(path):
    episodes = read_episodes(Path(path) / "episodes.csv")
    if {r["domain"] for r in episodes} != {"id", "ood"}:
        raise ValueError("selection requires both ID and stress domains")
    return {
        f"{d}_{k}": float(np.mean([r[k] for r in episodes if r["domain"] == d]))
        for d in ["id", "ood"]
        for k in ["qoe", "violation_rate"]
    }


def select_candidate(metrics, protocol):
    """Pure function accepting ONLY validation summaries; final-test paths are not inputs."""
    baseline = metrics["v1"]

    def score(m):
        return 0.5 * (m["id_qoe"] + m["ood_qoe"]) - protocol.risk_penalty * m["ood_violation_rate"]

    ranking = []
    for candidate in protocol.candidates:
        m = metrics[candidate]
        feasible = (
            m["id_qoe"] >= baseline["id_qoe"] - protocol.max_id_qoe_drop
            and m["id_violation_rate"] <= baseline["id_violation_rate"] + protocol.max_id_violation_increase
            and m["ood_violation_rate"] <= baseline["ood_violation_rate"]
        )
        ranking.append(dict(candidate=candidate, feasible=feasible, score=score(m), metrics=m))
    eligible = [
        r for r in ranking if r["feasible"] and r["score"] > score(baseline) + protocol.minimum_score_gain
    ]
    selected = max(eligible, key=lambda r: r["score"])["candidate"] if eligible else "v1"
    return dict(
        selected=selected,
        baseline=baseline,
        baseline_score=score(baseline),
        ranking=ranking,
        selection_split="validation",
        validation_seeds=protocol.validation_seeds,
        test_seeds=protocol.test_seeds,
        rule=vars(protocol),
    )


def complete_evaluation(config, models, out, split, plots=False, model_map=None):
    if out.exists():
        data = audit_directory(out, "complete")
        if not config.digest_matches(data["config_sha256"]) or data.get("evaluation_split") != split:
            raise ValueError("completed run does not match requested config/split")
        return
    evaluate_experiment(config, models, out, split=split, model_map=model_map)
    build_report(out, plots=plots)
    manifest(out, config, "complete")


def benchmark_safety(config, run, model_dirs):
    """Compare predictors on exactly the same fresh ungated-policy states and labels."""
    rows = []
    from .scenarios import SCENARIOS

    for seed in config.seeds:
        bundles = {
            name: ModelBundle.load(directory / "models" / f"seed_{seed}.json")
            for name, directory in model_dirs.items()
        }
        policy = bundles["v1"].policy
        if any(b.policy.to_dict() != policy.to_dict() for b in bundles.values()):
            raise ValueError("same-state safety benchmark requires identical frozen policy weights")
        features, labels = {"id": [], "ood": []}, {"id": [], "ood": []}
        for scenario in config.scenarios:
            domain = SCENARIOS[scenario]
            for trace_seed in config.test_seeds:
                env = MediaEnvironment(
                    config.simulator, load_trace(run / "traces" / f"{scenario}_{trace_seed}.npz")
                )
                obs = env.reset()
                for _ in range(config.simulator.steps):
                    action = int(np.argmax(policy(np.clip(obs.vector(), -12, 12))))
                    features[domain].append(risk_features(obs, env.actions[action]))
                    obs, _, _, info = env.step(action)
                    labels[domain].append(info["safe"])
        for domain in ["id", "ood"]:
            x, y = np.asarray(features[domain]), np.asarray(labels[domain])
            for name, bundle in bundles.items():
                p, _ = bundle.safety.predict(x)
                for kind, probabilities in [("raw", p), ("calibrated", bundle.calibrator.predict(p))]:
                    rows.append(
                        dict(
                            model_seed=seed,
                            domain=domain,
                            predictor=name,
                            score=kind,
                            count=len(y),
                            **calibration_metrics(probabilities, y),
                        )
                    )
    write_csv(run / "confidence_benchmark.csv", rows)


def run_improvement(settings_path, models, out, plots=True):
    settings = json.loads(Path(settings_path).read_text())
    protocol = ImprovementConfig(**settings).validate()
    models, out = Path(models).resolve(), Path(out)
    base = load_config(models / "config.json")
    if not set(protocol.model_seeds) <= set(base.seeds):
        raise ValueError("missing pretrained model seeds")
    if (set(protocol.validation_seeds) | set(protocol.test_seeds)) & set(base.test_seeds):
        raise ValueError("follow-up cannot reuse original evaluation seed panel")
    source = json.loads((models / "manifest.json").read_text())
    parent_hashes = {
        f"models/seed_{s}.json": sha256(models / "models" / f"seed_{s}.json") for s in protocol.model_seeds
    }
    if any(source["artifacts_sha256"].get(k) != v for k, v in parent_hashes.items()):
        raise ValueError("source checkpoint audit failed")
    identity = dict(
        protocol=settings,
        source_config_sha256=base.digest(),
        source_model_sha256=parent_hashes,
        implementation_sha256={p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    )
    if out.exists():
        if json.loads((out / "campaign.json").read_text()) != identity:
            raise ValueError(
                "campaign settings, source weights, or implementation changed; use a new output directory"
            )
    else:
        out.mkdir(parents=True)
        dump_json(out / "campaign.json", identity)
    config = replace(
        base, name=protocol.name, seeds=protocol.model_seeds, bootstrap_samples=protocol.bootstrap_samples
    ).validate()
    refit_candidates(config, protocol, models, out)
    directories = {"v1": models, **{name: out / "candidates" / name for name in protocol.candidates}}
    metrics = {}
    validation_hashes = {}
    for candidate, directory in directories.items():
        variant = replace(
            config,
            name=f"validation-{candidate}",
            methods=["calibrated"],
            test_seeds=protocol.validation_seeds,
        ).validate()
        dest = out / "validation" / candidate
        complete_evaluation(variant, directory, dest, "validation")
        metrics[candidate] = validation_metrics(dest)
        validation_hashes[candidate] = sha256(dest / "manifest.json")
        print(f"validation complete: {candidate}", flush=True)
    selection = select_candidate(metrics, protocol)
    selection["validation_manifests_sha256"] = validation_hashes
    locked = out / "selection.json"
    if locked.exists():
        if json.loads(locked.read_text()) != selection:
            raise ValueError("locked selection changed")
    else:
        dump_json(locked, selection)
    print(f"LOCKED selected={selection['selected']} before fresh-test evaluation", flush=True)
    final_config = replace(
        config,
        name="rlcd-v2-fresh-test",
        test_seeds=protocol.test_seeds,
        methods=[
            "safe",
            "heuristic",
            "gcc",
            "rl",
            "calibrated",
            "calibrated_v1",
            "id_refit",
            "stress_safe",
            "uncalibrated",
        ],
    ).validate()
    dest = out / "test"
    complete_evaluation(
        final_config,
        directories[selection["selected"]],
        dest,
        "test",
        plots=plots,
        model_map={
            "calibrated_v1": models,
            "id_refit": directories["id_refit"],
            "stress_safe": directories["stress_safe"],
        },
    )
    final_manifest = audit_directory(dest, "complete")
    if (
        "confidence_benchmark.csv" not in final_manifest["artifacts_sha256"]
        or "selection.json" not in final_manifest["artifacts_sha256"]
    ):
        benchmark_safety(
            final_config, dest, {name: directories[name] for name in ["v1", "id_refit", "stress_safe"]}
        )
        shutil.copy2(locked, dest / "selection.json")
        manifest(dest, final_config, "complete")
    dump_json(
        out / "status.json",
        dict(
            stage="complete",
            selected=selection["selected"],
            selection_sha256=sha256(locked),
            test_manifest_sha256=sha256(dest / "manifest.json"),
        ),
    )
    return dest
