"""Bounded text-only acquisition audit. No media downloader, model or relaxed N."""

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from .native_panel_assets import PERMITTED, verify_controller_freeze
from .native_protocol import digest, read_json, require, write_json

ABI = "native_acquisition_dry_run_v1"
MEDIA_SUFFIX = re.compile(
    r"\.(mp4|mov|mkv|webm|yuv|y4m|zip|gz|bz2|xz|tar|exr|tiff?|png|jpe?g|wav|mp3|pdf)$", re.I
)


class Page(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.links, self.parts = [], []
        self.current, self.skip = None, 0
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if self.skip:
            return
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.current = dict(href=attrs["href"], text="")
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "br"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        self.parts.append(data)
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if self.skip:
            return
        if tag == "a" and self.current is not None:
            self.links.append(self.current)
            self.current = None
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    @property
    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, config):
        self.config = config

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl, self.config)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def allowed_url(url, config):
    parsed = urllib.parse.urlsplit(url)
    require(
        parsed.scheme == "https"
        and parsed.hostname in config["allowed_text_hosts"]
        and not parsed.username
        and not parsed.password
        and parsed.port in (None, 443),
        "unapproved metadata host/scheme",
    )
    require(
        not MEDIA_SUFFIX.search(urllib.parse.unquote(parsed.path))
        or url in config.get("allowed_rights_pdf_urls", []),
        "media/binary GET forbidden in acquisition dry run",
    )
    return url


class EvidenceStore:
    def __init__(self, out, config):
        self.out, self.config = Path(out), config
        self.receipts, self.total, self.calls = {}, 0, 0
        (self.out / "evidence").mkdir(parents=True)
        self.opener = urllib.request.build_opener(SafeRedirect(config))

    def get(self, url):
        if url in self.receipts:
            return self.receipts[url]
        allowed_url(url, self.config)
        if getattr(self, "offline", False):
            raise ValueError("metadata URL absent from offline evidence snapshot")
        require(self.calls < self.config["maximum_metadata_requests"], "metadata request budget exhausted")
        remaining = self.config["maximum_total_text_bytes"] - self.total
        require(remaining > 0, "metadata byte budget exhausted")
        self.calls += 1
        receipt = dict(
            url=url, retrieved_at_utc=datetime.now(UTC).isoformat(), method="GET", media_bytes_downloaded=0
        )
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "networkRLCD-acquisition-audit/1.0",
                    "Accept": "text/html,text/plain,application/json",
                },
            )
            with self.opener.open(req, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
                require(
                    content_type.startswith("text/")
                    or content_type in ("application/json", "application/xml", "application/xhtml+xml")
                    or (
                        url in self.config.get("allowed_rights_pdf_urls", [])
                        and content_type == "application/pdf"
                    )
                    or (
                        any(
                            marker in urllib.parse.urlsplit(url).path.lower()
                            for marker in ("readme", "copyright")
                        )
                        and content_type in ("", "application/octet-stream")
                    ),
                    "non-text metadata response refused before body download",
                )
                limit = min(remaining, self.config["maximum_single_text_bytes"])
                length = response.headers.get("Content-Length")
                require(length is None or int(length) <= limit, "metadata response exceeds byte cap")
                body = response.read(limit)
                self.total += len(body)
                receipt["bytes"] = len(body)
                require(
                    len(body) < limit or (length is not None and int(length) == len(body)),
                    "possibly truncated metadata refused",
                )
                identifier = hashlib.sha256(url.encode()).hexdigest()[:20]
                relative = (
                    "evidence/" + identifier + (".pdf" if content_type == "application/pdf" else ".txt")
                )
                (self.out / relative).write_bytes(body)
                readable = self.out / ("evidence/" + identifier + ".readable.txt")
                if content_type == "application/pdf":
                    subprocess.run(
                        ["pdftotext", "-layout", str(self.out / relative), str(readable)],
                        check=True,
                        timeout=30,
                        capture_output=True,
                    )
                else:
                    readable.write_text(Page(body.decode("utf-8", errors="replace")).text)
                receipt.update(
                    status="preserved",
                    final_url=response.url,
                    content_type=content_type,
                    bytes=len(body),
                    sha256=digest(self.out / relative),
                    path=relative,
                    readable_path="evidence/" + identifier + ".readable.txt",
                )
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            subprocess.SubprocessError,
        ) as error:
            receipt.update(status="unresolved", error=str(error))
        self.receipts[url] = receipt
        return receipt

    def text(self, receipt):
        path = (
            receipt.get("readable_path")
            if receipt.get("content_type") == "application/pdf"
            else receipt.get("path")
        )
        return (self.out / path).read_text(errors="replace") if receipt["status"] == "preserved" else ""

    def save(self):
        write_json(
            self.out / "evidence.json",
            dict(
                abi=ABI + "_evidence",
                receipts=self.receipts,
                metadata_requests=self.calls,
                metadata_response_bytes=self.total,
                media_bytes_downloaded=0,
            ),
        )


