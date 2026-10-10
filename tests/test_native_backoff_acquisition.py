"""The undrawn-candidate manifest continues the seeded N1 order and clears nothing."""

import csv

import pytest
from test_native_qualification_acquisition import inventory

from media_rl import native_actuator_qualification_panel as n1
from media_rl import native_backoff_acquisition as backoff
from media_rl import native_qualification_acquisition as acquisition
from media_rl.native_protocol import read_json, write_json


@pytest.fixture
def drawn(tmp_path):
    write_json(tmp_path / "inventory.json", inventory(50))
    seed = acquisition.load_settings()["queue"]["seed"]
    write_json(tmp_path / "queue.json", n1.acquisition_queue(tmp_path / "inventory.json", seed, 36))
    return tmp_path


def test_continuation_is_the_rest_of_the_seeded_order_and_never_repeats_a_candidate(drawn):
    queue = backoff.continuation(drawn / "inventory.json", drawn / "queue.json")
    first = read_json(drawn / "queue.json")
    full = n1.acquisition_queue(drawn / "inventory.json", first["seed"], 50)
    assert queue["drawn_by_n1"] == 36 and len(queue["queue"]) == 14
    assert [q["asset_id"] for q in queue["queue"]] == [q["asset_id"] for q in full["queue"][36:]]
    assert [q["position"] for q in queue["queue"]] == list(range(14))
    assert [q["seeded_position"] for q in queue["queue"]] == list(range(36, 50))
    assert not {q["asset_id"] for q in queue["queue"]} & {q["asset_id"] for q in first["queue"]}
    assert queue["media_downloaded"] is False and queue["rights_reviewed"] is False


def test_manifest_has_the_reviewers_columns_and_clears_nothing(drawn):
    summary = backoff.export(drawn / "inventory.json", drawn / "queue.json", drawn / "b1")
    assert summary["candidates"] == 14 and summary["rights_cleared_candidates"] == 0
    assert summary["media_downloaded"] is False and summary["catalogue_bytes"] == 1_400_000_000
    assert "not registered" in summary["phase_status"]
    manifest = read_json(drawn / "b1/rights-review/rights-review-manifest.json")
    assert all(r["rights_cleared"] is False and r["rights_review_decision"] == "" for r in manifest["rows"])
    with (drawn / "b1/rights-review/rights-review-manifest.csv").open(newline="") as stream:
        table = list(csv.DictReader(stream))
    assert len(table) == 14 and set(table[0]) == set(acquisition.COLUMNS)
    assert [r["queue_position"] for r in table] == [str(i) for i in range(14)]
    with pytest.raises(ValueError, match="fresh output directory"):
        backoff.export(drawn / "inventory.json", drawn / "queue.json", drawn / "b1")


def test_refuses_an_inventory_the_n1_queue_was_not_drawn_from(drawn):
    write_json(drawn / "other.json", inventory(60))
    with pytest.raises(ValueError, match="not the start of the seeded order"):
        backoff.continuation(drawn / "other.json", drawn / "queue.json")
    foreign = n1.acquisition_queue(drawn / "inventory.json", 5, 36)
    write_json(drawn / "foreign.json", dict(foreign, abi="something_else"))
    with pytest.raises(ValueError, match="registered N1 queue"):
        backoff.continuation(drawn / "inventory.json", drawn / "foreign.json")
