"""Public owned-browser studies: repeatability, factual calibration and locked evaluation.

This is a native encoder-cap overlay on GCC, not a replacement transport controller.
"""

import errno
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from .native_dataset import history_matrix
from .native_frame_metrics import summarize_native_frames
from .native_learning import NativePolicy
from .native_policy_replay import verify_live_capture_associations, verify_native_live_evidence
from .native_protocol import (
    ASSET_NAMES,
    DEFAULT_LIMITS,
    SCHEDULES,
    STUDY_ABI,
    artifact_path,
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    source_identity,
    spans_overlap,
    verify_seal,
    write_json,
)
from .native_protocol import (
    load_protocol as load_base_protocol,
)
from .native_protocol import (
    validate_protocol as validate_base_protocol,
)
from .native_quality import summarize_native_quality
from .native_statistics import analyze_native_rows, validation_selection
from .native_wire import replay_native_wire

STUDY_SEAL = "native_reliability_study_complete"
EPISODE_SEAL = "native_reliability_episode_verified"


def validate_protocol(protocol):
    if protocol.get("source_kind") == "recorded_video_v1":
        from .native_video import validate_video_protocol

        return validate_video_protocol(protocol)
    return validate_base_protocol(protocol)


def load_protocol(path, check_sources=True):
    if read_json(path).get("source_kind") == "recorded_video_v1":
        from .native_video import load_video_protocol

        return load_video_protocol(path, check_sources=check_sources)
    return load_base_protocol(path, check_sources=check_sources)


def known_scene_ranges(results):
    """Read all recorded native scenes, including partial captures; never recycle them."""
    spans, inputs = [], {}
    for path in sorted(Path(results).glob("native-*/**/frame_events.json")):
        frames = read_json(path)
        if not frames.get("sources") or "quality_protocol" not in frames:
            continue  # Older marker-only probes used a different, unseeded scene generator.
        parent = path.parent / "manifest.json"
        seal = read_json(parent) if parent.exists() else {}
        if parent.exists():
            expected = seal.get("artifacts_sha256", {}).get("frame_events.json")
            require(expected == digest(path), "previous native frame evidence changed")
        if frames.get("video_source") is not None:
            continue  # Verify its seal first; movie coordinates are not generated IDs.
        seed = frames.get("scene_seed")
        if seed is None:
            # The exact archived original rollout calls drawSourceScene(ctx,n) and
            # drawSourceScene(refctx,marker.source_id): its implicit offset is zero.
            driver = path.parent / "source_snapshot.mjs"
            legacy_sha = "9d1cbe53e7462ddce2d92a56b53286efcb693214195c82d7a1960c6a7f3ab723"
            require(
                seal.get("artifacts_sha256", {}).get("source_snapshot.mjs") == legacy_sha
                and driver.exists()
                and digest(driver) == legacy_sha,
                "generated native quality capture missing its source identity",
            )
            seed = 0
            inputs[str(driver.resolve())] = legacy_sha
        require(type(seed) is int and seed >= 0, "invalid generated native scene identity")
        span = [
            seed + min(x["source_id"] for x in frames["sources"]),
            seed + max(x["source_id"] for x in frames["sources"]),
        ]
        if span not in spans:
            spans.append(span)
        inputs[str(path.resolve())] = digest(path)
    return spans, inputs


