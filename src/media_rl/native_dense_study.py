"""Independent scalar-cap mechanism probe; all V5 engines/labels remain sealed.

No neural policy can be loaded or trained here. Full raw replay and original
measurement/runtime limits apply; diagnostic outcomes cannot qualify a policy.
"""

import copy
import re
import shutil
from pathlib import Path

import numpy as np

from .native_dense_control import (
    ACTUATION_ABI,
    BEHAVIORS,
    CAP_DOMAIN,
    CONFIG,
    RepairPolicy,
    SenderContentEncoder,
    executed_learned_action,
    exploration_cap,
)
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
from .native_repair5_statistics import analyze_native_rows, cluster_estimate
from .native_repair5_study import _base_bundle, _close, trial_schedule
from .native_repair5_study import extra_sources as repair_sources
from .native_study import _collect, _recover_cleanup_capture, _verify_all_models
from .native_video import summarize_video_quality, validate_catalog
from .native_wire import replay_native_wire

STUDY_ABI = "native_dense_scalar_probe_v1"
SOURCE_KIND = "recorded_video_dense_probe_v1"
PARENT_SEAL = "native_dense_probe_complete"
CHILD_SEAL = "native_dense_probe_episode_verified"
RECIPE = dict(
    abi="native_dense_probe_measurement_v1",
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
    risk_architecture="no_dense_learned_actor_common_shadow_only",
    fallback="diagnostic_controls_not_learned",
    encoder_degradation_preference="maintain-framerate",
    scalar_cap_domain_bps=list(CAP_DOMAIN),
    continuous_bwe_headroom=0.85,
    shadow_cap_projection="legacy_floor_cap",
)
ENCODER_RECIPE = dict(degradation_preference="maintain-framerate", readback_verified=True)


def extra_sources():
    return {
        **repair_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in ("native_dense_control.py", "native_dense_study.py", "native_dense_cli.py")
        },
        **{
            "assets/" + n: asset_directory() / n
            for n in (
                "dense_episode.mjs",
                "dense_control.mjs",
                "dense_actuation.mjs",
                "streamed_dense_video.mjs",
            )
        },
    }


def video_overlap(a, b):
    return max(a[0], b[0]) < min(a[1], b[1])


def _entry(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=digest(path))


def reservations(results):
    excluded, inputs = [], {}
    paths = set(Path(results).glob("**/protocol.json"))
    configs = Path(results).parent / "configs"
    if configs.exists():
        paths |= set(configs.glob("native_*.json"))
    kinds = {
        SOURCE_KIND,
        "recorded_video_v1",
        "recorded_video_repair_v2",
        "recorded_video_repair_v3",
        "recorded_video_repair_v4",
        "recorded_video_repair_v5",
    }
    for path in sorted(paths):
        p = read_json(path)
        if p.get("source_kind") not in kinds:
            continue
        inputs[str(path.resolve())] = digest(path)
        excluded += [
            dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
        ]
    return excluded, inputs


def validate_dense_protocol(p):
    require(
        p.get("panel_abi") == STUDY_ABI
        and p.get("source_kind") == SOURCE_KIND
        and p.get("stage") == "diagnostic"
        and p.get("SOTA_achieved") is False,
        "dense probe is diagnostic only",
    )
    require(
        p.get("repair_model") is None and p.get("learner") is None,
        "dense probe cannot load or fit neural weights",
    )
    require(
        p.get("measurement_recipe") == RECIPE
        and p.get("controller_config") == CONFIG
        and p.get("limits") == DEFAULT_LIMITS
        and p.get("common_shadow_inference") is True,
        "original measurement and runtime limits required",
    )
    require(
        p.get("source_sha256", {}).keys() == source_identity().keys()
        and p.get("extra_source_sha256", {}).keys() == extra_sources().keys(),
        "complete dense source bindings required",
    )
    require(
        all(
            isinstance(s, str) and re.fullmatch(r"[0-9a-f]{64}", s)
            for s in [*p["source_sha256"].values(), *p["extra_source_sha256"].values()]
        ),
        "source SHA required",
    )
    catalog = validate_catalog(p["video_source"])
    require(
        type(p["repetitions"]) is int and 2 <= p["repetitions"] <= 20 and p["episode_timeout_s"] == 90,
        "bounded prospective repeated peers required",
    )
    require(
        set(p["models"]) == {"source"} and set(p["models"]["source"]) == {"path", "sha256"},
        "frozen common native model required",
    )
    expected = {n: dict(controller="explore", model="source", behavior=n) for n in BEHAVIORS}
    require(p["conditions"] == expected, "complete legacy/continuous/fixed450/GCC controls required")
    require(
        p["groups"] and len({g["id"] for g in p["groups"]}) == len(p["groups"]),
        "unique source groups required",
    )
    reserved = []
    for i, g in enumerate(p["groups"]):
        require(
            re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", g["id"])
            and g["family"] in SCHEDULES
            and g["scene_seed"] == i * 2000
            and g["reservation_frames"] == 1000,
            "dense group identity invalid",
        )
        s = g["video_segment"]
        require(
            isinstance(s, list)
            and len(s) == 2
            and all(type(x) is int for x in s)
            and 0 <= s[0] < s[1] <= catalog["duration_ms"]
            and s[1] - s[0] == 20000,
            "full source reservation required",
        )
        require(all(not video_overlap(s, old) for old in reserved), "dense group source overlap")
        reserved.append(s)
        for old in p["excluded_video_ranges"]:
            require(
                set(old) == {"sha256", "segment"}
                and re.fullmatch(r"[0-9a-f]{64}", old["sha256"])
                and isinstance(old["segment"], list)
                and len(old["segment"]) == 2
                and all(type(x) is int for x in old["segment"])
                and 0 <= old["segment"][0] < old["segment"][1],
                "valid role exclusion required",
            )
            require(
                old["sha256"] != catalog["sha256"] or not video_overlap(s, old["segment"]),
                "dense probe overlaps an existing role",
            )
        require(len(g["schedule"]) == 3, "three phases required")
        for row, label in zip(g["schedule"], ("high", "collapse", "recovery"), strict=True):
            require(
                len(row) == 3
                and finite(row[0])
                and 0 < row[0] <= 4
                and row[1] == label
                and type(row[2]) is int
                and 1000 <= row[2] <= 6000,
                "bounded schedule required",
            )
        require(
            len(g["orders"]) == p["repetitions"]
            and all(len(o) == len(BEHAVIORS) and set(o) == set(BEHAVIORS) for o in g["orders"]),
            "prospectively complete diagnostic order required",
        )
    return p


