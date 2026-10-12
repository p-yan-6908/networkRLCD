"""Post-capture proximal ITT analysis of the factual native TURN hold assignments.

This is an exploratory secondary analysis of an already completed native-stack
probe. It never generates native or simulator counterfactual outcomes and never
fits or promotes a controller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import t as student_t

from .native_turn_probe import summarize, validate_peer

ABI = "native_turn_action_diagnostic_v1"
ARMS = (0.65, 0.85, 1.05)
CONTRASTS = ((0.85, 0.65), (1.05, 0.65), (1.05, 0.85))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _bound_file(project: Path, record: dict) -> Path:
    path = project / record["path"]
    if not path.is_file() or path.is_symlink() or sha(path) != record["sha256"]:
        raise ValueError("pinned analysis input changed: " + record["path"])
    return path


def _verify_local_capture(root: Path, inventory: dict) -> int:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("fresh factual capture directory required")
    root = root.resolve(strict=True)
    expected: dict[str, dict] = {}
    for row in inventory["files"]:
        source = Path(row["path"])
        try:
            rel = source.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel in expected:
            raise ValueError("duplicate path in local evidence inventory")
        expected[rel] = row
    actual = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink inside factual capture is not accepted")
        if path.is_file():
            actual[path.relative_to(root).as_posix()] = path
    if not expected or set(actual) != set(expected):
        raise ValueError("factual capture file inventory differs from its receipt")
    for rel, path in actual.items():
        row = expected[rel]
        if path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise ValueError("factual capture file changed: " + rel)
    return len(actual)


def _verified_sessions(config: dict, project: Path) -> tuple[list[dict], dict]:
    inputs = config["inputs"]
    inventory_path = _bound_file(project, inputs["local_inventory"])
    audit_path = _bound_file(project, inputs["independent_audit"])
    report_path = _bound_file(project, inputs["probe_report"])
    reference_path = _bound_file(project, inputs["probe_sessions"])
    verification_path = _bound_file(project, inputs["probe_verification"])

    inventory = json.loads(inventory_path.read_text())
    audit = json.loads(audit_path.read_text())
    report = json.loads(report_path.read_text())
    reference = json.loads(reference_path.read_text())
    verification = json.loads(verification_path.read_text())
    root = Path(inputs["capture_root"])
    inventory_files = _verify_local_capture(root, inventory)

    if (
        inventory.get("abi") != "native_turn_probe_v1_local_evidence_inventory"
        or inventory.get("archive_verified") is not False
        or inventory.get("raw_bytes_pruned") is not False
        or audit.get("abi") != "native_turn_probe_v1_independent_audit"
        or audit.get("registered_spec_sha256") != inputs["probe_spec_sha256"]
        or audit.get("registered_source_hashes_unchanged") is not True
        or audit.get("summaries_recomputed") is not True
        or audit.get("native_factual_only") is not True
        or audit.get("raw_bytes_pruned") is not False
        or audit.get("controller_promoted") is not False
        or audit.get("real_network_validation") is not False
        or verification.get("raw_inventory_sha256") != inputs["local_inventory"]["sha256"]
        or verification.get("archive_verified") is not False
        or verification.get("raw_bytes_pruned") is not False
        or report.get("abi") != "native_turn_probe_v1_report"
        or report.get("native_stack_factual") is not True
        or report.get("native_counterfactuals") is not False
        or report.get("controller_promoted") is not False
        or report.get("real_network_validation") is not False
        or report.get("sessions") != 16
        or len(reference) != 16
    ):
        raise ValueError("the pinned factual-only native evidence contract failed")

    spec_path = root / "spec.json"
    if not spec_path.is_file() or sha(spec_path) != inputs["probe_spec_sha256"]:
        raise ValueError("registered native probe specification changed")
    spec = json.loads(spec_path.read_text())
    if spec.get("abi") != "native_turn_probe_v1_spec" or spec.get("native_counterfactuals") is not False:
        raise ValueError("factual native probe specification required")
    for relative, expected_sha in spec["source_sha256"].items():
        source = project / relative
        if not source.is_file() or sha(source) != expected_sha:
            raise ValueError("registered probe source changed: " + relative)

    sessions = []
    for trial in spec["trials"]:
        peer, assignments = validate_peer(root / trial["id"], trial)
        sessions.append(summarize(peer, assignments, trial))
    if _canonical(sessions) != _canonical(reference):
        raise ValueError("raw factual replay differs from the pinned session summaries")
    return sessions, {
        "inventory_files_verified": inventory_files,
        "sessions_replayed": len(sessions),
        "capture_file_count": len([p for p in root.rglob("*") if p.is_file()]),
        "capture_bytes_unmodified": True,
        "summaries_match_pinned_report": True,
        "wire_audit_sha256": sha(audit_path),
        "inventory_sha256": sha(inventory_path),
        "reference_sessions_sha256": sha(reference_path),
        "probe_report_sha256": sha(report_path),
        "probe_spec_sha256": sha(spec_path),
    }


def _rows(sessions: list[dict]) -> list[dict]:
    rows = []
    for session in sessions:
        trial = session["trial"]
        peer = trial["id"]
        for epoch, cohort in enumerate(session["cohorts"]):
            if cohort["epoch"] != epoch:
                raise ValueError("native hold epochs must remain in recorded order")
            arm = int(cohort["arm"])
            if arm < 0 or arm >= len(ARMS) or cohort["ratio"] != ARMS[arm]:
                raise ValueError("native assigned arm does not match its frozen ratio")
            if not np.isclose(cohort["propensity"], 1 / 3, rtol=0, atol=1e-12):
                raise ValueError("the registered per-hold assignment probability changed")
            if (
                not cohort["window_complete"]
                or cohort["realized_ratio"] is None
                or cohort["on_time_share"] is None
                or cohort["capture_requests"] <= 0
                or cohort["on_time_requests"] < 0
                or cohort["on_time_requests"] > cohort["capture_requests"]
                or cohort["clipped_or_aliased"]
            ):
                raise ValueError("registered complete, non-aliased factual hold required")
            rows.append(
                {
                    "peer": peer,
                    "epoch": epoch,
                    "arm": arm,
                    "ratio": ARMS[arm],
                    "actual_payload_ratio": float(cohort["realized_ratio"]),
                    "on_time_requests": int(cohort["on_time_requests"]),
                    "capture_requests": int(cohort["capture_requests"]),
                    "on_time_share": float(cohort["on_time_share"]),
                    "scene_seed": int(trial["scene_seed"]),
                    "schedule": trial["regime"],
                }
            )
    if len(rows) != 96 or len({row["peer"] for row in rows}) != 16:
        raise ValueError("the registered 16-peer / 96-hold panel is required")
    if len({row["scene_seed"] for row in rows}) != 4 or len({row["schedule"] for row in rows}) != 2:
        raise ValueError("unexpected content or authored schedule panel")
    return rows


def _design(rows: list[dict]) -> tuple[np.ndarray, list[str], list[str]]:
    peers = sorted({row["peer"] for row in rows})
    epochs = sorted({row["epoch"] for row in rows})
    columns = [np.ones(len(rows))]
    names = ["intercept"]
    for peer in peers[1:]:
        columns.append(np.asarray([row["peer"] == peer for row in rows], dtype=float))
        names.append("peer=" + peer)
    for epoch in epochs[1:]:
        columns.append(np.asarray([row["epoch"] == epoch for row in rows], dtype=float))
        names.append("epoch=" + str(epoch))
    for arm in (1, 2):
        columns.append(np.asarray([row["arm"] == arm for row in rows], dtype=float))
        names.append("arm=" + str(ARMS[arm]))
    return np.column_stack(columns), names, peers


def _fit(rows: list[dict], outcome: str, weight_key: str | None) -> dict:
    design, names, peers = _design(rows)
    y = np.asarray([row[outcome] for row in rows], dtype=float)
    weights = (
        np.ones(len(rows), dtype=float)
        if weight_key is None
        else np.asarray([row[weight_key] for row in rows], dtype=float)
    )
    root_w = np.sqrt(weights)
    xw, yw = design * root_w[:, None], y * root_w
    xtx = xw.T @ xw
    if np.linalg.matrix_rank(xtx) != xtx.shape[0]:
        raise ValueError("fixed-effect design is rank deficient")
    bread = np.linalg.inv(xtx)
    beta = bread @ (xw.T @ yw)
    residual = y - design @ beta
    meat = np.zeros_like(xtx)
    peer_rows = np.asarray([row["peer"] for row in rows])
    for peer in peers:
        mask = peer_rows == peer
        score = design[mask].T @ (weights[mask] * residual[mask])
        meat += np.outer(score, score)
    n, k, groups = len(rows), design.shape[1], len(peers)
    correction = (groups / (groups - 1)) * ((n - 1) / (n - k))
    covariance = correction * bread @ meat @ bread
    contrasts = []
    for high, low in CONTRASTS:
        vector = np.zeros(k)
        if high != 0.65:
            vector[names.index("arm=" + str(high))] += 1
        if low != 0.65:
            vector[names.index("arm=" + str(low))] -= 1
        estimate = float(vector @ beta)
        se = float(np.sqrt(max(0.0, vector @ covariance @ vector)))
        df = groups - 1
        statistic = estimate / se if se > 0 else (0.0 if estimate == 0 else np.inf)
        p_value = float(2 * student_t.sf(abs(statistic), df)) if se > 0 else (1.0 if estimate == 0 else 0.0)
        critical = float(student_t.ppf(0.975, df))
        contrasts.append(
            {
                "contrast": f"{high:.2f} - {low:.2f}",
                "estimate": estimate,
                "standard_error": se,
                "ci95_low": estimate - critical * se,
                "ci95_high": estimate + critical * se,
                "t_statistic": float(statistic),
                "degrees_of_freedom": df,
                "p_value_two_sided": p_value,
            }
        )
    return {"n_holds": n, "n_peer_clusters": groups, "model_columns": names, "contrasts": contrasts}


def _holm(results: list[dict]) -> None:
    tests = [(result, contrast) for result in results for contrast in result["contrasts"]]
    ranked = sorted(tests, key=lambda item: item[1]["p_value_two_sided"])
    running = 0.0
    total = len(ranked)
    for rank, (_, contrast) in enumerate(ranked):
        running = max(running, (total - rank) * contrast["p_value_two_sided"])
        contrast["p_value_holm_all_six"] = min(1.0, running)


def _arm_summary(rows: list[dict]) -> list[dict]:
    summary = []
    for arm, ratio in enumerate(ARMS):
        own = [row for row in rows if row["arm"] == arm]
        summary.append(
            {
                "ratio": ratio,
                "holds": len(own),
                "actual_payload_ratio_mean": float(np.mean([row["actual_payload_ratio"] for row in own])),
                "on_time_requests": sum(row["on_time_requests"] for row in own),
                "capture_requests": sum(row["capture_requests"] for row in own),
                "on_time_share_request_weighted": float(
                    sum(row["on_time_requests"] for row in own) / sum(row["capture_requests"] for row in own)
                ),
            }
        )
    return summary


def _latex_table(arms: list[dict], results: list[dict]) -> str:
    lines = [
        r"\begin{tabular}{llrrr}",
        r"\toprule",
        "Outcome & Contrast & Difference (95\\% CI) & $p$ & Holm $p$ \\\\",
        r"\midrule",
    ]
    for result in results:
        label = (
            "Actual payload / assigned BWE"
            if result["name"] == "actual_payload_ratio"
            else "On-time requests (pp)"
        )
        scale = 1.0 if result["name"] == "actual_payload_ratio" else 100.0
        for contrast in result["contrasts"]:
            difference = contrast["estimate"] * scale
            low, high = contrast["ci95_low"] * scale, contrast["ci95_high"] * scale
            lines.append(
                f"{label} & {contrast['contrast']} & {difference:.3f} [{low:.3f}, {high:.3f}] & "
                f"{contrast['p_value_two_sided']:.3f} & {contrast['p_value_holm_all_six']:.3f} \\\\"
            )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def run(config_path: Path, out: Path) -> dict:
    config_path, out = Path(config_path), Path(out)
    if out.exists():
        raise ValueError("fresh diagnostic output directory required")
    project = Path(__file__).resolve().parents[2]
    config = json.loads(config_path.read_text())
    if config.get("abi") != ABI or config.get("analysis_status") != "post_capture_exploratory":
        raise ValueError("frozen post-capture analysis specification required")
    if tuple(config["treatment"]["arms"]) != ARMS:
        raise ValueError("registered action arms changed")
    sessions, raw_provenance = _verified_sessions(config, project)
    rows = _rows(sessions)
    actual = _fit(rows, "actual_payload_ratio", None)
    actual["name"] = "actual_payload_ratio"
    delivery = _fit(rows, "on_time_share", "capture_requests")
    delivery["name"] = "on_time_share"
    results = [actual, delivery]
    _holm(results)
    arms = _arm_summary(rows)
    spec_sha = sha(project / "configs/native_turn_probe_v1.json")
    diagnostic = {
        "abi": ABI + "_report",
        "analysis_status": "post_capture_exploratory",
        "native_factual_only": True,
        "native_counterfactuals": False,
        "model_fitted": False,
        "controller_promoted": False,
        "real_network_validation": False,
        "causal_scope": config["treatment"]["estimand"],
        "fixed_effects": config["estimator"]["fixed_effects"],
        "covariance": config["estimator"]["covariance"],
        "holm_family_size": 6,
        "sessions": len(sessions),
        "holds": len(rows),
        "peer_clusters": len({row["peer"] for row in rows}),
        "scene_seeds": len({row["scene_seed"] for row in rows}),
        "authored_schedules": len({row["schedule"] for row in rows}),
        "all_holds_complete_and_non_aliased": True,
        "arms": arms,
        "outcomes": results,
        "limitations": config["claim_limits"],
        "raw_evidence_provenance": raw_provenance,
        "analysis_spec_sha256": sha(config_path),
        "analysis_code_sha256": sha(Path(__file__)),
        "probe_spec_sha256": spec_sha,
        "reproduction": {
            "sessions_replayed_from_raw": True,
            "exact_inventory_verified": True,
            "full_wire_audit_required": True,
            "no_archive_or_pruned_evidence_used": True,
        },
    }
    out.mkdir(parents=True)
    (out / "report.json").write_text(json.dumps(diagnostic, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (out / "table.tex").write_text(_latex_table(arms, results))
    provenance = {
        "abi": ABI + "_provenance",
        "report_sha256": sha(out / "report.json"),
        "table_sha256": sha(out / "table.tex"),
        "config_sha256": sha(config_path),
        "analysis_code_sha256": diagnostic["analysis_code_sha256"],
        "raw_evidence_provenance": raw_provenance,
        "project_root": str(project),
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    return diagnostic


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.config, args.out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
