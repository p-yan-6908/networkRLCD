"""Validate the committed margin forecast against factual, compact native outcomes.

Recomputes the completed pilot's report from its session summaries, checks the
complete paired design and pinned inputs, and applies the existing registered
forecast rule without running a simulator. This is not raw seal/frame replay.
Holm and leave-one-source-out checks were specified after reading the report;
they neither replace the registered verdict nor select a controller.
"""

import argparse
import hashlib
import inspect
import itertools
import json
import math
import platform
from collections import Counter
from pathlib import Path

import numpy as np
import scipy

from . import native_margin_pilot as margin
from . import typed_bitrate_margin_forecast as forecast

ABI = "native_margin_validation_v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(saved, computed, path="report"):
    """Check all fields, tolerating only floating-point/library rounding.

    Historical unused encoder/rest timing fields can contain NaNs; matching
    NaNs are preserved rather than relabelled. Endpoint fields are checked
    separately for finiteness before statistics are computed.
    """
    if isinstance(saved, dict) and isinstance(computed, dict):
        if saved.keys() != computed.keys():
            raise ValueError(f"{path}: different keys")
        for key in saved:
            compare(saved[key], computed[key], f"{path}/{key}")
    elif isinstance(saved, list) and isinstance(computed, list):
        if len(saved) != len(computed):
            raise ValueError(f"{path}: different lengths")
        for index, (a, b) in enumerate(zip(saved, computed, strict=True)):
            compare(a, b, f"{path}/{index}")
    elif isinstance(saved, bool) or isinstance(computed, bool):
        if type(saved) is not type(computed) or saved != computed:
            raise ValueError(f"{path}: different flags")
    elif isinstance(saved, (int, float)) and isinstance(computed, (int, float)):
        if not (
            math.isnan(saved)
            and math.isnan(computed)
            or math.isclose(saved, computed, rel_tol=1e-12, abs_tol=1e-12)
        ):
            raise ValueError(f"{path}: different numeric values")
    elif type(saved) is not type(computed) or saved != computed:
        raise ValueError(f"{path}: different values")


def validate(report, sessions, made, spec, layer_sha):
    if spec.get("abi") != ABI + "_spec":
        raise ValueError("the margin validation spec is required")
    if (
        spec["registered_criteria"]["primary_span"] != forecast.SPANS[0]
        or spec["registered_criteria"]["forecast_minimum_absolute_difference"] != forecast.receiver.MINIMUM
        or spec["registered_criteria"]["schedule_agreement_fraction"] != 0.8
    ):
        raise ValueError("the registered forecast criteria must remain unchanged")
    if (
        report.get("abi") != margin.ABI + "_report"
        or report.get("development_pilot") is not True
        or report.get("confirmatory") is not False
        or report.get("learned_controller_promoted") is not False
        or report.get("models_fitted") != 0
    ):
        raise ValueError("factual development pilot report required; no promotion")
    if report.get("plan_sha256") != spec["plan_sha256"]:
        raise ValueError("the report belongs to another plan")
    if (
        made.get("study") != forecast.STUDY
        or made.get("synthetic") is not True
        or made.get("native_evidence") is not False
        or made.get("written_before_the_capture") is not True
        or made.get("learned_controller_promoted") is not False
        or made.get("layer_sha256") != layer_sha
    ):
        raise ValueError("the original synthetic forecast and unchanged layer are required")
    compare(made["arms"], list(margin.NAMES), "forecast/arms")
    compare(made["schedules"], margin.CAPACITIES, "forecast/schedules")
    if report["planned_sessions"] != spec["sessions"] or len(sessions) != spec["sessions"]:
        raise ValueError("incomplete capture")
    sources = sorted({s["source"] for s in sessions})
    expected = set(
        itertools.product(sources, margin.REGIMES, range(len(margin.NAMES)), range(spec["repetitions"]))
    )
    cells = Counter((s["source"], s["regime"], s["arm"], s["repetition"]) for s in sessions)
    if len(sources) != spec["sources"] or set(cells) != expected or any(n != 1 for n in cells.values()):
        raise ValueError("missing, duplicate or unknown paired source/schedule/arm/repetition cell")
    if len({s["trial_id"] for s in sessions}) != len(sessions):
        raise ValueError("duplicate trial identity")
    for s in sessions:
        for span in margin.SPANS:
            for key in margin.QUANTITIES:
                value = s[span][key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"nonfinite outcome: {s['trial_id']}/{span}/{key}")
    regenerated = margin.analyse(sessions, planned=spec["sessions"])
    regenerated["plan_sha256"] = spec["plan_sha256"]
    compare(report, regenerated)
    return forecast.judged(made, report)


