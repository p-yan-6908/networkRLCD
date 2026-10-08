"""Acquisition records for Native Phase N1: the rights-review manifest and the budget.

Kept outside the hash-frozen N1 registration and implementation. It reads the discovery
inventory and the seeded N1 queue and writes what a human reviewer needs. It downloads
nothing, probes nothing and never marks a source rights-cleared: every review field starts
empty and is the reviewer's to fill.
"""

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import quote

from . import native_actuator_qualification_panel as n1
from .native_protocol import digest, read_json, require, write_json

ABI = "native_actuator_qualification_n1_rights_review_manifest"
ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "configs/native_actuator_qualification_n1_acquisition.json"
DECISIONS = ("", "pass", "fail", "needs_media_inspection")
# Filled by the reviewer. The last five are what the unchanged ingest request then needs.
REVIEW = (
    "rights_review_decision",
    "rights_reviewer",
    "rights_reviewed_at_utc",
    "rights_review_notes",
    "attribution",
    "binding_quote",
    "capture_group",
    "independence_basis",
)
COLUMNS = (
    "queue_position",
    "candidate_id",
    "title",
    "creator",
    "uploader",
    "source_url",
    "media_url",
    "media_format",
    "resolution",
    "duration_seconds",
    "catalogue_bytes",
    "declared_license",
    "license_url",
    "rights_evidence_url",
    "rights_evidence_revision_url",
    "rights_evidence_snapshot",
    "rights_evidence_snapshot_sha256",
    "proposed_source_cluster",
    "proposed_title_cluster",
    "proposed_capture_cluster",
    "cluster_tokens",
    "external_source_urls",
    "original_source_credit",
    "declared_restrictions",
    "component_rights_review_required",
    "discovery_provenance_status",
    "discovery_metadata_screen_passed",
    "still_blocking",
    "rights_cleared",
    *REVIEW,
)


def load_settings(path=SETTINGS):
    settings = read_json(path)
    budget = settings["budget"]
    require(
        settings["abi"] == "native_actuator_qualification_n1_acquisition"
        and 0 < budget["maximum_download_bytes"] <= budget["maximum_temporary_storage_bytes"]
        and budget["retain_unnecessary_transcode_variants"] is False
        and settings["expand_discovery_automatically"] is False
        and 0
        < settings["eligible_sources_per_tercile"]["required"]
        <= settings["eligible_sources_per_tercile"]["preferred"],
        "N1 acquisition settings must keep their budget and stop rule",
    )
    return settings


def manifest_row(entry, record):
    """One candidate as discovery recorded it, with every review field empty."""
    chosen = [r for r in record["representations"] if r.get("selected")] or record["representations"]
    require(
        len(chosen) >= 1 and record["license_evidence"], "candidate needs a media file and archived evidence"
    )
    media, evidence = chosen[0], record["license_evidence"][0]
    page = "https://commons.wikimedia.org/w/index.php?title=" + quote(record["file_title"].replace(" ", "_"))
    row = dict(
        queue_position=entry["position"],
        candidate_id=record["asset_id"],
        title=record["source_title"],
        creator=record["creator"],
        uploader=record["uploader"],
        source_url=record["source_uri"],
        media_url=media["uri"],
        media_format=media.get("format"),
        resolution=media.get("resolution"),
        duration_seconds=record["duration_seconds"],
        catalogue_bytes=media.get("approximate_bytes"),
        declared_license=record["license_type"],
        license_url=record["license_url"],
        rights_evidence_url=evidence["url"],
        rights_evidence_revision_url=f"{page}&oldid={record['revision_id']}",
        rights_evidence_snapshot=evidence.get("path"),
        rights_evidence_snapshot_sha256=evidence.get("sha256"),
        proposed_source_cluster=record["source_cluster_id"],
        proposed_title_cluster=record["title_id"],
        proposed_capture_cluster=record["capture_cluster_id"],
        cluster_tokens=record["cluster_tokens"],
        external_source_urls=record["source_urls"],
        original_source_credit=record["original_source_credit_html"],
        declared_restrictions=record["declared_restrictions"],
        component_rights_review_required=record["component_rights_review_required"],
        discovery_provenance_status=record["provenance_status"],
        # A metadata screen by the discovery crawl. It is context for the reviewer, not a clearance.
        discovery_metadata_screen_passed=record["rights_cleared"],
        still_blocking=record["blocking_reasons"],
        rights_cleared=False,
    )
    row.update(dict.fromkeys(REVIEW, ""))
    return row


