# M7R: launcher failure before native instrumentation

M7R was preregistered in `6e4f5af2125949d9f6a631feb7eed19b7ff1abfa`.
All four original attempts failed before Chromium, TURN or native media started.
Node reported `MODULE_NOT_FOUND` for
`benchmarks/native_m7r/state_conditioning_episode_m7.mjs`; the generated
collector's actual filename ends in `episode_m7r.mjs`.

This is a launcher failure, with zero native sessions or state memberships
qualified. It provides no evidence about conditioning efficacy or prior-history
effects. The four failed seals and exact stderr are preserved. The 128-session
validation panel remains untouched; no original is retried or replaced within
M7R. The M7 deadline repair itself was not exercised.

A fresh registration can correct only this recorder path, add an existence/
hash prelaunch assertion, and retain the exact guarded recorder, conditioning
algorithm, target regions, counts, and all gates. It must have new trial IDs,
untouched panels and a disjoint raw root. No result is pooled with M7 or M7R,
and no action experiment, state search on M6R or controller fit is enabled.

Compact gate, summary, preservation audit and private archive receipt are
retained alongside this report. Prior freezes and all raw evidence are unchanged.
