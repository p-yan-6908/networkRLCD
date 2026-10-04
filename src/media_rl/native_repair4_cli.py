"""V4 public dispatch. Older commands and engines are unchanged."""

import json


def run(args):
    from .native_repair4_study import audit_repair_study, plan_repair_study, run_repair_study

    command = args.command.removeprefix("native-repair4-")
    if command == "plan":
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
        result = dict(config=str(args.out), role=p["stage"], groups=len(p["groups"]), SOTA_achieved=False)
    elif command == "study":
        result = run_repair_study(args.config, args.out, resume=args.resume)
    elif command == "audit":
        result = audit_repair_study(args.run)
    elif command == "calibrate":
        from .native_repair4_calibration import recalibrate_repair_study

        result = recalibrate_repair_study(args.run, args.out)
    elif command == "rebase":
        from .native_repair4_learning import rebase_repair_model

        result = rebase_repair_model(args.source_model, args.out)
    else:
        raise ValueError("unknown explicit repair4 command")
    print(json.dumps(result, indent=2))
