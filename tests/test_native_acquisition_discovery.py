import copy
import json
from pathlib import Path

import pytest

from media_rl.native_acquisition_discovery import (
    NATIVE_PANEL_ACQUISITION_DISCOVERY_V2,
    MetadataStore,
    allowed_license,
    base_record,
    capture_plan,
    cluster_records,
    commons_record,
    commons_url,
    enumerate_commons,
    protocol,
    publisher_grant,
    report,
    source_identity,
    title_id,
)
from media_rl.native_protocol import read_json

CONFIG = "configs/native_panel_acquisition_discovery_v2.json"


def receipt(url="https://commons.wikimedia.org/api"):
    return dict(
        url=url,
        status="preserved",
        path="evidence/test.txt",
        sha256="a" * 64,
        retrieved_at_utc="2026-10-05T00:00:00Z",
    )


def page(
    identifier=1,
    duration=80,
    creator="Alice",
    credit="Own work",
    license_id="cc-by-4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
):
    return dict(
        pageid=identifier,
        title=f"File:Test{identifier}.webm",
        revisions=[
            dict(
                revid=identifier,
                slots=dict(
                    main=dict(content="{{Information\n|source={{own}}\n|author=Alice}}\n{{self|cc-by-4.0}}")
                ),
            )
        ],
        videoinfo=[
            dict(
                duration=duration,
                width=1920,
                height=1080,
                size=1000,
                url=f"https://upload.wikimedia.org/Test{identifier}.webm",
                descriptionurl=f"https://commons.wikimedia.org/wiki/File:Test{identifier}.webm",
                user="Uploader-not-necessarily-author",
                sha1=str(identifier) * 40,
                extmetadata={
                    key: dict(value=value)
                    for key, value in dict(
                        Artist=creator,
                        Credit=credit,
                        License=license_id,
                        LicenseUrl=license_url,
                        DateTimeOriginal="2020-01-01",
                        DateTime="2026-01-01",
                        Restrictions="",
                    ).items()
                },
            )
        ],
    )


def test_duration_threshold_exact_and_no_media_hash_substitution():
    assert commons_record(page(duration=79.999), receipt()) is None
    assert commons_record(page(duration=float("nan")), receipt()) is None
    row = commons_record(page(), receipt())
    assert row["rights_cleared"] and row["duration_seconds"] == 80
    assert row["creator"] == "Alice" and row["uploader"] != "Alice"
    assert row["original_sha256"] is None and row["normalized_sha256"] is None
    assert row["creation_capture_metadata"]["DateTimeOriginal"] != "2026-01-01"
    assert not row["native_import_rights_verified"] and not row["fully_verified_eligible"]


@pytest.mark.parametrize(
    "identifier,url,expected",
    [
        ("cc-by-4.0", "https://creativecommons.org/licenses/by/4.0", "CC-BY-4.0"),
        ("CC BY 3.0", "http://creativecommons.org/licenses/by/3.0/deed.en", "CC-BY-3.0"),
        ("cc-zero", "https://creativecommons.org/publicdomain/zero/1.0/", "CC0-1.0"),
        ("cc-by-sa-4.0", "https://creativecommons.org/licenses/by-sa/4.0/", None),
        ("cc-by-nc-4.0", "https://creativecommons.org/licenses/by-nc/4.0/", None),
        ("cc-by-4.0", "https://evil.test/licenses/by/4.0/", None),
        ("cc-by-3.0", "https://creativecommons.org/licenses/by/4.0/", None),
        ("public domain", "https://creativecommons.org/publicdomain/mark/1.0/", None),
    ],
)
def test_exact_frozen_license_no_sa_nc_or_version_borrowing(identifier, url, expected):
    assert allowed_license(identifier, url)[0] == expected


@pytest.mark.parametrize("alter", ["external", "creator", "revision", "restriction", "source_template"])
def test_license_alone_does_not_clear_provenance(alter):
    p = page()
    info = p["videoinfo"][0]
    if alter == "external":
        info["extmetadata"]["Credit"]["value"] = "YouTube copy"
    if alter == "creator":
        info["extmetadata"]["Artist"]["value"] = "Unknown"
    if alter == "revision":
        p["revisions"] = []
    if alter == "restriction":
        info["extmetadata"]["Restrictions"]["value"] = "personality rights"
    if alter == "source_template":
        p["revisions"][0]["slots"]["main"]["content"] = "|source=Third party"
    assert not commons_record(p, receipt())["rights_cleared"]


