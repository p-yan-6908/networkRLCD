"""Versioned native repair studies. Legacy data/engines/gates are never rewritten."""

import copy
import re
import shutil
from pathlib import Path

import numpy as np

from .native_frame_metrics import summarize_native_frames
from .native_learning import validate_native_bundle
from .native_observations import CAPS, FEATURE_NAMES, NativeSenderObservationEncoder
from .native_policy_replay import verify_live_capture_associations
from .native_protocol import (
    DEFAULT_LIMITS,
    SCHEDULES,
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    source_identity,
    verify_seal,
    write_json,
)
from .native_repair4_policy import (
    CONFIG,
    RepairPolicy,
    SenderContentEncoder,
    executed_learned_action,
    validate_repair_bundle,
)
from .native_repair4_statistics import analyze_native_rows
from .native_statistics import validation_selection
from .native_study import _collect, _recover_cleanup_capture, _verify_all_models
from .native_video import extra_sources as video_sources
from .native_video import summarize_video_quality, validate_catalog
from .native_wire import replay_native_wire

STUDY_ABI = "native_repair4_study_v4"
SOURCE_KIND = "recorded_video_repair_v4"
PARENT_SEAL = "native_repair4_study_complete"
CHILD_SEAL = "native_repair4_episode_verified"
RECIPE = dict(
    abi="native_repair4_measurement_v4",
    movie_loading="verified_inode_http_range",
    warmup_iterations=64,
    warmup_disposable_instances=True,
    initial_cap_bps=300000,
    receiver_target_ms=0,
    feedback_channel="presentation-ack-v2",
    feedback_send_ms=100,
    feedback_same_impaired_connection=True,
    common_shadow_inference=True,
    sender_content="owned_pre_marker_rgb_gradient_motion",
    risk_architecture="seven_factual_action_heads",
    fallback="native_gcc",
)
LEARNER = dict(
    model_seeds=[3601, 3611, 3621],
    hidden=32,
    updates=3600,
    risk_updates=1600,
    batch_size=128,
    learning_rate=0.0003,
    cql_alpha=1.0,
    target_update_every=100,
    gamma=0.98,
    n_step=10,
    miss_penalty=3.0,
    switch_penalty=0.01,
    psnr_divisor=50,
)


def extra_sources():
    return {
        **video_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in (
                "native_repair4_policy.py",
                "native_repair4_study.py",
                "native_repair4_learning.py",
                "native_repair4_statistics.py",
                "native_repair3_policy.py",
                "native_repair3_study.py",
            )
        },
        **{
            "assets/" + n: asset_directory() / n
            for n in (
                "repair4_policy.mjs",
                "repair3_policy.mjs",
                "repair4_episode.mjs",
                "repair_http.mjs",
                "streamed_video4.mjs",
                "streamed_video.mjs",
            )
        },
    }


def video_overlap(a, b):
    """Movie playback reservations are [start,end); generated-scene IDs remain inclusive."""
    return a[0] < b[1] and b[0] < a[1]


def _entry(path):
    p = Path(path).resolve()
    return dict(path=str(p), sha256=digest(p))


def reservations(results):
    excluded, inputs = [], {}
    paths = sorted(
        set(Path(results).glob("native-*/protocol.json")) | set(Path("configs").glob("native*repair*.json"))
    )
    for path in paths:
        p = read_json(path)
        if p.get("source_kind") not in (
            "recorded_video_v1",
            "recorded_video_repair_v2",
            "recorded_video_repair_v3",
            SOURCE_KIND,
        ):
            continue
        source = validate_catalog(p["video_source"])
        for g in p["groups"]:
            s = g["video_segment"]
            require(
                isinstance(s, list)
                and len(s) == 2
                and all(type(x) is int for x in s)
                and 0 <= s[0] < s[1] <= source["duration_ms"],
                "invalid prior movie reservation",
            )
            excluded.append(dict(sha256=source["sha256"], segment=s))
        inputs[str(path.resolve())] = digest(path)
    return excluded, inputs


