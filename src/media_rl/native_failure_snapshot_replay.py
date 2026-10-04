"""Atomic diagnostic read-only replay; repair legacy hardcoded cohort role metadata only."""

import argparse
import json
from types import FunctionType, SimpleNamespace

from . import native_failure_evidence_replay as replay_base
from . import native_failure_snapshot as snapshot
from .native_protocol import require

ABI = "native_atomic_failure_diagnostic_role_replay_v3"


def diagnostic_cohort_metadata(derived, role):
    require(role == "diagnostic", "diagnostic-only cohort role adapter required")
    result = {**derived}
    for field in ("late_credit", "early_reference"):
        credit = derived[field]
        cohorts = []
        for c in credit["cohorts"]:
            require(c["role"] == "train", "exact legacy hardcoded role metadata required")
            cohorts.append({**c, "role": "diagnostic", "original_hardcoded_collector_role": "train"})
        result[field] = {**credit, "cohorts": cohorts}
    result["diagnostic_role_metadata_adapter"] = dict(
        original_raw_measurement_code_unchanged=True,
        only_cohort_role_metadata_changed=True,
        never_eligible_for_training=True,
    )
    return result


def _raw_peer(child, p, t, bundles):
    row, derived = snapshot.RAW_PEER(child, p, t, bundles)
    return row, diagnostic_cohort_metadata(derived, t["role"])


_capture = SimpleNamespace(**{**snapshot._NS, "RAW_PEER": _raw_peer})
_NS = {**replay_base.__dict__, "__file__": __file__, "ABI": ABI, "capture": _capture}
for _name in ("inspect_source", "replay", "audit_replay"):
    _f = getattr(replay_base, _name)
    _NS[_name] = FunctionType(_f.__code__, _NS, _name, _f.__defaults__)
replay = _NS["replay"]
audit_replay = _NS["audit_replay"]


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_failure_snapshot_replay")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("replay")
    run.add_argument("--source", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "replay":
        r = replay(a.source, a.out)
    else:
        r = audit_replay(a.run)
    print(json.dumps({k: v for k, v in r.items() if k != "source"}, indent=2))


if __name__ == "__main__":
    main()
