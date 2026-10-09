"""Acquisition records for Native Phase N1: the rights-review manifest and the budget.

Kept outside the hash-frozen N1 registration and implementation. It reads the discovery
inventory and the seeded N1 queue and writes what a human reviewer needs. It downloads
nothing, probes nothing and never marks a source rights-cleared: every review field starts
empty and is the reviewer's to fill.
"""

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse

from . import native_actuator_qualification_panel as n1
from .native_panel_assets import LICENSE_URLS, _text
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


def file_hashes(path):
    sha256, sha1 = hashlib.sha256(), hashlib.sha1()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            sha256.update(block)
            sha1.update(block)
    return sha256.hexdigest(), sha1.hexdigest()


def probe(path):
    fields = "format=duration,size:stream=codec_type,codec_name,profile,width,height,r_frame_rate,pix_fmt"
    command = ["ffprobe", "-v", "error", "-show_entries", fields, "-of", "json", str(path)]
    data = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=120).stdout)
    video = [s for s in data["streams"] if s.get("codec_type") == "video"]
    audio = [s for s in data["streams"] if s.get("codec_type") == "audio"]
    require(video, "no video stream")
    return dict(
        duration_seconds=float(data["format"]["duration"]),
        bytes=int(data["format"]["size"]),
        video_codec=video[0].get("codec_name"),
        profile=video[0].get("profile"),
        width=video[0].get("width"),
        height=video[0].get("height"),
        frame_rate=video[0].get("r_frame_rate"),
        pixel_format=video[0].get("pix_fmt"),
        video_streams=len(video),
        audio_streams=len(audio),
        audio_codecs=[s.get("codec_name") for s in audio],
    )


def conversion_command(source, target, spec):
    """One video-only H.264 file, never larger than the registered box, aspect and frame rate unchanged."""
    scale = f"scale=w='min({spec['maximum_width']},iw)':h='min({spec['maximum_height']},ih)'"
    scale += ":force_original_aspect_ratio=decrease:force_divisible_by=2"
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source)]
    command += ["-map", "0:v:0", "-an", "-sn", "-dn", "-map_metadata", "-1", "-vf", scale]
    command += ["-c:v", spec["codec"], "-preset", spec["preset"], "-crf", str(spec["crf"])]
    command += ["-profile:v", spec["profile"], "-pix_fmt", spec["pixel_format"], "-movflags", "+faststart"]
    return [*command, str(target)]


def download(url, target, user_agent, limit):
    part = Path(str(target) + ".part")
    command = [
        "curl",
        "--fail",
        "--location",
        "--silent",
        "--show-error",
        "--retry",
        "3",
        "--retry-delay",
        "5",
    ]
    command += ["--max-filesize", str(int(limit)), "--user-agent", user_agent, "--output", str(part), url]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=3600)
    part.rename(target)
    return target.stat().st_size


def stored_bytes(root):
    return sum(f.stat().st_size for f in Path(root).rglob("*") if f.is_file())


def lineage(out, settings):
    """Everything fetched so far: original hash, derived hash, how one became the other, and the budget."""
    records = sorted(
        (read_json(p) for p in (Path(out) / "records").glob("*.json")), key=lambda r: r["queue_position"]
    )
    ready = [
        r
        for r in records
        if r["native_ready"]
        and r["native_ready"]["video_codec"] == "h264"
        and r["native_ready"]["duration_seconds"] >= 80
    ]
    return dict(
        abi="native_actuator_qualification_n1_acquisition_lineage",
        fetched_candidates=len(records),
        downloaded_bytes=sum(r["original"]["bytes"] for r in records),
        stored_bytes=stored_bytes(out),
        budget=settings["budget"],
        native_ready_format_candidates=len(ready),
        undecodable_originals=[r["candidate_id"] for r in records if r["native_ready"] is None],
        reviewed_as_pass_at_fetch=sum(r["reviewed_as_pass_at_fetch"] for r in records),
        native_ready_conversion=settings["native_ready"],
        outcome_data_collected=False,
        records=records,
    )


