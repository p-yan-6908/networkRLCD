"""Where in the schedule a benefit of backing off sits: an addendum to Native Phase B1.

Fixed before any B1 data exist, after B1's registration was frozen, and informed by an
exploratory pass over N1's raw logs (docs/NATIVE_PHASE_N1_DYNAMICS.md). It is not part of the
registration and changes no registered quantity or outcome. It reads B1's audited rows through
the frozen panel code and runs only after the registered final report has been written.
"""

import argparse
import gzip
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from . import native_backoff_benefit as benefit
from . import native_backoff_benefit_panel as b1
from .native_protocol import digest, read_json, require, write_json

ABI = benefit.ABI + "_positions_addendum"
DROP_REGIMES = ("queue-building", "collapse-recovery")  # capacity falls just before the third hold
KINDS = ("before_drop", "drop", "after_drop", "late_drop_schedules", "near_capacity", "room")
USABLE = ("after_drop", "late_drop_schedules", "near_capacity")  # states the sender's estimate can show
ENDPOINTS = (benefit.ENDPOINT, "ontime_fraction")


def kind(regime, epoch):
    """The position of a hold in its scripted schedule. Holds are numbered from zero."""
    require(regime in b1.REGIMES, "unknown schedule")
    if regime in DROP_REGIMES:
        return {1: "before_drop", 2: "drop", 3: "after_drop"}.get(epoch, "late_drop_schedules")
    return "near_capacity" if regime == "near-capacity" else "room"


def _over(values, names):
    return benefit.summary([values[n] for n in names if n in values])


def table(held, names, plan):
    """Per kind of hold: the registered contrast among its flagged holds and among all its holds.

    ``held`` are B1's holds with a predecessor, as the registered flag marks them, and ``names``
    the sources of the registered analysis. The split is thin, so a source counts when it has one
    complete hold in every arm of the cell, and the number of such sources is reported.
    """
    loose = replace(plan, minimum_flagged_cell=1)
    chosen = set(names)
    held = [dict(h, kind=kind(h["regime"], h["epoch"])) for h in held if h["source"] in chosen]
    flagged_total = sum(h["flagged"] for h in held)
    out = {}
    for name in KINDS:
        members = [h for h in held if h["kind"] == name]
        everything = [dict(h, flagged=True) for h in members]
        marked = sum(h["flagged"] for h in members)
        entry = dict(
            holds=len(members),
            flagged_holds=marked,
            share_of_flagged_holds=marked / flagged_total if flagged_total else None,
        )
        for key in ENDPOINTS:
            entry[key] = dict(
                flagged=_over(benefit.source_benefits(members, loose, key=key)[0], names),
                all_holds=_over(benefit.source_benefits(everything, loose, key=key)[0], names),
            )
        out[name] = entry
    return out


def above_zero(entry):
    return entry["interval"] is not None and entry["interval"][0] > 0


def reading(made):
    """What the split says, by rules fixed with it. Intervals are not corrected for the six kinds."""
    flagged = {name: above_zero(made[name][benefit.ENDPOINT]["flagged"]) for name in KINDS}
    return dict(
        benefit_among_flagged_holds=flagged,
        sits_in_the_hold_of_the_drop=flagged["drop"]
        and not any(v for k, v in flagged.items() if k != "drop"),
        flag_finds_a_usable_state=any(flagged[k] for k in USABLE),
        helps_in_the_drop_hold_whatever_the_flag=above_zero(made["drop"][benefit.ENDPOINT]["all_holds"]),
        intervals_not_corrected_for_the_number_of_kinds=True,
    )


def composition(rows, plan):
    """Which holds the registered flag marks, by position. No outcome is read.

    Only the frozen estimates, the arms and the plan enter, so this can be computed for any
    capture without looking at a result.
    """
    shaped = [
        dict(
            trial_id=r["trial_id"],
            epoch=r["epoch"],
            arm=r["arm"],
            base_bwe_bps=r["base_bwe_bps"],
            regime=r["network_regime"],
            source=r["cluster_id"],
            complete=r["complete"],
        )
        for r in rows
    ]
    held = [dict(h, kind=kind(h["regime"], h["epoch"])) for h in benefit.flag_rows(shaped, plan)]
    total = sum(h["flagged"] for h in held)
    require(total > 0, "the flag marks no hold")

    def share(members):
        return sum(h["flagged"] for h in members) / len(members) if members else None

    kinds = {}
    for name in KINDS:
        members = [h for h in held if h["kind"] == name]
        marked = sum(h["flagged"] for h in members)
        kinds[name] = dict(
            holds=len(members),
            flagged_holds=marked,
            flagged_share=share(members),
            share_of_flagged_holds=marked / total,
        )
    epochs = sorted({h["epoch"] for h in held})
    drop = [h for h in held if h["kind"] == "drop"]
    return dict(
        abi=ABI + "_flag_composition",
        outcome_free=True,
        flag=f"frozen estimate below {plan.growth_limit:g} times the previous hold's",
        holds_with_a_predecessor=len(held),
        flagged_holds=total,
        kinds=kinds,
        by_schedule_and_hold={
            regime: {
                str(epoch + 1): share([h for h in held if h["regime"] == regime and h["epoch"] == epoch])
                for epoch in epochs
            }
            for regime in b1.REGIMES
        },
        drop_hold_by_previous_ratio={
            f"{ratio:.2f}": share([h for h in drop if h["previous_arm"] == arm])
            for arm, ratio in enumerate(benefit.RATIOS)
        },
    )


def positions(protocol_path, roots, final_path):
    """The split for one B1 study. The registered final report has to exist already."""
    final = read_json(final_path)
    require(
        final.get("abi") == benefit.ABI + "_final" and isinstance(final.get("sources"), list),
        "the registered final report comes first",
    )
    protocol, rows, _, inputs = b1.gather(protocol_path, roots)
    require(final["mock"] == protocol["mock"], "final report and plan disagree about being mock")
    plan = b1.registered_plan(protocol)
    held = benefit.flag_rows(b1.estimator_rows(rows, protocol), plan)
    made = table(held, final["sources"], plan)
    return dict(
        abi=ABI,
        addendum=True,
        part_of_the_registration=False,
        changes_the_registered_outcome=False,
        mock=protocol["mock"],
        registered_outcome=final["outcome"],
        analysed_sources=len(final["sources"]),
        kinds=made,
        reading=reading(made),
        final_report_sha256=digest(final_path),
        capture_manifests_sha256=inputs,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="B1 addendum: where in the schedule a benefit sits")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--capture", type=Path, action="append")
    parser.add_argument("--final", type=Path)
    parser.add_argument(
        "--composition", type=Path, help="audited rows: only count which holds the flag marks"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output path required\n")
    try:
        if args.composition:
            raw = args.composition.read_bytes()
            rows = json.loads(gzip.decompress(raw) if args.composition.suffix == ".gz" else raw)
            report = dict(
                composition(rows, benefit.load_registration(b1.REGISTRATION).plan),
                rows_sha256=hashlib.sha256(
                    gzip.decompress(raw) if args.composition.suffix == ".gz" else raw
                ).hexdigest(),
            )
            shown = {name: entry["share_of_flagged_holds"] for name, entry in report["kinds"].items()}
        else:
            require(
                args.protocol and args.capture and args.final,
                "the split needs --protocol, --capture and --final",
            )
            report = positions(args.protocol, args.capture, args.final)
            shown = report["reading"]
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    write_json(args.out, report)
    print(json.dumps(shown, indent=1))


if __name__ == "__main__":
    main()