def test_unicode_identity_and_source_tracking_aliases():
    assert title_id("中国河流") and title_id("中国河流") != title_id("Россия")
    assert source_identity("http://x.test/movie?id=1&utm_source=commons#t=30") == source_identity(
        "https://x.test/movie?id=1"
    )


def test_creator_event_source_and_media_lineage_collisions_are_transitive():
    cfg = read_json(CONFIG)
    a = commons_record(page(1, creator="Alice"), receipt())
    b = commons_record(page(2, creator="Alice"), receipt())
    c = commons_record(page(3, creator="Bob"), receipt())
    b["event_id"] = c["event_id"] = "one event"
    edges = cluster_records([a, b, c], cfg)
    assert len({r["source_cluster_id"] for r in (a, b, c)}) == 1 and len(edges) == 2
    assert all(not r["fully_verified_eligible"] for r in (a, b, c))
    assert report([a, b, c], cfg, edges, 3, [])["conditional_deficit_if_all_metadata_candidates_verify"] == 95


def test_rights_units_do_not_merge_statistics_and_prior_title_excludes_whole_cluster():
    cfg = read_json(CONFIG)
    a = commons_record(page(1, creator="Alice"), receipt())
    b = commons_record(page(2, creator="Bob"), receipt())
    a["rights_unit_id"] = b["rights_unit_id"] = "shared-license-document"
    cluster_records([a, b], cfg)
    assert a["source_cluster_id"] != b["source_cluster_id"]
    a["title_id"] = "sintel"
    b["event_id"] = a["event_id"] = "one"
    cluster_records([a, b], cfg)
    assert not a["planning_candidate"] and not b["planning_candidate"]


def test_blender_distinct_production_but_shared_franchise_and_mirrors_merge():
    cfg = read_json(CONFIG)
    a = base_record("Blender Open Movies", "b1", "spring", receipt())
    b = base_record("Blender Open Movies", "b2", "hero", receipt())
    c = base_record("Blender Open Movies", "c1", "caminandes-1", receipt())
    d = base_record("Blender Open Movies", "c2", "caminandes-2", receipt())
    mirror = commons_record(page(7, creator="Blender Foundation", credit="Studio"), receipt())
    mirror["title_id"] = "spring"
    mirror["known_production"] = "spring"
    cluster_records([a, b, c, d, mirror], cfg)
    assert a["source_cluster_id"] == mirror["source_cluster_id"] != b["source_cluster_id"]
    assert c["source_cluster_id"] == d["source_cluster_id"]


def test_capture_ids_are_immutable_reserves_not_units_and_matrix_balanced():
    cfg = read_json(CONFIG)
    a = capture_plan(cfg, 96, 13)
    b = capture_plan(cfg, 96, 0)
    assert [r["capture_id"] for r in a["captures"]] == [r["capture_id"] for r in b["captures"]]
    assert len(set(r["capture_id"] for r in a["captures"])) == 96
    assert sum(r["conditional_priority"] for r in a["captures"]) == 13
    assert all(sum(row.values()) == 32 for row in a["matrix"].values())
    assert all(sum(row[column] for row in a["matrix"].values()) == 32 for column in ("low", "medium", "high"))
    assert all(
        r["planned_duration_seconds"] >= 80
        and r["original_sha256"] is None
        and not r["fully_verified_eligible"]
        for r in a["captures"]
    )
    assert a["projected_original_plus_normalized_bytes_bounds"] == [14400000000, 40320000000]


@pytest.mark.parametrize(
    "key,value",
    [
        ("target_independent_units", 95),
        ("minimum_duration_seconds", 79),
        ("allowed_licenses", ["CC-BY-SA-4.0"]),
        ("media_download_budget_bytes", 1),
        ("minimum_request_interval_seconds", 0),
    ],
)
def test_frozen_boundaries_not_relaxed(tmp_path, key, value):
    cfg = read_json(CONFIG)
    cfg[key] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        protocol(path)