def validate_repair_protocol(p):
    require(
        p.get("panel_abi") == STUDY_ABI and p.get("source_kind") == SOURCE_KIND,
        "repair protocol ABI required",
    )
    require(
        p.get("stage")
        in ("train", "calibration", "selected-calibration", "repeatability", "validation", "test")
        and p.get("SOTA_achieved") is False,
        "explicit repair role required",
    )
    require(
        p.get("measurement_recipe") == RECIPE
        and p.get("controller_config") == CONFIG
        and p.get("learner") == LEARNER,
        "frozen repair recipe required",
    )
    require(
        p.get("limits") == DEFAULT_LIMITS and p.get("common_shadow_inference") is True,
        "repair may not relax legacy promotion/repeatability limits",
    )
    require(
        p.get("source_sha256", {}).keys() == source_identity().keys()
        and p.get("extra_source_sha256", {}).keys() == extra_sources().keys(),
        "complete repair source bindings required",
    )
    require(
        all(
            isinstance(s, str) and re.fullmatch(r"[0-9a-f]{64}", s)
            for s in [*p["source_sha256"].values(), *p["extra_source_sha256"].values()]
        ),
        "source SHA required",
    )
    c = validate_catalog(p["video_source"])
    require(
        type(p["repetitions"]) is int and 2 <= p["repetitions"] <= 20 and p["episode_timeout_s"] == 90,
        "bounded repeated repair collection required",
    )
    require(
        set(p["models"]) == {"source"} and set(p["models"]["source"]) == {"path", "sha256"},
        "original comparison model required",
    )
    if p["stage"] in ("selected-calibration", "repeatability", "validation", "test"):
        require(p.get("repair_model") is not None, "fitted repair model required for evaluation")
    if p["repair_model"] is not None:
        require(set(p["repair_model"]) == {"path", "sha256"}, "pinned repair model required")
    expected = {
        "train": {"bwe", "fixed300", "sweep", "bounded", "gcc"},
        "calibration": {"bwe", "fixed300", "sweep", "bounded", "gcc"},
        "selected-calibration": {"source"},
        "repeatability": {"rlcd-a", "rlcd-b", "bwe", "gcc"},
        "validation": {"baseline", "candidate", "bwe", "gcc"},
        "test": {"baseline", "candidate", "bwe", "gcc"},
    }[p["stage"]]
    require(set(p["conditions"]) == expected, "complete repair conditions required")
    for name, condition in p["conditions"].items():
        require(condition.get("model") == "source", "common source shadow required")
        if p["stage"] in ("train", "calibration"):
            require(
                condition == dict(controller="explore", model="source", behavior=name),
                "declared exploration only in fitting roles",
            )
        else:
            controller = name if name in ("bwe", "gcc") else "rlcd" if name == "baseline" else "repair"
            require(condition == dict(controller=controller, model="source"), "wrong repair control mapping")
    reserved = []
    require(
        p["groups"] and len({g["id"] for g in p["groups"]}) == len(p["groups"]),
        "unique source groups required",
    )
    for i, g in enumerate(p["groups"]):
        require(
            re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", g["id"])
            and g["family"] in SCHEDULES
            and g["scene_seed"] == i * 2000
            and g["reservation_frames"] == 1000,
            "repair group identity invalid",
        )
        s = g["video_segment"]
        require(
            isinstance(s, list)
            and len(s) == 2
            and all(type(x) is int for x in s)
            and 0 <= s[0] < s[1] <= c["duration_ms"]
            and s[1] - s[0] == 20000,
            "full repair source reservation required",
        )
        require(all(not video_overlap(s, old) for old in reserved), "repair group source leakage")
        reserved.append(s)
        for old in p["excluded_video_ranges"]:
            require(
                set(old) == {"sha256", "segment"}
                and re.fullmatch(r"[0-9a-f]{64}", old["sha256"])
                and isinstance(old["segment"], list)
                and len(old["segment"]) == 2
                and all(type(x) is int for x in old["segment"])
                and 0 <= old["segment"][0] < old["segment"][1],
                "valid role exclusions required",
            )
            require(
                old["sha256"] != c["sha256"] or not video_overlap(s, old["segment"]),
                "repair source role leakage",
            )
        schedule = g["schedule"]
        require(len(schedule) == 3, "three phases required")
        for row, label in zip(schedule, ("high", "collapse", "recovery"), strict=True):
            require(
                len(row) == 3
                and finite(row[0])
                and 0 < row[0] <= 4
                and row[1] == label
                and type(row[2]) is int
                and 1000 <= row[2] <= 6000,
                "bounded repair schedule required",
            )
        require(
            len(g["orders"]) == p["repetitions"]
            and all(len(o) == len(expected) and set(o) == expected for o in g["orders"]),
            "complete prospectively ordered peers required",
        )
    return p