def plan_native_study(
    model,
    out,
    stage="repeatability",
    candidate=None,
    repetitions=2,
    groups_per_family=2,
    seed=1901,
    exclude_runs=(),
    repeatability_run=None,
    validation_run=None,
    results_directory=None,
    families=None,
    video_source=None,
):
    if video_source is not None:
        from .native_video import plan_video_study

        return plan_video_study(
            model,
            out,
            video_source,
            stage=stage,
            candidate=candidate,
            repetitions=repetitions,
            groups_per_family=groups_per_family,
            seed=seed,
            exclude_runs=exclude_runs,
            repeatability_run=repeatability_run,
            validation_run=validation_run,
            results_directory=results_directory,
            families=families,
        )
    """Freeze before outcomes. Paths in generated plans are absolute, roles are explicit."""
    require(stage in ("repeatability", "calibration", "validation", "test"), "unknown native role")
    require(type(groups_per_family) is int and 1 <= groups_per_family <= 8, "bounded native groups required")
    require(type(seed) is int and seed >= 0, "integer order seed required")
    model = Path(model).resolve()
    models = dict(source=dict(path=str(model), sha256=digest(model)))
    bundle = read_json(model)
    from .native_learning import validate_native_bundle

    validate_native_bundle(bundle)
    require(
        bundle["risk_cutoff"] == 0.5 and bundle["disagreement_cutoff"] == 0.2,
        "native screens must remain unchanged",
    )
    require(type(repetitions) is int and 2 <= repetitions <= 20, "at least two native repetitions required")
    excluded = [list(s) for s in bundle.get("provenance", {}).get("generated_scene_ranges", [])]
    excluded += [
        list(s) for s in bundle.get("provenance", {}).get("excluded_prior_generated_scene_ranges", [])
    ]
    excluded += [list(s) for s in bundle.get("selected_calibration", {}).get("source_scene_ranges", [])]
    excluded_inputs = {}
    if results_directory is not None:
        spans, hashes = known_scene_ranges(results_directory)
        excluded += spans
        excluded_inputs.update(hashes)
    for prior in exclude_runs:
        prior = Path(prior).resolve()
        audit_native_study(prior)
        old = read_json(prior / "protocol.json")
        excluded += [[g["scene_seed"], g["scene_seed"] + g["reservation_frames"]] for g in old["groups"]]
        excluded_inputs[str(prior / "manifest.json")] = digest(prior / "manifest.json")
    if stage in ("validation", "test"):
        require(
            candidate is not None and repeatability_run is not None,
            "candidate and repeatability evidence required",
        )
        candidate = Path(candidate).resolve()
        models["candidate"] = dict(path=str(candidate), sha256=digest(candidate))
        cal = read_json(candidate).get("selected_calibration", {})
        excluded += [list(s) for s in cal.get("source_scene_ranges", [])]
        conditions = dict(
            baseline=dict(controller="rlcd", model="source"),
            candidate=dict(controller="rlcd", model="candidate"),
            bwe=dict(controller="bwe", model="source"),
        )
    elif stage == "calibration":
        conditions = dict(source=dict(controller="rlcd", model="source"))
    else:
        conditions = {
            k: dict(controller="bwe" if k == "bwe" else "rlcd", model="source")
            for k in ("rlcd-a", "rlcd-b", "bwe")
        }
    validation_root = None
    for prior_root in [repeatability_run, validation_run if stage == "test" else None]:
        if prior_root is None:
            continue
        prior_root = Path(prior_root).resolve()
        audit_native_study(prior_root)
        old = read_json(prior_root / "protocol.json")
        excluded += [[g["scene_seed"], g["scene_seed"] + g["reservation_frames"]] for g in old["groups"]]
        excluded_inputs[str(prior_root / "manifest.json")] = digest(prior_root / "manifest.json")
        if stage == "test" and prior_root == Path(validation_run).resolve():
            require(old["stage"] == "validation", "validation role required before test")
            validation_root = prior_root
    rng = np.random.default_rng(seed)
    groups, used = [], list(excluded)
    families = list(SCHEDULES) if families is None else list(families)
    require(
        families and len(set(families)) == len(families) and set(families) <= set(SCHEDULES),
        "unique supported native families required",
    )
    for family in families:
        for index in range(groups_per_family):
            scene = next(
                (s for s in range(0, 64501, 25) if all(not spans_overlap([s, s + 1000], x) for x in used)),
                None,
            )
            require(
                scene is not None, "no fresh scene reservation: need a new versioned natural-content source"
            )
            used.append([scene, scene + 1000])
            order = list(rng.permutation(list(conditions)))
            groups.append(
                dict(
                    id=f"{family}-{index}",
                    family=family,
                    scene_seed=scene,
                    reservation_frames=1000,
                    schedule=SCHEDULES[family],
                    orders=[order[r % len(order) :] + order[: r % len(order)] for r in range(repetitions)],
                )
            )
    protocol = dict(
        panel_abi=STUDY_ABI,
        stage=stage,
        source_kind="generated_canvas",
        models=models,
        conditions=conditions,
        repetitions=repetitions,
        groups=groups,
        order_seed=seed,
        limits=DEFAULT_LIMITS.copy(),
        risk_cutoff=0.5,
        disagreement_cutoff=0.2,
        common_shadow_inference=True,
        episode_timeout_s=90,
        excluded_scene_ranges=excluded,
        excluded_inputs_sha256=excluded_inputs,
        source_sha256=source_identity(),
        repeatability_run=str(Path(repeatability_run).resolve()) if repeatability_run else None,
        SOTA_achieved=False,
        transport_role="encoder_cap_overlay_on_native_GCC",
        natural_content_or_measured_link=False,
        published_learned_peer_comparison=False,
    )
    if stage == "test":
        require(validation_root is not None, "test requires sealed validation selection")
        lock = validation_root / "selection.json"
        protocol["validation_lock"] = dict(path=str(lock), sha256=digest(lock))
    validate_protocol(protocol)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    write_json(out, protocol)
    load_protocol(out)
    return protocol


