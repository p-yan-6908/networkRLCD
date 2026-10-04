"""Prospective local action-outcome repeatability probe, never qualification.

Reuse the frozen Dense raw audit through a checked, isolated source projection.
Only its no-actor guard and collector identity change; physics/causality checks
remain. Fitted weights, budgets, legacy collectors and module globals are frozen.
No fitting, selected calibration, validation, final test or promotion API here.
"""

import copy
import inspect
import re
import shutil
from pathlib import Path

import numpy as np

from . import native_dense_study as dense
from .native_action_policy import CONFIG, ActionPolicy, validate_bundle
from .native_protocol import (
    DEFAULT_LIMITS,
    SCHEDULES,
    asset_directory,
    digest,
    read_json,
    require,
    seal_directory,
    source_identity,
    verify_seal,
    write_json,
)
from .native_repair5_statistics import analyze_native_rows, cluster_estimate
from .native_repair5_study import _close, trial_schedule
from .native_study import _collect, _recover_cleanup_capture, _verify_all_models
from .native_video import validate_catalog

STUDY_ABI = "native_action_outcome_live_probe_v1"
SOURCE_KIND = "recorded_video_action_outcome_live_v1"
PARENT_SEAL = "native_action_outcome_live_probe_complete"
CHILD_SEAL = "native_action_outcome_live_episode_verified"
MIN_GENUINE_USE_FRACTION = 0.05
CONDITIONS = {
    "rlcd-a": dict(controller="repair", model="source"),
    "rlcd-b": dict(controller="repair", model="source"),
    "bwe": dict(controller="explore", model="source", behavior="bwe"),
    "bwe-continuous": dict(controller="explore", model="source", behavior="bwe-continuous"),
}
RECIPE = {
    **copy.deepcopy(dense.RECIPE),
    "abi": "native_action_outcome_live_measurement_v1",
    "risk_architecture": "bounded_state_action_outcomes",
    "fallback": "continuous85_bwe",
    "shadow_cap_projection": "none_actual_scalar_state",
}
COLLECTOR_PROJECTION = (
    (
        "// Independent diagnostic collector: scalar controls are not a trained RLCD policy.",
        "// Independent experimental action-outcome control; no qualification or promotion.",
        1,
    ),
    ("native_dense_scalar_probe_v1", STUDY_ABI, 1),
    ("panel.repair_model!==null", "!panel.repair_model", 1),
    (
        "condition.controller!=='explore'||!['bwe','bwe-continuous','fixed450','gcc'].includes(condition.behavior)",
        "!['repair','explore'].includes(condition.controller)||(condition.controller==='explore'&&!['bwe','bwe-continuous'].includes(condition.behavior))",
        1,
    ),
    ("panel.stage!=='diagnostic'", "panel.stage!=='repeatability'", 1),
    ("recorded_video_dense_probe_v1", SOURCE_KIND, 2),
    ("'/dense_control.mjs'", "'/action_live_control.mjs'", 2),
    ("'/streamed_dense_video.mjs'", "'/streamed_action_live_video.mjs'", 2),
    (
        "const moduleRoutes=new Set([",
        "const moduleRoutes=new Set(['/action_policy.mjs','/dense_control.mjs',",
        1,
    ),
)


def project_collector(text):
    for old, new, count in COLLECTOR_PROJECTION:
        require(text.count(old) == count, "frozen live collector projection anchor changed")
        text = text.replace(old, new)
    return text


def extra_sources():
    return {
        **dense.extra_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in ("native_action_policy.py", "native_action_live_study.py", "native_action_live_cli.py")
        },
        **{
            "assets/" + n: asset_directory() / n
            for n in (
                "action_policy.mjs",
                "action_live_control.mjs",
                "action_live_episode.mjs",
                "streamed_action_live_video.mjs",
            )
        },
    }


def compatible_engines(p):
    return (
        p["source_sha256"] == source_identity()
        and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()}
        and p["collector_template_sha256"] == digest(asset_directory() / "dense_episode.mjs")
        and (asset_directory() / "action_live_episode.mjs").read_text()
        == project_collector((asset_directory() / "dense_episode.mjs").read_text())
    )


def _entry(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=digest(path))