def plan_repair_study(
    source_model,
    video_source,
    out,
    *,
    stage="train",
    model=None,
    groups_per_family=2,
    repetitions=2,
    seed=2601,
    results_directory="results",
    repeatability_run=None,
    validation_run=None,
    families=None,
):
    require(
        type(groups_per_family) is int and 1 <= groups_per_family <= 8 and type(seed) is int and seed >= 0,
        "bounded repair group/seed required",
    )
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "repair plan already exists; choose a fresh path")
    catalog = validate_catalog(read_json(video_source))
    require(digest(catalog["path"]) == catalog["sha256"], "movie source changed")
    conditions = {}
    if stage in ("train", "calibration"):
        conditions = {
            n: dict(controller="explore", model="source", behavior=n)
            for n in ("bwe", "fixed300", "sweep", "bounded", "gcc")
        }
    elif stage == "selected-calibration":
        conditions = {"source": dict(controller="repair", model="source")}
    elif stage == "repeatability":
        conditions = {
            n: dict(controller=n if n in ("bwe", "gcc") else "repair", model="source")
            for n in ("rlcd-a", "rlcd-b", "bwe", "gcc")
        }
    else:
        conditions = {
            n: dict(
                controller=n if n in ("bwe", "gcc") else "rlcd" if n == "baseline" else "repair",
                model="source",
            )
            for n in ("baseline", "candidate", "bwe", "gcc")
        }
    excluded, inputs = reservations(results_directory)
    inputs[str(Path(video_source).resolve())] = digest(video_source)
    if model is not None:
        bundle = validate_repair_bundle(read_json(model))
        excluded += bundle.get("source_reservations", [])
    rng = np.random.default_rng(seed)
    groups = []
    families = list(SCHEDULES) if families is None else families
    require(
        families and len(set(families)) == len(families) and set(families) <= set(SCHEDULES),
        "unique supported families required",
    )
    for family in families:
        schedule = SCHEDULES[family]
        for index in range(groups_per_family):
            start = next(
                (
                    s
                    for s in range(60000, catalog["duration_ms"] - 20000, 20000)
                    if all(
                        x["sha256"] != catalog["sha256"] or not video_overlap([s, s + 20000], x["segment"])
                        for x in excluded
                    )
                ),
                None,
            )
            require(start is not None, "fresh movie reservations exhausted; import another licensed source")
            segment = [start, start + 20000]
            excluded.append(dict(sha256=catalog["sha256"], segment=segment))
            order = list(rng.permutation(list(conditions)))
            actual = copy.deepcopy(schedule)
            if stage in ("train", "calibration"):
                scale = rng.uniform(0.7, 1.25)
                for row in actual:
                    factor = scale if family == "stable" else rng.uniform(0.7, 1.25)
                    row[0] = round(min(4, max(0.12, row[0] * factor)), 5)
                    row[2] = 6000
            groups.append(
                dict(
                    id=f"{family}-{index}",
                    family=family,
                    scene_seed=len(groups) * 2000,
                    reservation_frames=1000,
                    video_segment=segment,
                    schedule=actual,
                    orders=[order[r % len(order) :] + order[: r % len(order)] for r in range(repetitions)],
                )
            )
    own = {(catalog["sha256"], tuple(g["video_segment"])) for g in groups}
    exclusions = [x for x in excluded if (x["sha256"], tuple(x["segment"])) not in own]
    p = dict(
        panel_abi=STUDY_ABI,
        source_kind=SOURCE_KIND,
        stage=stage,
        models={"source": _entry(source_model)},
        repair_model=_entry(model) if model else None,
        conditions=conditions,
        repetitions=repetitions,
        groups=groups,
        order_seed=seed,
        limits=DEFAULT_LIMITS.copy(),
        controller_config=CONFIG.copy(),
        learner=LEARNER.copy(),
        measurement_recipe=RECIPE.copy(),
        source_sha256=source_identity(),
        extra_source_sha256={k: digest(v) for k, v in extra_sources().items()},
        video_source=catalog,
        excluded_video_ranges=exclusions,
        excluded_inputs_sha256=inputs,
        episode_timeout_s=90,
        common_shadow_inference=True,
        repeatability_run=str(Path(repeatability_run).resolve()) if repeatability_run else None,
        validation_run=str(Path(validation_run).resolve()) if validation_run else None,
        SOTA_achieved=False,
    )
    if stage == "test":
        require(validation_run is not None, "validation lock required")
        p["validation_lock"] = _entry(Path(validation_run) / "selection.json")
    validate_native_bundle(read_json(source_model))
    validate_repair_protocol(p)
    write_json(out, p)
    return p


def trial_schedule(p):
    return [
        dict(
            id=f"{g['id']}-r{rep}-{c}",
            group=g["id"],
            family=g["family"],
            condition=c,
            repetition=rep,
            position=pos,
            role=p["stage"],
            scene_seed=g["scene_seed"],
            reservation_frames=g["reservation_frames"],
            schedule=g["schedule"],
            video_segment=g["video_segment"],
            exploration_seed=p["order_seed"] + i * 31 + rep * 7,
        )
        for i, g in enumerate(p["groups"])
        for rep, order in enumerate(g["orders"])
        for pos, c in enumerate(order)
    ]