def _check_prerequisites(protocol):
    for path, sha in protocol.get("excluded_inputs_sha256", {}).items():
        require(digest(path) == sha, "excluded evidence changed after planning")
    stage = protocol["stage"]
    if stage in ("validation", "test"):
        root = Path(protocol["repeatability_run"])
        audit_native_study(root)
        prior = read_json(root / "protocol.json")
        report = read_json(root / "report.json")
        require(
            prior["stage"] == "repeatability" and report["identical_policy"]["passed"] is True,
            "repeatability failed: fix measurement/control before validation",
        )
        require(
            prior["models"]["source"]["sha256"] == protocol["models"]["source"]["sha256"],
            "repeatability control is a different policy",
        )
        if protocol["source_kind"] == "recorded_video_v1":
            require(
                prior["source_kind"] == "recorded_video_v1"
                and prior["video_source"]["sha256"] == protocol["video_source"]["sha256"],
                "repeatability uses a different recorded source",
            )
            _require_video_groups_disjoint(protocol, prior)
        for g in [] if protocol["source_kind"] == "recorded_video_v1" else protocol["groups"]:
            span = [g["scene_seed"], g["scene_seed"] + g["reservation_frames"]]
            require(
                all(
                    not spans_overlap(
                        span, [old["scene_seed"], old["scene_seed"] + old["reservation_frames"]]
                    )
                    for old in prior["groups"]
                ),
                "repeatability scenes reused for evaluation",
            )
    if stage == "test":
        entry = protocol["validation_lock"]
        require(digest(entry["path"]) == entry["sha256"], "validation selection changed before test")
        root = Path(entry["path"]).parent
        audit_native_study(root)
        lock = read_json(entry["path"])
        require(
            lock["models_sha256"] == {k: v["sha256"] for k, v in protocol["models"].items()}
            and lock["limits"] == protocol["limits"]
            and read_json(root / "protocol.json")["conditions"] == protocol["conditions"],
            "test models/bounds/conditions differ from locked validation",
        )
        prior = read_json(root / "protocol.json")
        if protocol["source_kind"] == "recorded_video_v1":
            _require_video_groups_disjoint(protocol, prior)
        for g in [] if protocol["source_kind"] == "recorded_video_v1" else protocol["groups"]:
            require(
                all(
                    not spans_overlap(
                        [g["scene_seed"], g["scene_seed"] + g["reservation_frames"]],
                        [x["scene_seed"], x["scene_seed"] + x["reservation_frames"]],
                    )
                    for x in prior["groups"]
                ),
                "test/validation source leakage",
            )


def _require_video_groups_disjoint(protocol, prior):
    require(prior["source_kind"] == "recorded_video_v1", "recorded validation/source role required")
    if prior["video_source"]["sha256"] == protocol["video_source"]["sha256"]:
        require(
            all(
                not spans_overlap(g["video_segment"], old["video_segment"])
                for g in protocol["groups"]
                for old in prior["groups"]
            ),
            "recorded source role leakage",
        )


def trial_schedule(protocol):
    trials = []
    for g in protocol["groups"]:
        for rep, order in enumerate(g["orders"]):
            for position, condition in enumerate(order):
                trials.append(
                    dict(
                        id=f"{g['id']}-r{rep}-{condition}",
                        group=g["id"],
                        family=g["family"],
                        condition=condition,
                        repetition=rep,
                        position=position,
                        role=protocol["stage"],
                        scene_seed=g["scene_seed"],
                        reservation_frames=g["reservation_frames"],
                        schedule=g["schedule"],
                        **({"video_segment": g["video_segment"]} if "video_segment" in g else {}),
                    )
                )
    return trials


