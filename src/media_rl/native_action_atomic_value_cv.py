"""Same fixed once-only neural comparison; fresh atomic source + lossless IDs only."""

import argparse
import json
from types import FunctionType, SimpleNamespace

from . import native_action_balanced_value_cv as base
from . import native_action_balanced_value_cv_v3 as identity
from .native_protocol import require

ABI = "native_atomic_combined_train_value_cv_v4"
CONTRACT = base.CONTRACT
RECIPE = base.RECIPE
MODEL_ABI = base.MODEL_ABI
FIT = base.FIT
PREDICT = base.PREDICT


def _redirect(fn):
    old = "native_action_balanced_matrix"
    new = "native_action_atomic_matrix"
    c = fn.__code__
    require(
        c.co_names.count(old) == 1 and c.co_consts.count((old,)) == 1,
        "sole named source import/fromlist required",
    )
    return c.replace(
        co_names=tuple(new if x == old else x for x in c.co_names),
        co_consts=tuple((new,) if x == (old,) else x for x in c.co_consts),
    )


RAW_LOAD = FunctionType(_redirect(base._load), base.__dict__, "load_atomic_source", base._load.__defaults__)
_ORIGINAL = SimpleNamespace(**{**base.__dict__, "_load": RAW_LOAD})
_ID_NS = {**identity.__dict__, "__file__": __file__, "ABI": ABI, "original": _ORIGINAL}
LOAD = FunctionType(
    identity.load_lossless.__code__, _ID_NS, "load_atomic_lossless", identity.load_lossless.__defaults__
)
REPORT = FunctionType(identity._report.__code__, _ID_NS, "atomic_train_report")
_NS = {**base.__dict__, "__file__": __file__, "ABI": ABI, "_load": LOAD, "_report": REPORT}
fit_cv = FunctionType(base.fit_cv.__code__, _NS, "fit_atomic_train", base.fit_cv.__defaults__)
audit_cv = FunctionType(_redirect(base.audit_cv), _NS, "audit_atomic_train_cv", base.audit_cv.__defaults__)


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_atomic_value_cv")
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
