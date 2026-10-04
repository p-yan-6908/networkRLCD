"""Artifact-producing experiment orchestration, with no implicit overwrites."""

import csv
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import SimulatorConfig, TrainingConfig, split_seed
from .controllers import REFERENCE_METHODS, make_controller
from .environment import MediaEnvironment, action_space
from .metrics import episode_metrics
from .scenarios import SCENARIOS, save_trace, simulation_trace
from .training import ModelBundle, train_bundle


def dump_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_files():
    root = Path(__file__).resolve().parents[2]
    files = {f"src/media_rl/{p.name}": p for p in Path(__file__).parent.glob("*.py")}
    for directory in ["src", "configs", "tests", "docs", "paper", ".github"]:
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".json", ".md", ".tex", ".yml"}:
                files[str(path.relative_to(root))] = path
    for name in [
        "pyproject.toml",
        "uv.lock",
        "GOAL.md",
        "README.md",
        "Makefile",
        ".python-version",
        "research/RELATED_WORK.md",
        "research/references.bib",
    ]:
        if (root / name).exists():
            files[name] = root / name
    return files


def initialize(out, config):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty experiment directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    dump_json(out / "config.json", config.to_dict())
    for name, path in source_files().items():
        destination = out / "source_snapshot" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return out


def manifest(out, config, stage, extra=None):
    out = Path(out)
    root = Path(__file__).resolve().parents[2]
    source = {name: sha256(path) for name, path in source_files().items()}
    try:
        git = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git = None
    prior = json.loads((out / "manifest.json").read_text()) if (out / "manifest.json").exists() else {}
    data = dict(
        schema_version=1,
        stage=stage,
        config_sha256=config.digest(),
        command=sys.argv,
        utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version,
        platform=platform.platform(),
        git_commit=git,
        dependencies={
            name: importlib.metadata.version(name)
            for name in ["numpy", "scipy", "matplotlib", "calibrated-media-rl"]
        },
        source_sha256=source,
        training_provenance=prior.get("training_provenance", prior.get("source_sha256", source)),
        artifacts_sha256={
            str(p.relative_to(out)): sha256(p)
            for p in sorted(out.rglob("*"))
            if p.is_file() and p != out / "manifest.json"
        },
        notes=[
            "Synthetic packet/frame simulation, not a real-network result."
            if config.simulator.backend == "packet_v2"
            else "Synthetic fluid simulation, not a real-network result.",
            "Packet-v2 confidence target is recorded by safety_horizon_steps: h=1 settled cohorts; h>1 new captures under fixed-action continuation; censored labels are excluded. No safety guarantee."
            if config.simulator.backend == "packet_v2"
            else "Confidence predicts proposed-action one-step safety, not optimality or episode safety.",
            "Timestamps and timing.csv are nondeterministic diagnostics.",
            "Inference checkpoints do not include replay/optimizer state; training resume is not supported.",
        ],
    )
    if config.simulator.backend == "packet_v2":
        data["notes"].append(
            "The historical domain=ood taxonomy means stress families, not unseen/OOD validation after stress training."
        )
        data["notes"].append(
            "Pending terminal frames are censored; they are not counted as successful on-time decodes."
        )
    for key in [
        "model_artifacts",
        "episode_counts",
        "evaluation_split",
        "reference_artifacts",
        "gate_overrides",
    ]:
        if key in prior:
            data[key] = prior[key]
    if extra:
        data.update(extra)
    dump_json(out / "manifest.json", data)


def train_experiment(config, out):
    out = initialize(out, config)
    (out / "models").mkdir()
    for seed in config.seeds:
        bundle, calibration = train_bundle(config, seed)
        bundle.save(out / "models" / f"seed_{seed}.json")
        write_csv(out / f"calibration_{seed}.csv", calibration)
        write_csv(out / f"training_{seed}.csv", bundle.metadata["training_log"])
        print(
            f"trained seed={seed} risk_samples={bundle.metadata['risk_samples']} calibration={bundle.calibrator.method}",
            flush=True,
        )
    manifest(out, config, "trained")
    return out


def validate_bundle(bundle, config, seed):
    old = bundle.metadata["config"]
    if bundle.metadata["seed"] != seed:
        raise ValueError("checkpoint seed mismatch")
    from dataclasses import asdict

    if (
        asdict(SimulatorConfig(**old["simulator"])) != config.to_dict()["simulator"]
        or asdict(TrainingConfig(**old["training"])) != config.to_dict()["training"]
    ):
        raise ValueError(
            "checkpoint simulator/action/training config mismatch; retrain for physical ablations"
        )
    for key in ["ood_quantile", "calibration"]:
        if old["gate"][key] != getattr(config.gate, key):
            raise ValueError("fitted gate configuration changed; retrain/recalibrate")