def _verify_all_models(sender, bundles):
    latencies = []
    policies = {k: NativePolicy(b) for k, b in bundles.items()}
    for row in sender["decisions"]:
        require(
            set(row["all_policy_decisions"]) == set(bundles)
            and set(row["model_inference_ms"]) == set(bundles),
            "missing common shadow model",
        )
        primary = row["policy_decision"]
        for key, policy in policies.items():
            actual = row["all_policy_decisions"][key]
            require(actual["history"] == primary["history"], "models did not see a common causal history")
            expected = policy.decide(actual["history"])
            require(set(actual) == {"history", *expected}, "extra/missing common model fields")
            for name in ("q_values", "predicted_frame_miss", "risk_disagreement"):
                a = np.asarray(actual[name], dtype=float)
                require(
                    a.shape == (7,)
                    and all(finite(v) for v in actual[name])
                    and np.isfinite(a).all()
                    and np.max(np.abs(a - expected[name])) <= 1e-10,
                    "common model score replay mismatch",
                )
            for name in (
                "action_index",
                "native_action_index",
                "encoder_max_bitrate_bps",
                "receiver_jitter_buffer_target_ms",
                "fallback",
            ):
                require(
                    type(actual[name]) is type(expected[name]) and actual[name] == expected[name],
                    "common model action/fallback replay mismatch",
                )
        total, times = row["total_inference_ms"], list(row["model_inference_ms"].values())
        require(
            finite(total)
            and all(finite(t) and t >= 0 for t in times)
            and sum(times) <= total + 1e-6
            and total <= row["ack_ms"] - row["observation"]["sample_ms"] + 1e-6,
            "invalid common inference timing",
        )
        latencies.append(total)
    return float(np.quantile(latencies, 0.99))


