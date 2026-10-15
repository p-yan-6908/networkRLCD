"""Read-only publication checks against frozen reports; never reads raw sessions.

The optional --write-report writes only the new publication verification receipt.
Semantic classification is a manual review; this checks its source bindings,
copied numbers, document references, build receipt and preservation claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/publication-readiness-rd1"
PAPER = ROOT / "paper/negative-result-publication"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def git_tree(commit: str) -> dict[str, str]:
    raw = subprocess.check_output(["git", "ls-tree", "-r", "-z", commit], cwd=ROOT)
    return {item.split(b"\t", 1)[1].decode(): item.split(b"\t", 1)[0].split()[2].decode()
            for item in raw.split(b"\0") if item}


def git_blob_hash(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def pointer(value, address: str):
    if not address:
        return value
    for part in address.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def verify() -> dict:
    freeze = read(DATA / "prior-files-sha256.json")
    baseline = git_tree(freeze["preservation_anchor"])
    assert set(baseline) == set(freeze["files"]), "Incomplete prior-file inventory"
    for name, info in freeze["files"].items():
        path = ROOT / name
        raw = path.readlink().as_posix().encode() if path.is_symlink() else path.read_bytes()
        assert len(raw) == info["bytes"] and sha(raw) == info["sha256"], name
        assert git_blob_hash(raw) == baseline[name], "Baseline Git blob mismatch: " + name

    ledger = read(DATA / "claim-traceability.json")
    assert ledger["scientific_stopping_commit"] == freeze["scientific_stopping_commit"]
    assert ledger["publication_baseline_commit"] == freeze["preservation_anchor"]
    stopped = git_tree(ledger["scientific_stopping_commit"])
    for name, info in ledger["sources"].items():
        raw = (ROOT / info["path"]).read_bytes()
        assert len(raw) == info["bytes"] and sha(raw) == info["sha256"], name
        assert git_blob_hash(raw) == stopped[info["path"]], "Source was not frozen at RD1: " + name

    main = (PAPER / "main.tex").read_text()
    lines = main.splitlines()
    markers = [(i, match.group(1)) for i, line in enumerate(lines)
               if (match := re.fullmatch(r"% claim: (\w+)", line))]
    ids = [row["id"] for row in ledger["claims"]]
    assert len(set(ids)) == len(ids) == len(markers)
    assert set(ids) == {name for _, name in markers}
    locators = 0
    scalar_records = 0
    for row in ledger["claims"]:
        assert row["finding_classes"] and row["independence_unit"] and row["evidence"]
        place = row["manuscript"]
        index = next(i for i, (_, name) in enumerate(markers) if name == row["id"])
        start = markers[index][0] + 1
        end = markers[index + 1][0] if index + 1 < len(markers) else len(lines)
        assert place["marker_line"] == start and place["end_line"] == end
        assert sha(("\n".join(lines[start:end]) + "\n").encode()) == place["block_sha256"]
        for ref in row["evidence"]:
            source = ROOT / ledger["sources"][ref["source"]]["path"]
            if ref["kind"] == "line_span":
                text = source.read_text().splitlines()
                assert text[ref["start"] - 1] == ref["heading"]
                excerpt = "\n".join(text[ref["start"] - 1:ref["end"]]) + "\n"
                assert sha(excerpt.encode()) == ref["excerpt_sha256"]
            elif ref["kind"] == "json_pointer":
                value = pointer(read(source), ref["pointer"])
                canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
                assert sha(canonical) == ref["value_sha256"]
                if "reported_value" in ref:
                    assert value == ref["reported_value"]
                    scalar_records += 1
            else:
                assert ref["kind"] == "whole_file_sha256"
            locators += 1

    # All displayed numbers are copied/rounded; none is re-estimated.
    table = (PAPER / "evidence-tables.tex").read_text()
    assert table == (ROOT / "paper/negative-result/evidence-tables.tex").read_text()
    macros = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(-?[\d.]+)\}", table))
    v9 = read(ROOT / "reports/native-clock-action-turntcp-v9-analysis.json")
    v10 = read(ROOT / "reports/native-clock-action-turntcp-v10-analysis.json")
    m5 = read(ROOT / "reports/native-prefix-memory-m5-summary.json")
    psnr = v9["action_effects"]["mean_ontime_psnr_db"]["interaction_high_bwe_minus_low_bwe"]
    expected = {
        "NVNinePSNR": f'{psnr["mean"]:.3f}',
        "NVNinePSNRLow": f'{psnr["ci95"][0]:.3f}',
        "NVNinePSNRHigh": f'{psnr["ci95"][1]:.3f}',
        "NVTenDelta": f'{100 * v10["primary_effect"]["mean"]:.1f}',
        "NVTenLow": f'{100 * v10["primary_effect"]["ci95"][0]:.1f}',
        "NVTenHigh": f'{100 * v10["primary_effect"]["ci95"][1]:.1f}',
    }
    for name, content in [("Kampar", "content_kampar_boating_01"),
                          ("Volga", "content_volga_lock_01")]:
        window = m5["contents"][content]["windows"]["18000"]
        expected["MFive" + name] = f'{window["paired_mean_octaves"]:.5f}'
        expected["MFive" + name + "Low"] = f'{window["uncertainty"]["paired_mean_95pct"][0]:.5f}'
        expected["MFive" + name + "High"] = f'{window["uncertainty"]["paired_mean_95pct"][1]:.5f}'
    assert macros == expected
    po1 = read(ROOT / "reports/partial-observability-po1-result.json")
    copied = {}
    for line in table.splitlines():
        if " & " not in line:
            continue
        columns = line.removesuffix(r"\\").split(" & ")
        if len(columns) == 7:
            copied[columns[0].replace(r"\_", "_")] = columns[1:]
    for family in po1["families"]:
        values = [family["comparisons"]["factual_bwe"]["persistence"]["baseline_mae"],
                  family["metrics"]["summary_linear"]["mae"][0],
                  family["metrics"]["history_linear"]["mae"][0],
                  family["comparisons"]["synthetic_advantage"]["constant"]["baseline_mae"],
                  family["metrics"]["summary_linear"]["mae"][1],
                  family["metrics"]["history_linear"]["mae"][1]]
        assert copied[family["family"]] == [f"{value:.3f}" for value in values]

    references = (PAPER / "references.tex").read_text()
    cited = {key for group in re.findall(r"\\cite\{([^}]+)\}", main) for key in group.split(",")}
    bibliography = re.findall(r"\\bibitem\{([^}]+)\}", references)
    assert len(set(bibliography)) == len(bibliography)
    assert cited <= set(bibliography), "Unresolved source citation"
    for path in re.findall(r"\\path\{([^}]+)\}", references):
        assert path in stopped, "Unpinned bibliography path: " + path

    build = read(ROOT / "reports/publication-readiness-rd1-paper-build.json")
    for name, digest in build["source_sha256"].items():
        assert sha((ROOT / name).read_bytes()) == digest, "Document-build source drift: " + name
    pdf = ROOT / build["repository_pdf"]
    assert sha(pdf.read_bytes()) == build["pdf_sha256"]
    assert build["unresolved_reference_tokens"] == build["undefined_reference_warnings"] == 0
    assert build["overfull_box_warnings"] == 0
    # These are the explicit publication reporting requirements, not a new gate.
    for phrase in ["0.02 utility", "six registered 800 ms", "80\\% minimum", "75\\% minimum",
                   "scientific stopping", "0/2 originals", "no PO1 native predictive result"]:
        assert phrase.lower() in main.lower(), phrase
    report = {
        "abi": "rd1_publication_readiness_audit_v1", "verified": True,
        "scientific_stopping_commit": ledger["scientific_stopping_commit"],
        "preservation_anchor": freeze["preservation_anchor"],
        "prior_tracked_files_unchanged": len(baseline), "prior_files_changed_or_deleted": 0,
        "claim_blocks_checked": len(ids), "frozen_sources_checked": len(ledger["sources"]),
        "claim_source_locators_checked": locators, "scalar_source_records_checked": scalar_records,
        "rounded_macro_values_checked": len(expected), "po1_mae_table_values_checked": 24,
        "bibliography_entries": len(bibliography), "cited_entries": len(cited),
        "build_receipt_sha256": sha((ROOT / "reports/publication-readiness-rd1-paper-build.json").read_bytes()),
        "source_map_sha256": sha((DATA / "claim-traceability.json").read_bytes()),
        "preservation_inventory_sha256": sha((DATA / "prior-files-sha256.json").read_bytes()),
        "manuscript_pdf_sha256": build["pdf_sha256"],
        "semantic_review": "Manual frozen-study review; provenance checks are not an automated causal proof.",
        "new_experiment_or_successor": False, "new_estimate_or_cross_study_pooling": False,
        "new_model_controller_or_calibrator": False, "raw_telemetry_restored_or_decoded": False,
        "receiver_outcomes_opened": False, "reserved_panels_opened": False,
        "old_panel_status_basis": "Frozen reports and unchanged allocation files; no raw session-directory inspection.",
        "rd1_stopping_decision_unchanged": True, "prior_gates_or_conclusions_weakened": False,
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write_report:
        (ROOT / "reports/publication-readiness-rd1-audit.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
