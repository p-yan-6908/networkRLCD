# Native Phase N1: capture log

A procedural record of the N1 capture. It holds no outcome: no rate, no contrast, no variance
and nothing labelled by arm. Outcomes are read only through the registered `interim` and
`final` routines of the [preregistration](NATIVE_PHASE_N1_ACTUATOR_QUALIFICATION.md).

## 2026-10-09: before the first capture

- Go-ahead and importer's assertion: recorded in the
  [acquisition log](NATIVE_PHASE_N1_ACQUISITION_LOG.md).
- Sealed plan: `results/native-actuator-qualification-n1-plan/protocol.json`, 21 sources,
  stage one is planned positions 0 to 12, `outcomes_observed` false.
- Machine: Apple M1, 8 cores, 8 GB, macOS 27.0 (26A428), on mains power.
- Browser and runtime: Google Chrome 154.0.8037.98 (`--headless=new`, a fresh temporary
  profile per peer), Node v26.8.2.
- The collector runs one peer at a time. Nothing else heavy is run on the machine during the
  capture. The owner's own desktop session, including a Chrome window, stays open; that
  background load is not controlled.

### Tooling pre-flight, not on an N1 source

Before the capture, the unchanged collector was run once on the earlier smoke runtime
(`results/native-actuator-identification-smoke-v3/discovery-f0.json`, the Sintel film, which
is not an N1 source) into a scratch directory outside the repository. It exited cleanly in
50 s against Chrome 154, and the unchanged raw audit replayed it: six cohorts, six complete.
No rate was read. This checks that the collector still runs against today's browser; it is
not N1 data and does not enter any analysis.

### Freezes

`media-actuator-qualification verify-freeze`: 4 files, `ae567d09...`, verified.
`media-panel-assets verify-freeze`: 31 files, `68f770b4...`, verified.

## 2026-10-09 16:54 EDT: stage-one capture started

```sh
caffeinate -dims uv run --frozen media-actuator-qualification capture \
    --protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --start 0 --stop 12 --out results/native-actuator-qualification-n1-stage-one
```

This is the registered command. `caffeinate` only keeps the machine awake. Standard output
and error go to `results/native-actuator-qualification-n1-stage-one.log`.

- The first two peers were collected, audited and sealed within 100 s, so 480 peers should
  take about six and a half hours.
- Progress is followed by counting sealed peer directories and watching for `failure.json`.
  No cohort file, summary or raw event file is opened.
- The capture loop is all-or-nothing: an exception at any peer, including a collector
  validity check or the 90 s limit, writes `failure.json` and ends the run, and a rerun needs
  a fresh path. A failed prefix is kept and is never analysed.

### Reporting fixed while the capture ran

Written and committed during the stage-one capture, before `status`, the interim or any
outcome:

- `src/media_rl/native_actuator_qualification_report.py` (outside the N1 freeze): reads the
  registered final report, the public interim record, the sealed plan and the capture
  manifests, and writes the paper's macros and tables. It refuses mock rows. The sentences
  that state the outcome, its registered consequence, the heterogeneity designation, and the
  one-sentence summaries for the abstract and the conclusion exist once per registered
  outcome, and the verdict alone selects among them.
- `paper/native-n1-qualification.tex` (Study 13): design and limits in prose, every result a
  macro or generated table. The paper includes it only when the generated evidence exists.
- `make native-n1-evidence`.

The exporter was exercised on the registered mock dry run only (`dry-run`, synthetic rows).