def plan_dense_study(
    source_model,
    video_source,
    out,
    *,
    families=None,
    groups_per_family=1,
    repetitions=2,
    seed=6101,
    results_directory="results",
):
    require(
        type(groups_per_family) is int and 1 <= groups_per_family <= 8 and type(seed) is int and seed >= 0,
        "bounded group/seed required",
    )
    require(type(repetitions) is int and 2 <= repetitions <= 20, "bounded repetition count required")
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "dense plan exists; use a fresh path")
    catalog = validate_catalog(read_json(video_source))
    require(digest(catalog["path"]) == catalog["sha256"], "movie source changed")
    excluded, inputs = reservations(results_directory)
    inputs[str(Path(video_source).resolve())] = digest(video_source)
    rng = np.random.default_rng(seed)
    families = ["stable"] if families is None else list(families)
    require(
        families and len(set(families)) == len(families) and set(families) <= set(SCHEDULES),
        "unique supported families required",
    )
    groups = []
    for family in families:
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
            require(start is not None, "fresh licensed source segments exhausted")
            segment = [start, start + 20000]
            excluded.append(dict(sha256=catalog["sha256"], segment=segment))
            order = list(rng.permutation(list(BEHAVIORS)))
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
    own = {(catalog["sha256"], tuple(g["video_segment"])) for g in groups}
    p = dict(
        panel_abi=STUDY_ABI,
        source_kind=SOURCE_KIND,
        stage="diagnostic",
        models={"source": _entry(source_model)},
        repair_model=None,
        conditions={n: dict(controller="explore", model="source", behavior=n) for n in BEHAVIORS},
        repetitions=repetitions,
        groups=groups,
        order_seed=seed,
        limits=DEFAULT_LIMITS.copy(),
        controller_config=CONFIG.copy(),
        learner=None,
        measurement_recipe=copy.deepcopy(RECIPE),
        source_sha256=source_identity(),
        extra_source_sha256={k: digest(v) for k, v in extra_sources().items()},
        video_source=catalog,
        excluded_video_ranges=[x for x in excluded if (x["sha256"], tuple(x["segment"])) not in own],
        excluded_inputs_sha256=inputs,
        episode_timeout_s=90,
        common_shadow_inference=True,
        repeatability_run=None,
        validation_run=None,
        SOTA_achieved=False,
    )
    validate_native_bundle(read_json(source_model))
    validate_dense_protocol(p)
    write_json(out, p)
    return p


def _report(rows, p):
    result = analyze_native_rows(rows, p)
    contrasts = {}
    for c in ("bwe-continuous", "fixed450", "gcc"):
        contrasts[c] = {
            k: cluster_estimate(
                [
                    float(
                        np.mean([r[k] for r in rows if r["group"] == g["id"] and r["condition"] == c])
                        - np.mean([r[k] for r in rows if r["group"] == g["id"] and r["condition"] == "bwe"])
                    )
                    for g in p["groups"]
                ]
            )
            for k in ("utility", "ontime_fraction")
        }
    return dict(
        **result,
        paired_group_contrasts_vs_legacy_bwe=contrasts,
        measurement_recipe=copy.deepcopy(RECIPE),
        dense_learned_policy_present=False,
        actual_executed_learned_steps=0,
        mechanism_probe_not_policy_qualification=True,
    )


def _forbidden_selection():
    raise ValueError("diagnostic controls cannot qualify or promote a learned policy")


def _compatible_engines(p, for_audit=False):
    return p["source_sha256"] == source_identity() and p["extra_source_sha256"] == {
        k: digest(v) for k, v in extra_sources().items()
    }


