"""Metadata-only Commons/Blender discovery and immutable original-capture planning."""

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import time
import unicodedata
import urllib.parse
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from .native_acquisition_audit import EvidenceStore, Page
from .native_panel_assets import LICENSE_URLS, PERMITTED, verify_controller_freeze
from .native_protocol import digest, read_json, require, write_json

NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 = "NATIVE_PANEL_ACQUISITION_DISCOVERY_V2"
MEDIA = re.compile(
    r"\.(mp4|m4v|mov|mkv|mxf|webm|ogv|ogg|avi|mpeg|mpg|yuv|y4m|zip|7z|gz|tar|exr|tiff?|png|jpe?g|wav|mp3|pdf)$",
    re.I,
)


def normalized(value):
    return " ".join(Page(str(value or "")).text.casefold().split())


def title_id(value):
    """Preserve non-Latin title identity; never merge all non-ASCII titles as empty."""
    return "".join(
        character for character in unicodedata.normalize("NFKC", normalized(value)) if character.isalnum()
    )


def source_identity(uri):
    parsed = urllib.parse.urlsplit(uri)
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query)
        if not key.casefold().startswith("utm_")
    ]
    return urllib.parse.urlunsplit(
        (
            "https",
            parsed.netloc.casefold(),
            urllib.parse.unquote(parsed.path).rstrip("/"),
            urllib.parse.urlencode(sorted(query)),
            "",
        )
    )


