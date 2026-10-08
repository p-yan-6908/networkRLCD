"""Native Phase N1 plumbing: plan, blinded capture, sealed interim and final analysis.

Everything physical is reused unchanged: the screening output and the runtime builder of the
existing studies, the Node collector and the raw peer auditor. This module differs from the
source panel (Phase N2) only where the N1 registration does: one confirmatory sample, a seeded
stratum-balanced order of sources, ten fresh peers per regime, and no outcome statistic
computed at capture time. The planner and capture loop have only ever run against test
doubles and mock rows, never against a browser.
"""

import argparse
import copy
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from scipy import stats

from . import native_actuator_control as control
from . import native_actuator_panel as panel
from . import native_actuator_panel_statistics as panel_statistics
from . import native_actuator_qualification as qualification
from . import native_actuator_statistics as base_statistics
from . import native_actuator_study as physical
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

ABI = qualification.ABI
ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "configs/native_actuator_qualification_n1.json"
FREEZE = ROOT / "configs/native_actuator_qualification_n1_freeze.json"
FROZEN = (
    "configs/native_actuator_qualification_n1.json",
    "docs/NATIVE_PHASE_N1_ACTUATOR_QUALIFICATION.md",
    "src/media_rl/native_actuator_qualification.py",
    "src/media_rl/native_actuator_qualification_panel.py",
)
STRATA = panel_statistics.STRATA
REGIMES = panel_statistics.REGIMES
RUNTIME_STAGE = "discovery"  # the frozen collector accepts only its two legacy labels; N1 has one sample
PLAN_STAGE, MOCK_PLAN_STAGE = ABI + "_plan", ABI + "_mock_plan"
PEER_STAGE, CAPTURE_STAGE, MOCK_STAGE = (
    ABI + "_peer_verified",
    ABI + "_capture_complete",
    ABI + "_mock_capture",
)
BINDINGS = ("clip_id", "cluster_id", "source_title", "capture_group", "source_sha256", "complexity_stratum")


def freeze_record():
    files = {name: digest(ROOT / name) for name in FROZEN}
    return dict(
        abi=ABI + "_freeze",
        files=files,
        sha256=hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        controller_freeze_sha256=digest(assets.FREEZE),
        registered_before_any_outcome=True,
        native_data_collected=False,
    )


def write_freeze(path=FREEZE):
    assets.verify_controller_freeze()
    write_json(
        path, freeze_record()
    )  # refuses to overwrite: a changed registration needs a visible new record
    return read_json(path)


def verify_freeze(path=FREEZE):
    assets.verify_controller_freeze()
    record = read_json(path)
    require(record == freeze_record(), "N1 registration or implementation changed after it was frozen")
    return dict(files=len(record["files"]), sha256=record["sha256"], verified=True)


def allocate(clips, excluded, plan, seed):
    """Sources in analysis order: a seeded draw within complexity terciles, interleaved in balanced blocks.

    The first four blocks are stage one; later blocks are the reserve the blinded rule may call,
    one source per tercile at a time. A source cluster that any earlier native role touched is
    excluded whole, and each cluster contributes one representative window.
    """
    require(plan.strata == len(STRATA), "N1 uses the three screening terciles")
    panel.verify_pool_clusters(clips)
    reserved = {e["sha256"] for e in excluded}
    used = {
        c["cluster_id"] for c in clips if c["source_sha256"] in reserved or c.get("parent_sha256") in reserved
    }
    rng = np.random.default_rng(seed)
    first, ceiling = plan.first_stage_sources // plan.strata, plan.maximum_sources // plan.strata
    drawn = {}
    for stratum in STRATA:
        units = {}
        for clip in sorted(clips, key=lambda c: c["clip_id"]):
            if clip["complexity_stratum"] != stratum or clip["cluster_id"] in used:
                continue
            require(clip["panel_eligible"], "quarantined source cannot enter N1")
            distance = abs(clip["complexity"]["score"] - clip["source_complexity_score"])
            prior = units.get(clip["cluster_id"])
            if prior is None or (distance, clip["clip_id"]) < (prior[0], prior[1]["clip_id"]):
                units[clip["cluster_id"]] = distance, clip
        candidates = [v[1] for _, v in sorted(units.items())]
        require(
            len(candidates) >= first,
            f"N1 needs {first} fresh independent {stratum}-complexity source clusters; {len(candidates)} available",
        )
        drawn[stratum] = [candidates[int(i)] for i in rng.permutation(len(candidates))][:ceiling]
    sources = []
    for block in range(min(len(v) for v in drawn.values())):
        for stratum in STRATA:
            sources.append(dict(drawn[stratum][block], n1_block=block, n1_order=len(sources)))
    return sources


