"""Isolated public plan/study/audit entry point; no fitting or promotion commands."""

import argparse
import json


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_readback_guard_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="freeze fresh readback-vs-canonical native roles")
    for name in ("source-model", "action-model", "video-source", "out"):
        plan.add_argument("--" + name, required=True)
    plan.add_argument("--families", nargs="+", default=["stable", "collapse"])
    plan.add_argument("--groups-per-family", type=int, default=1)
    plan.add_argument("--repetitions", type=int, default=2)
    plan.add_argument("--seed", type=int, default=11101)
    plan.add_argument("--results-dir", default="results")
    study = commands.add_parser("study", help="collect only a complete frozen repeatability panel")
    study.add_argument("--config", required=True)
    study.add_argument("--out", required=True)
    audit = commands.add_parser("audit", help="read-only full raw wire/model/cap replay")
    audit.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    from .native_readback_guard_study import (
        audit_readback_guard_study,
        plan_readback_guard_study,
        run_readback_guard_study,
    )

    if args.command == "plan":
        p = plan_readback_guard_study(
            args.source_model,
            args.action_model,
            args.video_source,
            args.out,
            families=args.families,
            groups_per_family=args.groups_per_family,
            repetitions=args.repetitions,
            seed=args.seed,
            results_directory=args.results_dir,
        )
        result = dict(
            config=args.out,
            role=p["stage"],
            groups=len(p["groups"]),
            conditions=len(p["conditions"]),
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    elif args.command == "study":
        result = run_readback_guard_study(args.config, args.out)
    else:
        result = audit_readback_guard_study(args.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