def hash_object(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ContactOpener:
    def __init__(self, inner, config):
        self.inner, self.config, self.last = inner, config, 0

    def open(self, request, **kwargs):
        delay = self.config["minimum_request_interval_seconds"] - (time.monotonic() - self.last)
        if delay > 0:
            time.sleep(delay)
        request.add_header("User-Agent", self.config["user_agent"])
        self.last = time.monotonic()
        return self.inner.open(request, **kwargs)


class MetadataStore(EvidenceStore):
    def __init__(self, out, config, seed=None, offline=False):
        super().__init__(out, config)
        self.opener = ContactOpener(self.opener, config)
        self.offline = offline
        if seed:
            root = Path(seed)
            require(
                read_json(root / "protocol.json")["abi"] == NATIVE_PANEL_ACQUISITION_DISCOVERY_V2,
                "Discovery V2 seed required",
            )
            existing = read_json(root / "evidence.json")
            self.receipts = existing["receipts"]
            self.total, self.calls = existing["metadata_response_bytes"], existing["metadata_requests"]
            for receipt in self.receipts.values():
                if receipt["status"] != "preserved":
                    continue
                relative = Path(receipt["path"])
                require(
                    relative.parent == Path("evidence")
                    and not relative.is_absolute()
                    and relative.suffix == ".txt",
                    "text-only safe seed evidence path required",
                )
                require(digest(root / relative) == receipt["sha256"], "seed evidence SHA256 drift")
                shutil.copyfile(root / relative, self.out / relative)
                receipt["readable_path"] = str(relative.with_name(relative.stem + ".readable.txt"))
                (self.out / receipt["readable_path"]).write_text(Page(self.text(receipt)).text)

    def get(self, url):
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
        require(not MEDIA.search(path), "all media/binary body GETs forbidden in Discovery V2")
        return super().get(url)


def protocol(path):
    config = read_json(path)
    capture = config["capture_plan"]
    require(
        config["abi"] == NATIVE_PANEL_ACQUISITION_DISCOVERY_V2
        and config["target_independent_units"] == 96
        and config["minimum_duration_seconds"] == 80
        and set(config["allowed_licenses"]) == PERMITTED
        and config["media_download_budget_bytes"] == 0
        and config["minimum_request_interval_seconds"] >= 1
        and 0 < config["maximum_single_text_bytes"] <= 2097152
        and 0 < config["maximum_total_text_bytes"] <= 67108864
        and 0 < config["maximum_metadata_requests"] <= 256
        and 0 < config["commons"]["batch_size"] <= 10,
        "frozen N/duration/rights and bounded zero-media discovery required",
    )
    require(
        capture["reserve_slots"] == 96
        and capture["duration_seconds"] >= 80
        and capture["license_type"] in PERMITTED
        and capture["planned_targets_are_not_measured_strata"] is True
        and capture["planned_slots_are_not_eligible_units"] is True
        and capture["no_excerpts_as_independent_units"] is True,
        "immutable independent-capture planning contract required",
    )
    return config


def commons_url(config, query, continuation=None):
    args = dict(
        action="query",
        format="json",
        formatversion="2",
        generator="search",
        gsrnamespace="6",
        gsrsearch=query,
        gsrlimit=str(config["commons"]["batch_size"]),
        prop="videoinfo|revisions",
        viprop="url|size|mime|user|timestamp|extmetadata|metadata|derivatives|sha1",
        rvprop="ids|timestamp|content",
        rvslots="main",
        maxlag="5",
    )
    args.update(continuation or {})
    return config["commons"]["api"] + "?" + urllib.parse.urlencode(args)


def get_json(store, url):
    receipt = store.get(url)
    if receipt["status"] != "preserved":
        return {}, receipt, receipt.get("error", "unresolved HTTP metadata")
    try:
        data = json.loads(store.text(receipt))
        return data, receipt, data.get("error")
    except (json.JSONDecodeError, AttributeError):
        return {}, receipt, "invalid metadata JSON"


def allowed_license(identifier, url):
    parsed = urllib.parse.urlsplit(url if "://" in str(url) else "https:" + str(url))
    path = parsed.path.rstrip("/")
    path = re.sub(r"/(deed|legalcode)(\.[a-z_-]+)?$", "", path)
    canonical = "https://creativecommons.org" + path + "/"
    kind = next((kind for kind, value in LICENSE_URLS.items() if value == canonical), None)
    aliases = {
        "CC-BY-4.0": {"cc-by-4.0", "cc by 4.0"},
        "CC-BY-3.0": {"cc-by-3.0", "cc by 3.0"},
        "CC0-1.0": {"cc0", "cc-zero", "cc0 1.0", "cc0-1.0"},
    }
    if (
        parsed.hostname != "creativecommons.org"
        or parsed.scheme not in ("http", "https")
        or not kind
        or normalized(identifier) not in aliases[kind]
    ):
        return None, None
    return kind, canonical


def base_record(source, asset_id, title, receipt):
    return dict(
        asset_id=asset_id,
        source=source,
        source_title=title,
        title_id=title_id(title),
        creator=None,
        uploader=None,
        source_uri=receipt["url"],
        source_urls=[],
        creation_capture_metadata={},
        capture_cluster_id=None,
        event_id=None,
        license_type=None,
        license_url=None,
        license_evidence_sha256=None,
        license_evidence=[],
        rights_unit_id=None,
        rights_cleared=False,
        provenance_status="unresolved",
        representations=[],
        duration_seconds=None,
        original_sha256=None,
        normalized_sha256=None,
        media_probe_verified=False,
        independence_reviewed=False,
        source_cluster_id=None,
        synthetic_or_real="unknown",
        spatial_complexity=None,
        temporal_complexity=None,
        content_stratum=None,
        network_panel_split=None,
        fully_verified_eligible=False,
        blocking_reasons=[],
    )


def source_review_evidence(wikitext):
    """Accept only a completed, named and dated review, never an empty pending tag."""
    start = re.search(r"\{\{\s*LicenseReview\s*\|", wikitext, re.I)
    if not start:
        return None
    depth, end = 0, None
    for token in re.finditer(r"\{\{|\}\}", wikitext[start.start() : start.start() + 4096]):
        depth += 1 if token.group() == "{{" else -1
        if depth == 0:
            end = start.start() + token.end()
            break
    if end is None:
        return None
    template = wikitext[start.start() : end]
    if re.search(
        r"failed|rejected|pending|reviewed\s*=\s*(?:no|false)|(?:review|status)\s*=\s*(?:fail|no)",
        template,
        re.I,
    ):
        return None
    reviewer = re.search(r"\|\s*user\s*=\s*([^|{}\n]+)", template, re.I)
    date = re.search(r"\|\s*date\s*=\s*(\d{4}-\d{2}-\d{2})(?=\s*[|}])", template, re.I)
    if not reviewer or not date or normalized(reviewer.group(1)) in {"unknown", "none", "pending"}:
        return None
    try:
        datetime.strptime(date.group(1), "%Y-%m-%d")
    except ValueError:
        return None
    return dict(
        reviewer=reviewer.group(1).strip(),
        date=date.group(1),
        binding_template=template,
        source_review_is_not_native_import_review=True,
    )


def catalog_fps(info):
    values = {}

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if isinstance(value.get("value"), list):
                visit(value["value"])
            elif "name" in value:
                values[str(value["name"]).casefold()] = value.get("value")

    visit(info.get("metadata", []))
    for key in ("framerate", "frame_rate", "frame rate", "fps"):
        raw = info.get(key) or values.get(key)
        if raw is not None:
            try:
                pieces = str(raw).split("/")
                rate = float(pieces[0]) / (float(pieces[1]) if len(pieces) == 2 else 1)
                if 0 < rate <= 1000 and math.isfinite(rate):
                    return rate
            except (ValueError, ZeroDivisionError):
                pass
    try:
        rate = float(values["frn"]) / float(values["frd"])
        return rate if 0 < rate <= 1000 and math.isfinite(rate) else None
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return None


def commons_record(page, receipt, production_slugs=()):
    infos = page.get("videoinfo", [])
    if not infos:
        return None
    info = infos[0]
    duration = info.get("duration")
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 80:
        return None
    meta = {key: value.get("value", "") for key, value in info.get("extmetadata", {}).items()}
    revision = (page.get("revisions") or [{}])[0]
    slot = revision.get("slots", {}).get("main", {})
    wikitext = slot.get("content", slot.get("*", ""))
    title = Page(meta.get("ObjectName") or page["title"].removeprefix("File:")).text
    record = base_record("Wikimedia Commons", "commons-" + str(page["pageid"]), title, receipt)
    credit = str(meta.get("Credit", ""))
    source_urls = [
        urllib.parse.urljoin("https://commons.wikimedia.org/", link["href"])
        for link in Page(credit).links
        if link["href"].startswith(("http:", "https:"))
    ]
    artist = Page(str(meta.get("Artist", ""))).text.strip()
    own = normalized(credit) == "own work" and bool(
        re.search(r"\|\s*source\s*=\s*\{\{\s*own(?:\s*\||\s*\}\})", wikitext, re.I)
    )
    creator_known = bool(artist and normalized(artist) not in ("unknown", "anonymous", "unknown author"))
    kind, canonical = allowed_license(
        meta.get("License") or meta.get("LicenseShortName"), meta.get("LicenseUrl", "")
    )
    record.update(
        creator=artist or None,
        uploader=info.get("user"),
        file_title=page["title"],
        page_id=page["pageid"],
        revision_id=revision.get("revid"),
        revision_timestamp=revision.get("timestamp"),
        source_uri=info.get("descriptionurl"),
        source_urls=source_urls,
        original_source_credit_html=credit,
        description=Page(str(meta.get("ImageDescription", ""))).text,
        creation_capture_metadata={
            k: meta[k] for k in ("DateTimeOriginal", "DateTime", "Event", "Location") if meta.get(k)
        },
        event_id=meta.get("Event") or None,
        reported_media_sha1=info.get("sha1"),
        duration_seconds=duration,
        fps=catalog_fps(info),
        license_type=kind or str(meta.get("LicenseShortName") or meta.get("License") or "unknown"),
        license_url=canonical or meta.get("LicenseUrl"),
        synthetic_or_real="unreviewed",
        declared_restrictions=Page(str(meta.get("Restrictions", ""))).text,
    )
    production = None
    if "blender" in normalized(artist) or any("blender.org" in url for url in source_urls):
        for slug in production_slugs:
            if title_id(slug) in title_id(title):
                production = slug
                record.update(
                    title_id=title_id(slug),
                    source_title=slug,
                    known_production=slug,
                    synthetic_or_real="animated",
                )
                break
    review = source_review_evidence(wikitext)
    mixed_components = bool(
        re.search(
            r"music\s*:|soundtrack|third.party|gameplay|video game|clips? from",
            artist + " " + record["description"],
            re.I,
        )
    )
    provenance = own or bool(review and source_urls)
    record["source_license_review"] = review
    record["component_rights_review_required"] = bool(mixed_components and not review)
    record["provenance_status"] = (
        "named_creator_and_dated_source_license_review"
        if review and source_urls
        else "explicit_own_work_with_named_creator_and_revision"
        if own and creator_known and revision.get("revid")
        else "external_or_incomplete_provenance_review_required"
    )
    record["rights_cleared"] = bool(
        kind
        and provenance
        and creator_known
        and revision.get("revid")
        and not record["declared_restrictions"]
        and not record["component_rights_review_required"]
    )
    if record["component_rights_review_required"]:
        record["provenance_status"] = "contributor_or_component_grants_need_review"
    scope = dict(
        file_title=page["title"],
        page_id=page["pageid"],
        revision_id=revision.get("revid"),
        extmetadata=info.get("extmetadata", {}),
        wikitext=wikitext,
    )
    proof_hash = hash_object(scope)
    record.update(
        license_evidence_sha256=receipt.get("sha256"),
        license_scope_sha256=proof_hash,
        rights_unit_id="rights-commons-" + proof_hash[:24],
        license_retrieved_at=receipt.get("retrieved_at_utc"),
        license_evidence=[
            dict(
                url=receipt["url"],
                path=receipt.get("path"),
                sha256=receipt.get("sha256"),
                page_id=page["pageid"],
                revision_id=revision.get("revid"),
                scope_sha256=proof_hash,
                license_identifier=meta.get("License"),
                license_url=meta.get("LicenseUrl"),
                creator_html=meta.get("Artist"),
                source_credit_html=credit,
                is_native_import_review=False,
            )
        ],
    )
    record["representations"] = [
        dict(
            uri=info["url"],
            role="Commons original file; not proof of original-camera/master lineage",
            duration_seconds=duration,
            resolution=[info.get("width"), info.get("height")],
            fps=record["fps"],
            format=info.get("mime"),
            approximate_bytes=info.get("size"),
            bytes_basis="Commons videoinfo catalog; not downloaded/probed",
            selected=True,
        )
    ]
    record["native_import_rights_verified"] = False
    record["known_production"] = production
    return record


def enumerate_commons(store, config):
    pages, records, progress = {}, {}, []
    for query in config["commons"]["search_queries"]:
        continuation = None
        seen_continuations = set()
        for batch in range(config["commons"]["maximum_batches_per_query"]):
            if len(pages) >= config["commons"]["maximum_enumerated_files"]:
                break
            data, receipt, error = get_json(store, commons_url(config, query, continuation))
            batch_pages = data.get("query", {}).get("pages", [])
            progress.append(
                dict(
                    query=query,
                    batch=batch,
                    url=receipt["url"],
                    evidence_sha256=receipt.get("sha256"),
                    returned_files=len(batch_pages),
                    error=error,
                )
            )
            if error:
                break
            for page in batch_pages:
                key = str(page["pageid"])
                candidate = commons_record(page, receipt)
                if key in pages and candidate and key in records:
                    old = records[key]
                    if old.get("revision_id") != candidate.get("revision_id") or old.get(
                        "reported_media_sha1"
                    ) != candidate.get("reported_media_sha1"):
                        old.update(
                            rights_cleared=False, provenance_status="revision_or_media_drift_between_queries"
                        )
                elif len(pages) < config["commons"]["maximum_enumerated_files"]:
                    pages[key] = page
                    if candidate:
                        records[key] = candidate
            continuation = data.get("continue")
            if not continuation or not batch_pages:
                break
            token = hash_object(continuation)
            require(token not in seen_continuations, "Commons repeated continuation token")
            seen_continuations.add(token)
    return list(records.values()), progress, len(pages)


def movie_catalog(store, config):
    receipt = store.get(config["blender"]["catalog_url"])
    entries = {}
    for link in Page(store.text(receipt)).links:
        match = re.fullmatch(r"/projects/([a-z0-9-]+)/", link["href"])
        text = Page(link["text"]).text
        if match and "Showcase" not in text:
            slug = match.group(1)
            entries[slug] = dict(
                slug=slug,
                uri=urllib.parse.urljoin(config["blender"]["catalog_url"], link["href"]),
                catalog_text=text,
                in_development="In Development" in text,
            )
    return list(entries.values())[: config["blender"]["maximum_productions"]], receipt


def publisher_grant(body, title):
    page = Page(body)
    text = " ".join(page.text.split())
    name = re.escape(title)
    subject = (
        r"(?:results of the [^.]{0,160}(?:movie|Peach)[^.]{0,60}project|(?:this|the) (?:film|movie|production)|(?:the )?work of (?:the )?"
        + name
        + r" project|"
        + name
        + r"(?::[^.]{0,70}?)?(?: open)?(?: movie| film)?)"
    )
    explicit = re.search(
        subject
        + r" (?:are being|has been|is|are|was) (?:licensed|released) (?:under|un) (?:the )?[^.]{0,160}?(?:Attribution (?:1\.0|2\.0|2\.5|3\.0|4\.0)|CC[- ]BY(?:[- ]ND|[- ]SA|[- ]NC(?:[- ]SA)?)?(?:\s*(?:1\.0|2\.0|2\.5|3\.0|4\.0))?)",
        text,
        re.I,
    )
    if not explicit:
        return None, None, "production_license_scope_not_explicit"
    if normalized(title) not in normalized(text) and not any(
        value in text for value in ("Peach", "Durian", "Mango", "Orange")
    ):
        return None, None, "production_membership_not_bound"
    quote = explicit.group()
    version = re.search(r"[1-4]\.[05]", quote)
    suffix = re.search(r"CC[- ]BY[- ](ND|SA|NC(?:[- ]SA)?)", quote, re.I)
    family = "CC-BY" + ("-" + suffix.group(1).upper().replace(" ", "-") if suffix else "")
    if not version:
        target = "licenses/" + family.removeprefix("CC-").lower() + "/"
        links = [
            link["href"]
            for link in page.links
            if urllib.parse.urlsplit(link["href"]).hostname == "creativecommons.org"
            and target in link["href"]
        ]
        versions = {re.search(r"[1-4]\.[05]", url).group() for url in links if re.search(r"[1-4]\.[05]", url)}
        if len(versions) != 1:
            return family, None, "publisher_license_version_unresolved"
        value = versions.pop()
    else:
        value = version.group()
    return family + "-" + value, quote, None


def declared_license_url(kind):
    parts = kind.lower().removeprefix("cc-").rsplit("-", 1)
    return (
        "https://creativecommons.org/licenses/" + parts[0] + "/" + parts[1] + "/" if len(parts) == 2 else None
    )


def directory_representations(store, url):
    receipt = store.get(url)
    body = store.text(receipt)
    result = []
    for link in Page(body).links:
        if not re.search(r"\.(mp4|mov|mkv|webm|avi|zip)$", link["href"], re.I):
            continue
        size = re.search(
            r'href="' + re.escape(link["href"]) + r'"[^>]*>.*?</a>[^\n]*?\s(\d+)\s*(?:\n|$)', body, re.I
        )
        result.append(
            dict(
                uri=urllib.parse.urljoin(url, link["href"]),
                role="publisher downloadable representation; duration not yet bound",
                duration_seconds=None,
                resolution=None,
                fps=None,
                format=link["href"].rsplit(".", 1)[-1],
                approximate_bytes=int(size.group(1)) if size else None,
                bytes_basis="publisher directory index" if size else "unknown",
                selected=False,
                metadata_evidence_sha256=receipt.get("sha256"),
            )
        )
    return result


def enumerate_blender(store, config):
    entries, catalog_receipt = movie_catalog(store, config)
    directory = directory_representations(store, config["blender"]["downloads_url"])
    grants = {}
    for uri in config["blender"]["source_copyright_pages"]:
        proof = store.get(uri)
        grants[uri] = (proof, store.text(proof))
    aliases = {
        "big-buck-bunny": ["bigbuckbunny", "bbb"],
        "tears-of-steel": ["tearsofsteel", "tos"],
        "elephants-dream": ["elephantsdream"],
    }
    legacy = {
        "big-buck-bunny": "peach.blender.org",
        "sintel": "durian.blender.org",
        "tears-of-steel": "mango.blender.org",
        "elephants-dream": "orange.blender.org",
    }
    result, auxiliary = [], []
    auxiliary_batches = 0
    for entry in entries:
        slug = entry["slug"]
        record = base_record("Blender Open Movies", "blender-" + slug, slug, catalog_receipt)
        record.update(
            creator="Blender Studio / production credits; contributor review pending",
            uploader="publisher",
            source_uri=entry["uri"],
            source_urls=[entry["uri"]],
            synthetic_or_real="animated",
            production_status="in_development" if entry["in_development"] else "listed_production",
            provenance_status="publisher_distinct_production; shared_asset_lineage_review_pending",
        )
        proof = store.get(entry["uri"])
        body = store.text(proof)
        candidates = [(proof, body)]
        for link in Page(body).links:
            if len(candidates) >= 4:
                break
            if (
                re.search(r"copyright|sharing|open content|license", link["text"], re.I)
                or normalized(link["text"]) == "about"
            ) and not link["href"].startswith(("javascript:", "#")):
                uri = urllib.parse.urljoin(entry["uri"], link["href"])
                if urllib.parse.urlsplit(uri).hostname in config["allowed_text_hosts"]:
                    linked = store.get(uri)
                    candidates.append((linked, store.text(linked)))
        if slug in legacy:
            candidates.extend(value for uri, value in grants.items() if legacy[slug] in uri)
        for receipt, text in candidates:
            kind, quote, _ = publisher_grant(text, slug.replace("-", " "))
            if kind and receipt["status"] == "preserved":
                record.update(
                    license_type=kind,
                    license_url=declared_license_url(kind),
                    rights_cleared=kind in PERMITTED,
                    license_evidence_sha256=receipt["sha256"],
                    rights_unit_id="rights-" + hash_object([receipt["sha256"], slug])[:24],
                    license_retrieved_at=receipt["retrieved_at_utc"],
                )
                record["license_evidence"].append(
                    dict(
                        url=receipt["url"],
                        path=receipt["path"],
                        sha256=receipt["sha256"],
                        binding_quote=quote,
                        scope="publisher declaration for this production; native importer review still required",
                    )
                )
                break
        names = [title_id(slug)] + aliases.get(slug, [])
        record["representations"] = [
            rep.copy()
            for rep in directory
            if any(name in title_id(urllib.parse.urlsplit(rep["uri"]).path) for name in names)
        ]
        if not entry["in_development"] and auxiliary_batches < config["commons"]["maximum_auxiliary_batches"]:
            query = 'filetype:video "' + slug.replace("-", " ") + '" "Blender"'
            data, receipt, error = get_json(store, commons_url(config, query))
            auxiliary_batches += 1
            for page in data.get("query", {}).get("pages", []) if not error else []:
                mirror = commons_record(page, receipt, [slug])
                if mirror and mirror.get("known_production") == slug:
                    auxiliary.append(mirror)
                    if not re.search(
                        r"trailer|teaser|making.?of|behind.the.scenes|documentary|interview|commentary|in.progress",
                        mirror["file_title"],
                        re.I,
                    ):
                        record["representations"].append(
                            dict(
                                **mirror["representations"][0],
                                publisher_master_verified=False,
                                mirrored_file_title=mirror["file_title"],
                                metadata_evidence_sha256=receipt.get("sha256"),
                            )
                        )
        known = [
            rep
            for rep in record["representations"]
            if rep.get("duration_seconds", 0) is not None and rep.get("duration_seconds", 0) >= 80
        ]
        if known:
            selected = min(known, key=lambda rep: rep.get("approximate_bytes") or math.inf)
            selected["selected"] = True
            record["duration_seconds"] = selected["duration_seconds"]
        result.append(record)
    return result, auxiliary


def reconcile_publisher_rights(records):
    """Do not let a reviewed mirror override an explicit incompatible producer grant."""
    publishers = {
        title_id(row["source_title"]): row
        for row in records
        if row["source"] == "Blender Open Movies" and row.get("license_type")
    }
    for row in records:
        if row["source"] != "Wikimedia Commons":
            continue
        producer = publishers.get(title_id(row.get("known_production") or row["source_title"]))
        if (
            producer
            and producer["license_evidence"]
            and (producer["license_type"] not in PERMITTED or row["license_type"] != producer["license_type"])
        ):
            row.update(
                rights_cleared=False,
                provenance_status="publisher_and_mirror_license_scope_or_version_conflict",
                publisher_rights_conflict_evidence=producer["license_evidence"],
            )


def cluster_records(records, config):
    parent = list(range(len(records)))
    owners, tokens_by_record, collisions = {}, [], []

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, record in enumerate(records):
        tokens = {"title:" + record["title_id"]}
        if record.get("reported_media_sha1"):
            tokens.add("reported-media-sha1:" + record["reported_media_sha1"])
        for key in ("event_id", "capture_cluster_id"):
            if record.get(key):
                tokens.add(key + ":" + normalized(record[key]))
        for uri in record.get("source_urls", []):
            tokens.add("source:" + source_identity(uri))
        if (
            record["source"] == "Wikimedia Commons"
            and record.get("creator")
            and not record.get("known_production")
        ):
            # Without independently reviewed sessions, one creator's uploads are one conservative provisional family.
            tokens.add("unreviewed-creator:" + normalized(record["creator"]))
        franchise = config["blender"]["shared_franchise_lineage"].get(
            record.get("known_production") or record["source_title"]
        )
        if franchise:
            tokens.add("shared-production-lineage:" + franchise)
        tokens_by_record.append(tokens)
        for token in sorted(tokens):
            if token in owners and root(i) != root(owners[token]):
                collisions.append(
                    dict(token=token, left=records[owners[token]]["asset_id"], right=record["asset_id"])
                )
                parent[root(i)] = root(owners[token])
            owners[token] = i
    components = defaultdict(set)
    for i, tokens in enumerate(tokens_by_record):
        components[root(i)].update(tokens)
    for i, record in enumerate(records):
        record["source_cluster_id"] = "candidate-" + hash_object(sorted(components[root(i)]))[:24]
        record["cluster_tokens"] = sorted(tokens_by_record[i])
        record["previously_exposed_title"] = record["title_id"] in config["previously_exposed_title_ids"]
        record["duration_qualified"] = (
            record["duration_seconds"] is not None and record["duration_seconds"] >= 80
        )
        record["planning_candidate"] = (
            record["rights_cleared"]
            and record["duration_qualified"]
            and not record["previously_exposed_title"]
            and record.get("production_status") != "in_development"
        )
        record["blocking_reasons"] = [
            "actual_original_and_normalized_sha256_missing",
            "native_media_probe_not_performed",
            "independent_capture_or_asset_lineage_review_pending",
            "owned_quantitative_complexity_unmeasured",
        ]
        if not record["rights_cleared"]:
            record["blocking_reasons"].append("explicit_license_or_provenance_not_cleared")
        if not record["duration_qualified"]:
            record["blocking_reasons"].append(">=80_second_representation_not_bound")
        if record["previously_exposed_title"]:
            record["blocking_reasons"].append("previously_exposed_title")
    exposed = {record["source_cluster_id"] for record in records if record["previously_exposed_title"]}
    for record in records:
        if record["source_cluster_id"] in exposed:
            record["planning_candidate"] = False
            record["blocking_reasons"].append("cluster_contains_previously_exposed_title")
    return collisions


def capture_plan(config, verified_deficit, conditional_deficit):
    settings = config["capture_plan"]
    axes = [
        ("low", "low"),
        ("medium", "medium"),
        ("high", "high"),
        ("low", "medium"),
        ("medium", "high"),
        ("high", "low"),
        ("low", "high"),
        ("medium", "low"),
        ("high", "medium"),
    ]
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, settings["namespace"])
    rows = []
    for index in range(96):
        spatial, temporal = axes[index % len(axes)]
        identifier = "NPA2-CAP-" + str(uuid.uuid5(namespace, str(index + 1)))
        rows.append(
            dict(
                capture_id=identifier,
                receipt_id=identifier + "-rights-v1",
                planned_session_id=identifier + "-session",
                source_title=identifier,
                status="planned_only_not_eligible",
                planned_spatial_target=spatial,
                planned_temporal_target=temporal,
                planned_duration_seconds=settings["duration_seconds"],
                planned_resolution=settings["resolution"],
                planned_fps=settings["fps"],
                conditional_priority=index < conditional_deficit,
                operational_reserve=index < verified_deficit,
                actual_capture_session_id=None,
                actual_event_id=None,
                independent_scene_source_id=None,
                creator=None,
                owner=None,
                captured_at_utc=None,
                creation_capture_metadata=None,
                source_uri=None,
                original_sha256=None,
                normalized_sha256=None,
                license_type=settings["license_type"],
                license_url=LICENSE_URLS[settings["license_type"]],
                rights_evidence_sha256=None,
                contributor_and_location_releases=[],
                independent_capture_reviewed=False,
                measured_spatial_complexity=None,
                measured_temporal_complexity=None,
                actual_content_stratum=None,
                fully_verified_eligible=False,
            )
        )
    matrix = {
        spatial: {
            temporal: sum(
                r["planned_spatial_target"] == spatial and r["planned_temporal_target"] == temporal
                for r in rows
            )
            for temporal in ("low", "medium", "high")
        }
        for spatial in ("low", "medium", "high")
    }
    seconds = settings["duration_seconds"] * verified_deficit
    original = [int(seconds * bitrate * 10**6 / 8) for bitrate in settings["source_bitrate_mbps_bounds"]]
    normalized_sizes = [
        int(seconds * bitrate * 10**6 / 8) for bitrate in settings["normalized_bitrate_mbps_bounds"]
    ]
    return dict(
        abi=NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 + "_capture_plan",
        plan_sha256=hash_object(rows),
        immutable_namespace=settings["namespace"],
        verified_deficit=verified_deficit,
        conditional_deficit_after_metadata_clearance=conditional_deficit,
        matrix=matrix,
        captures=rows,
        spatial_recipes=dict(
            low="plain background, few edges/objects; separate genuine scene/session",
            medium="mixed indoor/outdoor detail",
            high="dense texture/foliage/architecture; diverse sources",
        ),
        temporal_recipes=dict(
            low="tripod/static or slow movement",
            medium="ordinary walking/moderate object or camera motion",
            high="fast independent action/panning/object motion",
        ),
        targets_are_not_measured_strata=True,
        acquisition_or_rights_grants_created=False,
        receipt_requirements=[
            "actual session/event/scene provenance and start/end UTC",
            "named creator AND copyright owner; work-for-hire/contributor review",
            "explicit CC BY 4.0 grant bound to immutable capture ID and real media hash",
            "signed contributor/property/person release references where needed",
            "no third-party footage/music; silent capture preferred",
            "actual duration >=80s and unpadded original; 120s planned",
            "native H264 normalization/probe and actual SHA256",
            "independent-session/source review; shared session/event/lineage merges, excerpts never new units",
            "owned preassignment spatial/temporal measurements; targets may fail/quarantine",
            "seal full pool before source-disjoint network-panel split",
        ],
        projected_original_bytes_bounds=original,
        projected_normalized_bytes_bounds=normalized_sizes,
        projected_original_plus_normalized_bytes_bounds=[original[i] + normalized_sizes[i] for i in range(2)],
        encoded_outputs_logs_and_replay_bytes=None,
        conditional_activation_requires_verified_source_pool=True,
    )