def protocol(config_path):
    config = read_json(config_path)
    require(
        config["abi"] == ABI
        and config["target_independent_units"] == 96
        and config["media_download_budget_bytes"] == 0
        and set(config["main_panel_allowed_licenses"]) == PERMITTED
        and config["native_source_minimum_duration_seconds"] == 80
        and config["unknown_capture_provenance_is_not_verified_independence"] is True
        and config["content_strata_require_owned_preassignment_measurement"] is True
        and 0 < config["maximum_metadata_requests"] <= 256
        and 0 < config["maximum_total_text_bytes"] <= 16777216
        and 0 < config["maximum_single_text_bytes"] <= 2097152,
        "unchanged preregistration and bounded text-only budgets required",
    )
    return config


def snapshot(config_path, out):
    config = protocol(config_path)
    verify_controller_freeze()
    out = Path(out)
    require(not out.exists(), "fresh evidence directory required")
    store = EvidenceStore(out, config)
    for source in config["source_pages"]:
        store.get(source["url"])
    store.save()
    write_json(out / "protocol.json", config)
    return dict(
        metadata_requests=store.calls,
        metadata_response_bytes=store.total,
        media_bytes_downloaded=0,
        pages={u: r["status"] for u, r in store.receipts.items()},
        freeze=verify_controller_freeze(),
    )


UVG = "https://ultravideo.fi/UVG-VCM/index.html"
NETFLIX = "https://opencontent.netflix.com/home"
XIPH = "https://media.xiph.org/video/derf/"
ORIGINAL_UVG = "https://ultravideo.fi/dataset.html"
S3 = "https://s3.amazonaws.com/download.opencontent.netflix.com"
TITLES = {
    "SolLevante": "Sol Levante",
    "Nocturne": "Nocturne",
    "sparks": "Sparks",
    "Meridian": "Meridian",
    "CosmosLaundromat": "Cosmos Laundromat",
    "Chimera": "Chimera",
    "ElFuente": "El Fuente",
}


def title_id(title):
    value = re.sub(r"[^a-z0-9]", "", title.casefold())
    return "sintel" if value.startswith("sintel") else value


def candidate(source, title, tier, receipt):
    token = title_id(title)
    return dict(
        asset_id=source.lower().replace(" ", "-") + "-" + token,
        source=source,
        source_title=title,
        title_id=token,
        source_cluster_id="candidate-" + token,
        capture_cluster_id=None,
        independence_status="unreviewed_capture_and_lineage",
        rights_unit_id=None,
        source_uri=receipt["url"],
        license_type=None,
        license_evidence_sha256=None,
        license_retrieved_at=None,
        original_sha256=None,
        normalized_sha256=None,
        synthetic_or_real="unknown",
        content_stratum=None,
        network_panel_split=None,
        tier=tier,
        license_evidence=[],
        representations=[],
        duration_seconds=None,
        rights_status="unresolved",
        metadata_evidence_sha256=receipt.get("sha256"),
        metadata_evidence_uri=receipt["url"],
        media_acquired=False,
        main_panel_eligible=False,
    )


def grant(record, kind, receipt, quote, scope):
    require(receipt["status"] == "preserved" and quote and scope, "preserved explicit grant required")
    previous = record.get("license_type")
    conflict = previous is not None and previous != kind
    record.update(
        license_type=kind,
        rights_status="clear_publisher_grant" if kind in PERMITTED else "restricted_or_nonpermitted",
        rights_unit_id="rights-"
        + hashlib.sha256((receipt["sha256"] + kind + scope).encode()).hexdigest()[:24],
        license_evidence_sha256=receipt["sha256"],
        license_retrieved_at=receipt["retrieved_at_utc"],
    )
    if conflict:
        record.update(
            license_type="LicenseRef-Conflicting-Grants", rights_status="unresolved", rights_unit_id=None
        )
    record["license_evidence"].append(
        dict(
            license_type=kind,
            quote_normalization="whitespace-collapsed extracted text",
            url=receipt["url"],
            path=receipt["path"],
            sha256=receipt["sha256"],
            retrieved_at_utc=receipt["retrieved_at_utc"],
            scope=scope,
            binding_quote=quote,
        )
    )