def evaluate_experiment(
    config, models, out, in_place=False, split="test", model_map=None, gate_overrides=None
):
    models, out = Path(models), Path(out)
    if split not in {"test", "validation"}:
        raise ValueError("evaluation split must be test or validation")
    if model_map is None and (models / "model_map.json").exists():
        model_map = {m: models / p for m, p in json.loads((models / "model_map.json").read_text()).items()}
    model_map = model_map or {}
    if gate_overrides is None and (models / "gate_overrides.json").exists():
        gate_overrides = json.loads((models / "gate_overrides.json").read_text())
    gate_overrides = {str(method): float(value) for method, value in (gate_overrides or {}).items()}
    if set(gate_overrides) - set(config.methods) or any(
        not math.isfinite(value) or not 0 <= value <= 1 for value in gate_overrides.values()
    ):
        raise ValueError("gate overrides must map configured methods to probabilities")
    if "calibrated_090" in config.methods and gate_overrides.get("calibrated_090") != 0.9:
        raise ValueError("calibrated_090 requires an explicit 0.90 gate override")
    if (
        set(model_map) - set(config.methods)
        or not (set(config.methods) & REFERENCE_METHODS) <= model_map.keys()
    ):
        raise ValueError("reference methods require an explicit, matching model map")
    if not in_place:
        out = initialize(out, config)
    elif (out / "episodes.csv").exists() or (out / "steps.csv.gz").exists():
        raise FileExistsError("evaluation artifacts already exist")
    bundles = {}
    for seed in config.seeds:
        bundle = ModelBundle.load(models / "models" / f"seed_{seed}.json")
        validate_bundle(bundle, config, seed)
        bundles[seed] = bundle
    if gate_overrides:
        dump_json(out / "gate_overrides.json", gate_overrides)
    if not in_place:
        (out / "models").mkdir()
        for seed in config.seeds:
            shutil.copy2(models / "models" / f"seed_{seed}.json", out / "models" / f"seed_{seed}.json")
        original_source = models / "training_source"
        if not original_source.exists():
            original_source = models / "source_snapshot"
        if original_source.exists():
            shutil.copytree(original_source, out / "training_source")
    references, reference_artifacts = {}, {}
    for method, directory in model_map.items():
        directory = Path(directory)
        references[method], reference_artifacts[method] = {}, {}
        dest = out / "reference_models" / method / "models"
        dest.mkdir(parents=True)
        for seed in config.seeds:
            source = directory / "models" / f"seed_{seed}.json"
            ref = ModelBundle.load(source)
            validate_bundle(ref, config, seed)
            references[method][seed] = ref
            shutil.copy2(source, dest / source.name)
            reference_artifacts[method][str(seed)] = sha256(source)
    if model_map:
        dump_json(out / "model_map.json", {m: f"reference_models/{m}" for m in model_map})
    (out / "traces").mkdir(exist_ok=True)
    traces = {}
    for name in config.scenarios:
        for test_seed in config.test_seeds:
            trace = simulation_trace(config.simulator, name, split_seed(test_seed, split))
            traces[name, test_seed] = trace
            save_trace(trace, out / "traces" / f"{name}_{test_seed}.npz")
    episodes, timings = [], []
    # Zero mtime and empty filename make compressed step logs reproducible.
    with (
        (out / "steps.csv.gz").open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped,
        io.TextIOWrapper(zipped, newline="") as f,
    ):
        writer = None
        for seed in config.seeds:
            for name in config.scenarios:
                for test_seed in config.test_seeds:
                    for method in config.methods:
                        env = MediaEnvironment(config.simulator, traces[name, test_seed])
                        controller = make_controller(
                            method,
                            references.get(method, bundles)[seed],
                            action_space(config.simulator),
                            config.gate,
                            config.simulator.dt_s,
                            threshold=gate_overrides.get(method),
                        )
                        obs, rows, elapsed = env.reset(), [], []
                        identity = dict(
                            model_seed=seed,
                            test_seed=test_seed,
                            scenario=name,
                            domain=SCENARIOS[name],
                            method=method,
                        )
                        for step in range(config.simulator.steps):
                            start = time.perf_counter_ns()
                            decision = controller.act(obs)
                            elapsed.append((time.perf_counter_ns() - start) / 1000)
                            label_horizon = (
                                references.get(method, bundles)[seed]
                                .metadata["config"]["training"]
                                .get("safety_horizon_steps", 1)
                            )
                            proposal = env.safety_preview(decision.proposal, label_horizon)
                            old_obs = obs
                            obs, _, _, info = env.step(decision.action)
                            row = dict(
                                **identity,
                                step=step,
                                time_s=step * config.simulator.dt_s,
                                **asdict(decision),
                                proposal_safe=proposal["safe"],
                                proposal_qoe=proposal["qoe"],
                                observed_throughput=old_obs.throughput_mbps,
                                observed_rtt=old_obs.rtt_ms,
                                feedback_age_s=old_obs.feedback_age_s,
                                **info,
                            )
                            if config.simulator.backend == "packet_v2":
                                row["proposal_label_censored"] = int(proposal.get("label_censored", False))
                                row["proposal_label_horizon_steps"] = label_horizon
                            rows.append(row)
                        if writer is None:
                            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                            writer.writeheader()
                        writer.writerows(rows)
                        episodes.append(dict(**identity, **episode_metrics(rows, config.simulator.dt_s)))
                        import numpy as np

                        timings.append(
                            dict(
                                **identity,
                                inference_mean_us=float(np.mean(elapsed)),
                                inference_p95_us=float(np.quantile(elapsed, 0.95)),
                            )
                        )
            print(f"evaluated seed={seed}", flush=True)
    write_csv(out / "episodes.csv", episodes)
    write_csv(out / "timing.csv", timings)
    manifest(
        out,
        config,
        "evaluated",
        dict(
            model_artifacts={
                f"models/seed_{s}.json": sha256(out / "models" / f"seed_{s}.json") for s in config.seeds
            },
            episode_counts=dict(Counter(r["method"] for r in episodes)),
            evaluation_split=split,
            reference_artifacts=reference_artifacts,
            gate_overrides=gate_overrides,
            training_provenance=json.loads((models / "manifest.json").read_text())["training_provenance"],
        ),
    )
    return out


def run_experiment(config, out, plots=True):
    from .reporting import build_report

    out = train_experiment(config, out)
    evaluate_experiment(config, out, out, in_place=True)
    build_report(out, plots=plots)
    manifest(out, config, "complete")
    return out