def _candidate(entry):
    path = Path(entry["path"])
    require(digest(path) == entry["sha256"], "frozen fitted action model changed")
    seal = verify_seal(path.parent, "bounded_action_candidate_fitted")
    require(
        {"model.json", "training_report.json"} <= set(seal["artifacts_sha256"]),
        "complete fitted receipt seal required",
    )
    receipt = read_json(path.parent / "training_report.json")
    cv = receipt.get("training_cv", {})
    require(
        cv.get("passed") is True
        and len(cv.get("folds", [])) == 2
        and all(f["utility_skill"] >= 0.01 and f["risk_skill"] >= 0 for f in cv["folds"]),
        "actual sealed train-only skill receipt must pass",
    )
    require(
        receipt.get("diagnostic_selected_validation_test_labels_used") is False
        and receipt.get("native_deployment_qualified") is False,
        "legal unqualified fitting receipt required",
    )
    b = validate_bundle(read_json(path))
    require(b["training_skill_passed"], "both train-only held-out skill folds must pass before live use")
    require(b.get("provenance") and b.get("source_reservations"), "sealed legal fitting provenance required")
    require(all(digest(p) == sha for p, sha in b["provenance"].items()), "factual fitting parent changed")
    for name, sha in b["source_sha256"].items():
        path = (
            asset_directory() / name.split("/")[1]
            if name.startswith("assets/")
            else Path(__file__).with_name(name.split("/")[1])
        )
        require(digest(path) == sha, "frozen action fitting implementation changed")
    return b


def reservations(results):
    excluded, inputs = [], {}
    paths = set(Path(results).glob("**/protocol.json"))
    configs = Path(results).parent / "configs"
    if configs.exists():
        paths |= set(configs.glob("native_*.json"))
    for path in sorted(paths):
        p = read_json(path)
        if not str(p.get("source_kind", "")).startswith("recorded_video"):
            continue
        require(p.get("video_source") and p.get("groups"), "recorded role reservation is incomplete")
        inputs[str(path.resolve())] = digest(path)
        excluded.extend(
            dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
        )
    return excluded, inputs


