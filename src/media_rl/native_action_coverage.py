"""Prospective exact-cap augmentation of sealed legal V5 fitting roles only.

Same movie reservation/schedule == SAME physical group, never new independence.
The scalar collector is a checked namespace-only derivative of frozen Dense/V5
physics. The raw verifier uses the original complete Dense verifier bytecode with
an isolated ABI/recipe/exploration binding; no existing globals/files are mutated.
Diagnostic/selected/validation/test parents and learned actors are forbidden.
"""

import copy
import re
import shutil
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_dense_study as dense
from .native_action_coverage_control import BEHAVIORS, CONFIG, COVERAGE_CAPS, exploration_cap
from .native_protocol import (
    DEFAULT_LIMITS,
    asset_directory,
    digest,
    read_json,
    require,
    seal_directory,
    source_identity,
    verify_seal,
    write_json,
)
from .native_repair5_study import extra_sources as v5_sources
from .native_repair5_study import trial_schedule, validate_repair_protocol
from .native_study import _collect, _recover_cleanup_capture
from .native_video import validate_catalog

STUDY_ABI = "native_exact_cap_coverage_v1"
SOURCE_KIND = "recorded_video_exact_cap_coverage_v1"
PARENT_SEAL = "native_exact_cap_coverage_complete"
CHILD_SEAL = "native_exact_cap_coverage_episode_verified"
RECIPE = {
    **copy.deepcopy(dense.RECIPE),
    "abi": "native_exact_cap_coverage_measurement_v1",
    "risk_architecture": "no_learned_actor_exact_cap_coverage",
    "fallback": "fixed_exact_cap_exploration_not_learned",
}
PROJECTION = (
    (
        "// Independent diagnostic collector: scalar controls are not a trained RLCD policy.",
        "// Independent legal-role augmentation: fixed scalar coverage is not a learned policy.",
        1,
    ),
    ("native_dense_scalar_probe_v1", STUDY_ABI, 1),
    (
        "!['bwe','bwe-continuous','fixed450','gcc'].includes(condition.behavior)",
        "!['fixed400','fixed450','fixed500'].includes(condition.behavior)",
        1,
    ),
    ("panel.stage!=='diagnostic'", "!['train','calibration'].includes(panel.stage)", 1),
    ("recorded_video_dense_probe_v1", SOURCE_KIND, 2),
    ("'/dense_control.mjs'", "'/coverage_control.mjs'", 2),
    ("'/streamed_dense_video.mjs'", "'/streamed_coverage_video.mjs'", 2),
    ("const moduleRoutes=new Set([", "const moduleRoutes=new Set(['/dense_control.mjs',", 1),
)


def project_collector(text):
    for old, new, count in PROJECTION:
        require(text.count(old) == count, "frozen collector projection anchor changed")
        text = text.replace(old, new)
    return text


def extra_sources():
    return {
        **v5_sources(),
        **{
            "python/" + name: Path(__file__).with_name(name)
            for name in (
                "native_dense_control.py",
                "native_dense_study.py",
                "native_action_coverage_control.py",
                "native_action_coverage.py",
                "native_action_coverage_cli.py",
                "native_action_coverage_learning.py",
            )
        },
        **{
            "assets/" + name: asset_directory() / name
            for name in (
                "dense_control.mjs",
                "dense_actuation.mjs",
                "coverage_control.mjs",
                "coverage_episode.mjs",
                "streamed_coverage_video.mjs",
            )
        },
    }


def _parent(entry):
    require(
        set(entry) == {"path", "manifest_sha256", "protocol_sha256"},
        "pinned legal augmentation parent required",
    )
    root = Path(entry["path"]).resolve()
    require(
        digest(root / "manifest.json") == entry["manifest_sha256"]
        and digest(root / "protocol.json") == entry["protocol_sha256"],
        "augmentation parent changed",
    )
    seal = verify_seal(root, "native_repair5_study_complete")
    p = validate_repair_protocol(read_json(root / "protocol.json"))
    require(
        p["stage"] in ("train", "calibration")
        and seal["role"] == p["stage"]
        and seal.get("SOTA_achieved") is False,
        "only sealed legal exploration train/calibration parents accepted",
    )
    require(p["repair_model"] is None, "learned/selected-policy parents cannot supply coverage")
    require(
        set(seal.get("episodes", {})) == {t["id"] for t in trial_schedule(p)},
        "complete legal parent peers required",
    )
    for trial, sha in seal["episodes"].items():
        require(
            digest(root / trial / "manifest.json") == sha
            and read_json(root / trial / "manifest.json").get("stage") == "native_repair5_episode_verified",
            "legal parent child seal changed or incomplete",
        )
    require(digest(root / "recorded-video.mp4") == p["video_source"]["sha256"], "parent movie changed")
    return root, p


