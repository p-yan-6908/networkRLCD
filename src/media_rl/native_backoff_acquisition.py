"""Rights-review manifest for the candidates the N1 queue did not draw (proposed Native Phase B1).

It reviews nothing, downloads nothing, probes nothing and never marks a source rights-cleared.
The order is the continuation of the registered seeded N1 order over the same discovery
inventory, so no candidate is hand-picked and none of N1's is offered again. The rows have the
columns of the N1 manifest, so a reviewer fills them in the same way.
"""

import argparse
import csv
import json
from pathlib import Path

from . import native_actuator_qualification_panel as n1
from . import native_qualification_acquisition as acquisition
from .native_protocol import digest, read_json, require, write_json

ABI = "native_phase_b1_rights_review_manifest"


def continuation(inventory_path, drawn_path):
    """Every candidate cluster after the N1 queue, in the same seeded order."""
    drawn = read_json(drawn_path)
    require(drawn["abi"] == n1.ABI + "_acquisition_queue", "the registered N1 queue is required")
    full = n1.acquisition_queue(inventory_path, drawn["seed"], drawn["candidate_clusters"])
    taken = len(drawn["queue"])
    require(
        full["candidate_clusters"] == drawn["candidate_clusters"]
        and [q["asset_id"] for q in full["queue"][:taken]] == [q["asset_id"] for q in drawn["queue"]],
        "the N1 queue is not the start of the seeded order over this inventory",
    )
    rest = [dict(q, position=i, seeded_position=q["position"]) for i, q in enumerate(full["queue"][taken:])]
    require(
        not {q["source_cluster_id"] for q in rest} & {q["source_cluster_id"] for q in drawn["queue"]},
        "a candidate cluster the N1 queue drew cannot be offered again",
    )
    return dict(
        abi="native_phase_b1_acquisition_queue",
        seed=drawn["seed"],
        candidate_clusters=full["candidate_clusters"],
        drawn_by_n1=taken,
        queue=rest,
        estimated_bytes=sum(q["estimated_bytes"] or 0 for q in rest),
        verified_eligible_sources=0,
        media_downloaded=False,
        rights_reviewed=False,
        purpose="every discovered candidate the N1 queue did not draw, in the registered seeded order",
    )


def rights_manifest(inventory_path, drawn_path):
    queue = continuation(inventory_path, drawn_path)
    records = {r["asset_id"]: r for r in read_json(inventory_path)["records"]}
    rows = [acquisition.manifest_row(entry, records[entry["asset_id"]]) for entry in queue["queue"]]
    require(
        len({r["proposed_source_cluster"] for r in rows}) == len(rows),
        "one candidate per proposed source cluster",
    )
    known = [r["catalogue_bytes"] for r in rows if r["catalogue_bytes"] is not None]
    manifest = dict(
        abi=ABI,
        phase_status="proposed, not registered; no budget is set and nothing may be downloaded",
        inventory_sha256=digest(inventory_path),
        n1_queue_sha256=digest(drawn_path),
        candidates=len(rows),
        catalogue_bytes=sum(known),
        largest_catalogue_bytes=max(known, default=0),
        candidates_without_catalogue_size=len(rows) - len(known),
        expand_discovery_automatically=False,
        rights_cleared_candidates=0,
        media_downloaded=False,
        review_decisions_allowed=list(acquisition.DECISIONS[1:]),
        review_is_the_importers=True,
        rows=rows,
    )
    return queue, manifest


def export(inventory_path, drawn_path, out):
    """Write the queue and the manifest as JSON and as a CSV a reviewer can fill in. Refuses to overwrite."""
    queue, manifest = rights_manifest(inventory_path, drawn_path)
    out = Path(out)
    require(not out.exists(), "fresh output directory required")
    (out / "rights-review").mkdir(parents=True)
    write_json(out / "queue.json", queue)
    write_json(out / "rights-review" / "rights-review-manifest.json", manifest)
    with (out / "rights-review" / "rights-review-manifest.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=acquisition.COLUMNS)
        writer.writeheader()
        for row in manifest["rows"]:
            flat = {k: " | ".join(map(str, v)) if isinstance(v, list) else v for k, v in row.items()}
            writer.writerow({k: "" if flat[k] is None else flat[k] for k in acquisition.COLUMNS})
    return {k: v for k, v in manifest.items() if k != "rows"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rights-review manifest for the undrawn candidates")
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--n1-queue", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = export(args.inventory, args.n1_queue, args.out)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
