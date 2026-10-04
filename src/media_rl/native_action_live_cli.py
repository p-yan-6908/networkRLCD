"""Isolated live action-outcome experiments; no fit/calibrate/promote dispatch."""

import json


def run(args):
    from .native_action_live_study import audit_live_study, plan_live_study, run_live_study

    command = args.command.removeprefix("native-action-live-")
    if command == "plan":
        p = plan_live_study(
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
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    elif command == "study":
        result = run_live_study(args.config, args.out)
    elif command == "audit":
        result = audit_live_study(args.run)
    else:
        raise ValueError("live action-outcome probe cannot fit/calibrate/qualify/promote a model")
    print(json.dumps(result, indent=2))