def report(records, config, collisions, enumeration_count, progress):
    sources = {}
    for source in sorted({r["source"] for r in records}):
        rows = [r for r in records if r["source"] == source]
        sources[source] = dict(
            discovered_candidates=len(rows),
            rights_cleared_candidates=sum(r["rights_cleared"] for r in rows),
            rights_cleared_candidate_clusters=len(
                {r["source_cluster_id"] for r in rows if r["rights_cleared"]}
            ),
            fresh_rights_and_duration_candidate_clusters=len(
                {r["source_cluster_id"] for r in rows if r["planning_candidate"]}
            ),
            fully_verified_eligible_independent_units=0,
            unresolved_rights_cases=sum(not r["rights_cleared"] for r in rows),
        )
    planning = {r["source_cluster_id"] for r in records if r["planning_candidate"]}
    selected = {}
    for row in records:
        if row["planning_candidate"]:
            for representation in row["representations"]:
                if representation["selected"]:
                    selected[representation["uri"]] = representation.get("approximate_bytes")
    representatives = {}
    for record in records:
        if not record["planning_candidate"]:
            continue
        candidates = [
            r for r in record["representations"] if r["selected"] and r.get("approximate_bytes") is not None
        ]
        if candidates:
            size = min(r["approximate_bytes"] for r in candidates)
            representatives[record["source_cluster_id"]] = min(
                size, representatives.get(record["source_cluster_id"], size)
            )
    return dict(
        abi=NATIVE_PANEL_ACQUISITION_DISCOVERY_V2,
        target_independent_units=96,
        minimum_duration_seconds=80,
        source_counts=sources,
        commons_enumerated_files=enumeration_count,
        discovered_candidates=len(records),
        rights_cleared_candidates=sum(r["rights_cleared"] for r in records),
        fully_verified_eligible_independent_units=0,
        fresh_rights_and_duration_candidate_cluster_upper_bound=len(planning),
        verified_deficit_to_96=96,
        conditional_deficit_if_all_metadata_candidates_verify=max(0, 96 - len(planning)),
        cluster_collision_edges=len(collisions),
        unresolved_rights_cases=sum(not r["rights_cleared"] for r in records),
        stratum_coverage=dict(
            measured_low=0,
            measured_medium=0,
            measured_high=0,
            spatial_temporal_cells_measured=0,
            unmeasured_candidate_clusters=len(planning),
        ),
        estimated_download_bytes_known_cluster_representatives=sum(representatives.values()),
        missing_cluster_representative_sizes=len(planning) - len(representatives),
        estimated_retained_candidate_files_bytes=sum(v for v in selected.values() if v is not None),
        unknown_candidate_file_sizes=sum(v is None for v in selected.values()),
        normalized_outputs_logs_and_replay_volume=None,
        discovery_is_bounded_not_exhaustive=True,
        search_progress=progress,
        creator_only_merges_are_conservative_for_unreviewed_commons_not_proof_of_dependence=True,
        no_media_downloaded=True,
        media_bytes_downloaded=0,
        models_trained=False,
        policy_promoted=False,
        eligibility_requires_external_frozen_ingestion_and_native_probe=True,
    )