def validate_live_protocol(p):
    require(
        p.get("panel_abi") == STUDY_ABI
        and p.get("source_kind") == SOURCE_KIND
        and p.get("stage") == "repeatability"
        and p.get("SOTA_achieved") is False
        and p.get("native_deployment_qualified") is False
        and p.get("learner") is None,
        "live probe is repeatability-only, never fitting/validation/test/qualification",
    )
    require(
        p.get("measurement_recipe") == RECIPE
        and p.get("controller_config") == CONFIG
        and p.get("limits") == DEFAULT_LIMITS
        and p.get("common_shadow_inference") is True
        and p.get("episode_timeout_s") == 90
        and p.get("conditions") == CONDITIONS,
        "frozen live controls/measurement/guards required",
    )
    require(
        type(p.get("repetitions")) is int
        and 2 <= p["repetitions"] <= 20
        and type(p.get("order_seed")) is int
        and p["order_seed"] >= 0,
        "bounded prospective repeats/seed required",
    )
    require(set(p.get("models", {})) == {"source"}, "common legacy shadow required")
    for e in [p["repair_model"], *p["models"].values()]:
        require(
            set(e) == {"path", "sha256"}
            and Path(e["path"]).is_absolute()
            and re.fullmatch(r"[0-9a-f]{64}", e["sha256"]),
            "immutable model entry required",
        )
    candidate = _candidate(p["repair_model"])
    require(
        p.get("source_sha256", {}).keys() == source_identity().keys()
        and p.get("extra_source_sha256", {}).keys() == extra_sources().keys(),
        "complete live source bindings required",
    )
    require(
        all(
            isinstance(s, str) and re.fullmatch(r"[0-9a-f]{64}", s)
            for s in [
                p["collector_template_sha256"],
                *p["source_sha256"].values(),
                *p["extra_source_sha256"].values(),
                *p["excluded_inputs_sha256"].values(),
            ]
        ),
        "frozen source/exclusion digests required",
    )
    require(
        all(digest(path) == sha for path, sha in p["excluded_inputs_sha256"].items()),
        "prior source-role plan changed",
    )
    catalog = validate_catalog(p["video_source"])
    require(
        p["groups"] and len(p["groups"]) <= 32 and len({g["id"] for g in p["groups"]}) == len(p["groups"]),
        "unique bounded physical groups required",
    )
    reserved = []
    rng = np.random.default_rng(p["order_seed"])
    exclusions = [*p["excluded_video_ranges"], *candidate["source_reservations"]]
    for old in exclusions:
        require(
            set(old) == {"sha256", "segment"}
            and re.fullmatch(r"[0-9a-f]{64}", old["sha256"])
            and isinstance(old["segment"], list)
            and len(old["segment"]) == 2
            and all(type(x) is int for x in old["segment"])
            and 0 <= old["segment"][0] < old["segment"][1],
            "valid prior role reservation required",
        )
    for i, g in enumerate(p["groups"]):
        s = g["video_segment"]
        require(
            re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", g["id"])
            and g["family"] in SCHEDULES
            and g["scene_seed"] == i * 2000
            and g["reservation_frames"] == 1000,
            "live physical group identity changed",
        )
        require(
            isinstance(s, list)
            and len(s) == 2
            and all(type(x) is int for x in s)
            and 0 <= s[0] < s[1] <= catalog["duration_ms"]
            and s[1] - s[0] == 20000,
            "full physical movie reservation required",
        )
        require(
            all(not dense.video_overlap(s, old) for old in reserved)
            and all(
                old["sha256"] != catalog["sha256"] or not dense.video_overlap(s, old["segment"])
                for old in exclusions
            ),
            "live probe overlaps a prior fitting/selected/evaluation source role",
        )
        reserved.append(s)
        schedule = copy.deepcopy(SCHEDULES[g["family"]])
        for row in schedule:
            row[2] = 6000
        require(g["schedule"] == schedule, "unchanged frozen native schedule required")
        order = list(rng.permutation(list(CONDITIONS)))
        require(
            g["orders"]
            == [order[r % len(order) :] + order[: r % len(order)] for r in range(p["repetitions"])],
            "prospectively seeded complete peer order required",
        )
    return p