def compatible_engines(p):
    return (
        p["source_sha256"] == source_identity()
        and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()}
        and p["collector_template_sha256"] == digest(asset_directory() / "dense_episode.mjs")
        and (asset_directory() / "coverage_episode.mjs").read_text()
        == project_collector((asset_directory() / "dense_episode.mjs").read_text())
    )


def validate_coverage(p):
    require(
        p.get("panel_abi") == STUDY_ABI
        and p.get("source_kind") == SOURCE_KIND
        and p.get("stage") in ("train", "calibration"),
        "explicit legal exact-cap coverage ABI/role required",
    )
    require(
        p.get("SOTA_achieved") is False
        and p.get("no_new_independent_groups") is True
        and p.get("learned_policy_present") is False
        and p.get("repair_model") is None
        and p.get("learner") is None,
        "coverage cannot load/qualify a learned policy or invent independence",
    )
    require(
        p.get("measurement_recipe") == RECIPE
        and p.get("controller_config") == CONFIG
        and p.get("limits") == DEFAULT_LIMITS
        and p.get("coverage_caps") == list(COVERAGE_CAPS)
        and p.get("common_shadow_inference") is True,
        "frozen scalar physics and unchanged safety/runtime budgets required",
    )
    require(
        type(p.get("repetitions")) is int
        and 2 <= p["repetitions"] <= 4
        and type(p.get("order_seed")) is int
        and p["order_seed"] >= 0
        and p.get("episode_timeout_s") == 90,
        "bounded prospective coverage repetitions/seed required",
    )
    require(
        p.get("source_sha256", {}).keys() == source_identity().keys()
        and p.get("extra_source_sha256", {}).keys() == extra_sources().keys(),
        "complete source bindings required",
    )
    require(
        all(
            isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
            for v in [
                *p["source_sha256"].values(),
                *p["extra_source_sha256"].values(),
                p["collector_template_sha256"],
            ]
        ),
        "source digests required",
    )
    root, parent = _parent(p["augmentation_parent"])
    require(p["stage"] == parent["stage"], "coverage may not relabel parent roles")
    catalog = copy.deepcopy(parent["video_source"])
    catalog["path"] = str(root / "recorded-video.mp4")
    require(p["video_source"] == catalog, "owned source catalog/reservation changed")
    validate_catalog(p["video_source"])
    models = {
        k: {"path": str(root / "models" / (k + ".json")), "sha256": e["sha256"]}
        for k, e in parent["models"].items()
    }
    require(
        p["models"] == models and all(digest(e["path"]) == e["sha256"] for e in models.values()),
        "pinned common source model changed",
    )
    require(
        p["conditions"] == {b: dict(controller="explore", model="source", behavior=b) for b in BEHAVIORS},
        "all exact fixed-cap peers required",
    )
    require(
        p["excluded_video_ranges"] == parent["excluded_video_ranges"]
        and len(p["groups"]) == len(parent["groups"]),
        "parent role/source exclusions changed",
    )
    rng = np.random.default_rng(p["order_seed"])
    for group, old in zip(p["groups"], parent["groups"], strict=True):
        order = list(rng.permutation(list(BEHAVIORS)))
        require(
            group["orders"] == [order[r % 3 :] + order[: r % 3] for r in range(p["repetitions"])],
            "order must match the prospective seed",
        )
        require(
            {k: v for k, v in group.items() if k != "orders"}
            == {k: v for k, v in old.items() if k != "orders"},
            "physical source/schedule/seed group may not change",
        )
        require(
            len(group["orders"]) == p["repetitions"]
            and all(len(order) == 3 and set(order) == set(BEHAVIORS) for order in group["orders"]),
            "complete prospectively declared exact-cap peer order required",
        )
    return p