def identify_license(text):
    flat = " ".join(text.split())
    patterns = [
        ("CC-BY-NC-ND-4.0", r"licenses/by-nc-nd/4\.0"),
        ("CC-BY-NC-ND-3.0", r"licenses/by-nc-nd/3\.0"),
        ("CC-BY-NC-3.0", r"licenses/by-nc/3\.0"),
        ("CC-BY-NC-4.0", r"licenses/by-nc/4\.0"),
        ("CC-BY-ND", r"licenses/by-nd/"),
        ("CC0-1.0", r"publicdomain/zero/1\.0"),
        ("CC-BY-4.0", r"licenses/by/4\.0|CC[- ]BY\s*4\.0|Attribution 4\.0"),
        ("CC-BY-3.0", r"licenses/by/3\.0|CC[- ]BY\s*3\.0|Attribution 3\.0"),
    ]
    for kind, pattern in patterns:
        match = re.search(pattern, flat, re.I)
        if match:
            return kind, flat[max(0, match.start() - 160) : match.end() + 240]
    restrictions = [
        (
            "LicenseRef-SVT-Standards-Only-2006",
            r"only be used for the purpose of developing, testing and presenting technology standards",
        ),
        ("LicenseRef-NTIA-Research-Only-2008", r"research purposes, only"),
        ("LicenseRef-Research-Only", r"research purpose only|research purposes only"),
        ("LicenseRef-No-Copyright-Assertion", r"Copyright: No Copyright"),
    ]
    for kind, pattern in restrictions:
        match = re.search(pattern, flat, re.I)
        if match:
            return kind, flat[max(0, match.start() - 180) : match.end() + 300]
    return None, None


def is_video_object(key):
    if not re.search(r"\.(mp4|mov|mxf|y4m|yuv)$", key, re.I):
        return False
    if any(folder in key.casefold() for folder in ("/working_assets/", "/ocf/", "/audio/", "/atmos/")):
        return False
    # A parent IMF directory labelled LtRt can contain both video and audio.
    filename = key.rsplit("/", 1)[-1]
    return not re.search(r"(^|[_.-])(audio|atmos|adm|damf|ltrt|mixdown|wav)([_.-]|$)", filename, re.I)


def composition_metadata(text, track_uri, assetmap=None):
    """Bind duration/edit rate to one concrete MXF track through its UUID."""
    try:
        root = ET.fromstring(text)
        for node in root.iter():
            fields = {n.tag.rsplit("}", 1)[-1]: n.text for n in node}
            identifier = (fields.get("TrackFileId") or "").removeprefix("urn:uuid:")
            mapped = (assetmap or {}).get(identifier.casefold())
            bound = identifier and identifier.casefold() in track_uri.casefold()
            if mapped:
                bound = (
                    bound or urllib.parse.unquote(track_uri).rsplit("/", 1)[-1] == mapped.rsplit("/", 1)[-1]
                )
            if not bound:
                continue
            rate = [int(v) for v in fields["EditRate"].split()]
            duration = int(fields.get("IntrinsicDuration") or fields.get("SourceDuration"))
            fps = rate[0] / rate[1]
            return dict(fps=fps, duration_seconds=duration / fps, frames=duration)
    except (ET.ParseError, KeyError, ValueError, TypeError, ZeroDivisionError):
        pass
    return None