@pytest.mark.parametrize(
    "url",
    [
        "https://download.blender.org/f.ogv",
        "https://download.blender.org/f.avi",
        "https://download.blender.org/f.mkv",
        "https://download.blender.org/f.mp4",
        "https://download.blender.org/f.zip",
    ],
)
def test_no_media_body_get_even_from_approved_host(tmp_path, url):
    store = MetadataStore(tmp_path / "out", read_json(CONFIG), offline=True)
    with pytest.raises(ValueError, match="media/binary"):
        store.get(url)
    assert store.calls == 0


class ApiFixture:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        assert url in self.responses
        return receipt(url)

    def text(self, r):
        return json.dumps(self.responses[r["url"]])


def test_api_continuation_dedup_and_revision_drift():
    cfg = read_json(CONFIG)
    cfg["commons"]["search_queries"] = ["q"]
    cfg["commons"]["maximum_batches_per_query"] = 2
    p = page()
    changed = copy.deepcopy(p)
    changed["revisions"][0]["revid"] = 999
    cont = {"gsroffset": 10, "continue": "gsroffset||"}
    fixture = ApiFixture(
        {
            commons_url(cfg, "q"): {"query": {"pages": [p]}, "continue": cont},
            commons_url(cfg, "q", cont): {"query": {"pages": [changed]}},
        }
    )
    rows, progress, enumerated = enumerate_commons(fixture, cfg)
    assert len(rows) == enumerated == 1 and len(progress) == 2
    assert rows[0]["provenance_status"] == "revision_or_media_drift_between_queries"
    assert not rows[0]["rights_cleared"]


def test_publisher_asset_grant_not_generic_website_footer():
    genuine = "Spring. The results of the Spring open movie project are being licensed under Creative Commons Attribution 4.0."
    assert publisher_grant(genuine, "Spring")[0] == "CC-BY-4.0"
    assert (
        publisher_grant("Spring is a movie. This website is licensed under Attribution 4.0.", "Spring")[0]
        is None
    )


@pytest.mark.parametrize(
    "template,expected",
    [
        ("{{LicenseReview}}", False),
        ("{{LicenseReview|user=Alice|date=2020-01-01}}", True),
        ("{{LicenseReview|site={{From YouTube|1=x|2=Movie}}|user=Alice|date=2020-01-01}}", True),
        ("{{LicenseReview|user=Alice|date=2020-02-31}}", False),
        ("{{LicenseReview|user=Alice|date=2020-01-01|failed=1}}", False),
        ("{{LicenseReview|user=|date=2020-01-01}}", False),
        ("{{LicenseReview|user=Alice|date=2020-01-01", False),
    ],
)
def test_dated_source_review_never_pending_or_rejected(template, expected):
    from media_rl.native_acquisition_discovery import source_review_evidence

    assert bool(source_review_evidence(template)) == expected
    p = page(credit='<a href="https://www.youtube.com/watch?v=one">Original publisher</a>')
    p["revisions"][0]["slots"]["main"]["content"] += "\n" + template
    r = commons_record(p, receipt())
    assert r["rights_cleared"] == expected and not r["native_import_rights_verified"]


def test_own_work_does_not_grant_unreviewed_soundtrack_or_game_assets():
    p = page(creator="Alice Music: Someone else")
    r = commons_record(p, receipt())
    assert not r["rights_cleared"] and r["component_rights_review_required"]


def test_actual_receipt_schema_and_templates_are_unsigned_not_rights():
    from media_rl.native_acquisition_discovery import capture_receipt_schema, capture_receipt_templates

    plan = capture_plan(read_json(CONFIG), 96, 13)
    schema = capture_receipt_schema(plan)
    registry = capture_receipt_templates(plan)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["actual_duration_seconds"]["minimum"] == 80
    assert schema["properties"]["status"]["const"] == "signed_actual_capture_receipt"
    assert schema["properties"]["license_type"]["const"] == "CC-BY-4.0"
    assert len(schema["properties"]["capture_id"]["enum"]) == len(registry["receipts"]) == 96
    assert registry["grants_created"] == registry["eligible_units"] == 0
    assert all(
        r["status"] == "unsigned_plan_template"
        and r["copyright_owner"] is None
        and r["owner_signature_reference"] is None
        for r in registry["receipts"]
    )


