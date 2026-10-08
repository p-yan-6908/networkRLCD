"""N1 acquisition records: the rights-review manifest never clears a source by itself."""

import csv
import json

import pytest

from media_rl import native_actuator_qualification_panel as n1
from media_rl import native_qualification_acquisition as acquisition
from media_rl.native_protocol import read_json, write_json


def inventory(count=40):
    records = []
    for i in range(count):
        records.append(
            dict(
                asset_id=f"commons-{i}",
                source_cluster_id=f"candidate-{i}",
                title_id=f"title{i}",
                capture_cluster_id=None,
                cluster_tokens=[f"title:title{i}", "unreviewed-creator:someone"],
                planning_candidate=True,
                previously_exposed_title=False,
                source_title=f"Title {i}",
                file_title=f"File:Title {i}.webm",
                creator="Someone",
                uploader="Someone",
                source_uri=f"https://commons.wikimedia.org/wiki/File:Title_{i}.webm",
                source_urls=[],
                original_source_credit_html="Own work",
                declared_restrictions="",
                component_rights_review_required=False,
                provenance_status="explicit_own_work_with_named_creator_and_revision",
                rights_cleared=True,  # the crawl's metadata screen, which is not a clearance
                license_type="CC-BY-4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                license_evidence=[
                    dict(url=f"https://example.invalid/api?{i}", path=f"evidence/{i}.txt", sha256="a" * 64)
                ],
                revision_id=1000 + i,
                duration_seconds=120.0,
                representations=[
                    dict(
                        uri=f"https://upload.example.invalid/{i}.webm",
                        format="video/webm",
                        resolution=[1920, 1080],
                        approximate_bytes=100_000_000,
                        selected=True,
                    )
                ],
                blocking_reasons=["native_media_probe_not_performed"],
            )
        )
    return dict(records=records)


@pytest.fixture
def exported(tmp_path, monkeypatch):
    monkeypatch.setattr(n1, "verify_freeze", lambda *a: dict(files=4, sha256="f" * 64, verified=True))
    write_json(tmp_path / "inventory.json", inventory())
    settings = acquisition.load_settings()
    write_json(
        tmp_path / "queue.json",
        n1.acquisition_queue(tmp_path / "inventory.json", settings["queue"]["seed"], 36),
    )
    summary = acquisition.export(tmp_path / "inventory.json", tmp_path / "queue.json", tmp_path / "review")
    return tmp_path, summary


def test_settings_record_the_budget_and_the_stop_rule():
    settings = acquisition.load_settings()
    assert settings["budget"]["maximum_download_bytes"] == 10_000_000_000
    assert settings["budget"]["maximum_temporary_storage_bytes"] == 30_000_000_000
    assert settings["budget"]["retain_unnecessary_transcode_variants"] is False
    assert (
        settings["expand_discovery_automatically"] is False
        and settings["download_only_after_rights_review"] is True
    )
    assert settings["eligible_sources_per_tercile"] == dict(required=4, preferred=8)
    assert settings["queue"]["seed"] == n1.qualification.load_registration(n1.REGISTRATION).capture.seed


def test_manifest_lists_what_a_reviewer_needs_and_clears_nothing(exported):
    root, summary = exported
    assert summary["candidates"] == 36 and summary["rights_cleared_candidates"] == 0
    assert summary["media_downloaded"] is False and summary["catalogue_bytes"] == 3_600_000_000
    assert summary["within_download_budget_if_all_were_fetched"] and summary["review_is_the_importers"]
    manifest = read_json(root / "review/rights-review-manifest.json")
    row = manifest["rows"][0]
    needed = ("candidate_id", "source_url", "media_url", "title", "creator", "proposed_source_cluster")
    needed += ("proposed_title_cluster", "proposed_capture_cluster", "duration_seconds", "catalogue_bytes")
    needed += ("declared_license", "license_url", "rights_evidence_url")
    assert all(key in row for key in needed)
    assert row["rights_evidence_revision_url"].endswith(
        f"&oldid={1000 + int(row['candidate_id'].split('-')[1])}"
    )
    assert all(r["rights_cleared"] is False and r["rights_review_decision"] == "" for r in manifest["rows"])
    assert all(
        r["discovery_metadata_screen_passed"] is True for r in manifest["rows"]
    )  # context, not clearance
    with (root / "review/rights-review-manifest.csv").open(newline="") as stream:
        table = list(csv.DictReader(stream))
    assert len(table) == 36 and set(table[0]) == set(acquisition.COLUMNS)
    assert all(r["rights_cleared"] == "False" for r in table)
    with pytest.raises(ValueError, match="fresh rights-review directory"):
        acquisition.export(root / "inventory.json", root / "queue.json", root / "review")
    other = n1.acquisition_queue(root / "inventory.json", 5, 36)
    write_json(root / "other-queue.json", other)
    with pytest.raises(ValueError, match="registered seeded N1 queue"):
        acquisition.export(root / "inventory.json", root / "other-queue.json", root / "other")


