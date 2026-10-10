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

## 2026-10-09 23:16 EDT: stage-one capture complete

The capture ended normally after 6 h 22 min and sealed its root. Its own summary, which holds
no outcome:

| | |
|---|---:|
| Sources | 12 |
| Native peers | 480 |
| Assigned cohorts | 2,880 |
| Failures | none (`failure.json` absent) |
| Capture root | `results/native-actuator-qualification-n1-stage-one`, 8.3 GB |

- Chrome stayed at 154.0.8037.98 on disk at every check during the run.
- Nothing else was run on the machine by this study during the capture apart from the
  progress checks, the mock dry run (a few seconds) and the exporter's unit tests.
- After the capture and before `status`: the full test suite passes (1,205 passed, 107
  skipped), and the paper compiles with mock evidence in a scratch copy. That check found one
  LaTeX error in a table caption of the Study 13 section, which was corrected; no wording
  changed.

## 2026-10-09 23:28 EDT: `status`, outcome-free

```sh
uv run --frozen media-actuator-qualification status \
    --protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --capture results/native-actuator-qualification-n1-stage-one
```

The command replays the raw audit of every peer (12 minutes) and reports no outcome by arm.

| | Value | Gate |
|---|---:|---:|
| Captured sources | 12 | |
| Sources not evaluable | 0 | at most 4 |
| Assigned cohorts | 2,880 of 2,880 planned | |
| Complete cohorts | 100.0% | at least 95% |
| Aliased or clipped | 0.07% (2 cohorts) | at most 10% |
| Completeness gap between arms | 0.0 points | at most 5 |
| Arm shares against one third each | p = 0.956 | at least 0.001 |
| Capture support | passed | |
| Interim can run | yes | |

The record is `results/n1-status.json`.