def plan_live_study(
    source_model,
    action_model,
    video_source,
    out,
    *,
    families=None,
    groups_per_family=1,
    repetitions=2,
    seed=8101,
    results_directory="results",
):
    require(
        type(groups_per_family) is int and 1 <= groups_per_family <= 8 and type(seed) is int and seed >= 0,
        "bounded group/seed required",
    )
    require(type(repetitions) is int and 2 <= repetitions <= 20, "bounded repeats required")
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "live plan exists; use a fresh path")
    action_entry = _entry(action_model)
    candidate = _candidate(action_entry)
    catalog = validate_catalog(read_json(video_source))
    require(digest(catalog["path"]) == catalog["sha256"], "movie changed before plan")
    excluded, inputs = reservations(results_directory)
    excluded.extend(copy.deepcopy(candidate["source_reservations"]))
    inputs[str(Path(video_source).resolve())] = digest(video_source)
    inputs[str(Path(action_model).resolve().parent / "manifest.json")] = digest(
        Path(action_model).parent / "manifest.json"
    )
    original_exclusions = copy.deepcopy(excluded)
    families = ["stable"] if families is None else list(families)
    require(
        families and len(set(families)) == len(families) and set(families) <= set(SCHEDULES),
        "unique supported families required",
    )
    groups = []
    rng = np.random.default_rng(seed)
    for family in families:
        for index in range(groups_per_family):
            start = next(
                (
                    s
                    for s in range(60000, catalog["duration_ms"] - 20000, 20000)
                    if all(
                        x["sha256"] != catalog["sha256"]
                        or not dense.video_overlap([s, s + 20000], x["segment"])
                        for x in excluded
                    )
                ),
                None,
            )
            require(start is not None, "fresh licensed source segments exhausted")
            segment = [start, start + 20000]
            excluded.append(dict(sha256=catalog["sha256"], segment=segment))
            order = list(rng.permutation(list(CONDITIONS)))
            schedule = copy.deepcopy(SCHEDULES[family])
            for row in schedule:
                row[2] = 6000
            groups.append(
                dict(
                    id=f"{family}-{index}",
                    family=family,
                    scene_seed=len(groups) * 2000,
                    reservation_frames=1000,
                    video_segment=segment,
                    schedule=schedule,
                    orders=[order[r % len(order) :] + order[: r % len(order)] for r in range(repetitions)],
                )
            )
    p = dict(
        panel_abi=STUDY_ABI,
        source_kind=SOURCE_KIND,
        stage="repeatability",
        models={"source": _entry(source_model)},
        repair_model=action_entry,
        conditions=copy.deepcopy(CONDITIONS),
        repetitions=repetitions,
        groups=groups,
        order_seed=seed,
        limits=DEFAULT_LIMITS.copy(),
        controller_config=CONFIG.copy(),
        learner=None,
        measurement_recipe=copy.deepcopy(RECIPE),
        source_sha256=source_identity(),
        extra_source_sha256={k: digest(v) for k, v in extra_sources().items()},
        collector_template_sha256=digest(asset_directory() / "dense_episode.mjs"),
        video_source=catalog,
        excluded_video_ranges=original_exclusions,
        excluded_inputs_sha256=inputs,
        episode_timeout_s=90,
        common_shadow_inference=True,
        repeatability_run=None,
        validation_run=None,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    dense._base_bundle(source_model)
    validate_live_protocol(p)
    require(compatible_engines(p), "live collector differs from frozen checked projection")
    write_json(out, p)
    return p


def executed_learned_action(decision, cap, controller):
    return (
        controller == "repair"
        and not decision["fallback"]
        and cap == decision["encoder_max_bitrate_bps"]
        and decision["learned_departure"]
        and decision["departure_from_continuous_bwe"]
    )


def _verify_causal_common_models(sender, bundles):
    # The old score/timing audit does not reconstruct common histories. Tighten
    # this independent path: all shadows must consume actual raw scalar features.
    history = []
    for row in sender["decisions"]:
        history = (history + [row["observation"]["features"]])[-4:]
        expected = [0.0] * ((4 - len(history)) * 16) + [x for f in history for x in f]
        for d in row["all_policy_decisions"].values():
            _close(d["history"], expected)
    return _verify_all_models(sender, bundles)


# Checked adaptation, not monkeypatching Dense/coverage/legacy globals. Inspect
# the two explicit changes; every wire/ACK/content/clock/readback check survives.
AUDIT_PROJECTION = (
    (
        '    require(repair_bundle is None, "dense probe cannot load a learned actor")',
        "    validate_bundle(repair_bundle)",
    ),
    ('name.endswith("dense_episode.mjs")', 'name.endswith("action_live_episode.mjs")'),
)
_RAW_SOURCE = inspect.getsource(dense.audit_dense_episode)
for _old, _new in AUDIT_PROJECTION:
    require(_RAW_SOURCE.count(_old) == 1, "frozen live raw-audit projection anchor changed")
    _RAW_SOURCE = _RAW_SOURCE.replace(_old, _new)
_RAW_NAMESPACE = {
    **dense.audit_dense_episode.__globals__,
    "STUDY_ABI": STUDY_ABI,
    "RECIPE": RECIPE,
    "CONFIG": CONFIG,
    "RepairPolicy": ActionPolicy,
    "validate_bundle": validate_bundle,
    "executed_learned_action": executed_learned_action,
    "_verify_all_models": _verify_causal_common_models,
}
exec(compile(_RAW_SOURCE, "<isolated_action_live_raw_audit>", "exec"), _RAW_NAMESPACE)
_RAW_AUDIT = _RAW_NAMESPACE["audit_dense_episode"]


def audit_live_episode(root, p, trial, bundles, action_bundle):
    require(
        p["panel_abi"] == STUDY_ABI and p["stage"] == "repeatability" and p["conditions"] == CONDITIONS,
        "declared independent live probe required",
    )
    root = Path(root)
    require(
        digest(root / "source_snapshot.mjs") == p["extra_source_sha256"]["assets/action_live_episode.mjs"],
        "live collector changed",
    )
    for name, sha in {**p["source_sha256"], **p["extra_source_sha256"]}.items():
        if name.startswith("assets/") and name != "assets/episode.mjs":
            require(digest(root / name.split("/")[1]) == sha, "copied live dependency changed")
    summary, sender = read_json(root / "summary.json"), read_json(root / "sender_observations.json")
    active = p["conditions"][trial["condition"]]["controller"] == "repair"
    require(
        summary["learned_policy_loaded"] is active
        and sender["learned_policy"] is active
        and summary["repair_model_sha256"] == p["repair_model"]["sha256"],
        "actual actuating learned model attribution changed",
    )
    row, derived = _RAW_AUDIT(root, p, trial, bundles, action_bundle)
    decisions = sender["decisions"]
    genuine = sum(
        executed_learned_action(
            r["repair_decision"],
            r["actuation_readback"]["encoder_max_bitrate_bps"],
            p["conditions"][trial["condition"]]["controller"],
        )
        for r in decisions
    )
    row.update(decisions=len(decisions), actual_executed_learned_steps=genuine)
    require(row["above_bwe_budget_steps"] == 0, "executed learned cap violates frozen native BWE budget")
    return row, derived


def _report(rows, p):
    expected = trial_schedule(p)
    require(
        [{k: r[k] for k in t} for r, t in zip(rows, expected, strict=True)] == expected,
        "complete prospectively ordered live panel required",
    )
    result = analyze_native_rows(rows, p)
    aliases = [r for r in rows if r["condition"] in ("rlcd-a", "rlcd-b")]
    total = sum(r["decisions"] for r in aliases)
    genuine = sum(r["actual_executed_learned_steps"] for r in aliases)
    contrasts = {}
    for control in ("bwe", "bwe-continuous"):
        cases = []
        for g in p["groups"]:
            actor = [r for r in aliases if r["group"] == g["id"]]
            peers = [r for r in rows if r["group"] == g["id"] and r["condition"] == control]
            cases.append(
                dict(
                    group=g["id"],
                    family=g["family"],
                    **{
                        k: float(np.mean([r[k] for r in actor]) - np.mean([r[k] for r in peers]))
                        for k in ("utility", "ontime_fraction")
                    },
                    phases={
                        phase: {
                            k: float(
                                np.mean([r["phases"][phase][k] for r in actor])
                                - np.mean([r["phases"][phase][k] for r in peers])
                            )
                            for k in ("utility", "ontime_fraction")
                        }
                        for phase in ("high", "collapse", "recovery")
                    },
                )
            )
        contrasts[control] = dict(
            cases=cases,
            aggregate={k: cluster_estimate([r[k] for r in cases]) for k in ("utility", "ontime_fraction")},
        )
    return dict(
        **result,
        model_sha256=p["repair_model"]["sha256"],
        paired_descriptive_contrasts=contrasts,
        actual_executed_learned_steps=genuine,
        actual_learned_decisions=total,
        genuine_dual_and_continuous_use_fraction=genuine / total if total else 0,
        original_min_genuine_use_fraction=MIN_GENUINE_USE_FRACTION,
        genuine_use_gate_passed=bool(total and genuine / total >= MIN_GENUINE_USE_FRACTION),
        native_deployment_qualified=False,
        selected_calibration_still_required=True,
        independent_validation_test_still_required=True,
        native_improvement_proven=False,
    )


def run_live_study(config, out):
    p = validate_live_protocol(read_json(config))
    require(compatible_engines(p), "live sources changed after plan")
    action = _candidate(p["repair_model"])
    bundles = {k: dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    require(all(digest(e["path"]) == e["sha256"] for e in p["models"].values()), "common shadow changed")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "protocol.json", p)
    runtime = dense._expected_runtime(p, out)
    (out / "models").mkdir()
    for key, entry in p["models"].items():
        shutil.copyfile(entry["path"], out / "models" / (key + ".json"))
    shutil.copyfile(p["repair_model"]["path"], out / "models/repair.json")
    shutil.copyfile(p["video_source"]["path"], out / "recorded-video.mp4")
    require(digest(out / "recorded-video.mp4") == p["video_source"]["sha256"], "copied movie changed")
    write_json(out / "runtime.json", runtime)
    for name, source in {
        **{
            k: asset_directory() / k.split("/")[1]
            if k.startswith("assets/")
            else Path(__file__).with_name(k.split("/")[1])
            for k in p["source_sha256"]
        },
        **extra_sources(),
    }.items():
        target = out / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    dense._validate_recorded_runtime(out, p, runtime)
    rows, seals, last = [], {}, -1
    try:
        for trial in runtime["episodes"]:
            child = out / trial["id"]
            require(not child.exists(), "live outcomes cannot be replaced/recollected")
            print(f"action live {len(rows) + 1}/{len(runtime['episodes'])} {trial['id']}", flush=True)
            try:
                _collect(
                    [
                        "node",
                        str(asset_directory() / "action_live_episode.mjs"),
                        str(child),
                        str(out / "runtime.json"),
                        trial["id"],
                        trial["condition"],
                    ],
                    120,
                    out / (trial["id"] + ".log"),
                )
            except Exception:
                _recover_cleanup_capture(child, out / (trial["id"] + ".log"))
            row, derived = audit_live_episode(child, p, trial, bundles, action)
            require(
                row["start_epoch_ms"] > last
                and (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "nonprospective/changed-runtime live capture",
            )
            last = row["cutoff_epoch_ms"]
            write_json(child / "derived.json", derived)
            seal_directory(child, sorted(x.name for x in child.iterdir() if x.is_file()), CHILD_SEAL)
            seals[trial["id"]] = digest(child / "manifest.json")
            rows.append(row)
        require(compatible_engines(p), "live implementation changed during collection")
        validate_live_protocol(p)
        report = _report(rows, p)
        write_json(out / "episodes.json", rows)
        write_json(out / "report.json", report)
        files = sorted(
            str(x.relative_to(out))
            for x in out.rglob("*")
            if x.is_file() and (x.parent == out or x.relative_to(out).parts[0] in ("sources", "models"))
        )
        seal_directory(
            out,
            files,
            PARENT_SEAL,
            episodes=seals,
            role="repeatability",
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
        return report
    except Exception as error:
        write_json(
            out / "failure.json",
            dict(
                error=str(error),
                completed_peers=len(rows),
                all_partial_evidence_preserved=True,
                no_outcomes_replaced=True,
            ),
        )
        raise


def audit_live_study(root):
    root = Path(root).resolve()
    seal = verify_seal(root, PARENT_SEAL)
    p = validate_live_protocol(read_json(root / "protocol.json"))
    require(
        seal["role"] == "repeatability"
        and seal.get("native_deployment_qualified") is False
        and seal.get("SOTA_achieved") is False,
        "sealed live role mismatch",
    )
    require(compatible_engines(p), "live verifier implementation changed")
    for name, sha in {**p["source_sha256"], **p["extra_source_sha256"]}.items():
        require(digest(root / "sources" / name) == sha, "sealed live engine changed")
    require(digest(root / "recorded-video.mp4") == p["video_source"]["sha256"], "sealed movie changed")
    bundles = {k: dense._base_bundle(root / "models" / (k + ".json")) for k in p["models"]}
    action = validate_bundle(read_json(root / "models/repair.json"))
    runtime = read_json(root / "runtime.json")
    dense._validate_recorded_runtime(root, p, runtime)
    require(set(seal["episodes"]) == {t["id"] for t in runtime["episodes"]}, "missing frozen live peers")
    rows, last = [], -1
    for trial in runtime["episodes"]:
        child = root / trial["id"]
        verify_seal(child, CHILD_SEAL)
        require(
            digest(child / "manifest.json") == seal["episodes"][trial["id"]]
            and (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
            "live child/runtime seal changed",
        )
        row, derived = audit_live_episode(child, p, trial, bundles, action)
        require(
            row["start_epoch_ms"] > last and derived == read_json(child / "derived.json"),
            "raw live order/derived outcomes changed",
        )
        last = row["cutoff_epoch_ms"]
        rows.append(row)
    require(
        rows == read_json(root / "episodes.json") and _report(rows, p) == read_json(root / "report.json"),
        "live statistics changed",
    )
    return dict(
        verified_peers=len(rows),
        role="repeatability",
        full_raw_replay=True,
        read_only=True,
        actual_executed_learned_steps=sum(r["actual_executed_learned_steps"] for r in rows),
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