def fetch(review_path, manifest_path, inventory_path, out, settings_path=SETTINGS, limit=None):
    """Download reviewed candidates, verify identity, derive the native-ready file, record lineage.

    Only candidates the review marks ``pass`` or ``needs_media_inspection`` are touched. Each
    download is checked against the SHA-1 that Commons reported for the reviewed revision. The
    H.264 file is a derived verification artifact whose record carries the original's SHA-256
    as parent. Fetching stops at the download or storage budget and never widens the queue.
    It clears no rights and collects no outcome.
    """
    settings = load_settings(settings_path)
    budget, spec = settings["budget"], settings["native_ready"]
    decisions = reviewed(review_path, manifest_path)
    reported = {r["asset_id"]: r.get("reported_media_sha1") for r in read_json(inventory_path)["records"]}
    out = Path(out)
    for name in ("original", "native", "inspection", "records"):
        (out / name).mkdir(parents=True, exist_ok=True)
    version = subprocess.run(
        ["ffmpeg", "-version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    done = 0
    for row in read_json(manifest_path)["rows"]:
        identifier = row["candidate_id"]
        record_path = out / "records" / f"{identifier}.json"
        if not decisions[identifier]["may_download"] or record_path.exists():
            continue
        if limit is not None and done >= limit:
            break
        spent = sum(read_json(p)["original"]["bytes"] for p in (out / "records").glob("*.json"))
        require(
            spent + row["catalogue_bytes"] <= budget["maximum_download_bytes"],
            "download budget reached; stopping",
        )
        require(
            stored_bytes(out) + 2 * row["catalogue_bytes"] <= budget["maximum_temporary_storage_bytes"],
            "temporary storage budget reached; stopping",
        )
        original = out / "original" / (identifier + (Path(urlparse(row["media_url"]).path).suffix or ".bin"))
        if not original.exists():
            download(row["media_url"], original, settings["user_agent"], row["catalogue_bytes"] * 1.05 + 1e6)
        sha256, sha1 = file_hashes(original)
        require(
            sha1 == reported[identifier], f"{identifier}: downloaded bytes differ from the reviewed revision"
        )
        native = out / "native" / f"{identifier}.mp4"
        native.unlink(missing_ok=True)  # a half-written conversion is never kept as a variant
        command = conversion_command(original, native, spec)
        record = dict(
            candidate_id=identifier,
            queue_position=row["queue_position"],
            source_url=row["source_url"],
            media_url=row["media_url"],
            review_decision_at_fetch=decisions[identifier]["decision"],
            reviewed_as_pass_at_fetch=decisions[identifier]["rights_cleared"],
            original=dict(
                file=str(original.relative_to(out)),
                sha256=sha256,
                sha1=sha1,
                sha1_matches_reviewed_revision=True,
            ),
        )
        done += 1
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=7200)
            record["original"].update(probe(original))
        except subprocess.CalledProcessError as error:
            # An original that cannot be decoded is recorded as such and never becomes native-ready.
            native.unlink(missing_ok=True)
            record["original"].update(bytes=original.stat().st_size, unreadable=True)
            record.update(
                native_ready=None,
                conversion_failed=(error.stderr or "").strip()[-300:],
                inspection_sheet=None,
            )
            write_json(record_path, record)
            continue
        derived = probe(native)
        sheet = out / "inspection" / f"{identifier}.jpg"
        frames = f"fps=30/{max(derived['duration_seconds'], 1):.3f},scale=240:-2,tile=6x5"
        grid = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(native)]
        subprocess.run(
            [*grid, "-vf", frames, "-frames:v", "1", "-q:v", "4", str(sheet)], check=True, timeout=1800
        )
        record.update(
            native_ready=dict(
                file=str(native.relative_to(out)),
                sha256=file_hashes(native)[0],
                parent_sha256=sha256,
                derived_verification_artifact=True,
                ffmpeg=version,
                arguments=command[command.index("-map") : -1],
                **derived,
            ),
            inspection_sheet=str(sheet.relative_to(out)),
        )
        write_json(record_path, record)
    return lineage(out, settings)


