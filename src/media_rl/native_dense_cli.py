"""Diagnostic-only dense scalar controls; no train/calibrate/promote command."""

import json


def run(args):
    from .native_dense_study import audit_dense_study, plan_dense_study, run_dense_study

    command = args.command.removeprefix("native-dense-")
    if command == "plan":
        p = plan_dense_study(
            args.source_model,
            args.video_source,
            args.out,
            families=args.families,
            groups_per_family=args.groups_per_family,
            repetitions=args.repetitions,
            seed=args.seed,
            results_directory=args.results_dir,
        )
        result = dict(config=str(args.out), role=p["stage"], groups=len(p["groups"]), SOTA_achieved=False)
    elif command == "study":
        result = run_dense_study(args.config, args.out)
    elif command == "audit":
        result = audit_dense_study(args.run)
    else:
        raise ValueError("dense mechanism probe is diagnostic only")
    print(json.dumps(result, indent=2))