def audit_native_episode(root, protocol, trial, bundles):
    """Full raw wire, feature, model, acknowledgment and pixel replay; no writes."""
    root = Path(root)
    summary, sender, frames = [
        read_json(root / n) for n in ("summary.json", "sender_observations.json", "frame_events.json")
    ]
    condition = protocol["conditions"][trial["condition"]]
    key = condition["model"]
    hashes = {k: entry["sha256"] for k, entry in protocol["models"].items()}
    require(sender["common_models_sha256"] == hashes, "common model fingerprint mismatch")
    require(
        summary["native_controller"] == condition["controller"]
        and summary["learned_policy_loaded"] is (condition["controller"] == "rlcd")
        and sender["learned_policy"] is (condition["controller"] == "rlcd")
        and sender["controller"]["controller"]
        == {
            "rlcd": "native_rlcd_cql_v1",
            "bwe": "native_bwe_cap_headroom_v1",
            "fixed": "native_fixed_cap_v1",
        }[condition["controller"]],
        "wrong actuating policy",
    )
    require(
        summary["collection_config"]
        == dict(panel_abi=STUDY_ABI, panel_sha256=digest(root / "panel_snapshot.json"), **trial),
        "role/trial identity mismatch",
    )
    require(
        read_json(root / "panel_snapshot.json")["source_sha256"] == protocol["source_sha256"],
        "episode source snapshot mismatch",
    )
    require(digest(root / "model.json") == hashes[key], "wrong primary native model")
    for name, sha in hashes.items():
        require(digest(root / ("model_" + name + ".json")) == sha, "common model snapshot changed")
    require(read_json(root / "all_models.json") == bundles, "common model payload changed")
    for name in ASSET_NAMES:
        snapshot = "source_snapshot.mjs" if name == "episode.mjs" else name
        require(
            digest(root / snapshot) == protocol["source_sha256"]["assets/" + name], "collector asset changed"
        )
    require(
        sender["measurement_start_ms"] == frames["measurement_start_ms"]
        and sender["measurement_cutoff_ms"] == frames["measurement_cutoff_ms"],
        "native clock window mismatch",
    )
    require(
        summary["native_actuation"]["encoder_max_bitrate_bps"] == 4000000
        and summary["native_actuation"]["receiver_jitter_buffer_target_ms"] == 0,
        "initial native action changed",
    )
    wire = replay_native_wire(root)
    replay = verify_native_live_evidence(sender, bundles[key], hashes[key])
    association = verify_live_capture_associations(
        frames["sources"], sender["decisions"], summary["native_actuation"]
    )
    frame = summarize_native_frames(frames)
    if protocol["source_kind"] == "recorded_video_v1":
        from .native_video import summarize_video_quality

        quality = summarize_video_quality(frames, protocol, trial)
        require(
            digest(root / "recorded_video.mjs")
            == protocol["extra_source_sha256"]["assets/recorded_video.mjs"],
            "recorded source asset changed",
        )
    else:
        quality = summarize_native_quality(frames)
    require(
        frame["measurement_qualified"] and quality["eligible_requests"] > 0,
        "unqualified native outcome panel",
    )
    require(frames["scene_seed"] == trial["scene_seed"], "wrong generated source group")
    span = [
        frames["scene_seed"] + min(s["source_id"] for s in frames["sources"]),
        frames["scene_seed"] + max(s["source_id"] for s in frames["sources"]),
    ]
    require(
        trial["scene_seed"] <= span[0] <= span[1] <= trial["scene_seed"] + trial["reservation_frames"],
        "actual source exceeded frozen content reservation",
    )
    require(
        all(not spans_overlap(span, old) for old in protocol["excluded_scene_ranges"]),
        "actual source/role leakage",
    )
    p99 = _verify_all_models(sender, bundles)
    features = history_matrix([x["observation"]["features"] for x in sender["decisions"]])[:, -16:]
    signals = {}
    for name, value, valid, scale in [
        ("bwe_mbps", 0, 9, 4),
        ("media_rtt_ms", 1, 10, 150),
        ("packet_send_delay_ms", 6, 14, 150),
        ("sample_interval_ms", 15, None, 100),
    ]:
        a = features[:, value] if valid is None else features[features[:, valid] == 1, value]
        signals[name] = float(a.mean() * scale) if len(a) else None
    phases = {}
    for phase in ("high", "collapse", "recovery"):
        labels = [s for s in quality["source_labels"] if s["phase"] == phase]
        require(labels, "missing complete source phase")
        phases[phase] = dict(
            utility=sum(s["ontime_sampled_psnr_contribution"] for s in labels) / len(labels),
            ontime_fraction=sum(s["identifiable_ontime"] for s in labels) / len(labels),
        )
    row = dict(
        **trial,
        utility=quality["utility"],
        eligible=quality["eligible_requests"],
        ontime_fraction=quality["identified_ontime"] / quality["eligible_requests"],
        inference_p99_ms=p99,
        primary_inference_p99_ms=replay["inference_ms_p99"],
        signals=signals,
        phases=phases,
        actual_scene_range=span,
        start_epoch_ms=frames["time_origin_epoch_ms"] + frames["measurement_start_ms"],
        cutoff_epoch_ms=frames["time_origin_epoch_ms"] + frames["measurement_cutoff_ms"],
        browser_build=summary["browser_build"],
        model_sha256=hashes[key],
    )
    return row, dict(wire=wire, replay=replay, association=association, frame=frame, quality=quality)


def _collect(command, timeout, log):
    # No shell or user browser profile. The driver owns cleanup; kill its group only on infrastructure timeout.
    with Path(log).open("x") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise ValueError("native infrastructure timeout; partial evidence preserved") from None
    if code != 0:
        require(code == 1, "native collector failed; inspect " + str(log))
        _recover_cleanup_capture(Path(command[2]), log)


def run_native_study(config, out, resume=False):
    if resume:
        return resume_native_study(config, out)
    protocol, bundles = load_protocol(config)
    _check_prerequisites(protocol)
    require(shutil.which("node") is not None, "Node 22+ and installed Chrome required")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "protocol.json", protocol)
    runtime = json.loads(json.dumps(protocol))
    trials = trial_schedule(protocol)
    runtime["episodes"] = trials
    (out / "models").mkdir()
    for key, entry in runtime["models"].items():
        path = Path(entry["path"])
        if not path.is_absolute():
            path = Path(config).resolve().parent / path
        target = out / "models" / (key + ".json")
        shutil.copyfile(path, target)
        entry["path"] = str(target)
    write_json(out / "runtime.json", runtime)
    names = ["protocol.json", "runtime.json"] + ["models/" + k + ".json" for k in bundles]
    for name in [*protocol["source_sha256"], *protocol.get("extra_source_sha256", {})]:
        category, leaf = name.split("/")
        source = asset_directory() / leaf if category == "assets" else Path(__file__).with_name(leaf)
        target = out / "sources" / category / leaf
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        names.append(str(target.relative_to(out)))
    if protocol["source_kind"] == "recorded_video_v1":
        shutil.copyfile(protocol["video_source"]["path"], out / "recorded-video.mp4")
        require(
            digest(out / "recorded-video.mp4") == protocol["video_source"]["sha256"],
            "recorded source changed while copying",
        )
        names.append("recorded-video.mp4")
    if protocol["stage"] == "test":
        shutil.copyfile(protocol["validation_lock"]["path"], out / "selection_snapshot.json")
        names.append("selection_snapshot.json")
    return _execute_panel(out, protocol, bundles, trials, names, asset_directory() / "episode.mjs")


