"""Read-only adapter for the frozen hold producer's parent-template literal.

The sealed captures retain the original coverage template whose exact projection
creates excitation_episode.mjs. The inherited parent verifier's lone dense
snapshot path was not renamed by the frozen producer. Fix that lookup in a copied
code/namespace, never rewrite the producer, saved captures or verification rules.
"""

import argparse
import copy
import json
from types import CodeType, FunctionType

from . import native_action_excitation as producer
from .native_protocol import require

OLD = "sources/templates/dense_episode.mjs"
NEW = "sources/templates/coverage_episode.mjs"


def project_parent_code(code):
    count = 0

    def visit(current):
        nonlocal count
        constants = []
        for value in current.co_consts:
            if isinstance(value, CodeType):
                value = visit(value)
            elif isinstance(value, str) and value == OLD:
                count += 1
                value = NEW
            constants.append(value)
        return current.replace(co_consts=tuple(constants))

    result = visit(code)
    require(count == 1 and result.co_code == code.co_code, "exact lone parent template-path adapter required")
    return result


_original = producer.audit_excitation
audit_excitation = FunctionType(
    project_parent_code(_original.__code__),
    dict(_original.__globals__),
    "audit_excitation_capture",
    _original.__defaults__,
    _original.__closure__,
)
audit_excitation.__kwdefaults__ = copy.deepcopy(_original.__kwdefaults__)


def main():
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_excitation_audit")
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_excitation(args.run), indent=2))


if __name__ == "__main__":
    main()