def plan_coverage(parent, out, *, repetitions=2, seed=7101):
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "immutable fresh coverage plan required")
    root = Path(parent).resolve()
    entry = dict(
        path=str(root),
        manifest_sha256=digest(root / "manifest.json"),
        protocol_sha256=digest(root / "protocol.json"),
    )
    root, old = _parent(entry)
    require(
        type(seed) is int and seed >= 0 and type(repetitions) is int and 2 <= repetitions <= 4,
        "bounded coverage seed/repetitions required",
    )
    rng = np.random.default_rng(seed)
    groups = copy.deepcopy(old["groups"])
    for group in groups:
        order = list(rng.permutation(list(BEHAVIORS)))
        group["orders"] = [order[r % 3 :] + order[: r % 3] for r in range(repetitions)]
    video = copy.deepcopy(old["video_source"])
    video["path"] = str(root / "recorded-video.mp4")
    p = dict(
        panel_abi=STUDY_ABI,
        source_kind=SOURCE_KIND,
        stage=old["stage"],
        augmentation_parent=entry,
        coverage_caps=list(COVERAGE_CAPS),
        models={
            k: dict(path=str(root / "models" / (k + ".json")), sha256=e["sha256"])
            for k, e in old["models"].items()
        },
        repair_model=None,
        learner=None,
        groups=groups,
        repetitions=repetitions,
        order_seed=seed,
        conditions={b: dict(controller="explore", model="source", behavior=b) for b in BEHAVIORS},
        limits=DEFAULT_LIMITS.copy(),
        controller_config=CONFIG.copy(),
        measurement_recipe=copy.deepcopy(RECIPE),
        source_sha256=source_identity(),
        extra_source_sha256={k: digest(v) for k, v in extra_sources().items()},
        collector_template_sha256=digest(asset_directory() / "dense_episode.mjs"),
        video_source=video,
        excluded_video_ranges=copy.deepcopy(old["excluded_video_ranges"]),
        episode_timeout_s=90,
        common_shadow_inference=True,
        no_new_independent_groups=True,
        learned_policy_present=False,
        SOTA_achieved=False,
    )
    validate_coverage(p)
    require(compatible_engines(p), "collector differs from frozen namespace-only projection")
    write_json(out, p)
    return p


# Isolated immutable namespace binding: reuse the full raw verifier bytecode,
# never monkeypatch its module or relax its wire/feedback/source/actuation checks.
_RAW_AUDIT = FunctionType(
    dense.audit_dense_episode.__code__,
    {
        **dense.audit_dense_episode.__globals__,
        "STUDY_ABI": STUDY_ABI,
        "RECIPE": RECIPE,
        "exploration_cap": exploration_cap,
    },
    "audit_exact_cap_raw",
)


def audit_coverage_episode(root, p, trial, bundles):
    require(
        p["panel_abi"] == STUDY_ABI
        and p["stage"] in ("train", "calibration")
        and p["conditions"][trial["condition"]]["behavior"] in BEHAVIORS
        and p["repair_model"] is None,
        "legal exact-cap trial required",
    )
    require(
        digest(Path(root) / "source_snapshot.mjs") == p["extra_source_sha256"]["assets/coverage_episode.mjs"],
        "actual coverage collector changed",
    )
    return _RAW_AUDIT(root, p, trial, bundles, None)


def _report(rows, p):
    expected = trial_schedule(p)
    require(
        len(rows) == len(expected)
        and [{k: r[k] for k in t} for r, t in zip(rows, expected, strict=True)] == expected,
        "complete prospectively ordered coverage outcomes required",
    )
    return dict(
        role=p["stage"],
        verified_peers=len(rows),
        physical_groups=len(p["groups"]),
        coverage_caps=list(COVERAGE_CAPS),
        eligible_requests=sum(r["eligible"] for r in rows),
        means={
            b: {
                k: float(np.mean([r[k] for r in rows if r["condition"] == b]))
                for k in ("utility", "ontime_fraction")
            }
            for b in BEHAVIORS
        },
        actual_executed_learned_steps=0,
        no_new_independent_groups=True,
        native_improvement_proven=False,
        SOTA_achieved=False,
    )


