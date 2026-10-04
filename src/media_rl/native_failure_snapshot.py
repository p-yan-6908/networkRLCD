"""Atomic relay/stat/raw snapshot before diagnostic I/O; frozen V1 code kept intact."""

import argparse
import json
from types import FunctionType

from . import native_failure_evidence as original
from .native_protocol import require

ABI = "native_atomic_pre_rejection_failure_diagnostic_v2"
ENTRY = "native_failure_snapshot_episode.mjs"
HELPER = original.HELPER
REPLACEMENTS = [
    *original.REPLACEMENTS[:2],
    (
        " if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');",
        " const diagnosticRawEventCount=events.length;\n const diagnosticRaw=gzipSync(events.map(e=>JSON.stringify(e)).join(String.fromCharCode(10))+String.fromCharCode(10));\n await retainNativeResult(root,result,links.some(l=>l.unexpected),diagnosticRawEventCount);\n if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');",
    ),
    ("result.raw_event_count=events.length;", "result.raw_event_count=diagnosticRawEventCount;"),
    (
        "const raw=gzipSync(events.map(e=>JSON.stringify(e)).join(String.fromCharCode(10))+String.fromCharCode(10));",
        "const raw=diagnosticRaw;",
    ),
]
_old = "assets/" + original.ENTRY
_new = "assets/" + ENTRY
require(original.RAW_PEER.__code__.co_consts.count(_old) == 1, "single atomic diagnostic source key required")
_code = original.RAW_PEER.__code__.replace(
    co_consts=tuple(_new if x == _old else x for x in original.RAW_PEER.__code__.co_consts)
)
RAW_PEER = FunctionType(_code, original.RAW_PEER.__globals__, "audit_atomic_native_diagnostic")
_NS = {
    **original.__dict__,
    "__file__": __file__,
    "ABI": ABI,
    "ENTRY": ENTRY,
    "REPLACEMENTS": REPLACEMENTS,
    "RAW_PEER": RAW_PEER,
}
for _name in (
    "project_collector",
    "_runtime",
    "validate_plan",
    "plan_diagnostic",
    "_report",
    "run_diagnostic",
    "audit_diagnostic",
):
    _f = getattr(original, _name)
    _NS[_name] = FunctionType(_f.__code__, _NS, _name, _f.__defaults__)
project_collector = _NS["project_collector"]
validate_plan = _NS["validate_plan"]
plan_diagnostic = _NS["plan_diagnostic"]
run_diagnostic = _NS["run_diagnostic"]
audit_diagnostic = _NS["audit_diagnostic"]


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_failure_snapshot")
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--parent", required=True)
    plan.add_argument("--proof", required=True)
    plan.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "plan":
        c = plan_diagnostic(a.parent, a.proof, a.out)
        r = dict(abi=ABI, role=c["role"], planned_native_peers=1, models_fitted=0, SOTA_achieved=False)
    elif a.command == "run":
        r = run_diagnostic(a.config, a.out)
    else:
        r = audit_diagnostic(a.run)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
