"""Explicit legal exact-cap augmentation; not a deployment or promotion API."""

import json


def run(args):
    from .native_action_coverage import audit_coverage, plan_coverage, run_coverage

    command = args.command.removeprefix("native-action-coverage-")
    if command == "plan":
        p = plan_coverage(args.parent, args.out, repetitions=args.repetitions, seed=args.seed)
        result = dict(
            config=str(args.out),
            role=p["stage"],
            groups=len(p["groups"]),
            peers=len(p["groups"]) * p["repetitions"] * 3,
            no_new_independent_groups=True,
            SOTA_achieved=False,
        )
    elif command == "study":
        result = run_coverage(args.config, args.out)
    elif command == "audit":
        result = audit_coverage(args.run)
    elif command == "fit":
        from .native_action_coverage_learning import train_coverage_model

        result = train_coverage_model(args.train_run, args.calibration_run, args.out)
    else:
        raise ValueError("coverage is not a deployment/promotion command")
    print(json.dumps(result, indent=2))