def test_only_an_explicit_complete_review_lets_a_candidate_through(exported):
    root, _ = exported
    manifest = root / "review/rights-review-manifest.json"
    with (root / "review/rights-review-manifest.csv").open(newline="") as stream:
        table = list(csv.DictReader(stream))

    def save(rows, name):
        with (root / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=acquisition.COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return root / name

    untouched = acquisition.reviewed(save(table, "blank.csv"), manifest)
    assert all(
        e["decision"] == "not_reviewed" and not e["may_download"] and not e["rights_cleared"]
        for e in untouched.values()
    )
    filled = dict(
        table[0],
        rights_review_decision="pass",
        rights_reviewer="owner",
        rights_reviewed_at_utc="2026-10-08T00:00:00Z",
    )
    filled.update(
        attribution="Someone, CC BY 4.0", binding_quote="licensed under CC BY 4.0", capture_group="capture-a"
    )
    partial = [
        dict(filled),
        dict(table[1], rights_review_decision="needs_media_inspection"),
        dict(table[2], rights_review_decision="fail"),
        *table[3:],
    ]
    with pytest.raises(ValueError, match="a pass needs every review field"):
        acquisition.reviewed(save(partial, "partial.csv"), manifest)
    partial[0]["independence_basis"] = "single creator, single session, no shared assets"
    done = acquisition.reviewed(save(partial, "done.csv"), manifest)
    first, second, third = (done[r["candidate_id"]] for r in table[:3])
    assert first["rights_cleared"] and first["may_download"]
    assert second["may_download"] and not second["rights_cleared"]  # inspect the media, clear nothing yet
    assert not third["may_download"] and sum(e["may_download"] for e in done.values()) == 2
    guess = [dict(table[0], rights_review_decision="cleared"), *table[1:]]
    with pytest.raises(ValueError, match="unknown review decision"):
        acquisition.reviewed(save(guess, "guess.csv"), manifest)
    edited = [dict(table[0], declared_license="CC0-1.0"), *table[1:]]
    with pytest.raises(ValueError, match="edits a field that discovery recorded"):
        acquisition.reviewed(save(edited, "edited.csv"), manifest)
    assert (
        json.loads(manifest.read_text())["rights_cleared_candidates"] == 0
    )  # reading a review changes nothing


def test_conversion_is_one_video_only_h264_file_inside_the_registered_box():
    spec = acquisition.load_settings()["native_ready"]
    command = acquisition.conversion_command("in.webm", "out.mp4", spec)
    assert command[0] == "ffmpeg" and command[-1] == "out.mp4" and "-an" in command
    assert (
        command[command.index("-c:v") + 1] == "libx264" and command[command.index("-profile:v") + 1] == "main"
    )
    scale = command[command.index("-vf") + 1]
    assert (
        "min(1280,iw)" in scale and "min(720,ih)" in scale and "force_original_aspect_ratio=decrease" in scale
    )
    assert "fps" not in scale and "pad" not in scale  # no frame-rate change, no padding
    assert (
        spec["audio"] is False and spec["frame_rate"] == "unchanged" and spec["aspect_ratio"] == "unchanged"
    )


def save_review(path, table):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=acquisition.COLUMNS)
        writer.writeheader()
        writer.writerows(table)
    return path