def uvg_candidates(store):
    receipt = store.get(UVG)
    page = Page(store.text(receipt))
    quote = re.search(r"The dataset comprises.*?4\.0 license", " ".join(page.text.split()))
    groups = defaultdict(list)
    for link in page.links:
        if link["href"].endswith(".yuv"):
            groups[link["href"].split("/")[0]].append(link)
    result = []
    for title, links in groups.items():
        record = candidate("UVG-VCM", title, "A", receipt)
        record["synthetic_or_real"] = "synthetic" if title.startswith("Synthetic") else "real"
        if record["synthetic_or_real"] == "synthetic":
            record["tier"] = "C"
            record["origin_note"] = (
                "Publisher synthetic sequence, not created by this audit; shared scene lineage unreviewed."
            )
        for link in links:
            m = re.search(r"_(\d+)x(\d+)_(\d+)fps_yuv(444|422|420)_(\d+)bits_(\d+)\.yuv$", link["href"])
            require(m is not None, "UVG metadata grammar changed")
            w, h, fps, chroma, bits, frames = map(int, m.groups())
            record["representations"].append(
                dict(
                    uri=urllib.parse.urljoin(UVG, link["href"]),
                    format="raw YUV",
                    resolution=[w, h],
                    fps=fps,
                    bit_depth=bits,
                    chroma=chroma,
                    frames=frames,
                    duration_seconds=frames / fps,
                    approximate_bytes=int(
                        w * h * {444: 3, 422: 2, 420: 1.5}[chroma] * (2 if bits > 8 else 1) * frames
                    ),
                    bytes_basis="derived_uncompressed_payload_not_download_verified",
                    published_size_label=link["text"],
                    selected=not link["href"].split("/")[-1].startswith("stereo_rightcam"),
                )
            )
        record["duration_seconds"] = next(
            p["duration_seconds"] for p in record["representations"] if p["selected"]
        )
        if quote:
            grant(record, "CC-BY-4.0", receipt, quote.group(), "UVG-VCM dataset; all listed sequences")
        result.append(record)
    return result


def list_objects(store, prefix):
    query = urllib.parse.urlencode({"list-type": "2", "prefix": prefix, "delimiter": "/", "max-keys": "1000"})
    receipt = store.get(S3 + "?" + query)
    if receipt["status"] != "preserved":
        return [], [], True
    try:
        root = ET.fromstring(store.text(receipt))
        ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
        objects = [
            dict(key=n.findtext("s:Key", namespaces=ns), bytes=int(n.findtext("s:Size", namespaces=ns)))
            for n in root.findall("s:Contents", ns)
        ]
        dirs = [n.findtext("s:Prefix", namespaces=ns) for n in root.findall("s:CommonPrefixes", ns)]
        return objects, dirs, root.findtext("s:IsTruncated", namespaces=ns) == "true"
    except (ET.ParseError, TypeError, ValueError):
        return [], [], True


def netflix_candidates(store):
    receipt = store.get(NETFLIX)
    page = Page(store.text(receipt))
    result = []
    quote = "Our open source content is available under the Creative Commons Attribution 4.0 International Public License."
    for link in page.links:
        if "download.opencontent.netflix.com.s3.amazonaws.com/index.html" not in link["href"]:
            continue
        prefix = urllib.parse.parse_qs(urllib.parse.urlsplit(link["href"]).query).get("prefix", [""])[0]
        key = prefix.rstrip("/")
        if key not in TITLES:
            continue
        title = TITLES[key]
        record = candidate("Netflix", title, "A", receipt)
        record.update(
            s3_prefix=prefix,
            asset_browser_uri=link["href"],
            synthetic_or_real="animated" if key in ("SolLevante", "CosmosLaundromat") else "real",
        )
        if quote in page.text:
            grant(record, "CC-BY-4.0", receipt, quote, "Netflix Open Content listed projects")
        start = page.text.find(title + " (")
        end = page.text.find("Watch " + title, start)
        record["catalog_description"] = page.text[start:end] if start >= 0 and end >= 0 else None
        items, dirs, partial = list_objects(store, prefix)
        # Bounded metadata traversal, not an exhaustive image-sequence size estimate.
        for sub in dirs[:6]:
            more, children, truncated = list_objects(store, sub)
            items.extend(more)
            partial = partial or truncated
            for child in children[:3]:
                more, _, truncated = list_objects(store, child)
                items.extend(more)
                partial = partial or truncated
        unique = {item["key"]: item for item in items}
        record["listed_asset_bytes_lower_bound"] = sum(i["bytes"] for i in unique.values())
        record["asset_tree_fully_enumerated"] = False
        record["listing_truncated"] = partial
        for item in unique.values():
            if not is_video_object(item["key"]):
                continue
            dims = re.search(r"(\d{3,5})x(\d{3,5})", item["key"])
            fps = re.search(r"(\d+(?:\.\d+)?)fps", item["key"])
            record["representations"].append(
                dict(
                    uri=S3 + "/" + urllib.parse.quote(item["key"]),
                    format=item["key"].rsplit(".", 1)[-1].upper(),
                    resolution=list(map(int, dims.groups())) if dims else None,
                    fps=float(fps.group(1)) if fps else None,
                    duration_seconds=None,
                    approximate_bytes=item["bytes"],
                    bytes_basis="S3_ListObjects_Size",
                    selected=False,
                )
            )
        if record["representations"]:
            compact = [r for r in record["representations"] if r["format"] == "MP4"]
            selected = min(compact or record["representations"], key=lambda r: r["approximate_bytes"])
            selected["selected"] = True
            record["selection_note"] = (
                "Smallest listed MP4, else smallest master; not an approved acquisition/quality choice."
            )
        else:
            record["download_representation_note"] = (
                "Official master/image sequence descriptions preserved; no object size resolved."
            )
        selected = next((r for r in record["representations"] if r["selected"]), None)
        if selected and selected["format"] == "MXF":
            assetmap = {}
            for item in unique.values():
                if not re.search(r"/(ASSETMAP|ASSETMAP\.xml)$", item["key"], re.I):
                    continue
                mapping = store.get(S3 + "/" + urllib.parse.quote(item["key"]))
                if mapping["status"] != "preserved":
                    continue
                try:
                    for node in ET.fromstring(store.text(mapping)).iter():
                        if node.tag.rsplit("}", 1)[-1] == "Asset":
                            fields = {n.tag.rsplit("}", 1)[-1]: n.text for n in node.iter()}
                            if fields.get("Id") and fields.get("Path"):
                                assetmap[fields["Id"].removeprefix("urn:uuid:").casefold()] = fields["Path"]
                except ET.ParseError:
                    pass
            for item in unique.values():
                if not re.search(r"/CPL[-_].*\.xml$", item["key"], re.I):
                    continue
                composition = store.get(S3 + "/" + urllib.parse.quote(item["key"]))
                if composition["status"] == "preserved":
                    metadata = composition_metadata(store.text(composition), selected["uri"], assetmap)
                    if metadata:
                        selected.update(metadata, composition_evidence_sha256=composition["sha256"])
                        record["duration_seconds"] = metadata["duration_seconds"]
                        break
        result.append(record)
    return result