def holm(p_values):
    """Two-sided Holm adjusted p-values across the specified six comparisons."""
    ordered = sorted(p_values, key=p_values.get)
    running, adjusted = 0.0, {}
    for rank, pair in enumerate(ordered):
        running = max(running, (len(ordered) - rank) * p_values[pair])
        adjusted[pair] = min(1.0, running)
    return adjusted


def sensitivity(report, sessions):
    contrasts = report["all_schedules"]["session"]["utility"]["contrasts"]
    adjusted = holm({pair: contrasts[pair]["p_value"] for pair in forecast.PAIRS})
    omitted = {}
    for source in sorted({s["source"] for s in sessions}):
        table = margin.by_arm(
            [s for s in sessions if s["source"] != source], lambda s: s["session"]["utility"]
        )
        omitted[source] = table["contrasts"]["margin minus 0.65"]
    means = [e["mean"] for e in omitted.values()]
    return dict(
        added_after_native_report_was_read=True,
        selection_or_promotion=False,
        holm_family="six overall whole-session endpoint contrasts; two-sided alpha 0.05",
        holm={
            pair: dict(
                p_value=contrasts[pair]["p_value"], adjusted_p_value=value, rejects_at_005=value < 0.05
            )
            for pair, value in adjusted.items()
        },
        leave_one_source_out=dict(
            pair="margin minus 0.65",
            omitted_sources=omitted,
            mean_range=[min(means), max(means)],
            negative_means=sum(v < 0 for v in means),
        ),
    )


def trajectories(report, made):
    """Descriptive final-bin cap and buffer checks, specified after reading the report.

    Requested caps are compared on matching 6 s bins, not treated as actual
    encoded output. These outcome diagnostics are never runtime policy inputs.
    """
    return dict(
        added_after_native_report_was_read=True,
        causal_mechanism_identified=False,
        arm="0.65",
        bin_seconds=[54, 60],
        by_schedule={
            regime: dict(
                native_requested_kbps=report["timeline"][regime]["0.65"]["requested_kbps"][-1],
                forecast_requested_kbps=made["timeline"]["0.65"][regime]["requested_kbps"][-1],
                native_jitter_buffer_ms=report["timeline"][regime]["0.65"]["jitter_buffer_ms"][-1],
                forecast_jitter_buffer_ms=made["timeline"]["0.65"][regime]["jitter_buffer_ms"][-1],
            )
            for regime in margin.REGIMES
        },
    )


def tables(report, judged):
    primary = judged["spans"]["session"]
    rows = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Arm & Forecast & Native & Native 95\% interval & On time (\%) \\",
        r"\midrule",
    ]
    for name in margin.NAMES:
        e = primary["levels"][name]
        rate = report["all_schedules"]["session"]["on_time"]["arms"][name]["level"]["mean"]
        lo, hi = e["native_interval95"]
        rows.append(
            f"{name} & {e['forecast']:.2f} & {e['native']:.2f} & [{lo:.2f}, {hi:.2f}] & "
            f"{100 * rate:.1f}" + r" \\"
        )
    rows += [r"\bottomrule", r"\end{tabular}"]
    differences = [
        r"\begin{tabular}{lrrll}",
        r"\toprule",
        r"Difference & Forecast & Native & Native 95\% interval & Forecast verdict \\",
        r"\midrule",
    ]
    for pair in forecast.PAIRS:
        e = primary["differences_over_all_schedules"][pair]
        lo, hi = e["native_interval95"]
        differences.append(
            f"{pair.replace(' minus ', ' $-$ ')} & {e['simulated']:+.2f} & "
            f"{e['native']:+.2f} & [{lo:+.2f}, {hi:+.2f}] & {e['verdict']}" + r" \\"
        )
    differences += [r"\bottomrule", r"\end{tabular}"]
    return {
        "margin_pilot_arms.tex": "\n".join(rows) + "\n",
        "margin_pilot_contrasts.tex": "\n".join(differences) + "\n",
    }


