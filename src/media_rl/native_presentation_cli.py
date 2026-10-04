"""Wire-only local instrumentation; never fitting/calibration/promotion."""

import json


def run(args):
    from .native_presentation_study import (
        audit_presentation_study,
        plan_presentation_study,
        run_presentation_study,
    )

    command = args.command.removeprefix("native-presentation-")
    if command == "plan":
        p = plan_presentation_study(
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
            presentation_fields_used_for_actuation=False,
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    elif command == "study":
        result = run_presentation_study(args.config, args.out)
    elif command == "audit":
        result = audit_presentation_study(args.run)
    else:
        raise ValueError("instrumentation cannot fit/calibrate/validate/test/promote")
    print(json.dumps(result, indent=2))
