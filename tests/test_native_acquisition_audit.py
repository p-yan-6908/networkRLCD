import json

import pytest

from media_rl.native_acquisition_audit import (
    NETFLIX,
    UVG,
    XIPH,
    EvidenceStore,
    Page,
    allowed_url,
    audit,
    candidate,
    composition_metadata,
    grant,
    identify_license,
    is_video_object,
    protocol,
    qualify,
    summarize,
    uvg_candidates,
    xiph_candidates,
)
from media_rl.native_protocol import digest, read_json

CONFIG = "configs/native_panel_acquisition_audit_v1.json"


class FixtureStore:
    def __init__(self, bodies):
        self.bodies = bodies
        self.config = read_json(CONFIG)

    def get(self, url):
        assert url in self.bodies, "fixture network forbidden"
        return dict(
            url=url,
            status="preserved",
            sha256="a" * 64,
            path="fixture.txt",
            retrieved_at_utc="2026-10-05T00:00:00Z",
        )

    def text(self, receipt):
        return self.bodies[receipt["url"]]


def test_rights_unit_is_not_independence_cluster():
    receipt = FixtureStore({UVG: ""}).get(UVG)
    a, b = candidate("UVG", "A", "A", receipt), candidate("UVG", "B", "A", receipt)
    for row in (a, b):
        grant(row, "CC-BY-4.0", receipt, "All sequences CC BY 4.0", "shared publisher dataset")
    assert a["rights_unit_id"] == b["rights_unit_id"]
    assert a["source_cluster_id"] != b["source_cluster_id"]
    qualify([a, b])
    assert not any(row["main_panel_eligible"] for row in (a, b))


def test_stereo_variants_one_title_and_synthetic_tagged_separately():
    page = "The dataset comprises 2 video sequences released under the CC-BY 4.0 license."
    for name in (
        "A/A_1920x1080_30fps_yuv422_8bits_300.yuv",
        "A/stereo_rightcam_A_1920x1080_30fps_yuv422_8bits_300.yuv",
        "SyntheticCity/SyntheticCity_3840x2160_60fps_yuv444_8bits_600.yuv",
    ):
        page += f'<a href="{name}">RAW</a>'
    rows = uvg_candidates(FixtureStore({UVG: page}))
    assert len(rows) == 2 and len(rows[0]["representations"]) == 2
    assert sum(p["selected"] for p in rows[0]["representations"]) == 1
    assert rows[0]["representations"][0]["approximate_bytes"] == 1920 * 1080 * 2 * 300
    assert rows[1]["tier"] == "C" and rows[1]["synthetic_or_real"] == "synthetic"
    qualify(rows)
    assert all(
        "shorter_than_frozen_80_second_requirement_no_looping_or_padding" in r["blocking_reasons"]
        for r in rows
    )


def test_netflix_mirrors_and_excerpts_not_new_title_units():
    html = ""
    for clip in ("First", "Second"):
        html += f'<tr><strong>{clip}</strong>Source: Netflix Chimera <a href="{clip}_4096x2160_60fps.y4m">4K</a></tr>'
    rows = xiph_candidates(FixtureStore({XIPH: html}))
    master = candidate("Netflix", "Chimera", "A", FixtureStore({NETFLIX: ""}).get(NETFLIX))
    assert len({r["source_cluster_id"] for r in rows + [master]}) == 1
    assert all(r["license_type"] is None for r in rows)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("http://creativecommons.org/licenses/by-nc-nd/4.0/", "CC-BY-NC-ND-4.0"),
        ("http://creativecommons.org/licenses/by-nc/3.0/", "CC-BY-NC-3.0"),
        ("http://creativecommons.org/licenses/by/3.0/", "CC-BY-3.0"),
        ("may be used for research purposes, only", "LicenseRef-NTIA-Research-Only-2008"),
        ("Copyright: No Copyright", "LicenseRef-No-Copyright-Assertion"),
        ("believed to be freely redistributable", None),
    ],
)
def test_exact_restricted_and_unknown_license_classes(text, expected):
    assert identify_license(text)[0] == expected


def test_later_permissive_document_does_not_override_restriction():
    receipt = FixtureStore({UVG: ""}).get(UVG)
    row = candidate("Xiph", "A", "B", receipt)
    grant(row, "CC-BY-NC-ND-4.0", receipt, "NC ND", "asset")
    grant(row, "CC-BY-4.0", receipt, "BY", "asset")
    assert row["rights_status"] == "unresolved"
    assert row["rights_unit_id"] is None
    qualify([row])
    assert not row["main_panel_eligible"]


@pytest.mark.parametrize(
    "key,expected",
    [
        ("Nocturne/video.mxf", True),
        ("SolLevante/VIDEO_123.mxf", True),
        ("SolLevante/AUDIO_123.mxf", False),
        ("Nocturne/video_LtRt_Mixdown.mxf", False),
        ("sparks/P3_LtRt_IMF/video.mxf", True),
        ("SolLevante/working_assets/animatics.mov", False),
        ("sparks/OCF/raw_take.mxf", False),
    ],
)
def test_select_video_not_audio_or_storyboard(key, expected):
    assert bool(is_video_object(key)) is expected


def test_composition_binding_requires_exact_track_or_assetmap():
    xml = "<CPL><Resource><TrackFileId>urn:uuid:123</TrackFileId><EditRate>60 1</EditRate><SourceDuration>6000</SourceDuration></Resource></CPL>"
    assert composition_metadata(xml, "VIDEO_123.mxf")["duration_seconds"] == 100
    assert composition_metadata(xml, "named-master.mxf") is None
    assert composition_metadata(xml, "named-master.mxf", {"123": "named-master.mxf"})["fps"] == 60
    assert composition_metadata("invalid", "VIDEO_123.mxf") is None