def xiph_candidates(store):
    receipt = store.get(XIPH)
    result = []
    for block in re.findall(r"<tr\b[^>]*>(.*?)</tr>", store.text(receipt), re.S | re.I):
        name = re.search(r"<strong>(.*?)</strong>", block, re.S | re.I)
        if not name:
            continue
        page = Page(block)
        title = Page(name.group(1)).text
        mirror = re.search(r"Source:\s*Netflix\s+(Chimera|El Fuente|Meridian)", page.text, re.I)
        canonical = mirror.group(1) if mirror else title
        record = candidate("Xiph", canonical, "B", receipt)
        record["asset_id"] = "xiph-" + title_id(title)
        record["sequence_name"] = title
        if mirror:
            record.update(mirror_of_title=canonical, synthetic_or_real="real")
        frames = re.search(r"(\d+)\s+frames", page.text)
        for link in page.links:
            if not link["href"].endswith(".y4m"):
                continue
            dims = re.search(r"(\d{3,5})x(\d{3,5})", link["href"])
            fps = re.search(r"_(\d+(?:\.\d+)?)fps|\d{3,4}p(\d{2})(?:_|\.)", link["href"])
            rate = float(next(v for v in fps.groups() if v is not None)) if fps else None
            size = re.search(
                r'href="'
                + re.escape(link["href"])
                + r'"[^>]*>.*?</a>\s*(?:&nbsp;|\s)*\((\d+(?:\.\d+)?)\s*(?:&nbsp;|\s)*(MB|GB)\)',
                block,
                re.S,
            )
            record["representations"].append(
                dict(
                    uri=urllib.parse.urljoin(XIPH, link["href"]),
                    format="YUV4MPEG2",
                    advertised_resolution=link["text"],
                    resolution=list(map(int, dims.groups())) if dims else None,
                    fps=rate,
                    frames=int(frames.group(1)) if frames else None,
                    duration_seconds=int(frames.group(1)) / rate if frames and rate else None,
                    approximate_bytes=int(float(size.group(1)) * {"MB": 10**6, "GB": 10**9}[size.group(2)])
                    if size
                    else None,
                    bytes_basis="rounded_catalog_label_decimal_assumption" if size else "unknown",
                    selected=False,
                )
            )
        if not record["representations"]:
            continue

        def rank(p):
            if p["resolution"]:
                return p["resolution"][0] * p["resolution"][1]
            m = re.search(r"(\d{3,4})p", p["advertised_resolution"])
            return (
                int(m.group(1)) ** 2
                if m
                else {"CIF": 352 * 288, "QCIF": 176 * 144, "4CIF": 704 * 576}.get(
                    p["advertised_resolution"], 0
                )
            )

        selected = max(record["representations"], key=rank)
        selected["selected"] = True
        record["duration_seconds"] = selected["duration_seconds"]
        record["catalog_row_text"] = page.text
        record["catalog_fps_warning"] = (
            "Xiph warns some frame rates were guessed/inferred; no media probe in this audit."
        )
        record["rights_document_uris"] = [
            urllib.parse.urljoin(XIPH, link["href"])
            for link in page.links
            if any(w in link["text"].lower() for w in ("copyright", "readme", "license"))
        ]
        record["unresolved_rights_documents"] = []
        if "public domain" in page.text.lower():
            record.update(license_type="public-domain-assertion", rights_status="restricted_or_nonpermitted")
        for uri in record["rights_document_uris"]:
            parsed = urllib.parse.urlsplit(uri)
            if parsed.scheme == "http" and parsed.hostname in store.config["allowed_text_hosts"]:
                uri = urllib.parse.urlunsplit(parsed._replace(scheme="https"))
            try:
                proof = store.get(uri)
            except ValueError as error:
                record["unresolved_rights_documents"].append(dict(url=uri, error=str(error)))
                continue
            if proof["status"] != "preserved":
                record["unresolved_rights_documents"].append(dict(url=uri, error=proof.get("error")))
                continue
            document = store.text(proof)
            # Follow the explicitly labelled asset copyright page, not generic host footers.
            if urllib.parse.urlsplit(uri).hostname == "durian.blender.org":
                copyright_links = [
                    link for link in Page(document).links if "copyright" in link["text"].casefold()
                ]
                if copyright_links:
                    proof = store.get(urllib.parse.urljoin(uri, copyright_links[0]["href"]))
                    document = store.text(proof)
            kind, quote = identify_license(Page(document).text)
            if kind == "LicenseRef-SVT-Standards-Only-2006":
                # Publisher identifies all five shots as one Fairytale title.
                record.update(
                    source_title="Fairytale", title_id="fairytale", source_cluster_id="candidate-fairytale"
                )
            if urllib.parse.urlsplit(proof["url"]).hostname == "durian.blender.org" and kind in PERMITTED:
                record["synthetic_or_real"] = "animated"
            if kind:
                grant(record, kind, proof, quote, "publisher-linked accompanying sequence document")
            else:
                record["license_evidence"].append(
                    dict(
                        url=uri,
                        path=proof["path"],
                        sha256=proof["sha256"],
                        retrieved_at_utc=proof["retrieved_at_utc"],
                        scope="no permitted grant identified",
                    )
                )
        result.append(record)
    return result