def _close(a, b):
    if isinstance(b, dict):
        require(isinstance(a, dict) and set(a) == set(b), "repair decision schema mismatch")
        for k in b:
            _close(a[k], b[k])
    elif isinstance(b, list):
        require(isinstance(a, list) and len(a) == len(b), "repair vector shape mismatch")
        for x, y in zip(a, b, strict=True):
            _close(x, y)
    elif isinstance(b, bool) or b is None or isinstance(b, str):
        require(type(a) is type(b) and a == b, "repair decision identity mismatch")
    else:
        require(finite(a) and finite(b) and abs(a - b) <= 1e-9, "repair numerical replay mismatch")


def exploration_cap(behavior, step, seed, features):
    if behavior == "gcc":
        return CAPS[-1]
    budget = features[0] * 4000000 * 0.85 if features[9] == 1 else CAPS[0]
    maximum = max([i for i, c in enumerate(CAPS) if c <= budget + 0.001], default=0)
    if behavior == "bwe":
        return CAPS[maximum]
    if behavior == "fixed300":
        return CAPS[1]
    index = ((step // (10 if behavior == "sweep" else 30)) * 3 + seed) % 7
    if behavior == "sweep":
        return CAPS[index]
    if behavior == "bounded":
        return CAPS[min(index, maximum)]
    raise ValueError("unknown exploration behavior")


def audit_repair_episode(root, p, trial, bundles, repair_bundle):
    root = Path(root)
    summary, sender, frames = [
        read_json(root / n) for n in ("summary.json", "sender_observations.json", "frame_events.json")
    ]
    condition = p["conditions"][trial["condition"]]
    require(
        summary["collection_config"]
        == dict(panel_abi=STUDY_ABI, panel_sha256=digest(root / "panel_snapshot.json"), **trial),
        "repair trial identity changed",
    )
    require(
        summary["native_controller"] == condition["controller"]
        and sender["controller"]
        == dict(
            controller=condition["controller"],
            behavior=condition.get("behavior"),
            repair_model_sha256=p["repair_model"]["sha256"] if p["repair_model"] else None,
            repair_config=CONFIG,
        ),
        "repair controller provenance mismatch",
    )
    require(
        summary["measurement_recipe"] == RECIPE
        and sender["measurement_recipe"] == RECIPE
        and summary["native_rtc"] is True
        and summary["local_loopback_only"] is True
        and summary["connection"] == "connected"
        and summary["transport_cc_negotiated"] is True,
        "wrong repair measurement contract",
    )
    require(
        summary["native_actuation"]["encoder_max_bitrate_bps"] == 300000
        and summary["native_actuation"]["receiver_jitter_buffer_target_ms"] == 0,
        "repair initial readback mismatch",
    )
    require(
        not sender["sampling_errors"]
        and sender["measurement_start_ms"] == frames["measurement_start_ms"]
        and sender["measurement_cutoff_ms"] == frames["measurement_cutoff_ms"],
        "repair clock qualification failed",
    )
    require(
        sender["common_models_sha256"] == {k: e["sha256"] for k, e in p["models"].items()}
        and read_json(root / "all_models.json") == bundles
        and read_json(root / "repair_model.json") == repair_bundle,
        "frozen common models changed",
    )
    for name, sha in p["extra_source_sha256"].items():
        if name.startswith("assets/"):
            file = "source_snapshot.mjs" if name.endswith("repair4_episode.mjs") else name.split("/")[1]
            require(digest(root / file) == sha, "repair child engine changed")
    for name in (
        "frame_marker.mjs",
        "native_actuation.mjs",
        "sender_observation.mjs",
        "source_quality.mjs",
        "bwe_cap_controller.mjs",
        "native_policy.mjs",
    ):
        require(digest(root / name) == p["source_sha256"]["assets/" + name], "legacy child engine changed")
    wire = replay_native_wire(root)
    quality = summarize_video_quality(frames, p, trial)
    frame = summarize_native_frames(frames)
    require(
        frame["measurement_qualified"]
        and quality["eligible_requests"] > 0
        and frames["scene_seed"] == trial["scene_seed"],
        "repair frame/source qualification failed",
    )
    association = verify_live_capture_associations(
        frames["sources"], sender["decisions"], summary["native_actuation"]
    )
    born = {s["source_id"]: s["capture_request_ms"] for s in frames["sources"]}
    sent = {(s["source_id"], s["presented_frames"]): s for s in sender["feedback_sends"]}
    reads = {
        (r.get("source_id"), r.get("presented_frames")): r
        for r in frames["observations"]
        if r.get("known_source")
    }
    previous = None
    for event in sender["feedback_events"]:
        key = (event["source_id"], event["presented_frames"])
        require(
            key in sent
            and key in reads
            and event["capture_request_ms"] == born[event["source_id"]]
            and reads[key]["readback_ms"] <= sent[key]["sent_ms"] <= event["received_ms"],
            "feedback was not causally presented/sent/received",
        )
        require(
            previous is None
            or event["source_id"] > previous["source_id"]
            and event["received_ms"] > previous["received_ms"],
            "feedback order mismatch",
        )
        fps = (
            0
            if previous is None
            else (event["presented_frames"] - previous["presented_frames"])
            * 1000
            / (event["received_ms"] - previous["received_ms"])
        )
        require(abs(event["presented_fps"] - fps) <= 1e-9, "feedback presentation-rate replay mismatch")
        previous = event
    encoder = NativeSenderObservationEncoder()
    policy = RepairPolicy(repair_bundle)
    last_cap = 300000
    last_ack = frames["measurement_start_ms"]
    feedback_index = -1
    source_index = 0
    content_encoder = SenderContentEncoder()
    learned = 0
    above = 0
    for i, row in enumerate(sender["decisions"]):
        obs = row["observation"]
        sample = obs["sample_ms"]
        ack = row["ack_ms"]
        require(
            row["step_id"] == i
            and last_ack <= sample <= ack
            and sample <= frames["measurement_cutoff_ms"]
            and obs["raw_source"]["encoder_cap_bps"] == last_cap,
            "noncausal repair command/clock",
        )
        _close(obs["features"], encoder.observe(obs["raw_source"], sample))
        require(tuple(obs["feature_names"]) == FEATURE_NAMES, "wrong sender feature meanings")
        while (
            feedback_index + 1 < len(sender["feedback_events"])
            and sender["feedback_events"][feedback_index + 1]["received_ms"] <= sample
        ):
            feedback_index += 1
        expected_feedback = (
            None
            if feedback_index < 0
            else {
                k: sender["feedback_events"][feedback_index][k]
                for k in ("source_id", "capture_request_ms", "received_ms", "presented_fps")
            }
        )
        _close(row["feedback_input"], expected_feedback)
        while (
            source_index < len(frames["sources"])
            and frames["sources"][source_index]["capture_request_ms"] <= sample
        ):
            source = frames["sources"][source_index]
            content_encoder.observe(source["reference_rgb"], source["capture_request_ms"])
            source_index += 1
        _close(obs["content_features"], content_encoder.snapshot(sample))
        decision = policy.observe(obs, expected_feedback)
        _close(row["repair_decision"], decision)
        if condition["controller"] == "repair":
            cap = decision["encoder_max_bitrate_bps"]
        elif condition["controller"] == "rlcd":
            cap = row["policy_decision"]["encoder_max_bitrate_bps"]
        else:
            cap = exploration_cap(
                condition.get("behavior", "gcc" if condition["controller"] == "gcc" else "bwe"),
                i,
                trial["exploration_seed"],
                obs["features"],
            )
        _close(row["proposed_action"], dict(encoder_max_bitrate_bps=cap, receiver_jitter_buffer_target_ms=0))
        actual = row["actuation_readback"]
        require(
            actual["encoder_max_bitrate_bps"] == cap
            and actual["receiver_jitter_buffer_target_ms"] == 0
            and row["changed"] is (cap != last_cap),
            "repair action readback mismatch",
        )
        require(
            finite(row["repair_inference_ms"])
            and row["repair_inference_ms"] >= 0
            and row["repair_inference_ms"] + sum(row["model_inference_ms"].values())
            <= row["total_inference_ms"] + 1e-6,
            "unaccounted repair inference timing",
        )
        if row["changed"]:
            policy.acknowledge(cap, ack)
        learned += executed_learned_action(decision, cap, condition["controller"])
        above += (
            condition["controller"] == "repair"
            and not decision["fallback"]
            and cap > decision["hard_budget_bps"] + 0.001
            and cap != CAPS[0]
        )
        last_cap = cap
        last_ack = ack
    p99 = _verify_all_models(sender, bundles)
    phases = {}
    for phase in ("high", "collapse", "recovery"):
        labels = [s for s in quality["source_labels"] if s["phase"] == phase]
        require(labels, "missing complete repair phase")
        phases[phase] = dict(
            utility=float(np.mean([s["ontime_sampled_psnr_contribution"] for s in labels])),
            ontime_fraction=float(np.mean([s["identifiable_ontime"] for s in labels])),
        )
    ages = [
        o["readback_ms"] - born[o["source_id"]]
        for o in frames["observations"]
        if o.get("known_source") and o["readback_ms"] >= frames["measurement_start_ms"]
    ]
    row = dict(
        **trial,
        utility=quality["utility"],
        eligible=quality["eligible_requests"],
        ontime_fraction=quality["identified_ontime"] / quality["eligible_requests"],
        inference_p99_ms=p99,
        signals=dict(
            feedback_receipts=len(sender["feedback_events"]),
            receiver_age_p50_ms=float(np.quantile(ages, 0.5)) if ages else None,
            receiver_age_p99_ms=float(np.quantile(ages, 0.99)) if ages else None,
        ),
        phases=phases,
        learned_fraction=learned / len(sender["decisions"]),
        above_bwe_budget_steps=above,
        start_epoch_ms=frames["time_origin_epoch_ms"] + frames["measurement_start_ms"],
        cutoff_epoch_ms=frames["time_origin_epoch_ms"] + frames["measurement_cutoff_ms"],
    )
    return row, dict(
        wire=wire,
        quality=quality,
        frame=frame,
        association=association,
        feedback_receipts=len(sender["feedback_events"]),
    )


def _report(rows, p):
    report = analyze_native_rows(rows, p)
    report["measurement_recipe"] = RECIPE
    if p["stage"] in ("validation", "test"):
        active = [r for r in rows if r["condition"] == "candidate"]
        report["learned_fraction"] = float(np.mean([r["learned_fraction"] for r in active]))
        report["hard_envelope_violations"] = sum(r["above_bwe_budget_steps"] for r in active)
    return report


def _selection(report, p):
    decision = validation_selection(report, p)
    if report["learned_fraction"] < 0.05:
        decision["failures"].append("insufficient_learned_coverage")
    if report["hard_envelope_violations"]:
        decision["failures"].append("BWE_envelope_violation")
    if decision["failures"]:
        decision["selected"] = "baseline"
    return decision


def _prerequisites(p):
    if p["stage"] in ("repeatability", "validation", "test"):
        from .native_repair4_calibration import verify_selected_repair_calibration

        verify_selected_repair_calibration(read_json(p["repair_model"]["path"]))
    for file, sha in p["excluded_inputs_sha256"].items():
        require(digest(file) == sha, "prior role evidence changed")
    if p["stage"] in ("validation", "test"):
        require(p["repeatability_run"] is not None, "new-recipe repeatability required")
        audit_repair_study(p["repeatability_run"])
        prior = read_json(Path(p["repeatability_run"]) / "protocol.json")
        require(
            prior["stage"] == "repeatability"
            and prior["repair_model"] == p["repair_model"]
            and prior["models"] == p["models"]
            and prior["measurement_recipe"] == p["measurement_recipe"]
            and read_json(Path(p["repeatability_run"]) / "report.json")["identical_policy"]["passed"],
            "repair repeatability prerequisite failed",
        )
    if p["stage"] == "test":
        audit_repair_study(p["validation_run"])
        require(
            digest(p["validation_lock"]["path"]) == p["validation_lock"]["sha256"]
            and read_json(p["validation_lock"]["path"])["selected"] == "candidate",
            "candidate not selected before test",
        )


def _base_bundle(path):
    bundle = read_json(path)
    validate_native_bundle(bundle)
    return bundle


def _compatible_engines(p, for_audit=False):
    current = {k: digest(v) for k, v in extra_sources().items()}
    return p["source_sha256"] == source_identity() and all(
        name == "python/native_repair4_study.py"
        or (for_audit and name == "assets/repair4_episode.mjs")
        or current[name] == sha
        for name, sha in p["extra_source_sha256"].items()
    )


def _expected_runtime(p, root):
    root = Path(root).resolve()
    expected = copy.deepcopy(p)
    expected["episodes"] = trial_schedule(p)
    for key, entry in expected["models"].items():
        entry["path"] = str(root / "models" / (key + ".json"))
    if expected["repair_model"]:
        expected["repair_model"]["path"] = str(root / "models/repair.json")
    expected["video_source"]["path"] = str(root / "recorded-video.mp4")
    return expected


def _validate_recorded_runtime(out, p, runtime):
    require(runtime == _expected_runtime(p, out), "runtime differs from frozen repair protocol")
    for name, entry in p["models"].items():
        require(
            digest(out / "models" / (name + ".json")) == entry["sha256"], "copied comparison model changed"
        )
    if p["repair_model"]:
        require(
            digest(out / "models/repair.json") == p["repair_model"]["sha256"], "copied repair model changed"
        )


def _preflight_resume(out, p, runtime, bundles, repair_bundle):
    missing = False
    last = -1
    for trial in runtime["episodes"]:
        child = out / trial["id"]
        if not child.exists():
            missing = True
            continue
        require(not missing, "existing peers are not a prospective schedule prefix")
        require(
            all(
                (child / n).is_file()
                for n in ("summary.json", "frame_events.json", "sender_observations.json", "events.jsonl.gz")
            ),
            "partial repair capture cannot be replaced",
        )
        require(
            (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
            "capture used changed runtime",
        )
        sealed = (child / "manifest.json").exists()
        if sealed:
            verify_seal(child, CHILD_SEAL)
        row, derived = audit_repair_episode(child, p, trial, bundles, repair_bundle)
        require(row["start_epoch_ms"] > last, "nonprospective repair execution")
        last = row["cutoff_epoch_ms"]
        if sealed:
            require(
                read_json(child / "derived.json") == derived, "sealed repair outcomes changed during resume"
            )


def run_repair_study(config, out, resume=False):
    p = validate_repair_protocol(read_json(config))
    _prerequisites(p)
    require(
        _compatible_engines(p)
        if resume
        else p["source_sha256"] == source_identity()
        and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()},
        "repair code changed after plan",
    )
    bundles = {k: _base_bundle(e["path"]) for k, e in p["models"].items()}
    for e in [*p["models"].values(), *([p["repair_model"]] if p["repair_model"] else [])]:
        require(digest(e["path"]) == e["sha256"], "planned model changed")
    repair_bundle = (
        validate_repair_bundle(read_json(p["repair_model"]["path"])) if p["repair_model"] else None
    )
    out = Path(out).resolve()
    if resume:
        require(read_json(out / "protocol.json") == p, "resume plan differs from recorded recipe")
        if (out / "manifest.json").exists():
            audit_repair_study(out)
            return read_json(out / "report.json")
        for name, sha in {**p["source_sha256"], **p["extra_source_sha256"]}.items():
            require(digest(out / "sources" / name) == sha, "captured engine changed before resume")
        require(
            digest(out / "recorded-video.mp4") == p["video_source"]["sha256"], "movie changed before resume"
        )
        return _execute_panel(out, p, read_json(out / "runtime.json"), bundles, repair_bundle, resume=True)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "protocol.json", p)
    runtime = copy.deepcopy(p)
    runtime["episodes"] = trial_schedule(p)
    (out / "models").mkdir()
    for key, entry in runtime["models"].items():
        shutil.copyfile(entry["path"], out / "models" / (key + ".json"))
        entry["path"] = str(out / "models" / (key + ".json"))
    if runtime["repair_model"]:
        shutil.copyfile(runtime["repair_model"]["path"], out / "models/repair.json")
        runtime["repair_model"]["path"] = str(out / "models/repair.json")
    shutil.copyfile(p["video_source"]["path"], out / "recorded-video.mp4")
    require(digest(out / "recorded-video.mp4") == p["video_source"]["sha256"], "movie copy changed")
    runtime["video_source"]["path"] = str(out / "recorded-video.mp4")
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
    return _execute_panel(out, p, runtime, bundles, repair_bundle)


def _execute_panel(out, p, runtime, bundles, repair_bundle, resume=False):
    _validate_recorded_runtime(out, p, runtime)
    if resume:
        _preflight_resume(out, p, runtime, bundles, repair_bundle)
    rows = []
    seals = {}
    last = -1
    try:
        for trial in runtime["episodes"]:
            child = out / trial["id"]
            sealed = (child / "manifest.json").exists()
            if sealed:
                require(resume, "completed repair capture already exists")
                verify_seal(child, CHILD_SEAL)
            elif child.exists():
                require(
                    resume
                    and all(
                        (child / n).is_file()
                        for n in (
                            "summary.json",
                            "frame_events.json",
                            "sender_observations.json",
                            "events.jsonl.gz",
                        )
                    ),
                    "partial repair capture cannot be replaced",
                )
            else:
                try:
                    _collect(
                        [
                            "node",
                            str(asset_directory() / "repair4_episode.mjs"),
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
            row, derived = audit_repair_episode(child, p, trial, bundles, repair_bundle)
            require(row["start_epoch_ms"] > last, "nonprospective repair execution")
            last = row["cutoff_epoch_ms"]
            require(
                (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "capture used changed runtime",
            )
            if sealed:
                require(
                    read_json(child / "derived.json") == derived,
                    "sealed repair outcomes changed during resume",
                )
            else:
                write_json(child / "derived.json", derived)
                seal_directory(child, sorted(x.name for x in child.iterdir() if x.is_file()), CHILD_SEAL)
            seals[trial["id"]] = digest(child / "manifest.json")
            rows.append(row)
        require(
            _compatible_engines(p),
            "engine changed during repair collection",
        )
        report = _report(rows, p)
        write_json(out / "episodes.json", rows)
        write_json(out / "report.json", report)
        if p["stage"] == "validation":
            write_json(
                out / "selection.json",
                dict(
                    **_selection(report, p),
                    repair_model_sha256=p["repair_model"]["sha256"],
                    limits=p["limits"],
                    protocol_sha256=digest(out / "protocol.json"),
                ),
            )
        if p["stage"] == "test":
            shutil.copyfile(p["validation_lock"]["path"], out / "selection_snapshot.json")
        seal_directory(
            out,
            sorted(
                str(x.relative_to(out))
                for x in out.rglob("*")
                if x.is_file()
                and x.parent == out
                or x.is_file()
                and x.relative_to(out).parts[0] in ("sources", "models")
            ),
            PARENT_SEAL,
            episodes=seals,
            role=p["stage"],
            SOTA_achieved=False,
        )
        return report
    except Exception as error:
        write_json(
            out
            / (
                "failure.json"
                if not (out / "failure.json").exists()
                else next(
                    f"failure_resume_{i}.json"
                    for i in range(1, 100)
                    if not (out / f"failure_resume_{i}.json").exists()
                )
            ),
            dict(
                error=str(error),
                completed_peers=len(rows),
                all_partial_evidence_preserved=True,
                no_outcomes_replaced=True,
            ),
        )
        raise


def audit_repair_study(root):
    root = Path(root).resolve()
    seal = verify_seal(root, PARENT_SEAL)
    p = validate_repair_protocol(read_json(root / "protocol.json"))
    require(seal["role"] == p["stage"] and seal.get("SOTA_achieved") is False, "parent role mismatch")
    for name, sha in {**p["source_sha256"], **p["extra_source_sha256"]}.items():
        require(digest(root / "sources" / name) == sha, "sealed repair engine changed")
    require(
        _compatible_engines(p, for_audit=True),
        "repair verifier implementation changed",
    )
    require(digest(root / "recorded-video.mp4") == p["video_source"]["sha256"], "sealed repair movie changed")
    bundles = {k: _base_bundle(root / "models" / (k + ".json")) for k in p["models"]}
    for k, e in p["models"].items():
        require(digest(root / "models" / (k + ".json")) == e["sha256"], "original comparison model changed")
    repair_bundle = (
        validate_repair_bundle(read_json(root / "models/repair.json")) if p["repair_model"] else None
    )
    if p["repair_model"]:
        require(digest(root / "models/repair.json") == p["repair_model"]["sha256"], "repair model changed")
    runtime = read_json(root / "runtime.json")
    _validate_recorded_runtime(root, p, runtime)
    require(set(seal["episodes"]) == {t["id"] for t in runtime["episodes"]}, "missing repair episodes")
    rows = []
    last = -1
    for trial in runtime["episodes"]:
        child = root / trial["id"]
        verify_seal(child, CHILD_SEAL)
        require(
            digest(child / "manifest.json") == seal["episodes"][trial["id"]]
            and (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
            "repair child/runtime seal changed",
        )
        row, derived = audit_repair_episode(child, p, trial, bundles, repair_bundle)
        require(
            row["start_epoch_ms"] > last and derived == read_json(child / "derived.json"),
            "repair order/derived data changed",
        )
        rows.append(row)
        last = row["cutoff_epoch_ms"]
    require(
        rows == read_json(root / "episodes.json") and _report(rows, p) == read_json(root / "report.json"),
        "repair statistics changed",
    )
    if p["stage"] == "validation":
        require(
            read_json(root / "selection.json")
            == dict(
                **_selection(_report(rows, p), p),
                repair_model_sha256=p["repair_model"]["sha256"],
                limits=p["limits"],
                protocol_sha256=digest(root / "protocol.json"),
            ),
            "repair selection changed",
        )
    if p["stage"] == "test":
        require(
            digest(root / "selection_snapshot.json") == p["validation_lock"]["sha256"],
            "test selection snapshot changed",
        )
    return dict(
        verified_peers=len(rows), role=p["stage"], full_raw_replay=True, read_only=True, SOTA_achieved=False
    )
