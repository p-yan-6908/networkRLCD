"""Local guard-repeatability experiment only; no training/calibration/promotion."""

import json


def run(args):
    from .native_action_guard_study import audit_guard_study, plan_guard_study, run_guard_study

    command = args.command.removeprefix("native-action-guard-")
    if command == "plan":
        p = plan_guard_study(
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
            config=str(args.out),
            role=p["stage"],
            groups=len(p["groups"]),
            conditions=len(p["conditions"]),
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    elif command == "study":
        result = run_guard_study(args.config, args.out)
    elif command == "audit":
        result = audit_guard_study(args.run)
    else:
        raise ValueError("guard experiment cannot train/calibrate/qualify/promote")
    print(json.dumps(result, indent=2))
