# Native Phase N1: result

**Qualified.** On 2026-10-09 the registered final analysis of Native Phase N1 returned
`qualified`: on the native browser stack both adjacent contrasts of encoded rate over frozen
BWE have lower bounds above the registered margin of 0.03. Capture support passed, the blinded
rule prescribed no extension, and the heterogeneity designation is not attached.

This is a result about the actuator and nothing else. No learned controller acted, no quality
was measured and no controller is promoted. The network was a userspace relay on one machine,
not a real network path.

- Registration, frozen and unchanged: [preregistration](NATIVE_PHASE_N1_ACTUATOR_QUALIFICATION.md)
- What was run, step by step: [capture log](NATIVE_PHASE_N1_CAPTURE_LOG.md)
- Sources and rights: [acquisition log](NATIVE_PHASE_N1_ACQUISITION_LOG.md)
- Paper: Study 13 (`paper/native-n1-qualification.tex`, evidence in `paper/generated-native-n1/`)

## What was captured

| | |
|---|---:|
| Sources (4 / 4 / 4 by complexity tercile) | 12 |
| Fresh native peers | 480 |
| Assigned cohorts (0.65 / 0.85 / 1.05) | 2,880 (953 / 966 / 961) |
| Browser | Chrome 154.0.8037.98, one build for every peer |
| Machine | Apple M1, 8 cores, 8 GB, macOS 27.0 |
| Capture | 2026-10-09 16:54 to 23:16 EDT, one run, no failure |

Capture support, which looks at no outcome by arm:

| Gate | Value | Threshold |
|---|---:|---:|
| Complete cohorts | 100.0% | at least 95% |
| Aliased or clipped | 0.07% (2 cohorts) | at most 10% |
| Completeness gap between arms | 0.0 points | at most 5 |
| Arm shares against one third each | p = 0.956 | at least 0.001 |
| Sources passed over as not evaluable | 0 | at most 4 |

## The interim

The blinded interim released one number, a prescribed total of 12 sources. The sealed record,
opened by the final analysis, shows why: the larger first-stage standard deviation of a
per-source contrast is 0.041, below the 0.0607 at which the rule starts adding sources. It was
not precision futility. No reserve source was captured.

## Confirmatory result

Endpoint: actual encoded video payload rate before packetisation, divided by the frozen BWE.
Twelve sources, terciles and regimes weighted equally, Stein two-stage standard error with 11
degrees of freedom.

| Contrast of assigned ratios | Mean | Lower bound (one-sided 97.5%) | Upper bound (one-sided 98.75%) | p against 0.03 | Share of the 0.20 step |
|---|---:|---:|---:|---:|---:|
| 0.85 - 0.65 | +0.144 | +0.128 | +0.162 | 3 x 10^-9 | 72% |
| 1.05 - 0.85 | +0.094 | +0.067 | +0.125 | 0.0001 | 47% |

Both lower bounds exceed 0.03, so the outcome is **qualified**.

## Secondary analyses

Fixed in the registration. None of them changes the outcome.

**RTP send rate.** +0.145 (lower bound +0.131) and +0.092 (lower bound +0.066). The same rule
would read it as qualified.

**Regime map**, Holm-corrected over the eight tests:

| Regime | Contrast | Mean | Lower bound | Upper bound | Holm p |
|---|---|---:|---:|---:|---:|
| underutilized | 0.85 - 0.65 | +0.174 | +0.144 | +0.210 | <0.001 |
| | 1.05 - 0.85 | +0.145 | +0.112 | +0.184 | <0.001 |
| near-capacity | 0.85 - 0.65 | +0.152 | +0.126 | +0.182 | <0.001 |
| | 1.05 - 0.85 | +0.059 | +0.033 | +0.090 | 0.031 |
| queue-building | 0.85 - 0.65 | +0.153 | +0.128 | +0.183 | <0.001 |
| | 1.05 - 0.85 | +0.044 | +0.013 | +0.080 | 0.169 |
| collapse-recovery | 0.85 - 0.65 | +0.095 | +0.053 | +0.144 | 0.011 |
| | 1.05 - 0.85 | +0.126 | +0.056 | +0.208 | 0.017 |

At a family-wise one-sided 0.025, six of the eight are established above the margin. The two
that are not are the upper contrast under near-capacity and under queue-building.

**Complexity terciles**, descriptive 95% intervals, four sources each:

| Tercile | 0.85 - 0.65 | 1.05 - 0.85 |
|---|---|---|
| low | +0.131 [+0.103, +0.160] | +0.073 [+0.027, +0.118] |
| medium | +0.146 [+0.118, +0.175] | +0.089 [+0.044, +0.135] |
| high | +0.153 [+0.124, +0.182] | +0.119 [+0.073, +0.164] |

The test that the tercile means are equal gives p = 0.49 and p = 0.31, so the designation
"qualified on average, heterogeneous by complexity" is not attached. With four sources per
tercile that is not evidence that the actuator behaves alike across complexity.

**Other registered secondaries.**