def audit_dense_episode(root, p, trial, bundles, repair_bundle):
    root = Path(root)
    require(repair_bundle is None, "dense probe cannot load a learned actor")
    summary, sender, frames = [
        read_json(root / n) for n in ("summary.json", "sender_observations.json", "frame_events.json")
    ]
    condition = p["conditions"][trial["condition"]]
    require(
        summary.get("encoder_recipe") == ENCODER_RECIPE and sender.get("encoder_recipe") == ENCODER_RECIPE,
        "native degradation preference readback required",
    )
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
            file = "source_snapshot.mjs" if name.endswith("dense_episode.mjs") else name.split("/")[1]
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
    require(summary["native_actuation"]["native_action_abi"] == ACTUATION_ABI, "wrong scalar actuation ABI")
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
            actual["native_action_abi"] == ACTUATION_ABI
            and actual["scalar_cap_domain_bps"] == list(CAP_DOMAIN),
            "scalar readback domain changed",
        )
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


def run_dense_study(config, out):
    p = validate_dense_protocol(read_json(config))
    require(_compatible_engines(p), "dense code changed after plan")
    bundles = {k: _base_bundle(e["path"]) for k, e in p["models"].items()}
    require(
        all(digest(e["path"]) == e["sha256"] for e in p["models"].values()), "planned common model changed"
    )
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "protocol.json", p)
    runtime = _expected_runtime(p, out)
    (out / "models").mkdir()
    for key, entry in p["models"].items():
        shutil.copyfile(entry["path"], out / "models" / (key + ".json"))
    shutil.copyfile(p["video_source"]["path"], out / "recorded-video.mp4")
    require(digest(out / "recorded-video.mp4") == p["video_source"]["sha256"], "movie copy changed")
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
    _validate_recorded_runtime(out, p, runtime)
    rows, seals = [], {}
    last = -1
    try:
        for trial in runtime["episodes"]:
            child = out / trial["id"]
            require(not child.exists(), "dense peers cannot be replaced or recollected")
            try:
                _collect(
                    [
                        "node",
                        str(asset_directory() / "dense_episode.mjs"),
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
            row, derived = audit_dense_episode(child, p, trial, bundles, None)
            require(row["start_epoch_ms"] > last, "nonprospective dense execution")
            last = row["cutoff_epoch_ms"]
            require(
                (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "capture used changed runtime",
            )
            write_json(child / "derived.json", derived)
            seal_directory(child, sorted(x.name for x in child.iterdir() if x.is_file()), CHILD_SEAL)
            seals[trial["id"]] = digest(child / "manifest.json")
            rows.append(row)
        require(_compatible_engines(p), "engine changed during dense capture")
        report = _report(rows, p)
        write_json(out / "episodes.json", rows)
        write_json(out / "report.json", report)
        files = sorted(
            str(x.relative_to(out))
            for x in out.rglob("*")
            if x.is_file() and (x.parent == out or x.relative_to(out).parts[0] in ("sources", "models"))
        )
        seal_directory(out, files, PARENT_SEAL, episodes=seals, role="diagnostic", SOTA_achieved=False)
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


def audit_dense_study(root):
    root = Path(root).resolve()
    seal = verify_seal(root, PARENT_SEAL)
    p = validate_dense_protocol(read_json(root / "protocol.json"))
    require(seal["role"] == "diagnostic" and seal.get("SOTA_achieved") is False, "dense role mismatch")
    require(_compatible_engines(p, for_audit=True), "dense verifier implementation changed")
    for name, sha in {**p["source_sha256"], **p["extra_source_sha256"]}.items():
        require(digest(root / "sources" / name) == sha, "sealed engine changed")
    require(digest(root / "recorded-video.mp4") == p["video_source"]["sha256"], "sealed movie changed")
    bundles = {k: _base_bundle(root / "models" / (k + ".json")) for k in p["models"]}
    runtime = read_json(root / "runtime.json")
    _validate_recorded_runtime(root, p, runtime)
    require(set(seal["episodes"]) == {t["id"] for t in runtime["episodes"]}, "missing dense peers")
    rows, last = [], -1
    for trial in runtime["episodes"]:
        child = root / trial["id"]
        verify_seal(child, CHILD_SEAL)
        require(
            digest(child / "manifest.json") == seal["episodes"][trial["id"]]
            and (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
            "child/runtime seal changed",
        )
        row, derived = audit_dense_episode(child, p, trial, bundles, None)
        require(
            row["start_epoch_ms"] > last and derived == read_json(child / "derived.json"),
            "raw order/derived outcomes changed",
        )
        last = row["cutoff_epoch_ms"]
        rows.append(row)
    require(
        rows == read_json(root / "episodes.json") and _report(rows, p) == read_json(root / "report.json"),
        "dense statistics changed",
    )
    return dict(
        verified_peers=len(rows),
        role="diagnostic",
        full_raw_replay=True,
        read_only=True,
        learned_policy_present=False,
        SOTA_achieved=False,
    )
