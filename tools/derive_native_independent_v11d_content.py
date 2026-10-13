"""Verify licensed V11D Commons sources and make fixed native-ready clips."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote, urlparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path("/home/agent/.cache/networkrlcd/independent-v11d-sources")
RIGHTS_MANIFEST = REPO / "acquisition/native-n1/rights-review/rights-review-manifest-final.csv"
CONTACT_REVIEW = REPO / "acquisition/native-n1/rights-review/contact-sheet-review-final.json"
EVIDENCE_EXTRACTS = REPO / "acquisition/native-n1/rights-review/evidence-extracts.json"
OUTPUT = REPO / "data/native-v11d/content_sources.json"

SOURCES = [
    {"candidate_id": "commons-106384795", "content_id": "content_cicada_emergence_01", "segment_start_s": 60},
    {"candidate_id": "commons-29267197", "content_id": "content_vizanice_outdoor_01", "segment_start_s": 30},
    {"candidate_id": "commons-121308342", "content_id": "content_schmilka_firefighting_01", "segment_start_s": 60},
    {"candidate_id": "commons-32353576", "content_id": "content_d3_tree_layout_tutorial_01", "segment_start_s": 60},
]
SEGMENT_SECONDS = 30


def sha(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict:
    raw = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_name,profile,width,height,pix_fmt,avg_frame_rate,codec_type",
         "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return json.loads(raw.stdout)


def manifest_rows() -> dict[str, dict]:
    with RIGHTS_MANIFEST.open(newline="", encoding="utf-8-sig") as stream:
        return {row["candidate_id"]: row for row in csv.DictReader(stream)}


def build(source_root: Path, output: Path) -> dict:
    rights_rows = manifest_rows()
    contact = json.loads(CONTACT_REVIEW.read_text(encoding="utf-8"))
    contact_passes = set(contact["passes"])
    contacts = []
    originals = source_root / "content-originals"
    clips = source_root / "content-clips"
    originals.mkdir(parents=True, exist_ok=True)
    clips.mkdir(parents=True, exist_ok=True)
    source_records = []
    groups = set()
    ffmpeg_version = subprocess.run(["ffmpeg", "-version"], check=True,
                                    capture_output=True, text=True).stdout.splitlines()[0]

    for selected in SOURCES:
        candidate = selected["candidate_id"]
        row = rights_rows.get(candidate)
        if row is None:
            raise ValueError(f"rights review record missing for {candidate}")
        if (row["rights_review_decision"] != "pass" or row["rights_cleared"] != "True"
                or row["component_rights_review_required"] != "False"
                or candidate not in contact_passes):
            raise ValueError(f"source lacks exact rights/contact review pass: {candidate}")
        if row["capture_group"] in groups:
            raise ValueError(f"duplicate capture group: {row['capture_group']}")
        groups.add(row["capture_group"])
        if row["declared_license"] not in ("CC-BY-3.0", "CC-BY-4.0", "CC0-1.0"):
            raise ValueError(f"unsupported recorded license for {candidate}: {row['declared_license']}")
        match = re.search(r"reported-media-sha1:([0-9a-f]{40})", row["cluster_tokens"])
        if not match:
            raise ValueError(f"frozen catalogue SHA-1 missing for {candidate}")

        media_extension = Path(unquote(urlparse(row["media_url"]).path)).suffix
        if media_extension not in (".webm", ".ogv", ".ogg", ".mp4"):
            raise ValueError(f"unsupported licensed source media extension for {candidate}: {media_extension}")
        original = originals / f"{candidate}{media_extension}"
        if not original.is_file():
            raise FileNotFoundError(original)
        original_bytes = original.stat().st_size
        original_sha1 = sha(original, "sha1")
        original_sha256 = sha(original)
        if (original_bytes != int(row["catalogue_bytes"])
                or original_sha1 != match.group(1)):
            raise ValueError(f"Commons source bytes/SHA-1 differ from reviewed catalogue: {candidate}")
        original_probe = ffprobe(original)
        duration = float(original_probe["format"]["duration"])
        if selected["segment_start_s"] + SEGMENT_SECONDS > duration:
            raise ValueError(f"selected clip segment exceeds source duration: {candidate}")

        clip_name = f"{selected['content_id']}-30s.mp4"
        clip = clips / clip_name
        clip_filter = (
            "fps=30,"
            "scale=w='min(640,iw)':h='min(360,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,"
            "pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black"
        )
        command = ["ffmpeg", "-y", "-v", "error", "-i", str(original),
                   "-ss", str(selected["segment_start_s"]), "-t", str(SEGMENT_SECONDS),
                   "-map", "0:v:0", "-an", "-sn", "-dn", "-map_metadata", "-1",
                   "-vf", clip_filter, "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "18", "-profile:v", "main", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(clip)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        clip_probe = ffprobe(clip)
        streams = clip_probe["streams"]
        video = [item for item in streams if item.get("codec_type") == "video"]
        audio = [item for item in streams if item.get("codec_type") == "audio"]
        if (len(video) != 1 or audio or video[0].get("codec_name") != "h264"
                or video[0].get("profile") != "Main" or video[0].get("width") != 640
                or video[0].get("height") != 360 or video[0].get("pix_fmt") != "yuv420p"
                or video[0].get("avg_frame_rate") != "30/1"
                or abs(float(clip_probe["format"]["duration"]) - SEGMENT_SECONDS) > 0.1):
            raise ValueError(f"derived V11D clip failed native-ready media checks: {candidate}")

        cache_original = f"independent-v11d-sources/content-originals/{original.name}"
        cache_clip = f"independent-v11d-sources/content-clips/{clip.name}"
        source_records.append({
            "content_id": selected["content_id"],
            "candidate_id": candidate,
            "title": row["title"],
            "creator": row["creator"],
            "license": row["declared_license"],
            "license_url": row["license_url"],
            "source_url": row["source_url"],
            "source_revision_url": row["rights_evidence_revision_url"],
            "rights_review_decision": row["rights_review_decision"],
            "n1_pool_status": "reserve_not_stage_one_capture",
            "rights_review_manifest_sha256": sha(RIGHTS_MANIFEST),
            "rights_evidence_snapshot_sha256": row["rights_evidence_snapshot_sha256"],
            "capture_group": row["capture_group"],
            "attribution": (row["attribution"] or
                            f"“{row['title']}” — {row['creator']}, {row['declared_license']}, via Wikimedia Commons."),
            "original_cache_path": cache_original,
            "original_bytes": original_bytes,
            "original_sha1": original_sha1,
            "original_sha256": original_sha256,
            "clip_cache_path": cache_clip,
            "clip_bytes": clip.stat().st_size,
            "clip_sha256": sha(clip),
            "segment_start_s": selected["segment_start_s"],
            "segment_duration_s": SEGMENT_SECONDS,
            "derivative": "30-second H.264 Main, yuv420p, 640x360, 30 fps, no audio; aspect-preserving scale and center pad; source metadata stripped",
        })
        contacts.append({"candidate_id": candidate, "contact_sheet_review_pass": True,
                         "segment_visual_review": "six frames reviewed; no close legible personal details retained"})

    document = {
        "abi": "native_independent_v11d_content_sources_v1",
        "review_date_utc": "2026-10-13",
        "rights_review_manifest": "acquisition/native-n1/rights-review/rights-review-manifest-final.csv",
        "rights_review_manifest_sha256": sha(RIGHTS_MANIFEST),
        "contact_sheet_review": "acquisition/native-n1/rights-review/contact-sheet-review-final.json",
        "contact_sheet_review_sha256": sha(CONTACT_REVIEW),
        "evidence_extracts_sha256": sha(EVIDENCE_EXTRACTS),
        "visual_screening": contacts,
        "privacy_minimization": "Only the selected 30-second video clips are served. Reference RGB arrays exist transiently in the browser; saved frame evidence retains scalar quality values and source IDs, never pixel arrays.",
        "derivative_tool": "tools/derive_native_independent_v11d_content.py",
        "ffmpeg_version": ffmpeg_version,
        "content_capture_groups": len(groups),
        "sources": source_records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"output": str(output), "content_sources": len(source_records),
            "content_capture_groups": len(groups),
            "originals": [{"id": row["candidate_id"], "bytes": row["original_bytes"],
                           "sha256": row["original_sha256"]} for row in source_records],
            "clips": [{"id": row["content_id"], "bytes": row["clip_bytes"],
                       "sha256": row["clip_sha256"]} for row in source_records]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.source_root, args.output), indent=2))


if __name__ == "__main__":
    main()