def peer_groups(source, index, plan, seed):
    """Ten fresh peers per regime for one source, each with its own assignment seed."""
    groups = []
    for regime in REGIMES:
        for replicate in range(plan.peers_per_regime):
            key = f"{ABI}:{source['clip_id']}:{regime}:{replicate}:{seed}"
            groups.append(
                dict(
                    id=f"n1-{source['clip_id']}-{regime}-p{replicate}",
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


def bind(trial, group, source):
    trial.update(
        {k: source[k] for k in BINDINGS},
        parent_sha256=source.get("parent_sha256"),
        network_regime=group["family"],
        replicate=int(group["id"].rsplit("-p", 1)[1]),
    )
    return trial


def build_runtime(template, catalog, source, index, plan, seed):
    # Exactly the prior ABI, sampler, observer, credit and raw auditor: only the groups differ.
    groups = peer_groups(source, index, plan, seed)
    runtime = physical._runtime(template, catalog, RUNTIME_STAGE, groups)
    for trial in runtime["episodes"]:
        bind(trial, next(g for g in groups if g["id"] == trial["group"]), source)
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
        episodes.append(bind(trial, group, source))
    return dict(mock=True, episodes=episodes)


def planned_assignments(runtimes):
    """Every arm the plan will assign. Each is fixed by its peer's seed before any capture."""
    return [
        dict(
            trial_id=t["id"],
            cluster_id=t["cluster_id"],
            regime=t["network_regime"],
            seed=t["exploration_seed"],
            epoch=epoch,
            arm=control.assigned_arm(t["exploration_seed"], epoch),
        )
        for runtime in runtimes.values()
        for t in runtime["episodes"]
        for epoch in range(control.MAX_EPOCHS)
    ]


def verify_plan(sources, runtimes, plan):
    """What must hold before any capture: independence, balance, seeds and planned cell support.

    Arms stay IID: the seed is never redrawn to improve balance. A plan whose assigned cells
    fall below the registered minimum is refused, not repaired.
    """
    require(
        plan.strata == len(STRATA)
        and plan.regimes == len(REGIMES)
        and plan.holds_per_peer == control.MAX_EPOCHS,
        "N1 plan must match the frozen strata, regimes and holds per peer",
    )
    blocks = len(sources) // plan.strata
    require(
        len(sources) == blocks * plan.strata
        and plan.first_stage_sources <= len(sources) <= plan.maximum_sources,
        "whole stratum-balanced blocks between the first stage and the maximum",
    )
    for i, source in enumerate(sources):
        require(
            source["n1_order"] == i
            and source["n1_block"] == i // plan.strata
            and source["complexity_stratum"] == STRATA[i % plan.strata],
            "sources must be ordered in stratum-balanced blocks",
        )
    panel.verify_pool_clusters(sources)  # shared title, capture or lineage may not sit in different clusters
    require(
        len({s["cluster_id"] for s in sources}) == len(sources), "one window per independent source cluster"
    )
    require(set(runtimes) == {"n1-" + s["clip_id"] for s in sources}, "one runtime per planned source")
    trials = [t for runtime in runtimes.values() for t in runtime["episodes"]]
    seeds = [t["exploration_seed"] for t in trials]
    require(len(set(seeds)) == len(seeds), "every fresh peer needs its own assignment seed")
    peers = Counter((t["cluster_id"], t["network_regime"]) for t in trials)
    require(
        set(peers) == {(s["cluster_id"], g) for s in sources for g in REGIMES}
        and set(peers.values()) == {plan.peers_per_regime},
        "every source needs the registered number of peers in every regime",
    )
    planned = planned_assignments(runtimes)
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
        reserve_blocks=blocks - plan.first_stage_sources // plan.strata,
        rule_maximum_sources=len(sources),
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
        "n1-" + s["clip_id"]: build_runtime(
            template, screened["catalogs"][s["source_sha256"]], s, i, plan, seed
        )
        for i, s in enumerate(sources)
    }
    return sources, runtimes, verify_plan(sources, runtimes, plan)


def plan_study(screening_path, out, custodian, registration_path=REGISTRATION):
    """Seal the N1 plan. Reads screening output and reservations only; observes no outcome."""
    require(isinstance(custodian, str) and custodian.strip(), "name the interim custodian before planning")
    frozen = verify_freeze()
    require(Path(registration_path).resolve() == REGISTRATION.resolve(), "only the frozen N1 registration")
    registration = qualification.load_registration(registration_path)
    screened = panel._screen(screening_path)
    excluded, inputs = physical.reservations.reservations(registration.capture.reservation_root)
    sources, runtimes, checks = _derive(registration, screened, excluded)
    out = Path(out).resolve()
    require(not out.exists(), "N1 plan must be fresh")
    protocol = dict(
        abi=ABI,
        mock=False,
        n1_freeze_sha256=frozen["sha256"],
        controller_freeze_sha256=digest(assets.FREEZE),
        plan=asdict(registration.plan),
        capture=asdict(registration.capture),
        interim_custodian=custodian.strip(),
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
    registration = qualification.load_registration(REGISTRATION)
    require(
        protocol["abi"] == ABI
        and protocol["mock"] is False
        and protocol["n1_freeze_sha256"] == frozen["sha256"]
        and protocol["plan"] == asdict(registration.plan)
        and protocol["capture"] == asdict(registration.capture)
        and protocol["regimes"] == panel.REGIMES
        and protocol["outcomes_observed"] is False,
        "sealed N1 plan differs from the frozen registration",
    )
    entry = protocol["screened"]
    require(digest(entry["path"]) == entry["sha256"], "screening source changed")
    excluded = []
    for path, sha in protocol["excluded_inputs_sha256"].items():
        require(digest(path) == sha, "prospective all-role reservation changed")
        raw = read_json(path)
        for p in [raw, *raw.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                excluded.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    require(excluded == protocol["excluded_video_ranges"], "complete all-role reservation coverage required")
    sources, runtimes, checks = _derive(registration, panel._screen(entry["path"]), excluded)
    require(
        sources == protocol["sources"] and runtimes == protocol["runtimes"] and checks == protocol["checks"],
        "exact N1 assignments/runtime mismatch",
    )
    return protocol


def effective_plan(protocol):
    """The registered plan, capped at the sources this sealed plan actually holds.

    With fewer reserve sources than the registration allows, the blinded rule's maximum is the
    number planned. The cap is fixed in the sealed plan before any capture, so the rule is
    still chosen in advance; it is never raised or lowered afterwards.
    """
    plan = qualification.Plan(**protocol["plan"])
    return replace(plan, maximum_sources=min(plan.maximum_sources, len(protocol["sources"]))).validate()


def sealed_protocol(path):
    manifest = verify_seal(Path(path).resolve().parent)
    protocol = read_json(path)
    if manifest["stage"] == MOCK_PLAN_STAGE:
        require(protocol["mock"] is True, "mock plan must be labelled")
        verify_plan(
            protocol["sources"], protocol["runtimes"], qualification.Plan(**protocol["plan"]).validate()
        )
        return protocol
    require(manifest["stage"] == PLAN_STAGE, "sealed N1 plan required")
    return validate_plan(protocol)


def _planned(protocol, start, stop):
    plan = effective_plan(protocol)
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
        ("n1-" + s["clip_id"], protocol["runtimes"]["n1-" + s["clip_id"]], t)
        for s in chosen
        for t in protocol["runtimes"]["n1-" + s["clip_id"]]["episodes"]
    ]


def capture(protocol_path, out, start, stop):
    """Collect the planned peers of sources in planned positions [start, stop). No outcome statistic.

    The same collector command, raw audit and row bindings as the source panel; unlike it,
    nothing is analysed here, so collecting does not unblind anyone.
    """
    protocol = sealed_protocol(protocol_path)
    require(protocol["mock"] is False, "a mock plan cannot drive a native capture")
    chosen, peers = _planned(protocol, start, stop)
    rng = np.random.default_rng(protocol["capture"]["seed"] + 1 + start)
    peers = [peers[int(i)] for i in rng.permutation(len(peers))]
    out = Path(out).resolve()
    require(not out.exists(), "fresh N1 capture path required; never overwrite a failed prefix")
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


def synthetic_cohorts(trial, source_effects, scenario, rng):
    """Audited-looking rows for one peer with the planned arms and invented rates. Never evidence."""
    lower, upper = source_effects
    live = REGIMES.index(trial["network_regime"]) >= scenario.dead_regimes
    offset = rng.normal(0, scenario.peer_sd)
    absent = {k: dict(status="absent", value=None) for k in base_statistics.COVARIATES}
    rows = []
    for epoch in range(control.MAX_EPOCHS):
        arm = control.assigned_arm(trial["exploration_seed"], epoch)
        bwe = float(rng.uniform(4e5, 2.5e6))
        level = (
            0.55
            + live * ((arm >= 1) * lower + (arm == 2) * upper)
            + offset
            + rng.normal(0, scenario.cohort_sd)
        )
        rate = max(0.0, float(level)) * bwe
        rows.append(
            dict(
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
                encoder_bps=rate,
                send_bps=1.03 * rate,
                plateau_observed=bool(rng.random() < 0.5),
                block_id=trial["block_id"],
                role=trial["role"],
                state={**absent, "previous_action": None},
                **{k: trial[k] for k in BINDINGS},
                parent_sha256=trial.get("parent_sha256"),
                network_regime=trial["network_regime"],
                replicate=trial["replicate"],
            )
        )
    return rows


def source_effects(source, scenario, rng):
    shift = rng.normal(0, scenario.source_contrast_sd)
    saturating = STRATA.index(source["complexity_stratum"]) < scenario.saturating_strata
    return scenario.lower_effect + shift, (scenario.saturation if saturating else 1.0) * (
        scenario.upper_effect + shift
    )


def mock_capture(protocol_path, out, start, stop, scenario, seed):
    """A capture root of synthetic rows for a mock plan. It exercises the plumbing and proves nothing."""
    protocol = sealed_protocol(protocol_path)
    require(protocol["mock"] is True, "synthetic rows may only follow a mock plan")
    chosen, peers = _planned(protocol, start, stop)
    rng = np.random.default_rng(seed + start)
    effects = {s["cluster_id"]: source_effects(s, scenario, rng) for s in chosen}
    rows = [r for _, _, t in peers for r in synthetic_cohorts(t, effects[t["cluster_id"]], scenario, rng)]
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
        manifest["stage"] == CAPTURE_STAGE, "complete N1 capture required; a failed prefix is never analysed"
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


def estimator_rows(rows, protocol):
    """Audited cohort rows in the estimator's terms, each checked against the planned randomisation."""
    planned = {(a["trial_id"], a["epoch"]): a for a in planned_assignments(protocol["runtimes"])}
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
        measured = all(finite(r[k]) and r[k] >= 0 for k in ("encoder_bps", "send_bps")) if complete else True
        require(
            finite(r["base_bwe_bps"])
            and r["base_bwe_bps"] > 0
            and measured
            and complete == (r["censor_reason"] is None),
            "complete cohorts need measured rates; censored cohorts need a reason",
        )
        out.append(
            dict(
                source=r["cluster_id"],
                stratum=r["complexity_stratum"],
                regime=r["network_regime"],
                arm=r["arm"],
                base_bwe_bps=r["base_bwe_bps"],
                encoder_bps=r["encoder_bps"],
                send_bps=r["send_bps"],
                complete=complete,
                clipped_or_aliased=bool(r["clipped_or_aliased"]),
                plateau_observed=bool(r.get("plateau_observed")),
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


def analysis_order(protocol, captured, unevaluable, total):
    """The first ``total / 3`` evaluable sources per tercile in the pre-drawn order, block by block.

    Evaluability depends on completeness alone, so passing over a source looks at no outcome.
    Sources must be captured in planned order: a gap inside a tercile is refused.
    """
    plan = effective_plan(protocol)
    per = total // plan.strata
    queues, skipped = {}, 0
    for stratum in STRATA:
        planned = [s for s in protocol["sources"] if s["complexity_stratum"] == stratum]
        taken = [s for s in planned if s["cluster_id"] in captured]
        require(taken == planned[: len(taken)], "capture sources in planned order within every tercile")
        usable = [s for s in taken if s["cluster_id"] not in unevaluable]
        require(
            len(usable) >= per,
            f"{per} evaluable {stratum}-complexity sources needed, {len(usable)} captured: capture the next planned block",
        )
        queues[stratum] = usable[:per]
        skipped += sum(s["cluster_id"] in unevaluable for s in taken[: taken.index(usable[per - 1]) + 1])
    return [queues[stratum][block] for block in range(per) for stratum in STRATA], skipped


def status(protocol_path, roots):
    """Outcome-free progress: what is captured, what is evaluable, whether the interim can run."""
    protocol, rows, captured, _ = gather(protocol_path, roots)
    plan = effective_plan(protocol)
    estimator = estimator_rows(rows, protocol)
    _, unevaluable = qualification.source_contrasts(estimator, plan)
    try:
        analysis_order(protocol, captured, set(unevaluable), plan.first_stage_sources)
        ready, blocker = True, None
    except ValueError as error:
        ready, blocker = False, str(error)
    planned = sum(a["cluster_id"] in captured for a in planned_assignments(protocol["runtimes"]))
    return dict(
        mock=protocol["mock"],
        captured_sources=len(captured),
        not_evaluable_sources=sorted(unevaluable),
        planned_cohorts=planned,
        assigned_cohorts=len(rows),
        support=qualification.support(estimator, plan),
        interim_can_run=ready,
        blocker=blocker,
        outcome_free=True,
    )


def bindings(protocol_path, protocol, inputs):
    return dict(
        protocol_sha256=digest(protocol_path),
        registration_sha256=digest(REGISTRATION),
        n1_code_and_registration_sha256=freeze_record()["files"],
        n1_freeze_sha256=protocol.get("n1_freeze_sha256"),
        input_manifests_sha256=inputs,
        interim_custodian=protocol["interim_custodian"],
        mock=protocol["mock"],
    )


def interim(protocol_path, roots, public_out, sealed_out):
    """The blinded look. Writes a sealed record for the custodian and returns only the public one."""
    protocol, rows, captured, inputs = gather(protocol_path, roots)
    plan = effective_plan(protocol)
    estimator = estimator_rows(rows, protocol)
    _, unevaluable = qualification.source_contrasts(estimator, plan)
    order, skipped = analysis_order(protocol, captured, set(unevaluable), plan.first_stage_sources)
    first = [s["cluster_id"] for s in order]
    result = qualification.blinded_interim(estimator, first, plan)
    bound = bindings(protocol_path, protocol, inputs)
    sealed = dict(result["sealed"], first_stage_sources=first, skipped_sources=skipped, **bound)
    write_json(sealed_out, sealed)
    public = dict(result["public"], skipped_sources=skipped, sealed_record_sha256=digest(sealed_out), **bound)
    write_json(public_out, public)
    return public


def _strength(rows, key):
    """The earlier source-clustered first-stage F and partial R-squared: N2-readiness indicators only."""
    try:
        fit = base_statistics._fit(
            [r[key] / r["base_bwe_bps"] for r in rows], panel_statistics.panel_design(rows)
        )
        return dict(cluster_F=fit["F"], partial_R2=fit["partial_R2"])
    except (ValueError, np.linalg.LinAlgError) as error:
        return dict(cluster_F=None, partial_R2=None, unavailable=str(error))


def final(protocol_path, roots, public_path, sealed_path, out):
    """The confirmatory analysis. Runs once the prescribed sources are captured, and unseals the interim."""
    protocol, rows, captured, inputs = gather(protocol_path, roots)
    plan = effective_plan(protocol)
    public, sealed = read_json(public_path), read_json(sealed_path)
    require(digest(sealed_path) == public["sealed_record_sha256"], "sealed interim record changed")
    require(
        public["protocol_sha256"] == digest(protocol_path)
        and public["n1_code_and_registration_sha256"] == freeze_record()["files"]
        and all(inputs.get(root) == sha for root, sha in public["input_manifests_sha256"].items()),
        "plan, code, registration or stage-one capture changed since the interim",
    )
    total = public["prescribed_total_sources"]
    estimator = estimator_rows(rows, protocol)
    contrasts, unevaluable = qualification.source_contrasts(estimator, plan)
    order, skipped = analysis_order(protocol, captured, set(unevaluable), total)
    names = [s["cluster_id"] for s in order]
    require(names[: plan.first_stage_sources] == sealed["first_stage_sources"], "stage-one sources changed")
    strata = np.array([STRATA.index(s["complexity_stratum"]) for s in order])
    primary = qualification.decide([contrasts[n] for n in names], strata, plan)
    recomputed = np.square(primary["first_stage_contrast_sd"])
    require(
        np.allclose(recomputed, sealed["contrast_variances"], rtol=1e-9, atol=0)
        and primary["rule"]["total"] == sealed["prescribed_total_sources"] == total,
        "sealed interim variances do not reproduce",
    )
    used = [r for r in estimator if r["source"] in set(names)]
    support = qualification.support(used, plan)
    supported = support["passed"] and skipped <= plan.maximum_skipped_sources
    send, _ = qualification.source_contrasts(used, plan, key="send_bps")
    regime_map, tests = {}, []
    for regime in REGIMES:
        within, _ = qualification.source_contrasts(used, plan, regime=regime)
        result = qualification.analyse([within[n] for n in names], strata, plan)
        regime_map[regime] = {k: result[k] for k in ("mean_contrasts", "lower_bounds", "upper_bounds")}
        tests += [(p, regime, i) for i, p in enumerate(result["p_values_above_margin"])]
    running = 0.0  # Holm over the eight regime tests
    for rank, (p, regime, i) in enumerate(sorted(tests)):
        running = max(running, min(1.0, (len(tests) - rank) * p))
        regime_map[regime].setdefault("holm_p_values", [None, None])[i] = running
    audited = [r for r in rows if r["cluster_id"] in set(names) and r["complete"] is True]
    spread = np.std([contrasts[n] for n in names], axis=0, ddof=1)
    chi = stats.chi2.ppf([0.975, 0.025], len(names) - 1)
    plateau = [float(np.mean([r["plateau_observed"] for r in used if r["arm"] == arm])) for arm in range(3)]
    report = dict(
        abi=ABI + "_final",
        verdict=primary["verdict"] if supported else qualification.VERDICTS[2],
        designation=primary["designation"] if supported else None,
        capture_support_passed=bool(supported),
        endpoint="actual encoded payload rate / frozen BWE",
        primary=primary,
        support=dict(support, skipped_sources=skipped),
        interim=dict(
            precision_futility=sealed["precision_futility"],
            uncapped_sources=sealed["uncapped_sources"],
            precision_futility_is_not_evidence_about_the_effect=True,
        ),
        secondary=dict(
            send_rate=qualification.analyse([send[n] for n in names], strata, plan),
            regime_map=regime_map,
            first_stage_strength=dict(
                encoder=_strength(audited, "encoder_bps"), send=_strength(audited, "send_bps")
            ),
            per_source_contrast_sd=[float(v) for v in spread],
            per_source_contrast_sd_interval95=[
                [float(v * np.sqrt((len(names) - 1) / c)) for c in chi] for v in spread
            ],
            plateau_share_by_arm=plateau,
            none_of_these_changes_the_verdict=True,
        ),
        sources=names,
        **bindings(protocol_path, protocol, inputs),
        QoE_claims=False,
        policy_models_fitted=0,
        learned_controller_promoted=False,
    )
    write_json(out, report)
    return report


def acquisition_queue(inventory_path, seed, count):
    """Which discovered candidate clusters to verify first for N1, in a seeded order.

    It verifies nothing: no media is downloaded, no right is reviewed and no complexity is
    measured. The order is random so that N1's sources are not hand-picked, and it stops far
    short of the 96 further sources Phase N2 would need.
    """
    units = {}
    for record in sorted(read_json(inventory_path)["records"], key=lambda r: r["asset_id"]):
        if record["planning_candidate"] is True and record["previously_exposed_title"] is False:
            units.setdefault(record["source_cluster_id"], record)
    clusters = [units[key] for key in sorted(units)]
    rng = np.random.default_rng(seed)
    queue = []
    for position, index in enumerate(rng.permutation(len(clusters))[:count]):
        record = clusters[int(index)]
        sizes = [
            v for rep in record["representations"] for k, v in rep.items() if k.startswith("approximate_byte")
        ]
        sizes = [v for v in sizes if finite(v)]
        queue.append(
            dict(
                position=position,
                source_cluster_id=record["source_cluster_id"],
                asset_id=record["asset_id"],
                source_title=record["source_title"],
                license_type=record["license_type"],
                duration_seconds=record["duration_seconds"],
                source_uri=record["source_uri"],
                estimated_bytes=min(sizes) if sizes else None,
                still_blocking=record["blocking_reasons"],
            )
        )
    return dict(
        abi=ABI + "_acquisition_queue",
        seed=seed,
        candidate_clusters=len(clusters),
        queue=queue,
        estimated_bytes=sum(q["estimated_bytes"] or 0 for q in queue),
        verified_eligible_sources=0,
        media_downloaded=False,
        rights_reviewed=False,
        purpose="verify in this order until four, then eight, sources per complexity tercile are eligible",
    )


def mock_clips(per_stratum=8):
    clips = []
    for index, stratum in enumerate(STRATA):
        for i in range(per_stratum):
            sha = hashlib.sha256(f"n1-mock-source-{stratum}-{i}".encode()).hexdigest()
            record = dict(
                source_title=f"mock-title-{stratum}-{i}", capture_group=f"mock-capture-{stratum}-{i}"
            )
            record.update(source_sha256=sha)
            clips.append(
                dict(
                    record,
                    clip_id=panel.clip_identity(sha, [60000, 80000]),
                    cluster_id=assets.assign_clusters([record])[0],
                    segment=[60000, 80000],
                    complexity_stratum=stratum,
                    source_complexity_score=0.1 + 0.3 * index,
                    complexity=dict(score=0.1 + 0.3 * index),
                    panel_eligible=True,
                )
            )
    return clips


def dry_run(out, scenario_name="design_effect_smoke_noise", seed=7):
    """Planner to verdict on mock sources and synthetic rows. No media, browser or native data."""
    registration = qualification.load_registration(REGISTRATION)
    plan = registration.plan
    scenario = next(s for s in registration.scenarios if s.name == scenario_name)
    out = Path(out).resolve()
    require(not out.exists(), "fresh dry-run directory required")
    sources = allocate(mock_clips(plan.maximum_sources // plan.strata), [], plan, seed)
    runtimes = {"n1-" + s["clip_id"]: mock_runtime(s, i, plan, seed) for i, s in enumerate(sources)}
    protocol = dict(
        abi=ABI,
        mock=True,
        plan=asdict(plan),
        capture=dict(asdict(registration.capture), seed=seed),
        interim_custodian="dry-run (no custodian: mock rows)",
        sources=sources,
        runtimes=runtimes,
        checks=verify_plan(sources, runtimes, plan),
        outcomes_observed=False,
    )
    (out / "plan").mkdir(parents=True)
    write_json(out / "plan/protocol.json", protocol)
    seal_directory(out / "plan", ["protocol.json"], MOCK_PLAN_STAGE, mock=True)
    path, first = out / "plan/protocol.json", plan.first_stage_sources
    mock_capture(path, out / "stage-one", 0, first, scenario, seed)
    roots = [out / "stage-one"]
    before = status(path, roots)
    public = interim(path, roots, out / "interim-public.json", out / "interim-sealed.json")
    if public["prescribed_total_sources"] > first:
        mock_capture(path, out / "stage-two", first, public["prescribed_total_sources"], scenario, seed)
        roots.append(out / "stage-two")
    report = final(path, roots, out / "interim-public.json", out / "interim-sealed.json", out / "final.json")
    return dict(
        mock=True,
        scenario=scenario.name,
        plan_checks=protocol["checks"],
        status_before_interim=before,
        interim_public_keys=sorted(public),
        prescribed_total_sources=public["prescribed_total_sources"],
        verdict_on_mock_rows=report["verdict"],
        proves_nothing_about_the_native_stack=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Native Phase N1 actuator qualification")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("show", "freeze", "verify-freeze"):
        sub.add_parser(name)
    power = sub.add_parser("power", help="Simulate operating characteristics under the registered scenarios")
    power.add_argument("--out", required=True, type=Path)
    power.add_argument("--draws", type=int, default=20000)
    power.add_argument("--seed", type=int, default=260107)
    dry = sub.add_parser("dry-run", help="Planner to verdict on mock sources and synthetic rows")
    dry.add_argument("--out", required=True, type=Path)
    dry.add_argument("--scenario", default="design_effect_smoke_noise")
    plan = sub.add_parser("plan", help="Seal the N1 plan from a screening file; observes no outcome")
    plan.add_argument("--screen", required=True, type=Path)
    plan.add_argument("--custodian", required=True)
    plan.add_argument("--out", required=True, type=Path)
    queue = sub.add_parser("queue", help="Seeded order in which to verify discovered candidates for N1")
    queue.add_argument("--inventory", required=True, type=Path)
    queue.add_argument("--count", type=int, default=36)
    queue.add_argument("--out", required=True, type=Path)
    cap = sub.add_parser("capture", help="Collect planned sources; computes no outcome statistic")
    cap.add_argument("--protocol", required=True, type=Path)
    cap.add_argument("--start", required=True, type=int)
    cap.add_argument("--stop", required=True, type=int)
    cap.add_argument("--out", required=True, type=Path)
    for name in ("status", "interim", "final"):
        p = sub.add_parser(name)
        p.add_argument("--protocol", required=True, type=Path)
        p.add_argument("--capture", required=True, type=Path, action="append")
        if name != "status":
            p.add_argument("--public", required=True, type=Path)
            p.add_argument("--sealed", required=True, type=Path)
        if name == "final":
            p.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            registration = qualification.load_registration(REGISTRATION)
            result = dict(plan=asdict(registration.plan), rule=qualification.rule_table(registration.plan))
        elif args.command == "freeze":
            result = write_freeze()
        elif args.command == "verify-freeze":
            result = verify_freeze()
        elif args.command == "power":
            registration = qualification.load_registration(REGISTRATION)
            require(not args.out.exists(), "fresh power output required")
            result = qualification.power_report(
                registration.plan, registration.scenarios, args.draws, args.seed
            )
            args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
            result = {
                e["scenario"]["name"]: e["designs"]["adaptive"]["qualified"] for e in result["scenarios"]
            }
        elif args.command == "dry-run":
            result = dry_run(args.out, args.scenario)
        elif args.command == "queue":
            seed = qualification.load_registration(REGISTRATION).capture.seed
            result = acquisition_queue(args.inventory, seed, args.count)
            write_json(args.out, result)
            result = {k: v for k, v in result.items() if k != "queue"}
        elif args.command == "plan":
            result = plan_study(args.screen, args.out, args.custodian)["checks"]
        elif args.command == "capture":
            result = capture(args.protocol, args.out, args.start, args.stop)
        elif args.command == "status":
            result = status(args.protocol, args.capture)
        elif args.command == "interim":
            result = interim(args.protocol, args.capture, args.public, args.sealed)
        else:
            report = final(args.protocol, args.capture, args.public, args.sealed, args.out)
            result = {k: report[k] for k in ("verdict", "designation", "capture_support_passed", "mock")}
        print(json.dumps(result, indent=1, sort_keys=True))
    except (ValueError, FileExistsError, FileNotFoundError, StopIteration) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
