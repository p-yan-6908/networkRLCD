"""Separate CLI; legacy media-rl and supervised controller source stay unchanged."""

import argparse
import json
from pathlib import Path

from .jevbwe_rlcd import load_config
from .jevbwe_rlcd_experiment import audit, evaluate, run, train


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Experimental numeric JevBWE-RLCD; optional Laya; no automatic promotion"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "train", "evaluate", "laya"):
        p = sub.add_parser(command)
        p.add_argument("--config", required=True, type=Path)
        p.add_argument("--out", required=True, type=Path)
        if command in ("run", "train"):
            p.add_argument("--baseline-model", required=True, type=Path)
        if command == "train":
            p.add_argument(
                "--data-run",
                type=Path,
                help="Known factual conditional propensities required; never retrofit legacy 1/6",
            )
        if command == "evaluate":
            p.add_argument("--model", required=True, type=Path)
        if command == "laya":
            p.add_argument("--training", required=True, type=Path)
            p.add_argument(
                "--model-dir",
                required=True,
                type=Path,
                help="Explicit local pretrained Laya checkpoint; no automatic download",
            )
            p.add_argument("--device", default="cpu")
    p = sub.add_parser("audit")
    p.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = audit(args.run)
        else:
            config = load_config(args.config)
            if args.command == "run":
                result = run(config, args.baseline_model, args.out)
            elif args.command == "train":
                result = train(config, args.baseline_model, args.out, data_run=args.data_run)
            elif args.command == "evaluate":
                report = evaluate(config, args.model, args.out)
                result = {k: report[k] for k in ("promotion_eligible", "panels", "optional_laya", "promoted")}
            else:
                from .jevbwe_laya import LocalLaya, prepare

                if args.out.exists():
                    raise FileExistsError(args.out)
                args.out.mkdir(parents=True)
                backend = LocalLaya(args.model_dir, config, device=args.device)
                model = prepare(config, args.training, backend, args.out / "calibration")
                report = evaluate(
                    config, args.training / "model.json", args.out / "evaluation", laya_model=model
                )
                result = {k: report[k] for k in ("promotion_eligible", "panels", "optional_laya", "promoted")}
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, TypeError, FileNotFoundError, FileExistsError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