def capture_receipt_schema(plan):
    strings = {
        key: {"type": "string", "minLength": 1}
        for key in (
            "capture_id",
            "receipt_id",
            "capture_session_id",
            "event_id",
            "independent_scene_source_id",
            "creator",
            "copyright_owner",
            "source_uri",
            "owner_signature_reference",
        )
    }
    hashes = {
        key: {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        for key in (
            "original_sha256",
            "normalized_sha256",
            "license_evidence_sha256",
            "native_probe_evidence_sha256",
            "complexity_measurement_evidence_sha256",
        )
    }
    properties = dict(
        **strings,
        **hashes,
        abi={"const": NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 + "_capture_receipt"},
        status={"const": "signed_actual_capture_receipt"},
        license_type={"const": "CC-BY-4.0"},
        license_url={"const": LICENSE_URLS["CC-BY-4.0"]},
        actual_duration_seconds={"type": "number", "minimum": 80},
        captured_start_utc={"type": "string", "format": "date-time"},
        captured_end_utc={"type": "string", "format": "date-time"},
        signed_at_utc={"type": "string", "format": "date-time"},
        independent_capture_reviewed={"const": True},
        padded_or_looped={"const": False},
        release_evidence_refs={"type": "array", "items": {"type": "string", "minLength": 1}},
    )
    properties["capture_id"] = {"enum": [row["capture_id"] for row in plan["captures"]]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Original capture rights/provenance receipt, not a planned grant",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
        "x-capture-plan-sha256": plan["plan_sha256"],
        "x-unsigned-planned-receipts-do-not-validate": True,
        "x-native-eligible-promotion-requires-frozen-ingestion-review": True,
    }


def capture_receipt_templates(plan):
    schema = capture_receipt_schema(plan)
    templates = []
    for row in plan["captures"]:
        receipt = {key: None for key in schema["properties"]}
        receipt.update(
            abi=NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 + "_capture_receipt",
            capture_id=row["capture_id"],
            receipt_id=row["receipt_id"],
            status="unsigned_plan_template",
            license_type="CC-BY-4.0",
            license_url=LICENSE_URLS["CC-BY-4.0"],
            independent_capture_reviewed=False,
            padded_or_looped=False,
            release_evidence_refs=[],
        )
        templates.append(receipt)
    return dict(plan_sha256=plan["plan_sha256"], receipts=templates, grants_created=0, eligible_units=0)


def export_csv(path, records):
    fields = [
        "asset_id",
        "source",
        "file_title",
        "source_title",
        "creator",
        "uploader",
        "source_uri",
        "source_urls",
        "duration_seconds",
        "resolution",
        "file_size",
        "license_type",
        "license_url",
        "license_evidence_sha256",
        "rights_unit_id",
        "source_cluster_id",
        "capture_cluster_id",
        "event_id",
        "provenance_status",
        "rights_cleared",
        "planning_candidate",
        "fully_verified_eligible",
        "synthetic_or_real",
        "creation_capture_metadata",
        "original_sha256",
        "normalized_sha256",
        "content_stratum",
        "network_panel_split",
        "blocking_reasons",
    ]
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            selected = next((r for r in record["representations"] if r["selected"]), {})
            row = {field: record.get(field) for field in fields}
            row.update(resolution=selected.get("resolution"), file_size=selected.get("approximate_bytes"))
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                    for key, value in row.items()
                }
            )