def evidence_extract(row, review, discovery_root):
    """What the archived evidence says about one candidate, and which exact strings it contains.

    The unchanged ingest accepts a binding quote only if it occurs verbatim in the archived
    evidence file. This lists such strings. Choosing one and asserting the right is the
    reviewer's act; nothing here clears a source.
    """
    snapshot = Path(discovery_root) / row["rights_evidence_snapshot"]
    require(digest(snapshot) == row["rights_evidence_snapshot_sha256"], "archived rights evidence changed")
    raw = snapshot.read_text()
    number = int(row["candidate_id"].rsplit("-", 1)[1])
    page = next(p for p in json.loads(raw)["query"]["pages"] if p["pageid"] == number)
    lines = [
        line.strip() for line in page["revisions"][0]["slots"]["main"]["content"].splitlines() if line.strip()
    ]
    metadata = page["videoinfo"][0].get("extmetadata", {})
    wanted = ("LicenseShortName", "UsageTerms", "LicenseUrl", "Artist", "Credit", "AttributionRequired")
    values = {k: metadata[k]["value"] for k in (*wanted, "Restrictions", "Copyrighted") if k in metadata}
    templates = [
        x for x in lines if "{{" in x and re.search(r"cc-|cc0|cc zero|self\||pd-|licen[cs]e", x, re.I)
    ]
    fields = [x for x in lines if re.match(r"\|\s*(source|author|permission|date)\s*=", x, re.I)]
    quotes = [
        q for q in (*templates, values.get("LicenseShortName"), values.get("UsageTerms")) if q and q in raw
    ]
    quote = review["binding_quote"]
    return dict(
        candidate_id=row["candidate_id"],
        revision_id=page["revisions"][0]["revid"],
        review_decision=review["decision"],
        title_in_evidence=_text(row["title"]) in _text(raw),
        reviewer_binding_quote_in_evidence=bool(quote) and quote in raw,
        licence_templates=templates,
        information_fields=fields,
        extmetadata=values,
        verbatim_quote_candidates=list(dict.fromkeys(quotes)),
    )


def evidence_report(review_path, manifest_path, discovery_root):
    decisions = reviewed(review_path, manifest_path)
    extracts = [
        evidence_extract(row, decisions[row["candidate_id"]], discovery_root)
        for row in read_json(manifest_path)["rows"]
    ]
    passed = [e for e in extracts if e["review_decision"] == "pass"]
    return dict(
        abi="native_actuator_qualification_n1_rights_evidence_extracts",
        reviewers=sorted({d["rights_reviewer"] for d in decisions.values()}),
        passes=len(passed),
        passes_whose_binding_quote_is_in_the_archived_evidence=sum(
            e["reviewer_binding_quote_in_evidence"] for e in passed
        ),
        passes_the_unchanged_ingest_would_accept_on_evidence=sum(
            e["reviewer_binding_quote_in_evidence"] and e["title_in_evidence"] for e in passed
        ),
        clears_nothing=True,
        extracts=extracts,
    )