def run_coverage(config, out):
    p = validate_coverage(read_json(config))
    require(compatible_engines(p), "coverage sources changed after plan")
    bundles = {k: dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "protocol.json", p)
    runtime = dense._expected_runtime(p, out)
    (out / "models").mkdir()
    for key, entry in p["models"].items():
        shutil.copyfile(entry["path"], out / "models" / (key + ".json"))
    shutil.copyfile(p["video_source"]["path"], out / "recorded-video.mp4")
    require(digest(out / "recorded-video.mp4") == p["video_source"]["sha256"], "copied movie changed")
    write_json(out / "runtime.json", runtime)
    sources = {
        **{
            k: asset_directory() / k.split("/")[1]
            if k.startswith("assets/")
            else Path(__file__).with_name(k.split("/")[1])
            for k in p["source_sha256"]
        },
        **extra_sources(),
        "templates/dense_episode.mjs": asset_directory() / "dense_episode.mjs",
    }
    for name, source in sources.items():
        target = out / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    dense._validate_recorded_runtime(out, p, runtime)
    rows = []
    seals = {}
    last = -1
    try:
        for trial in runtime["episodes"]:
            child = out / trial["id"]
            require(not child.exists(), "coverage outcomes cannot be replaced/recollected")
            print(
                f"coverage {p['stage']} {len(rows) + 1}/{len(runtime['episodes'])} {trial['id']}", flush=True
            )
            try:
                _collect(
                    [
                        "node",
                        str(asset_directory() / "coverage_episode.mjs"),
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
            row, derived = audit_coverage_episode(child, p, trial, bundles)
            require(
                row["start_epoch_ms"] > last
                and (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "nonprospective/changed-runtime coverage",
            )
            last = row["cutoff_epoch_ms"]
            write_json(child / "derived.json", derived)
            seal_directory(child, sorted(x.name for x in child.iterdir() if x.is_file()), CHILD_SEAL)
            seals[trial["id"]] = digest(child / "manifest.json")
            rows.append(row)
        require(compatible_engines(p), "coverage source changed during collection")
        validate_coverage(p)
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
            role=p["stage"],
            no_new_independent_groups=True,
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


def audit_coverage(root):
    root = Path(root).resolve()
    seal = verify_seal(root, PARENT_SEAL)
    p = validate_coverage(read_json(root / "protocol.json"))
    require(
        seal["role"] == p["stage"]
        and seal.get("no_new_independent_groups") is True
        and seal.get("SOTA_achieved") is False,
        "sealed coverage role/independence mismatch",
    )
    require(compatible_engines(p), "coverage verifier implementation changed")
    for name, sha in {**p["source_sha256"], **p["extra_source_sha256"]}.items():
        require(digest(root / "sources" / name) == sha, "sealed coverage engine changed")
    require(
        digest(root / "sources/templates/dense_episode.mjs") == p["collector_template_sha256"]
        and digest(root / "recorded-video.mp4") == p["video_source"]["sha256"],
        "sealed template/movie changed",
    )
    bundles = {k: dense._base_bundle(root / "models" / (k + ".json")) for k in p["models"]}
    runtime = read_json(root / "runtime.json")
    dense._validate_recorded_runtime(root, p, runtime)
    require(
        set(seal["episodes"]) == {t["id"] for t in runtime["episodes"]}, "missing declared coverage peers"
    )
    rows = []
    last = -1
    for trial in runtime["episodes"]:
        child = root / trial["id"]
        verify_seal(child, CHILD_SEAL)
        require(
            digest(child / "manifest.json") == seal["episodes"][trial["id"]]
            and (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
            "child/runtime coverage seal changed",
        )
        row, derived = audit_coverage_episode(child, p, trial, bundles)
        require(
            row["start_epoch_ms"] > last and derived == read_json(child / "derived.json"),
            "raw coverage order/derived labels changed",
        )
        last = row["cutoff_epoch_ms"]
        rows.append(row)
    require(
        rows == read_json(root / "episodes.json") and _report(rows, p) == read_json(root / "report.json"),
        "coverage raw replay statistics changed",
    )
    return dict(
        verified_peers=len(rows),
        role=p["stage"],
        full_raw_replay=True,
        read_only=True,
        no_new_independent_groups=True,
        actual_executed_learned_steps=0,
        SOTA_achieved=False,
    )