def _require_replay_compatibility(root, protocol):
    """Captured code stays sealed. Only collector/auditor plumbing may evolve.

    All policy, feature, clock/label, wire, calibration and statistical modules
    must be byte-identical, and complete metrics must still rederive exactly.
    """
    current = source_identity()
    require(set(current) == set(protocol["source_sha256"]), "native source contract changed")
    plumbing = {"assets/episode.mjs", "python/native_study.py"}
    for name, sha in protocol["source_sha256"].items():
        require(digest(Path(root) / "sources" / name) == sha, "captured native source changed")
        if name not in plumbing:
            require(current[name] == sha, "native behavioral/verifier implementation changed: " + name)
    for name, sha in protocol.get("extra_source_sha256", {}).items():
        from .native_video import extra_sources

        require(
            digest(Path(root) / "sources" / name) == sha and digest(extra_sources()[name]) == sha,
            "recorded source implementation changed",
        )
    if protocol["source_kind"] == "recorded_video_v1":
        require(
            digest(Path(root) / "recorded-video.mp4") == protocol["video_source"]["sha256"],
            "sealed recorded source changed",
        )


def _recover_cleanup_capture(child, log):
    """Allow only the known post-outcome owned-profile ENOTEMPTY failure.

    A caller must subsequently fully replay the capture before sealing it. Missing
    outcomes or qualification failures are NOT permission to collect replacements.
    """
    child = Path(child)
    tail = Path(log).read_text()[-12000:]
    match = re.search(r"Error: ENOTEMPTY: directory not empty, rmdir '([^']+)'", tail)
    required = ["summary.json", "frame_events.json", "sender_observations.json", "events.jsonl.gz"]
    require(
        match is not None and all((child / n).is_file() for n in required),
        "native collector failed; only complete post-outcome cleanup errors are recoverable: " + str(log),
    )
    failed = Path(match.group(1))
    temporary = Path(tempfile.gettempdir()).resolve()
    profile = next(
        (
            p
            for p in [failed, *failed.parents]
            if p.parent.resolve() == temporary
            and p.name.startswith("rlcd-native-rtc-")
            and len(p.name) >= len("rlcd-native-rtc-") + 6
        ),
        None,
    )
    require(
        profile is not None and not profile.is_symlink(), "cleanup path is not an owned temporary profile"
    )
    before = {p.name: digest(p) for p in child.iterdir() if p.is_file()}
    for attempt in range(4):
        try:
            shutil.rmtree(profile)
            break
        except FileNotFoundError:
            break
        except OSError as error:
            if error.errno not in (errno.ENOTEMPTY, errno.EBUSY) or attempt == 3:
                raise ValueError("owned profile cleanup remains blocked; capture preserved") from error
            time.sleep(0.2 * (attempt + 1))
    require(
        before == {p.name: digest(p) for p in child.iterdir() if p.is_file()},
        "cleanup changed native outcome files",
    )
    receipt = child / "cleanup_recovery.json"
    if not receipt.exists():
        write_json(
            receipt,
            dict(
                infrastructure_only_post_outcome_cleanup=True,
                log_sha256=digest(log),
                raw_outcomes_sha256=before,
                no_recollection=True,
                profile_removed=True,
            ),
        )


