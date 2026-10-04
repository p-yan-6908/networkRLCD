"""Lossless episode metadata only; reuse immutable V2 inputs/fit/evaluation bytecode."""

import argparse
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_balanced_value_cv as original
from .native_protocol import digest, read_json, require

ABI = "native_balanced_combined_late_value_identity_cv_v3"
CONTRACT = original.CONTRACT
RECIPE = original.RECIPE
MODEL_ABI = original.MODEL_ABI
FIT = original.FIT
PREDICT = original.PREDICT


def repair_episode_metadata(data, old_episode, new_ids):
    require(
        len(data["episode"]) == len(old_episode) + len(new_ids)
        and np.array_equal(data["episode"][: len(old_episode)], old_episode),
        "original canonical rows/metadata prefix changed",
    )
    result = {**data, "episode": np.concatenate([old_episode, np.asarray(new_ids, dtype=str)])}
    require(
        result["episode"][len(old_episode) :].tolist() == list(new_ids),
        "full canonical episode identities truncated",
    )
    require(
        all(np.array_equal(v, result[k]) for k, v in data.items() if k != "episode"),
        "identity-only adapter changed numeric input or split metadata",
    )
    return result


def load_lossless(source, full_native=True):
    data, cfg = original._load(source, full_native)
    old_root, old = original.frozen.training_source(cfg["old_train"]["path"])
    del old_root
    new_ids = []
    for film, p in cfg["runtimes"].items():
        for t in p["episodes"]:
            if t["condition"] == "fixed450":
                continue
            cohorts = read_json(Path(source) / film / t["id"] / "derived.json")["late_credit"]["cohorts"]
            new_ids.extend([digest(Path(source) / "manifest.json") + ":" + t["id"]] * len(cohorts))
    require(
        len(new_ids) == 120 and len(set(new_ids)) == 24,
        "every actual randomized alias/physical peer identity required",
    )
    return repair_episode_metadata(data, old["episode"], new_ids), cfg


def _report(data, cfg, evaluation, source):
    report = original._report(data, cfg, evaluation, source)
    report.update(
        abi=ABI,
        implementation_sha256=digest(__file__),
        metadata_only_adapter=dict(
            abi=ABI,
            original_predeclared_cv_implementation_sha256=digest(original.__file__),
            original_contract_unmodified=True,
            only_changed_cache_field="episode",
            all_numeric_state_target_weight_cap_and_group_split_arrays_identical=True,
            actual_combined_unique_episode_ids=int(len(set(data["episode"].tolist()))),
            episode_dtype=str(data["episode"].dtype),
            model_fit_predict_evaluation_code_unmodified=True,
        ),
    )
    return report


_NS = {**original.__dict__, "__file__": __file__, "ABI": ABI, "_load": load_lossless, "_report": _report}
fit_cv = FunctionType(original.fit_cv.__code__, _NS, "fit_lossless_balanced", original.fit_cv.__defaults__)
audit_cv = FunctionType(
    original.audit_cv.__code__, _NS, "audit_lossless_balanced", original.audit_cv.__defaults__
)


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_balanced_value_cv_v3")
    sub = p.add_subparsers(dest="command", required=True)
    fit = sub.add_parser("fit")
    fit.add_argument("--source", required=True)
    fit.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "fit":
        r = fit_cv(a.source, a.out)
        result = dict(
            rows=r["rows"],
            requests=r["requests"],
            metadata_only_adapter=r["metadata_only_adapter"],
            evaluation=r["evaluation"],
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    else:
        result = audit_cv(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