def restricted_uvg_candidates(store):
    receipt = store.get(ORIGINAL_UVG)
    page = Page(store.text(receipt))
    groups = defaultdict(list)
    result = []
    for link in page.links:
        if "/video/" in link["href"] and link["href"].endswith(".7z"):
            groups[link["href"].split("/")[-1].split("_")[0]].append(link)
    for title, links in groups.items():
        record = candidate("original UVG", title, "restricted", receipt)
        record["synthetic_or_real"] = "real"
        grant(
            record,
            "CC-BY-NC-3.0",
            receipt,
            "All sequences are available under a non-commercial Creative Commons BY-NC license.",
            "original UVG dataset only; ineligible rights class",
        )
        for link in links:
            dims = re.search(r"(\d+)x(\d+)_(\d+)fps", link["href"])
            size = re.search(r"(\d+(?:\.\d+)?) GiB", link["text"])
            record["representations"].append(
                dict(
                    uri=urllib.parse.urljoin(ORIGINAL_UVG, link["href"]),
                    format="7z raw YUV archive",
                    resolution=list(map(int, dims.groups()[:2])) if dims else None,
                    fps=int(dims.group(3)) if dims else None,
                    duration_seconds=None,
                    approximate_bytes=int(float(size.group(1)) * 2**30) if size else None,
                    bytes_basis="rounded_catalog_GiB",
                    selected=False,
                )
            )
        result.append(record)
    return result