- Prevalence: 11 of 12 sources have both of their own contrasts above 0.03; the exact
  one-sided 97.5% lower bound on that share is 62%.
- Standard deviation across sources of a per-source contrast: 0.025 [0.018, 0.042] and 0.041
  [0.029, 0.070]. The registered power analysis used 0.027 under the powered panel's noise
  model and 0.056 under smoke-level noise.
- Source-clustered first-stage F and partial R-squared: 187.9 and 0.337 for the encoded rate,
  201.1 and 0.344 for the send rate. These are readiness indicators for a later quality
  stage.
- Plateau observed in 77%, 80% and 81% of holds at the three ratios.

## What follows under the registration

The actuator argument for acquiring the 96 source units of Phase N2 holds. N2 runs unchanged,
with its own gates on its own units. Nothing has been acquired for N2, and acquisition needs
the owner's decision on budget and rights review. N1's variance estimates may inform a
separately registered review of N2's sample size; that review is not enabled by N1.

## Reading the result (written after the outcome, descriptive)

- **The encoder follows a request in part.** It realises 72% of the lower step and 47% of the
  upper one. The simulator behind the typed-control studies has the encoder take up any
  requested rate exactly, 1.5 s after an increase and 0.1 s after a decrease.
- **The upper step is weak on a constrained link.** Under near-capacity and queue-building,
  the step from 0.85 to 1.05 is not established above the margin after correction.
- **Both fit the actuator.** The request is a cap on the encoder's maximum bitrate. A cap
  cannot raise the encoder above the rate the browser's own congestion controller allots, so
  a requested ratio above one is not expected to be realised in full. N1 does not separate
  that ceiling from encoder undershoot.
- **Consequence for the synthetic track.** The typed controllers' option sets include 1.05,
  and their train-selected base ratio is 1.05. In the simulator the sender follows it. This
  cap offers no such mechanism, so the simulator's gains do not transfer to this actuator as
  they stand.

## Exploratory description

A separate, unregistered description of the same rows is in
[NATIVE_PHASE_N1_EXPLORATORY.md](NATIVE_PHASE_N1_EXPLORATORY.md). In short: the encoder sits
at 0.59, 0.73 and 0.83 of the estimate at the three ratios; a cap below the estimate holds the
estimate's growth back when the link has room; and in a pilot look at the on-time PSNR proxy no
schedule shows a lower ratio to be better. None of it changes the outcome above.

## Limits

- One machine, one browser build, VP8 at 640x360, a userspace relay with scripted capacity.
  It is not a kernel emulator and not an Internet path.
- Twelve Commons videos from a seeded queue and a rights screen, not a representative corpus.
- A 3 s hold measured from 1.8 to 2.6 s after the request. Nothing is shown about shorter or
  longer holds.
- The blinding was procedural: the repository owner is custodian and study owner, and an AI
  agent with file access ran every step on the owner's machine.
- The rights review is an AI reviewer's reading of archived evidence, adopted by the owner.
- The owner's desktop session stayed open during the capture; that load was not controlled.

## How it was run, and what departs from a bare reading of the registration

The analysis is the registered one, unchanged; both freezes verify. Procedural points:

- The capture command was wrapped in `caffeinate` to keep the machine awake.
- Before the capture the unchanged collector was run once on the earlier smoke film, which is
  not an N1 source, to check it against the current browser.
- The evidence exporter and the paper section were committed during the capture, before any
  outcome, with one outcome sentence per registered verdict. After the outcome three
  presentation changes were made and are listed in the capture log: Commons page numbers and
  elision of non-Latin title text in the source table, a count of the regime tests that clear
  the margin, and the descriptive paragraph above.
- The owner's go-ahead named stage one, `status` and the interim. The interim prescribed no
  extension, so the registered sample was complete, and the agent ran the registered final
  analysis without asking again.

## Records

| Record | Path | SHA-256 |
|---|---|---|
| Final report | `results/native-actuator-qualification-n1-final.json` | `f5f4f5bc...` |
| Public interim | `results/n1-interim-public.json` | `bd7055c9...` |
| Sealed interim (copied after the final) | `results/n1-interim-sealed.json` | `8503928c...` |
| Outcome-free status | `results/n1-status.json` | |
| Audited cohort rows, gzip | `results/native-actuator-qualification-n1-stage-one-cohorts.json.gz` | `037aaa7e...` uncompressed |
| Stage-one capture manifest | `results/native-actuator-qualification-n1-stage-one/manifest.json` (local) | `910a5d47...` |

The raw capture is 8.3 GB under `results/native-actuator-qualification-n1-stage-one/` and is
not in git. The final analysis replays it, so reproducing `final` needs that directory:

```sh
uv run --frozen media-actuator-qualification verify-freeze
uv run --frozen media-actuator-qualification final \
    --protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --capture results/native-actuator-qualification-n1-stage-one \
    --public results/n1-interim-public.json --sealed results/n1-interim-sealed.json \
    --out results/my-n1-final.json
make native-n1-evidence && make paper-pdf
```