def discover(config_path, out, seed=None, offline=False):
    config = protocol(config_path)
    before = verify_controller_freeze()
    require(not Path(out).exists(), "fresh immutable discovery output directory required")
    store = MetadataStore(out, config, seed, offline)
    try:
        commons, progress, enumerated = enumerate_commons(store, config)
        blender, auxiliary = enumerate_blender(store, config)
        by_id = {r["asset_id"]: r for r in commons}
        for record in auxiliary:
            existing = by_id.get(record["asset_id"])
            if existing and (
                existing.get("reported_media_sha1") != record.get("reported_media_sha1")
                or existing.get("revision_id") != record.get("revision_id")
                or existing.get("provenance_status") == "revision_or_media_drift_between_queries"
            ):
                existing.update(rights_cleared=False, provenance_status="media_drift_between_source_queries")
            else:
                by_id[record["asset_id"]] = record
        records = list(by_id.values()) + blender
        reconcile_publisher_rights(records)
        collisions = cluster_records(records, config)
        result = report(records, config, collisions, enumerated, progress)
        result.update(
            generated_at_utc=datetime.now(UTC).isoformat(),
            protocol_sha256=digest(config_path),
            audit_module_sha256=digest(__file__),
            controller_freeze=before,
            metadata_requests=store.calls,
            metadata_response_bytes=store.total,
        )
        plan = capture_plan(config, 96, result["conditional_deficit_if_all_metadata_candidates_verify"])
        write_json(
            store.out / "inventory.json",
            dict(abi=NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 + "_inventory", records=records),
        )
        write_json(
            store.out / "commons_retained.json",
            dict(
                abi=NATIVE_PANEL_ACQUISITION_DISCOVERY_V2 + "_retained",
                records=[r for r in records if r["source"] == "Wikimedia Commons" and r["rights_cleared"]],
            ),
        )
        write_json(store.out / "cluster_collisions.json", dict(collisions=collisions))
        write_json(store.out / "capture_plan.json", plan)
        write_json(store.out / "capture_rights_receipt.schema.json", capture_receipt_schema(plan))
        write_json(store.out / "capture_rights_receipts.json", capture_receipt_templates(plan))
        write_json(store.out / "report.json", result)
        write_json(store.out / "protocol.json", config)
        export_csv(store.out / "inventory.csv", records)
        require(before == verify_controller_freeze(), "frozen controller/model hashes changed")
        return result
    finally:
        store.save()


def snapshot(config_path, out, extra_urls=()):
    config = protocol(config_path)
    before = verify_controller_freeze()
    require(not Path(out).exists(), "fresh snapshot directory required")
    store = MetadataStore(out, config)
    try:
        urls = [
            commons_url(config, config["commons"]["search_queries"][0]),
            config["blender"]["catalog_url"],
            config["blender"]["downloads_url"],
        ] + list(extra_urls)
        for url in urls:
            store.get(url)
        write_json(store.out / "protocol.json", config)
        require(before == verify_controller_freeze(), "frozen controller hashes changed")
        return dict(metadata_bytes=store.total, media_bytes_downloaded=0, freeze=before)
    finally:
        store.save()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "discover"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--out", required=True)
        if name == "snapshot":
            p.add_argument("--url", action="append", default=[])
        else:
            p.add_argument("--snapshots")
            p.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    result = (
        snapshot(args.config, args.out, args.url)
        if args.command == "snapshot"
        else discover(args.config, args.out, args.snapshots, args.offline)
    )
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