def qualify(records, previously_exposed_titles=()):
    for r in records:
        r["previously_exposed_title"] = r["title_id"] in previously_exposed_titles
        blocked = ["previously_exposed_source_title"] if r["previously_exposed_title"] else []
        if r["rights_status"] != "clear_publisher_grant":
            blocked.append("unclear_or_nonpermitted_rights")
        if r["independence_status"] != "reviewed_independent_source_capture_lineage":
            blocked.append("capture_and_cross_source_lineage_review_pending")
        if r["duration_seconds"] is None:
            blocked.append("source_duration_unknown")
        elif r["duration_seconds"] < 80:
            blocked.append("shorter_than_frozen_80_second_requirement_no_looping_or_padding")
        if not r["media_acquired"] or not r["original_sha256"] or not r["normalized_sha256"]:
            blocked.append("actual_media_hashes_and_native_codec_geometry_duration_unverified")
        if r["content_stratum"] is None:
            blocked.append("owned_preassignment_complexity_measurement_pending")
        r["blocking_reasons"] = blocked
        r["main_panel_eligible"] = not blocked


def summarize(records, config):
    sources = {}
    for source in sorted({r["source"] for r in records}):
        rows = [r for r in records if r["source"] == source]
        clean = [r for r in rows if r["rights_status"] == "clear_publisher_grant"]
        selected = [p for r in rows for p in r["representations"] if p["selected"]]
        known = [r["duration_seconds"] for r in rows if r["duration_seconds"] is not None]
        sources[source] = dict(
            candidate_sequences_or_titles=len(rows),
            provisional_title_clusters=len({r["title_id"] for r in rows}),
            rights_cleared_provisional_title_clusters=len({r["title_id"] for r in clean}),
            fresh_rights_cleared_title_upper_bound=len(
                {r["title_id"] for r in clean if not r.get("previously_exposed_title", False)}
            ),
            fully_eligible_independent_units=len(
                {r["source_cluster_id"] for r in rows if r["main_panel_eligible"]}
            ),
            rights_classes=dict(Counter(r["license_type"] or "unknown" for r in rows)),
            origins=dict(Counter(r["synthetic_or_real"] for r in rows)),
            native_length_known_pass=sum(v >= 80 for v in known),
            native_length_known_fail=sum(v < 80 for v in known),
            native_length_unknown=len(rows) - len(known),
            selected_representation_bytes_known_lower_bound=sum(
                {
                    p["uri"]: p["approximate_bytes"] for p in selected if p["approximate_bytes"] is not None
                }.values()
            ),
            selected_representation_unknown_bytes=sum(p["approximate_bytes"] is None for p in selected),
            no_selected_representation=sum(
                not any(p["selected"] for p in r["representations"]) for r in rows
            ),
        )
    clean = [r for r in records if r["rights_status"] == "clear_publisher_grant"]
    titles = {r["title_id"] for r in clean}
    fresh_titles = {r["title_id"] for r in clean if not r.get("previously_exposed_title", False)}
    native_length_upper = {
        r["title_id"]
        for r in clean
        if not r.get("previously_exposed_title", False)
        and (r["duration_seconds"] is None or r["duration_seconds"] >= 80)
    }
    eligible = {r["source_cluster_id"] for r in records if r["main_panel_eligible"]}
    return dict(
        abi=ABI + "_report",
        target_independent_units=96,
        source_counts=sources,
        cross_source_rights_cleared_title_upper_bound=len(titles),
        fresh_rights_cleared_title_upper_bound=len(fresh_titles),
        fresh_optimistic_deficit_to_96=max(0, 96 - len(fresh_titles)),
        fresh_rights_and_native_length_title_upper_bound=len(native_length_upper),
        native_length_optimistic_additional_cluster_deficit=max(0, 96 - len(native_length_upper)),
        rights_cleared_title_upper_bound_without_explicit_synthetic=len(
            {r["title_id"] for r in clean if r["synthetic_or_real"] != "synthetic"}
        ),
        rights_cleared_title_upper_bound_observed_real_only=len(
            {r["title_id"] for r in clean if r["synthetic_or_real"] == "real"}
        ),
        optimistic_deficit_even_if_all_clear_titles_independent=max(0, 96 - len(titles)),
        fully_eligible_independent_units=len(eligible),
        remaining_deficit_to_96=96 - len(eligible),
        candidate_cluster_ids_are_provisional_not_ingestable=True,
        content_stratum_coverage=dict(
            known_low=0, known_medium=0, known_high=0, unmeasured_titles=len(titles)
        ),
        with_and_without_synthetic_eligible_units=dict(
            with_synthetic=len(eligible),
            without_synthetic=len(
                {
                    r["source_cluster_id"]
                    for r in records
                    if r["main_panel_eligible"] and r["synthetic_or_real"] != "synthetic"
                }
            ),
        ),
        total_download_volume_is_incomplete=True,
        media_bytes_downloaded=0,
        scratch_plan_bytes=dict(
            minimum=config["estimated_scratch_minimum_bytes"],
            preferred=config["estimated_scratch_preferred_bytes"],
        ),
        generated_or_captured_tranche_created=0,
        policy_promoted=False,
        models_trained=False,
    )


