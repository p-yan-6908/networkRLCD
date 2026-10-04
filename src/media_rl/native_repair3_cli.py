"""Explicit V3 CLI dispatch; existing V2 commands retain their original engines."""

import json


def run(args):
    from .native_repair3_study import audit_repair_study, plan_repair_study, run_repair_study

    command = args.command.removeprefix("native-repair3-")
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
    elif command == "train":
        from .native_repair3_learning import train_repair_model

        result = train_repair_model(args.train_run, args.calibration_run, args.out)
    elif command == "calibrate":
        from .native_repair3_calibration import recalibrate_repair_study

        result = recalibrate_repair_study(args.run, args.out)
    else:
        raise ValueError("unknown explicit repair3 command")
    print(json.dumps(result, indent=2))
