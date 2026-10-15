# M7: instrumentation-limited feasibility failure

M7 was preregistered in `c262b151fff4c3aa81835c60b7b0069d36cae73d` before
capture. All four original feasibility sessions sealed; none qualified the
complete registered technical gate. Its 128-session validation panel remains
untouched. No action study, predictor or controller was run.

## Exact failure

The single-call `setTimeout` wait could return before its browser-clock
deadline. Of 104 service updates, 39 were **0.1–0.7ms early**. Two feedback-off
events occurred at +26999.7ms and +26999.5ms rather than at or after +27000ms.
The frozen gate correctly rejected these events. Input histories, the feedback
formula, exact service readback, and command response/lateness upper bounds
otherwise matched. No timing tolerance or state gate has been changed.

All four original sessions passed the inherited startup, full and beginning
clock, strict TURN/TCP, fixed encoder/jitter readback, media progression,
source-replay and post-cutoff cleanup checks. Maximum full held-out clock width
was **1.331ms**, beginning width **2.797ms**. This failure belongs to the new
conditioning scheduler, rather than the qualified clock mapping or transport.

The raw support records include three instantaneous target hits and one
sustained-history target hit, but **zero technically qualified memberships**.
These are debugging observations from four contexts, not confirmatory state
coverage or a causal prefix estimate. The registered result is unestimable for
prospective native common support. M5's causal history evidence remains intact;
M6R is still a coverage failure, and its validation telemetry was not reopened.

## Next prospective step

Preserve this failure and the untouched panel. A fresh registration may repair
only deadline waiting: re-read the monotonic browser clock after every timer
return and yield until the existing deadline has actually arrived. It must
retain the exact feedback formula, 26 updates, fixed release time, target
regions, history definition, original counts, calipers, range/SD/overlap and
repeatability gates. Fresh feasibility and validation identifiers are required;
no M7 attempt may be relabeled or pooled into the replacement validation.

See the compact [gate](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7-feasibility-gate.json),
[command diagnostic](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7-command-diagnostic.json),
[summary](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7-summary.json),
and [trajectory figure](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7-trajectories.png).
Quality/frame outcome files remain unopened by the analysis. All originals and
failed checks are retained; the private archive receipt and checksum-only
preservation audit record storage verification separately.