def run(spec_path, out, paper_out):
    """Read only pinned evidence; write new compact reports and paper evidence."""
    spec_path, out, paper_out = Path(spec_path), Path(out), Path(paper_out)
    if out.resolve() == paper_out.resolve() or out.exists() or paper_out.exists():
        raise ValueError("two distinct fresh output directories required")
    spec = json.loads(spec_path.read_text())
    paths = {role: Path(e["path"]) for role, e in spec["inputs"].items()}
    if set(paths) != {"forecast", "report", "sessions", "layer"}:
        raise ValueError("exactly four pinned evidence inputs required")
    for role, path in paths.items():
        if sha(path) != spec["inputs"][role]["sha256"]:
            raise ValueError(f"changed pinned {role} input")
    report, sessions, made = (
        json.loads(paths[role].read_text()) for role in ("report", "sessions", "forecast")
    )
    judged = validate(report, sessions, made, spec, sha(paths["layer"]))
    source_paths = [
        Path(__file__),
        Path(margin.__file__),
        Path(forecast.__file__),
        Path(margin.ladder.__file__),
        Path(forecast.receiver.__file__),
        Path(inspect.getfile(margin.ladder.summary)),
    ]

    def portable(path):
        resolved = path.resolve()
        return str(resolved.relative_to(Path.cwd())) if resolved.is_relative_to(Path.cwd()) else str(path)

    provenance = {portable(path): sha(path) for path in [spec_path, *paths.values(), *source_paths]}
    checked = dict(
        abi=ABI,
        development_pilot=True,
        confirmatory=False,
        controller_promoted=False,
        models_fitted=0,
        new_native_sessions=0,
        raw_replay_performed=False,
        report_recomputed_from_compact_factual_summaries=True,
        report_numeric_tolerance=dict(relative=1e-12, absolute=1e-12),
        sources=spec["sources"],
        sessions=len(sessions),
        plan_sha256=spec["plan_sha256"],
        registered_criteria=spec["registered_criteria"],
        registered_verdict=judged["verdict"],
        supplementary=sensitivity(report, sessions),
        trajectory_description=trajectories(report, made),
        input_and_code_sha256=provenance,
        runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        limitation="Compact outcome/statistic verification only; raw native seals and frames were not replayed.",
    )
    primary = judged["spans"]["session"]
    macros = dict(
        MarginPilotSessions=len(sessions),
        MarginPilotSources=spec["sources"],
        MarginForecastVerdict=judged["verdict"],
        MarginForecastAgree=primary["agreeing_over_all_schedules"],
        MarginForecastEstablished=primary["established_over_all_schedules"],
        MarginForecastLocalEstablished=primary["established_under_the_schedules"],
        MarginForecastLocalAgree=round(
            primary["share_agreeing_under_the_schedules"] * primary["established_under_the_schedules"]
        ),
        MarginPilotHolmLow=f"{checked['supplementary']['holm']['margin minus 0.65']['adjusted_p_value']:.3f}",
    )
    tex = "% Generated by media_rl.native_margin_pilot_report; development evidence only.\n"
    tex += "".join(f"\\newcommand{{\\{key}}}{{{value}}}\n" for key, value in macros.items())
    for directory in (out, paper_out):
        directory.mkdir(parents=True)
    for name, data in (("audit.json", checked), ("judged.json", judged)):
        (out / name).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
    for name, content in tables(report, judged).items():
        (paper_out / name).write_text(content)
    (paper_out / "evidence.tex").write_text(tex)
    provenance[str(out / "audit.json")] = sha(out / "audit.json")
    provenance[str(out / "judged.json")] = sha(out / "judged.json")
    (paper_out / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    return dict(
        verdict=judged["verdict"],
        sessions=len(sessions),
        raw_replay_performed=False,
        out=str(out),
        paper_out=str(paper_out),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--paper-out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.spec, args.out, args.paper_out)
    except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