def write_inventory_csv(path, records):
    """One auditable row per candidate; alternatives and original evidence remain in JSON."""
    fields = [
        "asset_id",
        "source",
        "source_title",
        "sequence_name",
        "tier",
        "title_id",
        "rights_unit_id",
        "source_cluster_id",
        "capture_cluster_id",
        "independence_status",
        "source_uri",
        "representation_uri",
        "representation_format",
        "resolution",
        "fps",
        "duration_seconds",
        "approximate_bytes",
        "bytes_basis",
        "license_type",
        "rights_status",
        "license_evidence_sha256",
        "license_retrieved_at",
        "original_sha256",
        "normalized_sha256",
        "synthetic_or_real",
        "content_stratum",
        "network_panel_split",
        "previously_exposed_title",
        "main_panel_eligible",
        "blocking_reasons",
    ]
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            selected = next((p for p in record["representations"] if p["selected"]), {})
            exported = {key: record.get(key) for key in fields}
            exported.update(
                representation_uri=selected.get("uri"),
                representation_format=selected.get("format"),
                resolution="x".join(map(str, selected["resolution"])) if selected.get("resolution") else None,
                fps=selected.get("fps"),
                approximate_bytes=selected.get("approximate_bytes"),
                bytes_basis=selected.get("bytes_basis"),
                blocking_reasons=";".join(record.get("blocking_reasons", [])),
            )
            writer.writerow(exported)


def audit(config_path, seed, out, offline=False, retry_unresolved=False):
    config = protocol(config_path)
    before = verify_controller_freeze()
    require(not Path(out).exists(), "fresh audit directory required")
    store = EvidenceStore(out, config)
    root = Path(seed)
    existing = read_json(root / "evidence.json")
    store.receipts = {
        u: r for u, r in existing["receipts"].items() if not retry_unresolved or r["status"] == "preserved"
    }
    store.offline = offline
    store.total = existing["metadata_response_bytes"]
    store.calls = existing["metadata_requests"]
    for receipt in store.receipts.values():
        if receipt["status"] == "preserved":
            require(digest(root / receipt["path"]) == receipt["sha256"], "seed evidence drift")
            shutil.copyfile(root / receipt["path"], store.out / receipt["path"])
            if receipt.get("content_type") == "application/pdf":
                subprocess.run(
                    [
                        "pdftotext",
                        "-layout",
                        str(store.out / receipt["path"]),
                        str(store.out / receipt["readable_path"]),
                    ],
                    check=True,
                    timeout=30,
                    capture_output=True,
                )
            else:
                (store.out / receipt["readable_path"]).write_text(Page(store.text(receipt)).text)
    try:
        records = (
            uvg_candidates(store)
            + netflix_candidates(store)
            + xiph_candidates(store)
            + restricted_uvg_candidates(store)
        )
        qualify(records, config["previously_exposed_title_ids"])
        report = summarize(records, config)
        report.update(
            metadata_requests=store.calls,
            metadata_response_bytes=store.total,
            controller_freeze=before,
            generated_at_utc=datetime.now(UTC).isoformat(),
            protocol_sha256=digest(config_path),
            audit_module_sha256=digest(__file__),
        )
        require(before == verify_controller_freeze(), "frozen controller/model hashes changed")
        write_json(store.out / "inventory.json", dict(abi=ABI + "_inventory", records=records))
        write_inventory_csv(store.out / "inventory.csv", records)
        write_json(store.out / "report.json", report)
        write_json(store.out / "protocol.json", config)
        return report
    finally:
        store.save()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "audit"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--out", required=True)
        if name == "audit":
            p.add_argument("--snapshots", required=True)
            p.add_argument("--offline", action="store_true")
            p.add_argument("--retry-unresolved", action="store_true")
    args = parser.parse_args(argv)
    result = (
        snapshot(args.config, args.out)
        if args.command == "snapshot"
        else audit(
            args.config,
            args.snapshots,
            args.out,
            offline=args.offline,
            retry_unresolved=args.retry_unresolved,
        )
    )
    print(json.dumps(result, allow_nan=False))
