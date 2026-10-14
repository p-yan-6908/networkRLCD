"""Generate M6R prospectively from closed M6; change only causal clock training."""
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parents[1]
anchor = subprocess.check_output(["git", "rev-parse", "2cdd630"], cwd=repo, text=True).strip()


def rename(text):
    return (text.replace("history_state_support_m6", "history_state_support_m6r")
            .replace("measure_history_state_m6", "measure_history_state_m6r")
            .replace("native-history-state-m6", "native-history-state-m6r")
            .replace("native_history_state_m6", "native_history_state_m6r")
            .replace("NATIVE_HISTORY_STATE_M6", "NATIVE_HISTORY_STATE_M6R")
            .replace("m6-r", "m6r-r").replace("M6:", "M6R:").replace("fresh M6 support", "fresh M6R support")
            .replace("20261117", "20261121").replace("20261120", "20261122"))


text = rename((repo / "tools/history_state_support_m6.py").read_text())
start, end = text.index("def beginning_polygon("), text.index("\ndef sender_features(")
text = text[:start] + '''def past_polygon(directory, sender_start, cutoff):
    original = v.core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    extra = v.read(directory / "instrument_clock_browser.json")
    latest = sender_start + cutoff - 100
    train = [x for i, x in enumerate(original) if i in (0, 1, 3, 4, 6, 7, 9, 11) and x["browser_receive_ms"] <= latest]
    train += [x for x in extra if x["role"] == "train" and x["browser_receive_ms"] <= latest]
    held = [x for i, x in enumerate(original) if i in (2, 5, 8, 10) and x["browser_receive_ms"] <= latest]
    held += [x for x in extra if x["role"] == "holdout" and x["browser_receive_ms"] <= latest]
    assert len(train) >= 35 and len(held) >= 4
    assert max(x["browser_receive_ms"] for x in train + held) <= latest
    certificate = v.core.validate_markers(train + held, list(range(len(train))), list(range(len(train), len(train) + len(held))))
    assert certificate["passed"]
    origin, vertices = v.core.feasible_polygon(train)
    return origin, vertices, {"training": len(train), "held_out": len(held), "passed": True,
                              "latest_available_guard_ms": 100, "max_training_receipt_elapsed_ms": max(x["browser_receive_ms"] for x in train) - sender_start}

''' + text[end:]
text = text.replace('        origin, vertices = beginning_polygon(directory, start)\n', '')
old = '            cutoff = row["windows"][str(now)]["history_ms"][-1]\n'
assert text.count(old) == 1
text = text.replace(old, old + '            origin, vertices, certificate = past_polygon(directory, start, cutoff)\n')
text = text.replace('"cutoff": cutoff, "features":', '"cutoff": cutoff, "causal_clock": certificate, "features":')
text = text.replace('"relay_clock_boundary_width_ms": w["boundary_width_ms"],', '"relay_clock_boundary_width_ms": w["boundary_width_ms"], "causal_clock": w["causal_clock"],')
text = text.replace('# First-phase mapping uses only training already available before 18 s.', '# Sequential mapping uses only training already available before each cutoff.')
(repo / "tools/history_state_support_m6r.py").write_text(text)

text = rename((repo / "tools/measure_history_state_m6.py").read_text())
text = text.replace('"ad0bf338b76df23ec190e5bdb71d4cfe822338b2"', repr(anchor)).replace('"ad0bf33"', '"2cdd630"')
text = text.replace('SCIENCE = [', 'SCIENCE = ["tools/build_history_state_m6r.py", ')
(repo / "tools/measure_history_state_m6r.py").write_text(text)

text = (repo / "docs/NATIVE_HISTORY_STATE_M6_PLAN.md").read_text().replace("M6", "M6R")
text = text.replace("native-history-state-m6/", "native-history-state-m6r/")
text = text.replace("ad0bf338b76df23ec190e5bdb71d4cfe822338b2", anchor)
text = text.replace("20261117", "20261121").replace("20261120", "20261122")
start = text.index('Use only the independent **35-training beginning clock polygon**')
end = text.index('\nCap readbacks', start)
text = text[:start] + '''Use the sequential affine polygon from **all original/extra training exchanges
whose browser receipt is at least 100 ms before the actual cutoff**. Preserve
the original train/held-out assignments. Require ≥35 training and ≥4 independent
held-out exchanges already available by that same guard, and validate them using
the unchanged every-feasible-vertex, 1 ms tolerance and 50 ms width rules. No
future exchange or held-out exchange trains the map. The clock-only M5 diagnostic
qualified all 252 cutoffs using 45/55 training and 5/6 held-out exchanges, with
maximum cutoff uncertainty 4.36912 ms; actual M6R checks remain mandatory.

Future service, trace capacities, prefix identity, receiver pixels and quality
labels cannot be features. At each cutoff retain only complete relay events in
the conservative mapped interval [cutoff−2100,cutoff−100] ms: lower node bound is
the maximum mapped lower boundary, upper node bound is the minimum mapped upper
boundary. Require boundary uncertainty ≤50 ms; queue integration needs ≥99%
complete-interval coverage. This 100 ms guard enforces temporal order, not a
demonstrated online feedback latency guarantee. Relay-assisted success would
require a separately qualified feedback path before a sender action study.
''' + text[end:]
intro = '''
The parent **M6** is closed at `2cdd630` after its first feature projection
failed an over-extrapolated beginning-map guard. No feature table, candidate
selection or fresh panel was created there. Preserve its registration, logs,
clock-only diagnostics and closure. M6R uses the existing exchanges available
by each cutoff; it changes no numerical clock limit, candidate, caliper,
matching/coverage rule, count, outcome definition or action gate. Its names,
namespace and randomization/bootstrap seeds are fresh. Include the complete M6
closure in the final verified private evidence snapshot.
'''
text = text.replace('## Question, stages and independence', intro + '\n## Question, stages and independence')
(repo / "docs/NATIVE_HISTORY_STATE_M6R_PLAN.md").write_text(text)

for suffix in ("access-preflight", "runtime-preflight", "input-verification"):
    old = repo / f"reports/native-history-state-m6-{suffix}.json"
    target = repo / f"reports/native-history-state-m6r-{suffix}.json"
    target.write_text(rename(old.read_text()))
print("Generated fresh M6R code, plan and references; no support features read.")
