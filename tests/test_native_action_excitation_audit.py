"""Filename-only parent-audit projection; no data/recipe/raw-check waiver."""

from types import CodeType

import pytest

from media_rl import native_action_excitation as producer
from media_rl import native_action_excitation_audit as audit


def flatten(code):
    for item in code.co_consts:
        if isinstance(item, CodeType):
            yield from flatten(item)
        else:
            yield item


def test_only_one_snapshot_literal_changes_and_full_parent_bytecode_is_preserved():
    original = producer.audit_excitation
    before = list(flatten(original.__code__))
    after = list(flatten(audit.audit_excitation.__code__))
    assert audit.audit_excitation.__code__.co_code == original.__code__.co_code
    assert sum(x == audit.OLD for x in before) == 1
    assert after == [audit.NEW if x == audit.OLD else x for x in before]
    assert audit.audit_excitation.__globals__ is not original.__globals__
    assert (
        audit.audit_excitation.__globals__["audit_coverage_episode"]
        is original.__globals__["audit_coverage_episode"]
    )
    assert audit.audit_excitation.__globals__["_report"] is original.__globals__["_report"]
    assert list(flatten(original.__code__)) == before


def test_projection_without_original_snapshot_anchor_fails_closed():
    def sample():
        return "wrong"

    with pytest.raises(ValueError):
        audit.project_parent_code(sample.__code__)


def test_projection_with_duplicate_snapshot_anchors_fails_closed():
    def sample():
        return "wrong"

    code = sample.__code__.replace(co_consts=(None, audit.OLD, audit.OLD))
    with pytest.raises(ValueError):
        audit.project_parent_code(code)
