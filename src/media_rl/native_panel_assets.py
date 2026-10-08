"""Licensed source-unit manifests and controller freeze; never trains a model."""

import argparse
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from .native_protocol import digest, finite, read_json, require, seal_directory, write_json

ROOT = Path(__file__).resolve().parents[2]
ABI = "licensed_independent_panel_assets_v1"
FREEZE = ROOT / "configs/native_controller_freeze_v1.json"
PERMITTED = {"CC-BY-4.0", "CC-BY-3.0", "CC0-1.0"}
LICENSE_URLS = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}


def _text(value):
    require(isinstance(value, str) and value.strip(), "explicit source/title/capture metadata required")
    return " ".join(value.casefold().split())


def identity_tokens(record):
    # Titles are global, not provider-scoped: mirrors/encodes of Meridian cannot
    # create additional independent units by changing the hosting website.
    title, capture = _text(record["source_title"]), _text(record["capture_group"])
    sha = record.get("source_sha256", record.get("sha256"))
    require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "source lineage SHA256 required")
    tokens = {"title:" + title, "capture:" + capture, "sha:" + sha}
    parent = record.get("parent_sha256")
    if parent is not None:
        require(
            isinstance(parent, str) and re.fullmatch(r"[0-9a-f]{64}", parent), "parent asset SHA256 required"
        )
        tokens.add("sha:" + parent)
    return tokens


