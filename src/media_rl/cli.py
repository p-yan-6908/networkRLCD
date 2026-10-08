"""Command-line interface; all settings are saved as resolved JSON."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .config import load_config
from .evidence import export_paper, run_status
from .experiment import evaluate_experiment, manifest, run_experiment, sha256, train_experiment
from .reporting import build_report
from .scenarios import SCENARIOS, make_trace, save_trace
from .sweeps import build_sweep_report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Calibrated RL for real-time media: reproducible simulation experiments"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in [
        "run",
        "train",
        "evaluate",
        "sweep",
        "improve",
        "tune-threshold",
        "policy-randomization",
        "safety-shield",
        "uncertainty-shield",
        "budget-shield",
        "delay-budget",
        "calibrate-actions",
        "realism-study",
    ]:
        p = sub.add_parser(name)
        p.add_argument("--config", required=True, type=Path)
        p.add_argument("--out", required=True, type=Path)
        p.add_argument("--no-plots", action="store_true")
        if name in {
            "evaluate",
            "sweep",
            "improve",
            "tune-threshold",
            "policy-randomization",
            "safety-shield",
            "uncertainty-shield",
            "budget-shield",
            "delay-budget",
            "calibrate-actions",
        }:
            p.add_argument(
                "--models",
                type=Path,
                required=name
                in {
                    "evaluate",
                    "improve",
                    "tune-threshold",
                    "policy-randomization",
                    "safety-shield",
                    "uncertainty-shield",
                    "budget-shield",
                    "delay-budget",
                    "calibrate-actions",
                },
            )
        if name == "evaluate":
            p.add_argument("--split", choices=["test", "validation"], default="test")
            p.add_argument("--model-map", type=Path)
            p.add_argument("--gate-map", type=Path)
        if name == "safety-shield":
            p.add_argument("--reference-models", type=Path)
        if name == "uncertainty-shield":
            p.add_argument(
                "--resume-from",
                type=Path,
                help="reuse an audited validation lock from an incomplete uncertainty-shield campaign",
            )
        if name == "sweep":
            p.add_argument("--kind", choices=["thresholds", "ablations"], required=True)
    p = sub.add_parser(
        "native-repair-plan",
        aliases=["native-repair3-plan", "native-repair4-plan", "native-repair5-plan"],
        help="Freeze versioned temporal/feedback repair training or evaluation",
    )
    p.add_argument("--source-model", required=True, type=Path)
    p.add_argument("--video-source", required=True, type=Path)
    p.add_argument("--model", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--stage",
        choices=["train", "calibration", "selected-calibration", "repeatability", "validation", "test"],
        default="train",
    )
    p.add_argument("--groups-per-family", type=int, default=2)
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--seed", type=int, default=2601)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    p.add_argument("--repeatability-run", type=Path)
    p.add_argument("--validation-run", type=Path)
    p.add_argument("--families", nargs="+", choices=["stable", "collapse", "variable", "brief-collapse"])
    for command in ("native-repair-study", "native-repair-audit"):
        p = sub.add_parser(
            command,
            aliases=[
                command.replace("native-repair-", "native-repair3-"),
                command.replace("native-repair-", "native-repair4-"),
                command.replace("native-repair-", "native-repair5-"),
            ],
        )
        p.add_argument("--config" if command.endswith("study") else "--run", required=True, type=Path)
        if command.endswith("study"):
            p.add_argument("--out", required=True, type=Path)
            p.add_argument(
                "--resume",
                action="store_true",
                help="Audit existing complete outcomes; never recollect a partial/failed peer",
            )
    p = sub.add_parser(
        "native-repair-train",
        aliases=["native-repair3-train"],
        help="Fit three-seed temporal CQL from sealed train/calibration roles only",
    )
    p.add_argument("--train-run", required=True, type=Path)
    p.add_argument("--calibration-run", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser(
        "native-repair-calibrate",
        aliases=["native-repair3-calibrate", "native-repair4-calibrate", "native-repair5-calibrate"],
        help="Calibrate a frozen repair policy on fresh factual selected-controller labels",
    )
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("native-repair5-train", help="Fit normalized factual IQL on fresh V5 roles only")
    p.add_argument("--train-run", required=True, action="append", type=Path)
    p.add_argument("--calibration-run", required=True, action="append", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser(
        "native-repair4-rebase",
        help="Rebase unselected V3 weights to a separate GCC-deferring config; no fitting",
    )
    p.add_argument("--source-model", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("native-plan", help="Freeze a fresh role-disjoint owned-browser protocol")
    p.add_argument("--model", required=True, type=Path)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--video-source", type=Path, help="Versioned licensed recorded-video catalog")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--stage", choices=["repeatability", "calibration", "validation", "test"], default="repeatability"
    )
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--groups-per-family", type=int, default=2)
    p.add_argument("--families", nargs="+", choices=["stable", "collapse", "variable", "brief-collapse"])
    p.add_argument("--seed", type=int, default=1901)
    p.add_argument("--exclude-run", action="append", type=Path, default=[])
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    p.add_argument("--repeatability-run", type=Path)
    p.add_argument("--validation-run", type=Path)
    p = sub.add_parser(
        "native-video-source", help="Hash and describe a local licensed H.264 recorded-video source"
    )
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--attribution", required=True)
    p.add_argument("--license-url", required=True)
    p.add_argument("--source-url", required=True)
    p = sub.add_parser("native-study", help="Execute a frozen native encoder-cap study (Node 22+/Chrome)")
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--resume",
        action="store_true",
        help="Recover only complete cleanup-interrupted captures; never recollect outcomes",
    )
    p = sub.add_parser("native-audit", help="Read-only raw-wire/model/pixel/statistics replay")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--hashes-only", action="store_true")
    p = sub.add_parser(
        "native-calibrate", help="Fit selected-action calibration; never fit validation/test labels"
    )
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("report")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--no-plots", action="store_true")
    p = sub.add_parser("audit")
    p.add_argument("--run", required=True, type=Path)
    p = sub.add_parser("status", help="Read filesystem progress without changing a run")
    p.add_argument("--run", required=True, type=Path)
    p = sub.add_parser("export-paper", help="Export manuscript numbers only from audited complete evidence")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--macro-prefix", default="Evidence")
    p = sub.add_parser("trace")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser(
        "native-action-train", help="Fit bounded state/action outcomes on legal V5 roles; not deployable"
    )
    p.add_argument("--train-run", required=True, action="append", type=Path)
    p.add_argument("--calibration-run", required=True, action="append", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser(
        "native-action-coverage-plan", help="Freeze exact-cap augmentation of a sealed legal V5 fitting role"
    )
    p.add_argument("--parent", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--seed", type=int, default=7101)
    for command in ("native-action-coverage-study", "native-action-coverage-audit"):
        p = sub.add_parser(
            command, help="Collect/replay declared 400/450/500 coverage; never learned qualification"
        )
        p.add_argument("--config" if command.endswith("study") else "--run", required=True, type=Path)
        if command.endswith("study"):
            p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser(
        "native-action-coverage-fit",
        help="Fit a new bounded candidate on legal original plus exact-cap augmentation roles",
    )
    p.add_argument("--train-run", required=True, action="append", type=Path)
    p.add_argument("--calibration-run", required=True, action="append", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser(
        "native-action-live-plan", help="Freeze a role-disjoint local action-outcome repeatability probe"
    )
    p.add_argument("--source-model", required=True, type=Path)
    p.add_argument("--action-model", required=True, type=Path)
    p.add_argument("--video-source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--families", nargs="+", choices=["stable", "collapse", "variable", "brief-collapse"])
    p.add_argument("--groups-per-family", type=int, default=1)
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--seed", type=int, default=8101)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    for command in ("native-action-live-study", "native-action-live-audit"):
        p = sub.add_parser(
            command, help="Collect/replay local learned aliases and BWE controls; never promote"
        )
        p.add_argument("--config" if command.endswith("study") else "--run", required=True, type=Path)
        if command.endswith("study"):
            p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser(
        "native-action-guard-plan", help="Freeze new guard/unchanged-model aliases and both BWE controls"
    )
    p.add_argument("--source-model", required=True, type=Path)
    p.add_argument("--action-model", required=True, type=Path)
    p.add_argument("--video-source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--families", nargs="+", choices=["stable", "collapse", "variable", "brief-collapse"])
    p.add_argument("--groups-per-family", type=int, default=1)
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--seed", type=int, default=9101)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    for command in ("native-action-guard-study", "native-action-guard-audit"):
        p = sub.add_parser(command, help="Collect/replay local guard repeatability; never qualify/promote")
        p.add_argument("--config" if command.endswith("study") else "--run", required=True, type=Path)
        if command.endswith("study"):
            p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("native-presentation-plan", help="Freeze wire-only causal readback instrumentation")
    p.add_argument("--source-model", required=True, type=Path)
    p.add_argument("--action-model", required=True, type=Path)
    p.add_argument("--video-source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--families", nargs="+", choices=["stable", "collapse", "variable", "brief-collapse"])
    p.add_argument("--groups-per-family", type=int, default=1)
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--seed", type=int, default=10101)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    for command in ("native-presentation-study", "native-presentation-audit"):
        p = sub.add_parser(command, help="Collect/replay wire-only instrumentation; no policy change")
        p.add_argument("--config" if command.endswith("study") else "--run", required=True, type=Path)
        if command.endswith("study"):
            p.add_argument("--out", required=True, type=Path)
    from .published_rtc_peer import MAX_REPLAY_ROWS, PEERS

    sub.add_parser("rtc-peer-list", help="List pinned published estimators; no inference dependency needed")
    for command in ("rtc-peer-inspect", "rtc-peer-replay"):
        p = sub.add_parser(command, help="CPU ONNX observation replay only, NOT closed-loop comparison")
        p.add_argument("--peer", required=True, choices=tuple(PEERS))
        p.add_argument("--checkpoint", required=True, type=Path)
        if command.endswith("replay"):
            p.add_argument("--trace", required=True, type=Path)
            p.add_argument("--out", required=True, type=Path)
            p.add_argument("--limit", type=int, default=256, help=f"Prefix rows (1..{MAX_REPLAY_ROWS})")
    p = sub.add_parser("rtc-peer-audit", help="Exactly re-execute a published observation replay")
    p.add_argument("--replay", required=True, type=Path)
    p.add_argument("--checkpoint", required=True, type=Path)
    p.add_argument("--trace", required=True, type=Path)
    p = sub.add_parser("native-dense-plan", help="Freeze a diagnostic-only scalar-cap/BWE mechanism probe")
    p.add_argument("--source-model", required=True, type=Path)
    p.add_argument("--video-source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--families", nargs="+", choices=["stable", "collapse", "variable", "brief-collapse"])
    p.add_argument("--groups-per-family", type=int, default=1)
    p.add_argument("--repetitions", type=int, default=2)
    p.add_argument("--seed", type=int, default=6101)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    for command in ("native-dense-study", "native-dense-audit"):
        p = sub.add_parser(command, help="Collect or fully replay diagnostic scalar controls; never promote")
        p.add_argument("--config" if command.endswith("study") else "--run", required=True, type=Path)
        if command.endswith("study"):
            p.add_argument("--out", required=True, type=Path)
    for command in ("jevbwe-run", "jevbwe-train", "jevbwe-evaluate"):
        p = sub.add_parser(command, help="Opt-in bitrate-only BWE residual; synthetic research only")
        p.add_argument("--config", required=True, type=Path)
        p.add_argument("--out", required=True, type=Path)
        if command == "jevbwe-evaluate":
            p.add_argument("--model", required=True, type=Path)
    p = sub.add_parser("jevbwe-audit", help="Verify JevBWE artifact hashes, not native efficacy")
    p.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command.startswith("jevbwe-"):
            from .jevbwe_experiment import audit_study, evaluate_study, load_study, run_study, train_study

            if args.command == "jevbwe-audit":
                result = audit_study(args.run)
            else:
                config = load_study(args.config)
                if args.command == "jevbwe-train":
                    result = train_study(config, args.out)
                elif args.command == "jevbwe-run":
                    result = run_study(config, args.out)
                else:
                    report = evaluate_study(config, args.model, args.out)
                    result = {
                        key: report[key] for key in ("contrasts", "action_value_passed", "synthetic_only")
                    }
            print(json.dumps(result, indent=2))
            return
        if args.command.startswith("rtc-peer-"):
            from .published_rtc_peer_cli import run

            return run(args)
        if args.command.startswith("native-presentation-"):
            from .native_presentation_cli import run

            return run(args)
        if args.command.startswith("native-action-guard-"):
            from .native_action_guard_cli import run

            return run(args)
        if args.command.startswith("native-action-live-"):
            from .native_action_live_cli import run

            return run(args)
        if args.command.startswith("native-action-coverage-"):
            from .native_action_coverage_cli import run

            return run(args)
        if args.command == "native-action-train":
            from .native_action_learning import train_action_model

            report = train_action_model(args.train_run, args.calibration_run, args.out)
            print(json.dumps(report, indent=2))
            return
        if args.command.startswith("native-dense-"):
            from .native_dense_cli import run

            return run(args)
        if args.command.startswith("native-repair5-"):
            from .native_repair5_cli import run

            return run(args)
        if args.command.startswith("native-repair4-"):
            from .native_repair4_cli import run

            run(args)
            return
        elif args.command.startswith("native-repair3-"):
            from .native_repair3_cli import run

            return run(args)
        if args.command == "native-repair-plan":
            from .native_repair_study import plan_repair_study

            p = plan_repair_study(
                args.source_model,
                args.video_source,
                args.out,
                stage=args.stage,
                model=args.model,
                families=args.families,
                groups_per_family=args.groups_per_family,
                repetitions=args.repetitions,
                seed=args.seed,
                results_directory=args.results_dir,
                repeatability_run=args.repeatability_run,
                validation_run=args.validation_run,
            )
            print(
                json.dumps(
                    dict(config=str(args.out), role=p["stage"], groups=len(p["groups"]), SOTA_achieved=False),
                    indent=2,
                )
            )
            return
        if args.command == "native-repair-study":
            from .native_repair_study import run_repair_study

            print(json.dumps(run_repair_study(args.config, args.out, resume=args.resume), indent=2))
            return
        if args.command == "native-repair-audit":
            from .native_repair_study import audit_repair_study

            print(json.dumps(audit_repair_study(args.run), indent=2))
            return
        if args.command == "native-repair-calibrate":
            from .native_repair_calibration import recalibrate_repair_study

            print(json.dumps(recalibrate_repair_study(args.run, args.out), indent=2))
            return
        if args.command == "native-repair-train":
            from .native_repair_learning import train_repair_model

            print(json.dumps(train_repair_model(args.train_run, args.calibration_run, args.out), indent=2))
            return
        if args.command == "native-plan":
            from .native_study import plan_native_study

            protocol = plan_native_study(
                args.model,
                args.out,
                stage=args.stage,
                candidate=args.candidate,
                repetitions=args.repetitions,
                groups_per_family=args.groups_per_family,
                seed=args.seed,
                exclude_runs=args.exclude_run,
                repeatability_run=args.repeatability_run,
                validation_run=args.validation_run,
                results_directory=args.results_dir,
                families=args.families,
                video_source=args.video_source,
            )
            print(
                json.dumps(
                    dict(
                        config=str(args.out),
                        role=protocol["stage"],
                        groups=len(protocol["groups"]),
                        SOTA_achieved=False,
                    ),
                    indent=2,
                )
            )
            return
        if args.command == "native-video-source":
            from .native_video import import_video_source

            print(
                json.dumps(
                    import_video_source(
                        args.video, args.out, args.attribution, args.license_url, args.source_url
                    ),
                    indent=2,
                )
            )
            return
        if args.command == "native-study":
            from .native_study import run_native_study

            print(json.dumps(run_native_study(args.config, args.out, resume=args.resume), indent=2))
            return
        if args.command == "native-audit":
            from .native_study import audit_native_study

            print(json.dumps(audit_native_study(args.run, replay=not args.hashes_only), indent=2))
            return
        if args.command == "native-calibrate":
            from .native_calibration import recalibrate_native_study

            print(json.dumps(recalibrate_native_study(args.run, args.out), indent=2))
            return
        if args.command == "status":
            print(json.dumps(run_status(args.run), indent=2))
            return
        if args.command == "export-paper":
            provenance = export_paper(args.run, args.out, prefix=args.macro_prefix)
            print(f"Exported {provenance['episodes']} audited episodes to {args.out}")
            return
        if args.command == "audit":
            data = json.loads((args.run / "manifest.json").read_text())
            failures = [
                name
                for name, expected in data["artifacts_sha256"].items()
                if not (args.run / name).exists() or sha256(args.run / name) != expected
            ]
            if failures:
                raise ValueError(f"Artifact hash mismatch: {failures}")
            print(f"Verified {len(data['artifacts_sha256'])} artifacts")
            return
        if args.command == "trace":
            if args.out.exists():
                raise FileExistsError(args.out)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            save_trace(make_trace(args.scenario, args.steps, args.seed), args.out)
            return
        if args.command == "report":
            build_report(args.run, plots=not args.no_plots)
            manifest(args.run, load_config(args.run / "config.json"), "complete")
            return
        if args.command == "tune-threshold":
            from .threshold_selection import run_threshold_selection

            result = run_threshold_selection(args.config, args.models, args.out, plots=not args.no_plots)
            print(f"Completed validation-selected gate experiment: {result}")
            return
        if args.command == "improve":
            from .improvement import run_improvement

            result = run_improvement(args.config, args.models, args.out, plots=not args.no_plots)
            print(f"Completed locked-selection follow-up: {result}")
            return
        if args.command == "policy-randomization":
            from .policy_randomization import run_policy_randomization

            result = run_policy_randomization(args.config, args.models, args.out, plots=not args.no_plots)
            print(f"Completed validation-locked policy-randomization study: {result}")
            return
        if args.command == "calibrate-actions":
            from .selected_calibration import recalibrate_screen_models

            result = recalibrate_screen_models(args.config, args.models, args.out)
            print(f"Completed selected-action calibration: {result}")
            return
        if args.command == "safety-shield":
            from .shield_selection import run_safety_shield

            result = run_safety_shield(
                args.config,
                args.models,
                args.out,
                plots=not args.no_plots,
                reference_models=args.reference_models,
            )
            print(f"Completed validation-locked action-shield study: {result}")
            return
        if args.command == "realism-study":
            from .realism_study import run_realism_study

            result = run_realism_study(args.config, args.out, plots=not args.no_plots)
            print(f"Completed matched packet-v2 training study: {result}")
            return
        if args.command == "delay-budget":
            from .delay_budget import run_delay_budget

            result = run_delay_budget(args.config, args.models, args.out, plots=not args.no_plots)
            print(f"Completed validation-locked delay-budget study: {result}")
            return
        if args.command == "budget-shield":
            from .budget_shield import run_budget_shield

            result = run_budget_shield(args.config, args.models, args.out, plots=not args.no_plots)
            print(f"Completed validation-locked budget-screen study: {result}")
            return
        if args.command == "uncertainty-shield":
            from .uncertainty_shield import resume_uncertainty_shield, run_uncertainty_shield

            runner = resume_uncertainty_shield if args.resume_from is not None else run_uncertainty_shield
            if args.resume_from is None:
                result = runner(args.config, args.models, args.out, plots=not args.no_plots)
            else:
                result = runner(
                    args.config,
                    args.models,
                    args.out,
                    args.resume_from,
                    plots=not args.no_plots,
                )
            print(f"Completed validation-locked uncertainty-screen study: {result}")
            return
        config = load_config(args.config)
        if args.command == "train":
            train_experiment(config, args.out)
        elif args.command == "run":
            run_experiment(config, args.out, plots=not args.no_plots)
        elif args.command == "evaluate":
            model_map = (
                None
                if args.model_map is None
                else {m: args.model_map.parent / p for m, p in json.loads(args.model_map.read_text()).items()}
            )
            gate_overrides = None if args.gate_map is None else json.loads(args.gate_map.read_text())
            evaluate_experiment(
                config,
                args.models,
                args.out,
                split=args.split,
                model_map=model_map,
                gate_overrides=gate_overrides,
            )
            build_report(args.out, plots=not args.no_plots)
            manifest(args.out, config, "complete")
        elif args.command == "sweep":
            if args.kind == "thresholds" and args.models is None:
                raise ValueError("threshold sweep requires --models")
            if args.out.exists():
                raise FileExistsError(args.out)
            args.out.mkdir(parents=True)
            if args.kind == "thresholds":
                for threshold in [0.5, 0.7, 0.85, 0.9, 0.95]:
                    variant = replace(
                        config,
                        name=f"threshold-{threshold}",
                        methods=["calibrated"],
                        gate=replace(
                            config.gate, threshold=threshold, release_margin=min(0.03, 1 - threshold)
                        ),
                    ).validate()
                    dest = args.out / f"threshold_{threshold}"
                    evaluate_experiment(variant, args.models, dest)
                    build_report(dest, plots=not args.no_plots)
                    manifest(dest, variant, "complete")
            else:
                variants = {
                    "no_fec": replace(config, simulator=replace(config.simulator, fec_levels=[0.0])),
                    "temperature": replace(config, gate=replace(config.gate, calibration="temperature")),
                }
                for name, variant in variants.items():
                    run_experiment(
                        replace(variant, name=name).validate(), args.out / name, plots=not args.no_plots
                    )
            build_sweep_report(args.out, plots=not args.no_plots)
            (args.out / "config.json").write_text(json.dumps(config.to_dict(), indent=2))
            (args.out / "README.md").write_text(
                "# Predeclared sensitivity sweep\nAll settings are reported; do not select thresholds using test results. Physical/action-space ablations retrain from scratch.\n"
            )
            manifest(args.out, config, "sweep_complete")
    except (ValueError, TypeError, FileNotFoundError, FileExistsError) as error:
        parser.exit(2, f"error: {error}\n")
