"""Native Phase B1 plumbing: plan, capture and the single final analysis.

Everything physical is reused unchanged, as in Native Phase N1: the screening output and the
runtime builder of the existing studies, the Node collector and the raw peer auditor. This
module differs from N1's only where the B1 registration does: a fixed set of sources with no
interim look, a flag on holds, and a quality-proxy endpoint. Capture computes no outcome
statistic, and the final analysis refuses to run before every planned source is captured.
"""

import argparse
import copy
import hashlib
import json
import math
import subprocess
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy import stats

from . import native_actuator_control as control
from . import native_actuator_panel as panel
from . import native_actuator_qualification as actuator
from . import native_actuator_qualification_panel as n1
from . import native_actuator_study as physical
from . import native_backoff_benefit as benefit
from . import native_panel_assets as assets
from .native_protocol import (
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = benefit.ABI
ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "configs/native_backoff_benefit_b1.json"
FREEZE = ROOT / "configs/native_backoff_benefit_b1_freeze.json"
FROZEN = (
    "configs/native_backoff_benefit_b1.json",
    "docs/NATIVE_PHASE_B1_BACKOFF_BENEFIT.md",
    "src/media_rl/native_backoff_benefit.py",
    "src/media_rl/native_backoff_benefit_panel.py",
)
STRATA, REGIMES, BINDINGS = n1.STRATA, n1.REGIMES, n1.BINDINGS
RUNTIME_STAGE = n1.RUNTIME_STAGE  # the frozen collector accepts only its two legacy labels
PLAN_STAGE, MOCK_PLAN_STAGE = ABI + "_plan", ABI + "_mock_plan"
PEER_STAGE, CAPTURE_STAGE, MOCK_STAGE = (
    ABI + "_peer_verified",
    ABI + "_capture_complete",
    ABI + "_mock_capture",
)
PREFIX = "b1-"


def freeze_record():
    files = {name: digest(ROOT / name) for name in FROZEN}
    return dict(
        abi=ABI + "_freeze",
        files=files,
        sha256=hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        controller_freeze_sha256=digest(assets.FREEZE),
        n1_freeze_sha256=read_json(n1.FREEZE)["sha256"],  # the N1 code this module reuses
        registered_before_any_outcome=True,
        native_data_collected=False,
    )


def write_freeze(path=FREEZE):
    assets.verify_controller_freeze()
    n1.verify_freeze()
    write_json(path, freeze_record())  # refuses to overwrite: a changed registration needs a new record
    return read_json(path)


def verify_freeze(path=FREEZE):
    assets.verify_controller_freeze()
    n1.verify_freeze()
    record = read_json(path)
    require(record == freeze_record(), "B1 registration or implementation changed after it was frozen")
    return dict(files=len(record["files"]), sha256=record["sha256"], verified=True)


def allocate(clips, excluded, plan, seed):
    """Every fresh source in analysis order: a seeded draw within terciles, in balanced blocks.

    A source cluster that any earlier native role touched is excluded whole, each cluster gives
    one representative window, and the plan holds as many whole blocks as the thinnest tercile
    allows. There is no reserve: every planned source is captured and none is added later.
    """
    require(plan.strata == len(STRATA), "B1 uses the three screening terciles")
    panel.verify_pool_clusters(clips)
    reserved = {e["sha256"] for e in excluded}
    used = {
        c["cluster_id"] for c in clips if c["source_sha256"] in reserved or c.get("parent_sha256") in reserved
    }
    rng = np.random.default_rng(seed)
    drawn = {}
    for stratum in STRATA:
        units = {}
        for clip in sorted(clips, key=lambda c: c["clip_id"]):
            if clip["complexity_stratum"] != stratum or clip["cluster_id"] in used:
                continue
            require(clip["panel_eligible"], "quarantined source cannot enter B1")
            distance = abs(clip["complexity"]["score"] - clip["source_complexity_score"])
            prior = units.get(clip["cluster_id"])
            if prior is None or (distance, clip["clip_id"]) < (prior[0], prior[1]["clip_id"]):
                units[clip["cluster_id"]] = distance, clip
        candidates = [v[1] for _, v in sorted(units.items())]
        drawn[stratum] = [candidates[int(i)] for i in rng.permutation(len(candidates))]
    blocks = min(len(v) for v in drawn.values())
    require(
        blocks * plan.strata >= plan.minimum_sources,
        f"B1 needs {plan.minimum_sources // plan.strata} fresh independent source clusters per "
        f"complexity tercile; the thinnest has {blocks}",
    )
    sources = []
    for block in range(blocks):
        for stratum in STRATA:
            sources.append(dict(drawn[stratum][block], b1_block=block, b1_order=len(sources)))
    return sources


def peer_groups(source, index, plan, seed):
    """Ten fresh peers per regime for one source, each with its own assignment seed."""
    groups = []
    for regime in REGIMES:
        for replicate in range(plan.peers_per_regime):
            key = f"{ABI}:{source['clip_id']}:{regime}:{replicate}:{seed}"
            groups.append(
                dict(
                    id=f"{PREFIX}{source['clip_id']}-{regime}-p{replicate}",
                    family=regime,
                    scene_seed=(index % 32) * 2000,
                    video_segment=source["segment"],
                    reservation_frames=1000,
                    schedule=copy.deepcopy(panel.REGIMES[regime]),
                    orders=[["instrument"]],
                    block_id=source["cluster_id"],
                    instrument_seed=int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big"),
                )
            )
    return groups


def build_runtime(template, catalog, source, index, plan, seed):
    # Exactly the prior ABI, sampler, observer, credit and raw auditor: only the groups differ.
    groups = peer_groups(source, index, plan, seed)
    runtime = physical._runtime(template, catalog, RUNTIME_STAGE, groups)
    for trial in runtime["episodes"]:
        n1.bind(trial, next(g for g in groups if g["id"] == trial["group"]), source)
    return runtime


def mock_runtime(source, index, plan, seed):
    """Trials with the planner's real seeds and bindings but no physical runtime: for dry runs only."""
    episodes = []
    for group in peer_groups(source, index, plan, seed):
        trial = dict(
            id=group["id"] + "-r0-instrument",
            group=group["id"],
            role=RUNTIME_STAGE,
            exploration_seed=group["instrument_seed"],
            block_id=group["block_id"],
        )
        episodes.append(n1.bind(trial, group, source))
    return dict(mock=True, episodes=episodes)


def verify_plan(sources, runtimes, plan):
    """What must hold before any capture: independence, balance, seeds and planned cell support.

    Arms stay IID: the seed is never redrawn to improve balance. A plan whose assigned cells
    fall below the registered minimum is refused, not repaired.
    """
    require(
        plan.strata == len(STRATA)
        and plan.regimes == len(REGIMES)
        and plan.holds_per_peer == control.MAX_EPOCHS
        and tuple(benefit.RATIOS) == tuple(control.RATIOS),
        "B1 plan must match the frozen strata, regimes, holds per peer and ratios",
    )
    blocks = len(sources) // plan.strata
    require(
        len(sources) == blocks * plan.strata and len(sources) >= plan.minimum_sources,
        "whole stratum-balanced blocks, at least the registered minimum",
    )
    for i, source in enumerate(sources):
        require(
            source["b1_order"] == i
            and source["b1_block"] == i // plan.strata
            and source["complexity_stratum"] == STRATA[i % plan.strata],
            "sources must be ordered in stratum-balanced blocks",
        )
    panel.verify_pool_clusters(sources)  # shared title, capture or lineage may not sit in different clusters
    require(
        len({s["cluster_id"] for s in sources}) == len(sources), "one window per independent source cluster"
    )
    require(set(runtimes) == {PREFIX + s["clip_id"] for s in sources}, "one runtime per planned source")
    trials = [t for runtime in runtimes.values() for t in runtime["episodes"]]
    seeds = [t["exploration_seed"] for t in trials]
    require(len(set(seeds)) == len(seeds), "every fresh peer needs its own assignment seed")
    peers = Counter((t["cluster_id"], t["network_regime"]) for t in trials)
    require(
        set(peers) == {(s["cluster_id"], g) for s in sources for g in REGIMES}
        and set(peers.values()) == {plan.peers_per_regime},
        "every source needs the registered number of peers in every regime",
    )
    planned = n1.planned_assignments(runtimes)
    cells = Counter((a["cluster_id"], a["regime"], a["arm"]) for a in planned)
    smallest = min(
        cells.get((s["cluster_id"], g, arm), 0) for s in sources for g in REGIMES for arm in range(3)
    )
    require(
        smallest >= plan.minimum_cell_cohorts, "a source x regime x arm cell is planned below the minimum"
    )
    arms = [sum(a["arm"] == arm for a in planned) for arm in range(3)]
    share = float(stats.chisquare(arms).pvalue)
    require(share >= 0.001, "planned arm shares are inconsistent with equal propensity")
    return dict(
        sources=len(sources),
        sources_per_stratum=blocks,
        planned_peers=len(trials),
        planned_cohorts=len(planned),
        planned_arm_counts=arms,
        planned_arm_share_p_value=share,
        smallest_planned_cell=smallest,
        propensity_per_arm=1 / 3,
        assignment_seeds_distinct=True,
        source_clusters_independent=True,
    )


def _derive(registration, screened, excluded):
    assets.verify_controller_freeze()
    plan, seed = registration.plan, registration.capture.seed
    sources = allocate(screened["clips"], excluded, plan, seed)
    template = read_json(registration.capture.template)
    require(
        physical.donor.compatible_engines(template)
        and template["repair_model"] is None
        and template["learner"] is None,
        "unchanged catalog/shadow-only template required; no outcomes reused",
    )
    verify_seal(Path(registration.capture.template).resolve().parent, physical.donor.PARENT_SEAL)
    runtimes = {
        PREFIX + s["clip_id"]: build_runtime(
            template, screened["catalogs"][s["source_sha256"]], s, i, plan, seed
        )
        for i, s in enumerate(sources)
    }
    return sources, runtimes, verify_plan(sources, runtimes, plan)


def _excluded(inputs):
    """The reserved video ranges of every earlier native role, re-read from the recorded inputs."""
    excluded = []
    for path, sha in inputs.items():
        require(digest(path) == sha, "prospective all-role reservation changed")
        raw = read_json(path)
        for p in [raw, *raw.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                excluded.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    return excluded


def plan_study(screening_path, out, registration_path=REGISTRATION):
    """Seal the B1 plan. Reads screening output and reservations only; observes no outcome."""
    frozen = verify_freeze()
    require(Path(registration_path).resolve() == REGISTRATION.resolve(), "only the frozen B1 registration")
    registration = benefit.load_registration(registration_path)
    screened = panel._screen(screening_path)
    excluded, inputs = physical.reservations.reservations(registration.capture.reservation_root)
    sources, runtimes, checks = _derive(registration, screened, excluded)
    out = Path(out).resolve()
    require(not out.exists(), "B1 plan must be fresh")
    protocol = dict(
        abi=ABI,
        mock=False,
        b1_freeze_sha256=frozen["sha256"],
        controller_freeze_sha256=digest(assets.FREEZE),
        plan=asdict(registration.plan),
        capture=asdict(registration.capture),
        secondary_flags=registration.secondary_flags,
        screened=dict(path=str(Path(screening_path).resolve()), sha256=digest(screening_path)),
        sources=sources,
        runtimes=runtimes,
        checks=checks,
        regimes=panel.REGIMES,
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        outcomes_observed=False,
        policy_models_fitted=0,
        learned_controller_promoted=False,
        SOTA_achieved=False,
    )
    out.mkdir()
    write_json(out / "protocol.json", protocol)
    seal_directory(out, ["protocol.json"], PLAN_STAGE, policy_models_fitted=0, SOTA_achieved=False)
    return protocol


def validate_plan(protocol):
    """Re-derive a sealed plan from its inputs; any drift in registration, pool or code is refused."""
    frozen = verify_freeze()
    registration = benefit.load_registration(REGISTRATION)
    require(
        protocol["abi"] == ABI
        and protocol["mock"] is False
        and protocol["b1_freeze_sha256"] == frozen["sha256"]
        and protocol["plan"] == asdict(registration.plan)
        and protocol["capture"] == asdict(registration.capture)
        and protocol["secondary_flags"] == registration.secondary_flags
        and protocol["regimes"] == panel.REGIMES
        and protocol["outcomes_observed"] is False,
        "sealed B1 plan differs from the frozen registration",
    )
    entry = protocol["screened"]
    require(digest(entry["path"]) == entry["sha256"], "screening source changed")
    excluded = _excluded(protocol["excluded_inputs_sha256"])
    require(excluded == protocol["excluded_video_ranges"], "complete all-role reservation coverage required")
    sources, runtimes, checks = _derive(registration, panel._screen(entry["path"]), excluded)
    require(
        sources == protocol["sources"] and runtimes == protocol["runtimes"] and checks == protocol["checks"],
        "exact B1 assignments/runtime mismatch",
    )
    return protocol


def registered_plan(protocol):
    return benefit.Plan(**protocol["plan"]).validate()


def sealed_protocol(path):
    manifest = verify_seal(Path(path).resolve().parent)
    protocol = read_json(path)
    if manifest["stage"] == MOCK_PLAN_STAGE:
        require(protocol["mock"] is True, "mock plan must be labelled")
        verify_plan(protocol["sources"], protocol["runtimes"], registered_plan(protocol))
        return protocol
    require(manifest["stage"] == PLAN_STAGE, "sealed B1 plan required")
    return validate_plan(protocol)


def _planned(protocol, start, stop):
    plan = registered_plan(protocol)
    require(
        type(start) is int
        and type(stop) is int
        and 0 <= start < stop <= len(protocol["sources"])
        and start % plan.strata == 0
        and stop % plan.strata == 0,
        "capture whole stratum-balanced blocks in planned order",
    )
    chosen = protocol["sources"][start:stop]
    return chosen, [
        (PREFIX + s["clip_id"], protocol["runtimes"][PREFIX + s["clip_id"]], t)
        for s in chosen
        for t in protocol["runtimes"][PREFIX + s["clip_id"]]["episodes"]
    ]


def capture(protocol_path, out, start, stop):
    """Collect the planned peers of sources in planned positions [start, stop). No outcome statistic.

    The same collector command, raw audit and row bindings as N1; nothing is analysed here, so
    collecting does not unblind anyone.
    """
    protocol = sealed_protocol(protocol_path)
    require(protocol["mock"] is False, "a mock plan cannot drive a native capture")
    chosen, peers = _planned(protocol, start, stop)
    rng = np.random.default_rng(protocol["capture"]["seed"] + 1 + start)
    peers = [peers[int(i)] for i in rng.permutation(len(peers))]
    out = Path(out).resolve()
    require(not out.exists(), "fresh B1 capture path required; never overwrite a failed prefix")
    out.mkdir()
    write_json(out / "protocol.json", protocol)
    rows, completed = [], {}
    try:
        for key, runtime, trial in peers:
            if not (out / (key + ".json")).exists():
                write_json(out / (key + ".json"), runtime)
            child = out / trial["id"]
            command = ["node", str(asset_directory() / "actuator_episode.mjs"), str(child)]
            command += [str(out / (key + ".json")), trial["id"], "instrument"]
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
            native, derived, cohorts = physical.audit_peer(child, runtime, trial)
            derived["panel_peer_queue"] = panel.peer_queue_realization(child)
            cohorts = panel._panel_rows(cohorts, trial, derived)
            write_json(child / "native_row.json", native)
            write_json(child / "native_derived.json", derived)
            write_json(child / "cohorts.json", cohorts)
            files = sorted(str(f.relative_to(child)) for f in child.rglob("*") if f.is_file())
            seal_directory(child, files, PEER_STAGE, policy_models_fitted=0, SOTA_achieved=False)
            completed[trial["id"]] = digest(child / "manifest.json")
            rows.extend(cohorts)
        write_json(out / "cohorts.json", rows)
        seal_directory(
            out,
            sorted(str(f.relative_to(out)) for f in out.rglob("*") if f.is_file()),
            CAPTURE_STAGE,
            episodes=completed,
            sources=[s["cluster_id"] for s in chosen],
            planned_positions=[start, stop],
            outcome_statistics_computed=False,
            policy_models_fitted=0,
            SOTA_achieved=False,
        )
        return dict(native_peers=len(completed), assigned_cohorts=len(rows), sources=len(chosen))
    except Exception as error:
        stderr = (
            error.stderr[-6000:]
            if isinstance(error, subprocess.CalledProcessError) and error.stderr
            else None
        )
        failure = dict(
            error=str(error), collector_stderr=stderr, completed=completed, rerun_requires_fresh_path=True
        )
        write_json(out / "failure.json", failure)
        raise


def synthetic_cohorts(trial, shift, scenario, plan, rng):
    """Audited-looking rows for one peer with the planned arms and invented values. Never evidence."""
    room = REGIMES.index(trial["network_regime"]) == 0  # the unconstrained schedule lets the estimate grow
    bwe, before, rows = float(rng.uniform(4e5, 1.5e6)), None, []
    for epoch in range(control.MAX_EPOCHS):
        arm = control.assigned_arm(trial["exploration_seed"], epoch)
        if before is not None:
            growth = (0.3 if room else 0.02) + (0.1 if before["arm"] == 2 else 0.0) + rng.normal(0, 0.08)
            bwe = before["base_bwe_bps"] * math.exp(growth)
        flagged = before is not None and bwe < plan.growth_limit * before["base_bwe_bps"]
        gain = shift + scenario.flagged_benefit if flagged else scenario.other_benefit
        value = 25.0 + (gain if arm < 2 else 0.0) + rng.normal(0, scenario.cohort_sd)
        known = dict(status="present")
        row = dict(
            mock=True,
            trial_id=trial["id"],
            epoch=epoch,
            seed=trial["exploration_seed"],
            arm=arm,
            ratio=control.RATIOS[arm],
            propensity=1 / 3,
            base_bwe_bps=bwe,
            requested_bps=control.RATIOS[arm] * bwe,
            clipped_or_aliased=False,
            complete=True,
            censor_reason=None,
            encoder_bps=(0.45 + 0.14 * arm) * bwe,
            send_bps=(0.47 + 0.14 * arm) * bwe,
            plateau_observed=bool(rng.random() < 0.8),
            utility=float(value),
            ontime_fraction=float(
                np.clip(0.75 + (0.02 * gain if arm < 2 else 0.0) + rng.normal(0, 0.05), 0, 1)
            ),
            state=dict(
                jitter_ms=dict(known, value=float(rng.uniform(2, 20)))
                if epoch
                else dict(status="absent", value=None),
                rtt_ms=dict(known, value=float(rng.uniform(50, 62)))
                if epoch
                else dict(status="absent", value=None),
                previous_action=None if before is None else before["arm"],
            ),
            block_id=trial["block_id"],
            role=trial["role"],
            **{k: trial[k] for k in BINDINGS},
            parent_sha256=trial.get("parent_sha256"),
            network_regime=trial["network_regime"],
            replicate=trial["replicate"],
        )
        rows.append(row)
        before = row
    return rows


def mock_capture(protocol_path, out, start, stop, scenario, seed):
    """A capture root of synthetic rows for a mock plan. It exercises the plumbing and proves nothing."""
    protocol = sealed_protocol(protocol_path)
    require(protocol["mock"] is True, "synthetic rows may only follow a mock plan")
    chosen, peers = _planned(protocol, start, stop)
    plan, rng = registered_plan(protocol), np.random.default_rng(seed + start)
    shifts = {s["cluster_id"]: float(rng.normal(0, scenario.source_sd)) for s in chosen}
    rows = [
        r for _, _, t in peers for r in synthetic_cohorts(t, shifts[t["cluster_id"]], scenario, plan, rng)
    ]
    out = Path(out).resolve()
    require(not out.exists(), "fresh mock capture path required")
    out.mkdir()
    write_json(out / "protocol.json", protocol)
    write_json(out / "cohorts.json", rows)
    seal_directory(
        out,
        ["protocol.json", "cohorts.json"],
        MOCK_STAGE,
        sources=[s["cluster_id"] for s in chosen],
        planned_positions=[start, stop],
        mock=True,
        native_data_collected=False,
    )
    return dict(mock=True, assigned_cohorts=len(rows), sources=len(chosen))


def load_capture(root, protocol):
    """Audited cohort rows of one capture root. Native roots are replayed from raw files, read-only."""
    root = Path(root).resolve()
    manifest = verify_seal(root)
    require(read_json(root / "protocol.json") == protocol, "capture belongs to a different sealed plan")
    if manifest["stage"] == MOCK_STAGE:
        require(protocol["mock"] is True, "mock rows cannot enter a native analysis")
        return read_json(root / "cohorts.json"), manifest
    require(
        manifest["stage"] == CAPTURE_STAGE, "complete B1 capture required; a failed prefix is never analysed"
    )
    trials = {t["id"]: (key, p, t) for key, p in protocol["runtimes"].items() for t in p["episodes"]}
    rows = []
    for identifier, sha in manifest["episodes"].items():
        key, runtime, trial = trials[identifier]
        child = root / identifier
        verify_seal(child, PEER_STAGE)
        require(
            digest(child / "manifest.json") == sha and read_json(root / (key + ".json")) == runtime,
            "peer binding or runtime changed",
        )
        native, derived, cohorts = physical.audit_peer(child, runtime, trial)
        derived["panel_peer_queue"] = panel.peer_queue_realization(child)
        cohorts = panel._panel_rows(cohorts, trial, derived)
        require(
            native == read_json(child / "native_row.json")
            and derived == read_json(child / "native_derived.json")
            and cohorts == read_json(child / "cohorts.json"),
            "original raw/frame/encoder/byte replay differs",
        )
        rows.extend(cohorts)
    saved = read_json(root / "cohorts.json")
    order = lambda r: (r["trial_id"], r["epoch"])  # noqa: E731
    require(sorted(rows, key=order) == sorted(saved, key=order), "factual cohort inventory differs")
    return saved, manifest


def _signal(row, name):
    """A pre-hold telemetry value, or None when the sender did not have it."""
    entry = row["state"].get(name)
    present = isinstance(entry, dict) and entry.get("status") == "present" and finite(entry.get("value"))
    return float(entry["value"]) if present else None


def estimator_rows(rows, protocol):
    """Audited cohort rows in the estimator's terms, each checked against the planned randomisation."""
    planned = {(a["trial_id"], a["epoch"]): a for a in n1.planned_assignments(protocol["runtimes"])}
    assets.validate_cluster_rows(rows)  # shared title, capture or lineage across clusters is refused
    seen, out = set(), []
    for r in rows:
        key = (r["trial_id"], r["epoch"])
        assigned = planned.get(key)
        require(assigned is not None and key not in seen, "cohort outside the sealed plan or duplicated")
        seen.add(key)
        require(
            r["arm"] == assigned["arm"]
            and r["seed"] == assigned["seed"]
            and r["cluster_id"] == assigned["cluster_id"]
            and r["network_regime"] == assigned["regime"],
            "assignment differs from the planned randomisation",
        )
        require(
            abs(r["propensity"] - 1 / 3) < 1e-12 and abs(r["ratio"] - control.RATIOS[r["arm"]]) < 1e-12,
            "forged propensity or ratio",
        )
        complete = r["complete"] is True
        values = ("encoder_bps", "send_bps", "utility", "ontime_fraction")
        measured = (
            all(finite(r[k]) for k in values) and min(r["encoder_bps"], r["send_bps"]) >= 0
            if complete
            else True
        )
        require(
            finite(r["base_bwe_bps"])
            and r["base_bwe_bps"] > 0
            and measured
            and complete == (r["censor_reason"] is None),
            "complete cohorts need measured rates and quality; censored cohorts need a reason",
        )
        out.append(
            dict(
                source=r["cluster_id"],
                stratum=r["complexity_stratum"],
                regime=r["network_regime"],
                trial_id=r["trial_id"],
                epoch=r["epoch"],
                arm=r["arm"],
                base_bwe_bps=r["base_bwe_bps"],
                encoder_bps=r["encoder_bps"],
                send_bps=r["send_bps"],
                utility=r["utility"],
                ontime_fraction=r["ontime_fraction"],
                jitter_ms=_signal(r, "jitter_ms"),
                rtt_ms=_signal(r, "rtt_ms"),
                complete=complete,
                clipped_or_aliased=bool(r["clipped_or_aliased"]),
            )
        )
    return out


def gather(protocol_path, roots):
    protocol = sealed_protocol(protocol_path)
    rows, inputs, captured = [], {}, []
    for root in roots:
        saved, manifest = load_capture(root, protocol)
        require(not set(manifest["sources"]) & set(captured), "a source may be captured once")
        captured += manifest["sources"]
        inputs[str(Path(root).resolve())] = digest(Path(root) / "manifest.json")
        rows += saved
    return protocol, rows, captured, inputs


def analysis_set(protocol, unevaluable):
    """The analysed sources: the first evaluable ones per tercile in planned order, equal numbers each.

    Evaluability depends on the flag and on completeness, never on an outcome by arm. A tercile
    with fewer evaluable sources than the others caps all three, so the weights stay equal.
    """
    usable = {
        stratum: [
            s
            for s in protocol["sources"]
            if s["complexity_stratum"] == stratum and s["cluster_id"] not in unevaluable
        ]
        for stratum in STRATA
    }
    count = min(len(v) for v in usable.values())
    chosen = [usable[stratum][block] for block in range(count) for stratum in STRATA]
    skipped = sum(s["cluster_id"] in unevaluable for s in protocol["sources"])
    return chosen, skipped, len(protocol["sources"]) - skipped - len(chosen)


def _held(protocol, rows):
    plan = registered_plan(protocol)
    estimator = estimator_rows(rows, protocol)
    return plan, estimator, benefit.flag_rows(estimator, plan)


def status(protocol_path, roots):
    """Outcome-free progress: what is captured, how the flag is supported, whether the final can run."""
    protocol, rows, captured, _ = gather(protocol_path, roots)
    plan, estimator, held = _held(protocol, rows)
    _, unevaluable = benefit.source_benefits(held, plan)
    planned = [s["cluster_id"] for s in protocol["sources"]]
    return dict(
        mock=protocol["mock"],
        planned_sources=len(planned),
        captured_sources=len(captured),
        not_evaluable_sources=sorted(unevaluable),
        assigned_cohorts=len(rows),
        support=benefit.support(estimator, plan),
        flag=benefit.flagged_support(held, plan),
        final_can_run=set(captured) == set(planned),
        outcome_free=True,
    )


def bindings(protocol_path, protocol, inputs):
    return dict(
        protocol_sha256=digest(protocol_path),
        registration_sha256=digest(REGISTRATION),
        b1_code_and_registration_sha256=freeze_record()["files"],
        b1_freeze_sha256=protocol.get("b1_freeze_sha256"),
        input_manifests_sha256=inputs,
        mock=protocol["mock"],
    )


def _over(benefits, names):
    return benefit.summary([benefits[n] for n in names if n in benefits])


def final(protocol_path, roots, out):
    """The confirmatory analysis. Runs once, after every planned source has been captured."""
    out = Path(out)
    require(not out.exists(), "the final analysis is written once; a fresh path is required")
    protocol, rows, captured, inputs = gather(protocol_path, roots)
    require(
        set(captured) == {s["cluster_id"] for s in protocol["sources"]},
        "every planned source must be captured before the final analysis",
    )
    plan, estimator, held = _held(protocol, rows)
    benefits, unevaluable = benefit.source_benefits(held, plan)
    order, skipped, trimmed = analysis_set(protocol, set(unevaluable))
    names = [s["cluster_id"] for s in order]
    used = [r for r in estimator if r["source"] in set(names)]
    held_used = [r for r in held if r["source"] in set(names)]
    support = benefit.support(used, plan) if used else dict(passed=False)
    enough = len(names) >= plan.minimum_sources
    supported = bool(
        support["passed"] and enough and skipped <= plan.maximum_skipped_share * len(protocol["sources"])
    )
    strata = np.array([STRATA.index(s["complexity_stratum"]) for s in order])
    primary = (
        benefit.analyse([benefits[n] for n in names], strata, plan) if len(names) >= 2 * plan.strata else None
    )
    pick = lambda **kwargs: benefit.source_benefits(held_used, plan, **kwargs)[0]  # noqa: E731
    other, following = pick(flagged=False), pick(following=True)
    alternatives = {}
    for signal, threshold in protocol["secondary_flags"].items():
        marked = [
            r for r in benefit.flag_rows(estimator, plan, signal, threshold) if r["source"] in set(names)
        ]
        alternatives[f"{signal} above {threshold:g}"] = _over(benefit.source_benefits(marked, plan)[0], names)
    by_regime = {
        regime: _over(
            benefit.source_benefits([r for r in held_used if r["regime"] == regime], plan)[0], names
        )
        for regime in REGIMES
    }
    top = len(benefit.RATIOS) - 1
    by_previous = {
        label: _over(
            benefit.source_benefits([r for r in held_used if (r["previous_arm"] == top) is after_top], plan)[
                0
            ],
            names,
        )
        for label, after_top in (("previous hold at 1.05", True), ("previous hold at 0.65 or 0.85", False))
    }
    rates, _ = actuator.source_contrasts(used, plan)
    report = dict(
        abi=ABI + "_final",
        outcome=primary["outcome"] if supported and primary else benefit.OUTCOMES[3],
        capture_support_passed=supported,
        endpoint="on-time sampled RGB-PSNR contribution in the outcome window; not perceptual quality",
        flag=f"frozen estimate below {plan.growth_limit:g} times the previous hold's",
        benefit="mean of the endpoint at ratios 0.65 and 0.85 minus the endpoint at ratio 1.05, flagged holds",
        primary=primary,
        support=dict(
            support,
            flag=benefit.flagged_support(held_used, plan),
            planned_sources=len(protocol["sources"]),
            analysed_sources=len(names),
            minimum_sources=plan.minimum_sources,
            skipped_sources=skipped,
            trimmed_for_balance=trimmed,
        ),
        secondary=dict(
            each_lower_ratio={
                "0.65 - 1.05": _over(pick(weights=[1.0, 0.0, -1.0]), names),
                "0.85 - 1.05": _over(pick(weights=[0.0, 1.0, -1.0]), names),
            },
            other_holds=_over(other, names),
            flagged_minus_other=benefit.summary([benefits[n] - other[n] for n in names if n in other]),
            next_hold=dict(
                benefit=_over(following, names),
                immediate_plus_next=benefit.summary(
                    [benefits[n] + following[n] for n in names if n in following]
                ),
            ),
            ontime_fraction=_over(pick(key="ontime_fraction"), names),
            alternative_flags=alternatives,
            by_previous_request=by_previous,
            by_regime=by_regime,
            actuator_replication={
                "0.85 - 0.65": benefit.summary([rates[n][0] for n in names if n in rates]),
                "1.05 - 0.85": benefit.summary([rates[n][1] for n in names if n in rates]),
            },
            none_of_these_changes_the_outcome=True,
        ),
        sources=names,
        **bindings(protocol_path, protocol, inputs),
        perceptual_quality_claims=False,
        policy_models_fitted=0,
        learned_controller_promoted=False,
    )
    write_json(out, report)
    return report


def dry_run(out, scenario_name="benefit_above_the_gate", seed=7):
    """Planner to outcome on mock sources and synthetic rows. No media, browser or native data."""
    registration = benefit.load_registration(REGISTRATION)
    plan = registration.plan
    scenario = next(s for s in registration.scenarios if s.name == scenario_name)
    out = Path(out).resolve()
    require(not out.exists(), "fresh dry-run directory required")
    sources = allocate(n1.mock_clips(plan.minimum_sources // plan.strata + 2), [], plan, seed)
    runtimes = {PREFIX + s["clip_id"]: mock_runtime(s, i, plan, seed) for i, s in enumerate(sources)}
    protocol = dict(
        abi=ABI,
        mock=True,
        plan=asdict(plan),
        capture=dict(asdict(registration.capture), seed=seed),
        secondary_flags=registration.secondary_flags,
        sources=sources,
        runtimes=runtimes,
        checks=verify_plan(sources, runtimes, plan),
        outcomes_observed=False,
    )
    (out / "plan").mkdir(parents=True)
    write_json(out / "plan/protocol.json", protocol)
    seal_directory(out / "plan", ["protocol.json"], MOCK_PLAN_STAGE, mock=True)
    path, half = out / "plan/protocol.json", (len(sources) // (2 * plan.strata)) * plan.strata
    mock_capture(path, out / "block-one", 0, half, scenario, seed)
    partial = status(path, [out / "block-one"])
    mock_capture(path, out / "block-two", half, len(sources), scenario, seed)
    roots = [out / "block-one", out / "block-two"]
    report = final(path, roots, out / "final.json")
    return dict(
        mock=True,
        scenario=scenario.name,
        plan_checks=protocol["checks"],
        status_after_first_block=partial,
        status_before_final=status(path, roots),
        outcome_on_mock_rows=report["outcome"],
        mean_benefit_on_mock_rows=report["primary"]["mean_benefit"],
        proves_nothing_about_the_native_stack=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Native Phase B1: benefit of backing off in flagged holds")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("show", "freeze", "verify-freeze"):
        sub.add_parser(name)
    dry = sub.add_parser("dry-run", help="Planner to outcome on mock sources and synthetic rows")
    dry.add_argument("--out", required=True, type=Path)
    dry.add_argument("--scenario", default="benefit_above_the_gate")
    plan = sub.add_parser("plan", help="Seal the B1 plan from a screening file; observes no outcome")
    plan.add_argument("--screen", required=True, type=Path)
    plan.add_argument("--out", required=True, type=Path)
    cap = sub.add_parser("capture", help="Collect planned sources; computes no outcome statistic")
    cap.add_argument("--protocol", required=True, type=Path)
    cap.add_argument("--start", required=True, type=int)
    cap.add_argument("--stop", required=True, type=int)
    cap.add_argument("--out", required=True, type=Path)
    for name in ("status", "final"):
        p = sub.add_parser(name)
        p.add_argument("--protocol", required=True, type=Path)
        p.add_argument("--capture", required=True, type=Path, action="append")
        if name == "final":
            p.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            registration = benefit.load_registration(REGISTRATION)
            result = dict(
                plan=asdict(registration.plan),
                secondary_flags=registration.secondary_flags,
                power=benefit.power_table(registration.plan, registration.planning),
            )
        elif args.command == "freeze":
            result = write_freeze()
        elif args.command == "verify-freeze":
            result = verify_freeze()
        elif args.command == "dry-run":
            result = dry_run(args.out, args.scenario)
        elif args.command == "plan":
            result = plan_study(args.screen, args.out)["checks"]
        elif args.command == "capture":
            result = capture(args.protocol, args.out, args.start, args.stop)
        elif args.command == "status":
            result = status(args.protocol, args.capture)
        else:
            report = final(args.protocol, args.capture, args.out)
            result = {k: report[k] for k in ("outcome", "capture_support_passed", "mock")}
        print(json.dumps(result, indent=1, sort_keys=True))
    except (ValueError, FileExistsError, FileNotFoundError, StopIteration) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