def rights_manifest(inventory_path, queue_path, settings):
    queue = read_json(queue_path)
    require(
        queue["abi"] == n1.ABI + "_acquisition_queue"
        and queue["seed"] == settings["queue"]["seed"]
        and len(queue["queue"]) == settings["queue"]["candidates"],
        "the registered seeded N1 queue is the only one reviewed",
    )
    records = {r["asset_id"]: r for r in read_json(inventory_path)["records"]}
    rows = [manifest_row(entry, records[entry["asset_id"]]) for entry in queue["queue"]]
    require(
        len({r["proposed_source_cluster"] for r in rows}) == len(rows),
        "one candidate per proposed source cluster",
    )
    known = [r["catalogue_bytes"] for r in rows if r["catalogue_bytes"] is not None]
    total = sum(known)
    return dict(
        abi=ABI,
        n1_freeze_sha256=n1.verify_freeze()["sha256"],
        inventory_sha256=digest(inventory_path),
        queue_sha256=digest(queue_path),
        candidates=len(rows),
        catalogue_bytes=total,
        candidates_without_catalogue_size=len(rows) - len(known),
        budget=settings["budget"],
        within_download_budget_if_all_were_fetched=bool(
            total <= settings["budget"]["maximum_download_bytes"]
        ),
        eligible_sources_per_tercile=settings["eligible_sources_per_tercile"],
        expand_discovery_automatically=False,
        rights_cleared_candidates=0,
        media_downloaded=False,
        review_decisions_allowed=list(DECISIONS[1:]),
        review_is_the_importers=True,
        rows=rows,
    )


def export(inventory_path, queue_path, out, settings_path=SETTINGS):
    """Write the manifest as JSON and as a CSV a reviewer can fill in. Refuses to overwrite."""
    manifest = rights_manifest(inventory_path, queue_path, load_settings(settings_path))
    out = Path(out)
    require(not out.exists(), "fresh rights-review directory required")
    out.mkdir(parents=True)
    write_json(out / "rights-review-manifest.json", manifest)
    with (out / "rights-review-manifest.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for row in manifest["rows"]:
            flat = {k: " | ".join(map(str, v)) if isinstance(v, list) else v for k, v in row.items()}
            writer.writerow({k: "" if flat[k] is None else flat[k] for k in COLUMNS})
    return {k: v for k, v in manifest.items() if k != "rows"}


def reviewed(csv_path, manifest_path):
    """Read a filled-in review back. A candidate passes only on an explicit, complete reviewer entry."""
    manifest = {r["candidate_id"]: r for r in read_json(manifest_path)["rows"]}
    with Path(csv_path).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(
        {r["candidate_id"] for r in rows} == set(manifest),
        "review must cover exactly the manifest's candidates",
    )
    result = {}
    for row in rows:
        original = manifest[row["candidate_id"]]
        require(
            all(str(row[k]) == str(original[k]) for k in ("media_url", "declared_license", "source_url")),
            "review edits a field that discovery recorded",
        )
        decision = row["rights_review_decision"].strip()
        require(decision in DECISIONS, f"unknown review decision for {row['candidate_id']}")
        complete = all(row[k].strip() for k in REVIEW if k != "rights_review_notes")
        require(decision != "pass" or complete, f"a pass needs every review field for {row['candidate_id']}")
        result[row["candidate_id"]] = dict(
            decision=decision or "not_reviewed",
            may_download=decision in ("pass", "needs_media_inspection"),
            rights_cleared=decision == "pass",
            **{k: row[k].strip() for k in REVIEW},
        )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Native Phase N1 acquisition records; downloads nothing")
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser(
        "rights-manifest", help="Export the rights-review manifest for the seeded queue"
    )
    manifest.add_argument("--inventory", required=True, type=Path)
    manifest.add_argument("--queue", required=True, type=Path)
    manifest.add_argument("--out", required=True, type=Path)
    review = sub.add_parser("review-status", help="Summarise a filled-in review; changes nothing")
    review.add_argument("--review", required=True, type=Path)
    review.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "rights-manifest":
            result = export(args.inventory, args.queue, args.out)
        else:
            entries = reviewed(args.review, args.manifest)
            counts = {}
            for entry in entries.values():
                counts[entry["decision"]] = counts.get(entry["decision"], 0) + 1
            result = dict(decisions=counts, may_download=sum(e["may_download"] for e in entries.values()))
        print(json.dumps(result, indent=1, sort_keys=True))
    except (ValueError, FileExistsError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