@pytest.mark.parametrize(
    "url",
    [
        "http://media.xiph.org/page",
        "https://evil.example/index",
        "https://media.xiph.org/a.y4m",
        "https://media.xiph.org/a%2Emp4",
        "https://media.xiph.org/a.gz",
        "https://media.xiph.org/a.pdf",
        "https://user@media.xiph.org/page",
        "https://media.xiph.org:444/page",
    ],
)
def test_media_and_unapproved_url_get_forbidden(url):
    with pytest.raises(ValueError):
        allowed_url(url, read_json(CONFIG))


def test_script_style_not_license_or_content_evidence():
    page = Page("<script>CC BY 4.0</script><style>CC BY 3.0</style><p>unlicensed</p>")
    assert page.text == "unlicensed" and identify_license(page.text)[0] is None


class Response:
    def __init__(self, headers, body=b"text"):
        self.headers, self.body, self.reads, self.url = (
            headers,
            body,
            0,
            "https://media.xiph.org/Copyright.txt",
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        self.reads += 1
        return self.body[:limit]


class Opener:
    def __init__(self, response):
        self.response = response

    def open(self, *args, **kwargs):
        return self.response


def test_wrong_mime_or_oversized_content_refused_before_body(tmp_path):
    for i, headers in enumerate(
        ({"Content-Type": "video/mp4"}, {"Content-Type": "text/plain", "Content-Length": "999999999"})
    ):
        store = EvidenceStore(tmp_path / str(i), read_json(CONFIG))
        response = Response(headers)
        store.opener = Opener(response)
        receipt = store.get(response.url)
        assert receipt["status"] == "unresolved" and response.reads == 0
        assert store.total == 0


def test_missing_mime_linked_rights_text_preserved_and_offline_blocks_new_url(tmp_path):
    store = EvidenceStore(tmp_path / "e", read_json(CONFIG))
    response = Response({"Content-Length": "4"})
    store.opener = Opener(response)
    receipt = store.get(response.url)
    assert receipt["status"] == "preserved" and digest(store.out / receipt["path"]) == receipt["sha256"]
    store.offline = True
    with pytest.raises(ValueError, match="offline"):
        store.get("https://media.xiph.org/new-readme")
    assert store.calls == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("target_independent_units", 95),
        ("media_download_budget_bytes", 1),
        ("native_source_minimum_duration_seconds", 20),
        ("unknown_capture_provenance_is_not_verified_independence", False),
        ("maximum_metadata_requests", 257),
        ("maximum_total_text_bytes", 16777217),
    ],
)
def test_preregistration_cannot_be_relaxed(tmp_path, key, value):
    config = read_json(CONFIG)
    config[key] = value
    path = tmp_path / "p.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        protocol(path)


def test_prior_titles_and_unmeasured_strata_not_fresh_eligible():
    receipt = FixtureStore({UVG: ""}).get(UVG)
    r = candidate("Xiph", "Sintel", "B", receipt)
    grant(r, "CC-BY-3.0", receipt, "BY3", "asset")
    r["duration_seconds"] = 100
    qualify([r], ["sintel"])
    report = summarize([r], read_json(CONFIG))
    assert r["previously_exposed_title"] and report["fresh_rights_cleared_title_upper_bound"] == 0
    assert report["fully_eligible_independent_units"] == 0 and report["remaining_deficit_to_96"] == 96
    assert report["content_stratum_coverage"]["known_high"] == 0


def test_snapshot_tamper_rejected_without_network(tmp_path):
    root = tmp_path / "seed"
    store = EvidenceStore(root, read_json(CONFIG))
    response = Response({"Content-Type": "text/plain"})
    store.opener = Opener(response)
    receipt = store.get(response.url)
    store.save()
    (root / receipt["path"]).write_text("tampered")
    with pytest.raises(ValueError, match="drift"):
        audit(CONFIG, root, tmp_path / "out", offline=True)


def test_native_length_upper_bound_does_not_count_short_rights_clean_titles():
    receipt = FixtureStore({UVG: ""}).get(UVG)
    short, long = candidate("UVG", "Short", "A", receipt), candidate("Netflix", "Long", "A", receipt)
    for record in (short, long):
        grant(record, "CC-BY-4.0", receipt, "licensed", "dataset")
    short["duration_seconds"] = 10
    qualify([short, long])
    result = summarize([short, long], read_json(CONFIG))
    assert result["fresh_rights_cleared_title_upper_bound"] == 2
    assert result["fresh_rights_and_native_length_title_upper_bound"] == 1
    assert result["native_length_optimistic_additional_cluster_deficit"] == 95


def test_csv_keeps_unknown_hashes_and_capture_as_empty_not_fake(tmp_path):
    import csv

    from media_rl.native_acquisition_audit import write_inventory_csv

    receipt = FixtureStore({UVG: ""}).get(UVG)
    row = candidate("UVG", "A", "A", receipt)
    qualify([row])
    path = tmp_path / "inventory.csv"
    write_inventory_csv(path, [row])
    with path.open() as stream:
        exported = list(csv.DictReader(stream))[0]
    assert exported["original_sha256"] == exported["capture_cluster_id"] == ""
    assert exported["main_panel_eligible"] == "False"
    assert "unverified" in exported["blocking_reasons"]


def test_public_registry_and_protocol_registration():
    import tomllib
    from pathlib import Path

    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert (
        project["project"]["scripts"]["media-acquisition-audit"] == "media_rl.native_acquisition_audit:main"
    )
    config = protocol(CONFIG)
    assert config["tiers"]["C"] and config["media_download_budget_bytes"] == 0
