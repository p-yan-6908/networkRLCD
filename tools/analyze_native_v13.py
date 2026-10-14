"""Registered finite-panel continuous action-effect summaries; no controller."""
from __future__ import annotations

import argparse
import importlib.util
import math
import statistics as st
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


runner=module("v13_registered_runner",REPO/"tools/design_native_v13.py")
legacy=module("v13_unchanged_hold_outcomes",REPO/"tools/analyze_native_v12.py")
METRICS=legacy.METRICS


def linear(rows):
    if len(rows)<3 or any(y is None for x,y in rows):return {"estimable":False,"slope":None,"intercept_at_500k":None}
    mx,my=st.mean(x for x,y in rows),st.mean(y for x,y in rows)
    denominator=sum((x-mx)**2 for x,y in rows)
    if denominator<=1e-12:return {"estimable":False,"slope":None,"intercept_at_500k":None}
    beta=sum((x-mx)*(y-my) for x,y in rows)/denominator
    return {"estimable":True,"slope":beta,"intercept_at_500k":my-beta*mx,"mean_action_effect":my,
        "census_state_log2_range":[min(x for x,y in rows),max(x for x,y in rows)],
        "pairs":len(rows),"population_interval":None,"scope":"Equal-pair finite-panel linear projection; the intercept may lie outside observed support and is not interpreted there."}


def analyze(output):
    if output.exists():raise ValueError("preserve completed outcomes")
    runner.verify()
    if not (runner.ROOT/"capture_index.json").exists():raise ValueError("confirmatory panel is untouched; no outcomes opened")
    gate=runner.gate(runner.ROOT)
    if not gate["passed"] or gate["qualified_sessions"]!=64 or len(gate["cells"])!=4:
        raise ValueError("all 64 sessions and four cells must qualify before outcomes are decoded")
    protocol=runner.read(runner.CONFIG)
    # This loader preserves the original 150ms timely sampled RGB PSNR,
    # ack+[1800,2600]ms window and clock-bounded relay accounting definitions.
    holds=[legacy.load_hold(runner.ROOT,t) for t in protocol["trials"]]
    pairs=[]
    for pair in sorted({t["pair_id"] for t in protocol["trials"]}):
        rows=[h for h in holds if h["pair_id"]==pair]
        assert len(rows)==2 and {h["ratio"] for h in rows}=={.65,1.05}
        low=next(h for h in rows if h["ratio"]==.65);high=next(h for h in rows if h["ratio"]==1.05)
        a,b=legacy.bucket([low]),legacy.bucket([high]);key=low["cell"]+"::"+low["profile_id"]
        pairs.append({"pair_id":pair,"cell":low["cell"],"profile":low["profile_id"],"content":low["content_id"],"family":low["network_family"],
            "campaign":low["network_campaign_id"],"x":gate["census_states"][key]["x"],
            "effects":{m:b[m]-a[m] if a[m] is not None and b[m] is not None else None for m in METRICS},"arm_hold_summaries":{"0.65":a,"1.05":b}})
    cells={}
    for cell in protocol["cells"]:
        rows=[p for p in pairs if p["cell"]==cell];assert len(rows)==8 and len({p["profile"] for p in rows})==4
        cells[cell]={"content":rows[0]["content"],"family":rows[0]["family"],"campaign":rows[0]["campaign"],
            "metrics":{m:linear([(p["x"],p["effects"][m]) for p in rows]) for m in METRICS},
            "leave_one_profile_sensitivities":{profile:linear([(p["x"],p["effects"][METRICS[0]]) for p in rows if p["profile"]!=profile]) for profile in sorted({p["profile"] for p in rows})}}
    summaries={}
    for metric in METRICS:
        estimates=[c["metrics"][metric]["slope"] for c in cells.values()];complete=all(v is not None for v in estimates)
        strata={}
        for field in ("content","campaign","family"):
            strata[field]={}
            for key in sorted({c[field] for c in cells.values()}):
                values=[c["metrics"][metric]["slope"] for c in cells.values() if c[field]==key]
                strata[field][key]={"cells":len(values),"all_estimable":all(v is not None for v in values),"mean_slope":st.mean(values) if all(v is not None for v in values) else None}
        summaries[metric]={"all_cells_estimable":complete,"cell_slopes":{name:c["metrics"][metric]["slope"] for name,c in cells.items()},
            "equal_crossed_mean":st.mean(estimates) if complete else None,"strata":strata}
    primary=summaries[METRICS[0]];mean=primary["equal_crossed_mean"];sign=1 if mean is not None and mean>0 else -1 if mean is not None and mean<0 else 0
    same=sign!=0 and all(v is not None and sign*v>0 for v in primary["cell_slopes"].values())
    strong=same and all(s["mean_slope"] is not None and sign*s["mean_slope"]>=.25 for field in ("campaign","content") for s in primary["strata"][field].values())
    robust=same and all(s["slope"] is not None and sign*s["slope"]>0 for c in cells.values() for s in c["leave_one_profile_sensitivities"].values())
    local_pass=bool(primary["all_cells_estimable"] and same and strong and robust)
    report={"abi":"native_v13_continuous_action_finite_panel_report_v1","protocol_sha256":runner.sha(runner.CONFIG),
        "gate_sha256":runner.sha(runner.ROOT/"support_clock_transport_gate.json"),"cells":cells,"pairs":pairs,"metrics":summaries,"holds":holds,
        "primary_direction":sign,"local_gradient_directional_stability_passed":local_pass,
        "common_support_log2_interval":gate["common_support_log2_interval"],
        "cross_campaign_common_support_stability_passed":bool(local_pass and gate["common_support_at_least_half_octave"]),
        "conditional_policy_value_established":False,"population_estimate":False,"controller_fitted_tuned_or_promoted":False,"prior_sources_pooled":False,
        "limits":["Continuous census BWE modifies a randomized action contrast; BWE itself is not randomized.",
            "The census state is checked against every action-run state; this is a common-conditioning context, not arbitrary live sender histories.",
            "Timely PSNR conditions on successful delivery and is not human QoE or utility over fixed .65.",
            "Disjoint campaign state ranges permit only local-gradient comparisons, not transportable conditional action values.",
            "Windows/directions/repeats are nested in two trace bundles from one measurement program; no population confidence interval or independent-program claim.",
            "All secondary delivery/cost strata remain reported; quality replication alone cannot authorize learned control or V10 retuning."]}
    runner.write(output,report)
    return {"all_primary_cells_estimable":primary["all_cells_estimable"],"local_gradient_stability":local_pass,
        "cross_campaign_common_support_stability":report["cross_campaign_common_support_stability_passed"],"controller_fitted":False,"output":str(output)}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,default=REPO/"reports/native-v13-analysis.json");args=p.parse_args();print(__import__('json').dumps(analyze(args.out)))