def assign_clusters(records):
    """Conservatively merge shared title OR capture OR asset/parent lineage."""
    parent = list(range(len(records)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owners = {}
    for i, record in enumerate(records):
        for token in identity_tokens(record):
            if token in owners:
                parent[root(i)] = root(owners[token])
            else:
                owners[token] = i
    components = defaultdict(set)
    for i, record in enumerate(records):
        components[root(i)].update(identity_tokens(record))
    return [
        "source-" + hashlib.sha256("\n".join(sorted(components[root(i)])).encode()).hexdigest()[:24]
        for i in range(len(records))
    ]


def validate_cluster_rows(rows):
    # IDs originate in a sealed full acquisition pool, not a data-dependent
    # re-hash of this subset. Repeated records must retain identical provenance.
    owners, clips, roles = {}, {}, {}
    for row in rows:
        require(
            isinstance(row.get("cluster_id"), str)
            and row["cluster_id"].startswith("source-")
            and row["block_id"] == row["cluster_id"],
            "source-cluster provenance required",
        )
        tokens = identity_tokens(row)
        for token in tokens:
            require(
                token not in owners or owners[token] == row["cluster_id"],
                "pseudo-replication: shared title/capture/lineage split into different clusters",
            )
            owners[token] = row["cluster_id"]
        metadata = row["cluster_id"], tuple(sorted(tokens))
        require(row["clip_id"] not in clips or clips[row["clip_id"]] == metadata, "clip provenance drift")
        clips[row["clip_id"]] = metadata
        require(
            row["cluster_id"] not in roles or roles[row["cluster_id"]] == row["role"],
            "source/title/capture role leakage",
        )
        roles[row["cluster_id"]] = row["role"]


def frozen_paths():
    patterns = (
        "jevbwe*.py",
        "*policy*.py",
        "*learning*.py",
        "*model*.py",
        "networks.py",
        "safety.py",
        "calibration.py",
        "native_actuator_control.py",
    )
    paths = {p for pattern in patterns for p in (ROOT / "src/media_rl").glob(pattern)}
    paths |= {
        ROOT / "benchmarks/native_rtc" / name
        for name in (
            "actuator_control.mjs",
            "actuator_meter.mjs",
            "actuator_episode.mjs",
            "streamed_actuator_video.mjs",
        )
    }
    return sorted(paths)


def freeze_controllers(out=FREEZE):
    require(not Path(out).exists(), "controller freeze is immutable; do not replace it for convenience")
    result = dict(
        abi="native_controller_freeze_v1",
        files={str(p.relative_to(ROOT)): digest(p) for p in frozen_paths()},
        no_models_trained=True,
        policy_promoted=False,
    )
    write_json(out, result)
    return result


def verify_controller_freeze(path=FREEZE):
    result = read_json(path)
    require(
        result["abi"] == "native_controller_freeze_v1"
        and result["no_models_trained"] is True
        and result["policy_promoted"] is False,
        "controller freeze contract required",
    )
    require(
        set(result["files"]) == {str(p.relative_to(ROOT)) for p in frozen_paths()},
        "frozen controller file inventory drift",
    )
    require(
        all(digest(ROOT / p) == sha for p, sha in result["files"].items()),
        "controller/model/actuator bytes changed after freeze",
    )
    return dict(verified=True, files=len(result["files"]), sha256=digest(path))


def validate_source(catalog):
    """Verify commercial-compatible per-asset permission evidence, not web hearsay.

    Importer must supply the original downloaded license/readme snapshot, matching
    hash, binding quote and attribution. Bytes/evidence are checked here; legal
    authenticity and independence cannot be inferred automatically.
    """
    identity_tokens(catalog)
    _text(catalog["source"])
    _text(catalog["independence_basis"])
    require(
        catalog.get("license") in PERMITTED,
        "main panel permits only explicit CC BY/CC0; NC, ND and unknown rights blocked",
    )
    require(
        catalog["license_url"] == LICENSE_URLS[catalog["license"]], "canonical per-asset license URL required"
    )
    proof = catalog["license_evidence"]
    require(
        proof["scope"] == "this_asset"
        and proof["source_title"] == catalog["source_title"]
        and proof["license"] == catalog["license"]
        and proof["source_url"].startswith("https://")
        and proof["reviewed_by_importer"] is True
        and proof["checked_at_utc"],
        "per-asset license binding/review required",
    )
    snapshot = Path(proof["path"])
    require(
        snapshot.is_file() and digest(snapshot) == proof["sha256"], "license/readme evidence bytes changed"
    )
    text = snapshot.read_text()
    require(
        _text(catalog["source_title"]) in _text(text), "asset title absent from accompanying license evidence"
    )
    require(
        proof["binding_quote"].strip() and proof["binding_quote"] in text,
        "license binding quote absent from accompanying asset evidence",
    )
    markers = {
        "CC-BY-4.0": ("CC BY 4.0", "CC-BY 4.0", "Attribution 4.0", "licenses/by/4.0"),
        "CC-BY-3.0": ("CC BY 3.0", "Attribution 3.0", "licenses/by/3.0"),
        "CC0-1.0": ("CC0", "publicdomain/zero/1.0"),
    }
    require(
        any(marker.casefold() in text.casefold() for marker in markers[catalog["license"]]),
        "declared license absent from evidence",
    )
    require(
        catalog["rights_asserted_by_importer"] is True
        and catalog["attribution"].strip()
        and catalog["source_url"].startswith("https://"),
        "explicit asset rights and attribution required",
    )
    require(
        catalog.get("synthetic", False) is False
        or catalog.get("generation_provenance", {}).get("all_components_owned_or_permitted") is True,
        "synthetic scenes need component-level ownership/permission provenance",
    )
    return catalog


def inspect_media(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration:stream=codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(result.stdout)
    require(len(data["streams"]) == 1, "one explicit video stream required")
    stream = data["streams"][0]
    duration = float(data["format"]["duration"])
    numerator, denominator = (int(x) for x in stream["r_frame_rate"].split("/"))
    require(
        finite(duration)
        and duration > 0
        and numerator > 0
        and denominator > 0
        and stream["width"] > 0
        and stream["height"] > 0,
        "actual video duration/resolution/fps required",
    )
    return dict(
        duration_ms=int(duration * 1000),
        width=stream["width"],
        height=stream["height"],
        frame_rate=stream["r_frame_rate"],
        codec=stream["codec_name"],
    )


def ingest(request_path, out):
    verify_controller_freeze()
    request = read_json(request_path)
    out = Path(out).resolve()
    require(
        not out.exists() and request["abi"] == ABI + "_request" and request["assets"],
        "fresh explicit asset import request required",
    )
    catalogs = []
    for asset in request["assets"]:
        record = dict(asset)
        media = Path(record["path"]).resolve()
        require(
            media.is_file() and digest(media) == record["sha256"], "owned/acquired asset checksum mismatch"
        )
        validate_source(record)
        record["license_evidence"] = dict(
            record["license_evidence"], path=str(Path(record["license_evidence"]["path"]).resolve())
        )
        geometry = inspect_media(media)
        record.update(
            geometry,
            path=str(media),
            source_abi="recorded_video_v1",
            not_representative_corpus=True,
            native_panel_ready=geometry["codec"] == "h264" and geometry["duration_ms"] >= 80000,
            no_looping_padding_or_interpolation_performed=True,
        )
        # The frozen native catalog/runtime needs >=60s and the original panel
        # reserves first 60s then a real 20s excerpt. Short codec test sequences
        # are inventoried but never repeated/padded to manufacture eligibility.
        catalogs.append(record)
    ids = assign_clusters(catalogs)
    out.mkdir()
    for i, record in enumerate(catalogs):
        record["cluster_id"] = ids[i]
        write_json(out / f"asset-{i:04d}.json", record)
    result = dict(
        abi=ABI,
        assets=catalogs,
        independent_source_clusters=len(set(ids)),
        native_ready_source_clusters=len({r["cluster_id"] for r in catalogs if r["native_panel_ready"]}),
        independence_is_importer_reviewed_not_statistically_proven=True,
        inferred_legal_permission=False,
        no_downloads_performed=True,
        controller_freeze=verify_controller_freeze(),
    )
    write_json(out / "assets.json", result)
    # Evidence snapshots stay externally bound by exact hash and are reverified.
    seal_directory(
        out,
        sorted(p.name for p in out.iterdir()),
        ABI + "_complete",
        policy_models_fitted=0,
        SOTA_achieved=False,
    )
    return result


def source_status(catalog):
    try:
        validate_source(catalog)
        return dict(eligible=True, reason=None)
    except (KeyError, ValueError, OSError, TypeError) as error:
        return dict(eligible=False, reason=str(error), no_license_or_independence_inferred=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--out", default=str(FREEZE))
    check = commands.add_parser("verify-freeze")
    check.add_argument("--path", default=str(FREEZE))
    imp = commands.add_parser("ingest")
    imp.add_argument("--request", required=True)
    imp.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        result = freeze_controllers(args.out)
        result = dict(frozen_files=len(result["files"]), path=args.out)
    elif args.command == "verify-freeze":
        result = verify_controller_freeze(args.path)
    else:
        result = ingest(args.request, args.out)
        result = dict(
            independent_source_clusters=result["independent_source_clusters"],
            native_ready_source_clusters=result["native_ready_source_clusters"],
        )
    print(json.dumps(result, allow_nan=False, sort_keys=True))
