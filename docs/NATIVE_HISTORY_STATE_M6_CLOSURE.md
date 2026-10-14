# M6: pre-selection temporal-mapping guard failure

Registration `9e8d5bae9effad3aec736efdd976cea191ea0367` is preserved unchanged.
The one development coordinator stopped on its first history-feature projection,
before writing a feature table, selecting a state, preparing a fresh panel or
starting a native session. No candidate/future-BWE comparison was produced.
This is a technical failure of this development specification, not evidence for
or against observable history-state sufficiency.

The design incorrectly attempted to extrapolate the 35-training **beginning**
clock polygon to all 18/24/30-second relay-history cutoffs. Those training
exchanges finish around the start of the first phase, not its end. Their
certificate remains valid for its registered early held-out exchanges; it does
not imply a 50 ms bound tens of seconds later. An outcome-free audit found
**252/252** extrapolated cutoff bounds failed M6's unchanged 50 ms limit, with
maximum **159.089 ms**. The guard correctly stopped extraction. M5's separate
qualified 64-training full-session mapping, startup qualification and causal
prefix result are unaffected. No old certificate or session is requalified.

A clock-only diagnostic instead used **every original/extra training exchange
whose browser receipt preceded each cutoff by at least 100 ms**, and tested
only independent held-out exchanges already available then. Across the same
252 clock-only checks, all sequential certificates and 50 ms boundaries passed;
the maximum cutoff uncertainty was **4.36912 ms**. Maps used 45 or 55 training
exchanges and five or six held-out exchanges. No future marker or held-out
exchange trained a map; the original slope/tolerance/every-vertex criteria stayed
unchanged. No BWE effect, candidate score or quality variable informed this fix.

Keep the failed registration, coordinator stdout/stderr/launch metadata,
`clock_guard_closure.json` and `sequential_clock_diagnostic.json` in the external
`native-history-state-m6` root. Preserve all prior files. A separately named
**M6R** registration may use these already available training exchanges under the
same numerical limits. M6 itself is closed; no retry or relaxed map is applied
to it. Candidate selection and its untouched native validation still have not
begun. The complete technical closure will accompany the next new verified
private evidence snapshot; no local evidence is deleted in the meantime.
