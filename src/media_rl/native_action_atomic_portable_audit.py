"""Read-only V5 portability view of immutable V4 artifacts; no capture or fitting."""

import argparse
import json
from pathlib import Path
from types import FunctionType, SimpleNamespace

from . import native_action_atomic_matrix as matrix
from . import native_action_atomic_value_cv as value
from . import native_action_balanced_value_cv as numeric
from . import native_action_balanced_value_cv_v3 as identity
from .native_protocol import require

ABI = matrix.ABI
ADAPTER_ABI = "native_atomic_read_only_portable_source_audit_v5"


def portable_dependencies(cfg, executing):
    expected = cfg["dependencies_sha256"]

    def names(entries):
        result = {Path(k).name: v for k, v in entries.items()}
        require(len(result) == len(entries), "unique source dependency file identities required")
        return result

    actual = names(executing)
    require(
        names(expected) == actual,
        "every exact executing collector/model/role/credit/diagnostic source SHA required",
    )
    # Paths identify the frozen original sources, not the relocation of the wheel.
    return {k: actual[Path(k).name] for k in expected}


def validate_plan(cfg):
    bound = portable_dependencies(cfg, matrix._dependencies(value))
    namespace = {**matrix.__dict__, "_dependencies": lambda unused: bound}
    fn = FunctionType(matrix.validate_plan.__code__, namespace, "validate_exact_portable_atomic_plan")
    return fn(cfg)


_MATRIX_NS = {**matrix.audit_matrix.__globals__, "validate_plan": validate_plan}
audit_matrix = FunctionType(matrix.audit_matrix.__code__, _MATRIX_NS, "audit_portable_atomic_source")


def _redirect(fn, old):
    c = fn.__code__
    new = "native_action_atomic_portable_audit"
    require(
        c.co_names.count(old) == 1 and c.co_consts.count((old,)) == 1,
        "unique read-only source import/fromlist required",
    )
    return c.replace(
        co_names=tuple(new if x == old else x for x in c.co_names),
        co_consts=tuple((new,) if x == (old,) else x for x in c.co_consts),
    )


_RAW_LOAD = FunctionType(
    _redirect(numeric._load, "native_action_balanced_matrix"),
    numeric.__dict__,
    "load_exact_portable_atomic_source",
    numeric._load.__defaults__,
)
_ORIGINAL = SimpleNamespace(**{**numeric.__dict__, "_load": _RAW_LOAD})
LOAD = FunctionType(
    identity.load_lossless.__code__,
    {**identity.__dict__, "original": _ORIGINAL},
    "load_portable_atomic_lossless",
    identity.load_lossless.__defaults__,
)
_CV_NS = {**value.audit_cv.__globals__, "_load": LOAD}
audit_cv = FunctionType(
    _redirect(value.audit_cv, "native_action_atomic_matrix"),
    _CV_NS,
    "audit_portable_atomic_cv",
    value.audit_cv.__defaults__,
)


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_atomic_portable_audit")
    p.add_argument("kind", choices=("source", "cv"))
    p.add_argument("--run", required=True)
    a = p.parse_args()
    print(json.dumps((audit_matrix if a.kind == "source" else audit_cv)(a.run), indent=2))


if __name__ == "__main__":
    main()