def ingest_request(review_path, manifest_path, lineage_path, media_root, discovery_root, importer):
    """The request the unchanged ingest takes, for every reviewed pass that has a native-ready file.

    The importer flags are the importer's assertion. They are set here because the importer
    submitted this review as final for ingest; the review itself is by the reviewer of record,
    and both facts are written into each asset.
    """
    require(isinstance(importer, str) and importer.strip(), "name the importer who adopts the review")
    decisions = reviewed(review_path, manifest_path)
    rows = {r["candidate_id"]: r for r in read_json(manifest_path)["rows"]}
    records = {r["candidate_id"]: r for r in read_json(lineage_path)["records"]}
    with Path(review_path).open(newline="") as stream:
        reviewed_at = {r["candidate_id"]: r["rights_reviewed_at_utc"] for r in csv.DictReader(stream)}
    assets, skipped = [], []
    for identifier, decision in decisions.items():
        if not decision["rights_cleared"]:
            continue
        row, record = rows[identifier], records[identifier]
        if record["native_ready"] is None:
            skipped.append(identifier)  # reviewed as pass, but the original cannot be decoded
            continue
        media = (Path(media_root) / record["native_ready"]["file"]).resolve()
        require(digest(media) == record["native_ready"]["sha256"], f"{identifier}: native-ready file changed")
        snapshot = (Path(discovery_root) / row["rights_evidence_snapshot"]).resolve()
        require(
            digest(snapshot) == row["rights_evidence_snapshot_sha256"], "archived rights evidence changed"
        )
        assets.append(
            dict(
                path=str(media),
                sha256=record["native_ready"]["sha256"],
                parent_sha256=record["original"]["sha256"],
                source="Wikimedia Commons",
                source_title=row["title"],
                capture_group=decision["capture_group"],
                independence_basis=decision["independence_basis"],
                source_url=row["source_url"],
                license=row["declared_license"],
                license_url=LICENSE_URLS[row["declared_license"]],
                attribution=decision["attribution"],
                rights_asserted_by_importer=True,
                license_evidence=dict(
                    path=str(snapshot),
                    sha256=row["rights_evidence_snapshot_sha256"],
                    scope="this_asset",
                    source_title=row["title"],
                    license=row["declared_license"],
                    source_url=row["rights_evidence_revision_url"],
                    checked_at_utc=reviewed_at[identifier],
                    reviewed_by_importer=True,
                    binding_quote=decision["binding_quote"],
                ),
                candidate_id=identifier,
                rights_review_provenance=dict(
                    reviewer_of_record=decision["rights_reviewer"],
                    review_file_sha256=digest(review_path),
                    importer=importer.strip(),
                    importer_flags_basis="importer submitted this review as final for ingest",
                    native_ready_is_derived_from_parent_sha256=True,
                ),
            )
        )
    require(assets, "no reviewed pass has a native-ready file")
    return dict(abi="licensed_independent_panel_assets_v1_request", assets=assets), skipped


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
    evidence = sub.add_parser("evidence", help="Extract what the archived evidence says; clears nothing")
    get = sub.add_parser("fetch", help="Download reviewed candidates within budget and record lineage")
    for p in (evidence, get):
        p.add_argument("--review", required=True, type=Path)
        p.add_argument("--manifest", required=True, type=Path)
        p.add_argument("--out", required=True, type=Path)
    evidence.add_argument("--discovery", required=True, type=Path)
    get.add_argument("--inventory", required=True, type=Path)
    get.add_argument("--limit", type=int)
    request = sub.add_parser("ingest-request", help="Write the request the unchanged ingest takes")
    for name in ("review", "manifest", "lineage", "media", "discovery", "out"):
        request.add_argument("--" + name, required=True, type=Path)
    request.add_argument("--importer", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest-request":
            body, skipped = ingest_request(
                args.review, args.manifest, args.lineage, args.media, args.discovery, args.importer
            )
            write_json(args.out, body)
            result = dict(assets=len(body["assets"]), reviewed_pass_without_native_ready_file=skipped)
        elif args.command == "evidence":
            result = evidence_report(args.review, args.manifest, args.discovery)
            write_json(args.out, result)
            result = {k: v for k, v in result.items() if k != "extracts"}
        elif args.command == "fetch":
            result = fetch(args.review, args.manifest, args.inventory, args.out, limit=args.limit)
            result = {k: v for k, v in result.items() if k != "records"}
        elif args.command == "rights-manifest":
            result = export(args.inventory, args.queue, args.out)
        else:
            entries = reviewed(args.review, args.manifest)
            counts = {}
            for entry in entries.values():
                counts[entry["decision"]] = counts.get(entry["decision"], 0) + 1
            result = dict(decisions=counts, may_download=sum(e["may_download"] for e in entries.values()))
        print(json.dumps(result, indent=1, sort_keys=True))
    except (ValueError, FileExistsError, FileNotFoundError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