def test_unsupported_publisher_version_recorded_not_borrowed():
    kind, quote, error = publisher_grant(
        "Elephants Dream. This film is licensed under Creative Commons Attribution 2.5.", "Elephants Dream"
    )
    assert kind == "CC-BY-2.5" and quote and error is None


def test_seed_paths_and_hashes_rejected_before_copy(tmp_path):
    cfg = read_json(CONFIG)
    root = tmp_path / "seed"
    root.mkdir()
    (root / "protocol.json").write_text(json.dumps(cfg))
    proof = receipt()
    proof["path"] = "../escape.txt"
    (root / "evidence.json").write_text(
        json.dumps(dict(receipts={proof["url"]: proof}, metadata_response_bytes=1, metadata_requests=1))
    )
    with pytest.raises(ValueError, match="safe seed"):
        MetadataStore(tmp_path / "out", cfg, seed=root, offline=True)
    proof["path"] = "evidence/test.txt"
    (root / "evidence").mkdir()
    (root / proof["path"]).write_text("drift")
    (root / "evidence.json").write_text(
        json.dumps(dict(receipts={proof["url"]: proof}, metadata_response_bytes=1, metadata_requests=1))
    )
    with pytest.raises(ValueError, match="SHA256 drift"):
        MetadataStore(tmp_path / "out2", cfg, seed=root, offline=True)


@pytest.mark.parametrize(
    "text,title,expected",
    [
        (
            "The Spring Open Movie is released un the Creative Commons Attribution 4.0 license.",
            "Spring",
            "CC-BY-4.0",
        ),
        (
            "The work of the Sprite Fright project is licensed under the Creative Commons Attribution 1.0 license.",
            "Sprite Fright",
            "CC-BY-1.0",
        ),
        (
            'Agent 327: Operation Barbershop is released under CC-BY-ND license. <a href="https://creativecommons.org/licenses/by-nd/2.0/">CC-BY-ND</a>',
            "Agent 327",
            "CC-BY-ND-2.0",
        ),
        ("Spring is a movie. This website is licensed under Attribution 4.0.", "Spring", None),
    ],
)
def test_primary_scope_exact_versions_and_no_permissive_relabeling(text, title, expected):
    assert publisher_grant(text, title)[0] == expected


def test_primary_incompatible_rights_quarantines_reviewed_mirror():
    from media_rl.native_acquisition_discovery import reconcile_publisher_rights

    producer = base_record("Blender Open Movies", "b1", "sprite-fright", receipt())
    producer.update(license_type="CC-BY-1.0", license_evidence=[receipt()])
    mirror = commons_record(page(), receipt())
    mirror["known_production"] = "sprite-fright"
    assert mirror["rights_cleared"]
    reconcile_publisher_rights([producer, mirror])
    assert not mirror["rights_cleared"] and mirror["publisher_rights_conflict_evidence"]


def test_catalog_fps_ratio_nested_header_and_unavailable():
    from media_rl.native_acquisition_discovery import catalog_fps

    assert catalog_fps({"frame_rate": "30000/1001"}) == pytest.approx(29.97003, abs=0.00001)
    assert (
        catalog_fps(
            {
                "metadata": [
                    {
                        "name": "streams",
                        "value": [
                            {
                                "name": "header",
                                "value": [{"name": "FRN", "value": 30}, {"name": "FRD", "value": 1}],
                            }
                        ],
                    }
                ]
            }
        )
        == 30
    )
    assert catalog_fps({"fps": "nan"}) is None and catalog_fps({"fps": "30/0"}) is None


def test_public_symbol_cli_and_config_registration():
    import tomllib

    assert NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 == "NATIVE_PANEL_ACQUISITION_DISCOVERY_V2"
    assert protocol(CONFIG)["target_independent_units"] == 96
    assert (
        tomllib.loads(Path("pyproject.toml").read_text())["project"]["scripts"]["media-acquisition-discovery"]
        == "media_rl.native_acquisition_discovery:main"
    )