def resume_native_study(config, out):
    """Explicitly continue a cleanup-interrupted frozen panel; never recollect a peer."""
    out = Path(out).resolve()
    require(
        not (out / "manifest.json").exists() and (out / "failure.json").is_file(),
        "only an interrupted native panel can be resumed",
    )
    require(
        not any((out / n).exists() for n in ("report.json", "episodes.json", "selection.json")),
        "do not resume a partially finalized or selected native panel",
    )
    protocol, external = load_protocol(config, check_sources=False)
    require(protocol == read_json(out / "protocol.json"), "resume changed the frozen native protocol")
    _require_replay_compatibility(out, protocol)
    _check_prerequisites(protocol)
    bundles = {k: read_json(out / "models" / (k + ".json")) for k in protocol["models"]}
    for key, entry in protocol["models"].items():
        require(
            digest(out / "models" / (key + ".json")) == entry["sha256"] and bundles[key] == external[key],
            "resume changed the frozen native models",
        )
    trials = trial_schedule(protocol)
    runtime = read_json(out / "runtime.json")
    require(
        runtime["episodes"] == trials
        and {k: v for k, v in runtime.items() if k not in ("models", "episodes")}
        == {k: v for k, v in protocol.items() if k != "models"},
        "resume changed runtime role/order",
    )
    names = [p.name for p in out.iterdir() if p.is_file()]
    names += [
        str(p.relative_to(out))
        for folder in ("models", "sources")
        for p in (out / folder).rglob("*")
        if p.is_file()
    ]
    receipt_name = next(
        (f"resume_receipt_{i}.json" for i in range(1, 21) if not (out / f"resume_receipt_{i}.json").exists()),
        None,
    )
    require(receipt_name is not None, "native resume attempt bound exceeded")
    write_json(
        out / receipt_name,
        dict(
            original_failure_sha256=digest(out / "failure.json"),
            original_protocol_sha256=digest(out / "protocol.json"),
            verifier_plumbing_sha256=digest(Path(__file__)),
            frozen_driver_executed=True,
            no_completed_outcome_replaced=True,
        ),
    )
    names.append(receipt_name)
    return _execute_panel(
        out, protocol, bundles, trials, names, out / "sources/assets/episode.mjs", resume=True
    )


