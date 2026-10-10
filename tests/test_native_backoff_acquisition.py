"""The undrawn-candidate manifest continues the seeded N1 order and clears nothing."""

import csv
import json

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


def test_b1_budget_is_the_owners_and_keeps_the_stop_rule(tmp_path):
    settings = acquisition.load_settings(acquisition.B1_SETTINGS)
    budget = settings["budget"]
    assert (
        budget["maximum_download_bytes"] == 10_000_000_000 and budget["maximum_file_bytes"] == 1_000_000_000
    )
    assert (
        settings["expand_discovery_automatically"] is False and settings["download_only_after_rights_review"]
    )
    assert settings["native_ready"] == {
        **acquisition.load_settings()["native_ready"],
        "note": settings["native_ready"]["note"],
    }
    assert settings["eligible_sources_per_tercile"]["required"] * 3 == 30  # B1's registered minimum
    for change in (dict(maximum_file_bytes=0), dict(maximum_file_bytes=11_000_000_000)):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(dict(settings, budget=dict(budget, **change))))
        with pytest.raises(ValueError, match="budget and stop rule"):
            acquisition.load_settings(path)