def test_fetch_touches_only_reviewed_candidates_checks_identity_and_stops_at_the_budget(
    exported, monkeypatch
):
    import hashlib
    import subprocess

    root, _ = exported
    manifest = root / "review/rights-review-manifest.json"
    with (root / "review/rights-review-manifest.csv").open(newline="") as stream:
        table = list(csv.DictReader(stream))
    table[0].update(rights_review_decision="needs_media_inspection")
    table[1].update(rights_review_decision="needs_media_inspection")
    table[2].update(rights_review_decision="fail")
    review = save_review(root / "reviewed.csv", table)
    stock = read_json(root / "inventory.json")
    payload = {r["asset_id"]: f"media of {r['asset_id']}".encode() for r in stock["records"]}
    for r in stock["records"]:
        r["reported_media_sha1"] = hashlib.sha1(payload[r["asset_id"]]).hexdigest()
    (root / "inventory.json").unlink()
    write_json(root / "inventory.json", stock)
    fetched = []

    def download(url, target, user_agent, limit):
        identifier = "commons-" + url.rsplit("/", 1)[1].split(".")[0]
        fetched.append(identifier)
        target.write_bytes(payload[identifier])
        return target.stat().st_size

    def run(command, **kwargs):
        if command[0] == "ffmpeg" and str(command[-1]).endswith((".mp4", ".jpg")):
            acquisition.Path(command[-1]).write_bytes(b"derived")
        return subprocess.CompletedProcess(command, 0, stdout="ffmpeg version test")

    probed = dict(duration_seconds=120.0, bytes=7, video_codec="h264", profile="Main", width=1280, height=720)
    probed.update(
        frame_rate="25/1", pixel_format="yuv420p", video_streams=1, audio_streams=0, audio_codecs=[]
    )
    monkeypatch.setattr(acquisition, "download", download)
    monkeypatch.setattr(acquisition.subprocess, "run", run)
    monkeypatch.setattr(acquisition, "probe", lambda path: dict(probed))
    result = acquisition.fetch(review, manifest, root / "inventory.json", root / "media")
    assert fetched == [
        table[0]["candidate_id"],
        table[1]["candidate_id"],
    ]  # never the failed or unreviewed ones
    assert result["fetched_candidates"] == 2 and result["reviewed_as_pass_at_fetch"] == 0
    assert result["outcome_data_collected"] is False
    record = result["records"][0]
    assert record["native_ready"]["parent_sha256"] == record["original"]["sha256"]  # lineage to the original
    assert record["native_ready"]["derived_verification_artifact"]
    assert record["original"]["sha1_matches_reviewed_revision"]
    again = acquisition.fetch(review, manifest, root / "inventory.json", root / "media")
    assert again["fetched_candidates"] == 2 and len(fetched) == 2  # nothing is fetched twice
    tight = read_json(acquisition.SETTINGS)
    tight["budget"].update(maximum_download_bytes=50_000_000)  # less than one candidate's catalogue size
    write_json(root / "tight.json", tight)
    with pytest.raises(ValueError, match="download budget reached"):
        acquisition.fetch(review, manifest, root / "inventory.json", root / "other", root / "tight.json")
    assert len(fetched) == 2  # stopped before touching the network
    stock["records"] = [dict(r, reported_media_sha1="0" * 40) for r in stock["records"]]
    (root / "inventory.json").unlink()
    write_json(root / "inventory.json", stock)
    table[3].update(rights_review_decision="needs_media_inspection")
    save_review(review, table)
    with pytest.raises(ValueError, match="differ from the reviewed revision"):
        acquisition.fetch(review, manifest, root / "inventory.json", root / "media")


def test_evidence_extract_lists_verbatim_quotes_and_flags_an_unanchored_review(tmp_path):
    lines = [
        "=={{int:filedesc}}==",
        "{{Information",
        "|source={{own}}",
        "|author=[[User:Someone|Someone]]",
        "}}",
    ]
    lines += ["=={{int:license-header}}==", "{{self|cc-by-4.0}}"]
    revision = dict(revid=5, slots=dict(main=dict(content=chr(10).join(lines))))
    page = dict(pageid=77, title="File:A Title.webm", revisions=[revision])
    page["videoinfo"] = [
        dict(extmetadata=dict(LicenseShortName=dict(value="CC BY 4.0"), Artist=dict(value="Someone")))
    ]
    (tmp_path / "evidence").mkdir()
    snapshot = tmp_path / "evidence/a.txt"
    snapshot.write_text(
        json.dumps(dict(query=dict(pages=[page, dict(pageid=1, revisions=[], videoinfo=[])])))
    )
    row = dict(candidate_id="commons-77", title="A Title", rights_evidence_snapshot="evidence/a.txt")
    row["rights_evidence_snapshot_sha256"] = acquisition.digest(snapshot)
    boilerplate = "This file is licensed under the Creative Commons Attribution 4.0 International license."
    extract = acquisition.evidence_extract(row, dict(decision="pass", binding_quote=boilerplate), tmp_path)
    assert (
        extract["title_in_evidence"] and not extract["reviewer_binding_quote_in_evidence"]
    )  # not in the evidence
    assert "{{self|cc-by-4.0}}" in extract["verbatim_quote_candidates"]
    assert "CC BY 4.0" in extract["verbatim_quote_candidates"]
    assert extract["information_fields"] == ["|source={{own}}", "|author=[[User:Someone|Someone]]"]
    anchored = acquisition.evidence_extract(
        row, dict(decision="pass", binding_quote="{{self|cc-by-4.0}}"), tmp_path
    )
    assert anchored["reviewer_binding_quote_in_evidence"]
    snapshot.write_text("tampered")
    with pytest.raises(ValueError, match="archived rights evidence changed"):
        acquisition.evidence_extract(row, dict(decision="pass", binding_quote=boilerplate), tmp_path)