def _execute_panel(out, protocol, bundles, trials, names, driver, resume=False):
    rows, seals = [], {}
    execution_identity = source_identity()
    try:
        previous_cutoff = -1
        for trial in trials:
            child = out / trial["id"]
            log_name = trial["id"] + ".log"
            sealed = (child / "manifest.json").exists()
            if sealed:
                require(resume, "completed native capture already exists")
                verify_seal(child, EPISODE_SEAL)
            elif child.exists():
                require(resume, "partial native capture already exists")
                _recover_cleanup_capture(child, out / log_name)
            else:
                _collect(
                    [
                        "node",
                        str(driver),
                        str(child),
                        str(out / "runtime.json"),
                        trial["id"],
                        trial["condition"],
                    ],
                    protocol["episode_timeout_s"] + 30,
                    out / log_name,
                )
            require(
                (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "capture used a changed runtime protocol",
            )
            row, derived = audit_native_episode(child, protocol, trial, bundles)
            require(row["start_epoch_ms"] > previous_cutoff, "native execution order is not prospective")
            previous_cutoff = row["cutoff_epoch_ms"]
            if sealed:
                require(
                    read_json(child / "derived.json") == derived,
                    "completed native evidence changed during resume",
                )
            else:
                write_json(child / "derived.json", derived)
                child_names = sorted(p.name for p in child.iterdir() if p.is_file())
                seal_directory(child, child_names, EPISODE_SEAL)
            seals[trial["id"]] = digest(child / "manifest.json")
            rows.append(row)
            names.append(log_name)
        require(execution_identity == source_identity(), "implementation changed during collection")
        report = analyze_native_rows(rows, protocol)
        write_json(out / "episodes.json", rows)
        write_json(out / "report.json", report)
        names += ["episodes.json", "report.json"]
        if protocol["stage"] == "validation":
            lock = dict(
                **validation_selection(report, protocol),
                models_sha256={k: v["sha256"] for k, v in protocol["models"].items()},
                limits=protocol["limits"],
                protocol_sha256=digest(out / "protocol.json"),
                report_sha256=digest(out / "report.json"),
                episodes_sha256=digest(out / "episodes.json"),
            )
            write_json(out / "selection.json", lock)
            names.append("selection.json")
        seal_directory(out, names, STUDY_SEAL, episodes=seals, role=protocol["stage"], SOTA_achieved=False)
    except Exception as error:
        failure_name = (
            "failure.json"
            if not (out / "failure.json").exists()
            else next(
                f"failure_resume_{i}.json"
                for i in range(1, 100)
                if not (out / f"failure_resume_{i}.json").exists()
            )
        )
        write_json(
            out / failure_name,
            dict(
                error=str(error),
                completed_peers=len(rows),
                partial_evidence_preserved=True,
                no_completed_peer_replaced=True,
                retry_in_new_directory_unless_post_outcome_cleanup=True,
            ),
        )
        raise
    return report


def audit_native_study(root, replay=True):
    """Idempotent replay, including rederived statistics. Never reseals or rewrites a capture."""
    root = Path(root)
    seal = verify_seal(root, STUDY_SEAL)
    protocol = validate_protocol(read_json(root / "protocol.json"))
    runtime = read_json(root / "runtime.json")
    trials = trial_schedule(protocol)
    require(
        {k: v for k, v in runtime.items() if k not in ("models", "episodes")}
        == {k: v for k, v in protocol.items() if k != "models"},
        "runtime protocol differs from frozen plan",
    )
    required = {"protocol.json", "runtime.json", "episodes.json", "report.json"}
    required |= {"models/" + k + ".json" for k in protocol["models"]}
    required |= {
        "sources/" + name for name in [*protocol["source_sha256"], *protocol.get("extra_source_sha256", {})]
    }
    if protocol["source_kind"] == "recorded_video_v1":
        required.add("recorded-video.mp4")
    if protocol["stage"] == "validation":
        required.add("selection.json")
    if protocol["stage"] == "test":
        required.add("selection_snapshot.json")
    require(required <= set(seal["artifacts_sha256"]), "incomplete parent native seal")
    require(
        runtime["episodes"] == trials and set(seal["episodes"]) == {x["id"] for x in trials},
        "sealed trial list differs from frozen panel",
    )
    bundles = {k: read_json(root / "models" / (k + ".json")) for k in protocol["models"]}
    for k, entry in protocol["models"].items():
        require(digest(root / "models" / (k + ".json")) == entry["sha256"], "sealed source model changed")
    rows = read_json(root / "episodes.json")
    for trial, row in zip(trials, rows, strict=True):
        child = artifact_path(root, trial["id"])
        require(digest(child / "manifest.json") == seal["episodes"][trial["id"]], "native child seal changed")
        child_seal = verify_seal(child, EPISODE_SEAL)
        child_required = {
            "summary.json",
            "sender_observations.json",
            "frame_events.json",
            "events.jsonl.gz",
            "panel_snapshot.json",
            "all_models.json",
            "model.json",
            "source_snapshot.mjs",
            "derived.json",
        }
        child_required |= set(ASSET_NAMES) - {"episode.mjs"}
        if protocol["source_kind"] == "recorded_video_v1":
            child_required.add("recorded_video.mjs")
        child_required |= {"model_" + k + ".json" for k in bundles}
        require(child_required <= set(child_seal["artifacts_sha256"]), "incomplete native child seal")
        require(
            (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
            "child used a different runtime protocol",
        )
        if replay:
            _require_replay_compatibility(root, protocol)
            actual, derived = audit_native_episode(child, protocol, trial, bundles)
            require(
                actual == row and derived == read_json(child / "derived.json"),
                "native derived evidence changed",
            )
    report = analyze_native_rows(rows, protocol)
    require(report == read_json(root / "report.json"), "native statistics cannot be reproduced")
    if protocol["stage"] == "validation":
        lock = read_json(root / "selection.json")
        expected = dict(
            **validation_selection(report, protocol),
            models_sha256={k: v["sha256"] for k, v in protocol["models"].items()},
            limits=protocol["limits"],
            protocol_sha256=digest(root / "protocol.json"),
            report_sha256=digest(root / "report.json"),
            episodes_sha256=digest(root / "episodes.json"),
        )
        require(lock == expected, "validation selection is not evidence-derived")
    if protocol["stage"] == "test":
        require(
            digest(root / "selection_snapshot.json") == protocol["validation_lock"]["sha256"],
            "final evidence does not retain before-test validation selection",
        )
    return dict(
        verified_peers=len(trials),
        artifact_hashes=len(seal["artifacts_sha256"]),
        full_raw_replay=replay,
        role=protocol["stage"],
        read_only=True,
        SOTA_achieved=False,
    )
