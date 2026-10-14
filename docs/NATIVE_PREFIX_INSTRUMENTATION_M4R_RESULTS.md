# M4R: prospective instrumentation qualification passed

Registration **`09d0b9553c754cf289a15c64c160001d9426800b`** preceded all captures.
All **32/32 original sessions qualified**, with zero failures, replacements or
added attempts. Four feasibility captures passed before the untouched 28-session
qualification stage began. Every content/prefix condition completed four
immediate-start and four 750 ms inactive-delay cases.

| Content | Prefix | Immediate qualified | Delayed qualified |
| --- | --- | ---: | ---: |
| Kampar | Ascending | 4/4 | 4/4 |
| Kampar | Descending | 4/4 | 4/4 |
| Volga | Ascending | 4/4 | 4/4 |
| Volga | Descending | 4/4 | 4/4 |

M4 remains a separate failed feasibility study at `472ed01`; its two successful
captures do not enter these counts. M3 remains unestimable, with all its failed
initialization/clock/interruption decisions preserved. No prefix-effect estimate,
later BWE distribution comparison, predictor, redesigned controller state or
action/QoE analysis was produced by M4R.

## Actual startup observability and strict readiness

The revised coordinator waited while encoding stayed inactive for the original
nominated/succeeded loopback TURN/TCP selected-pair predicate. It recorded every
probe and used no reconnect or retry. The wait was **2.4–31.9 ms**, median
**3.95 ms**, within its 2,000 ms deadline. This resolves the observed M4 race
between `connectionState=connected` and completed native selected-pair stats
in these fresh runs without accepting an `in-progress` pair.

All 32 sessions recorded missing/available native fields continuously from
before SDP through at least 1,000 ms after measurement start. Polling was
requested every 25 ms; maximum observed poll-response gaps were **27.4–42.9 ms**,
below 250 ms. Native stats timestamps advanced at their own cadence: per-run
median positive steps were approximately **51.6–74.4 ms**. Repeated native
timestamps and missing values were retained; polling frequency is not assumed
to equal native estimator update frequency or reveal latent internal GCC state.

Every pre-activation check confirmed inactive encoding, 4 Mbps ceiling and no
encoded media/payload. After activation, observed initialization latency was
**0.1–5.6 ms**, median **0.9 ms**, within 100 ms. Actual native initialization,
measurement-start and first standard sender measurements all read back exactly
**1,200,000 bps**; SDP start parameters independently read back 1,200 kbps.
The selected pair stayed the same. No requested target was substituted for a
missing native value, and no wrong positive estimate was waited out.

The 0/750 ms challenge occurs before RTP measurement while encoding is inactive.
It does not extend the original BWE conditioning/admission window. The new
common acquisition history differs prospectively from M3's live-media setup;
the captures are not pooled as exchangeable startup replicates.

## Independent clock coverage from the beginning

All 32 full-session certificates covered **7/7 independent held-out exchanges**
using 64 fixed training exchanges. All beginning certificates covered **4/4**
using only the 35 training exchanges available through the first-phase bracket.
The original phase/midpoint holdouts and the three new startup holdouts were
never fitted. The slope bound [0.98,1.02], every-feasible-vertex coverage rule,
1 ms timestamp tolerance and 50 ms width limit were unchanged.

| Maximum interval width | Minimum (ms) | Median (ms) | Maximum (ms) |
| --- | ---: | ---: | ---: |
| Beginning certificate | 1.3161 | 1.6816 | 2.2804 |
| Full-session certificate | 1.0236 | 1.1980 | 1.4676 |

The original eight-training/four-holdout map was retained as a diagnostic on
these new sessions; it passed **30/32**. The prospectively augmented mapping
passed all 32 under the same numerical criteria by adding independent training
information. This is not retrospective requalification of any M3/M4 session,
nor a causal attribution of reliability gains to one component of the acquisition
package.

Authenticated relay-only TURN/TCP, unchanged managed Chromium policy, native
media progress, actual cap/jitter readbacks, all 36 exact rate ticks, ordinary
18-second support and all four registered window-eligibility checks passed.
Every terminal drain qualified under the unchanged 2-second, empty-queue,
served/forwarded, zero-error and byte-conservation requirements.

## Scope and decision

This finite technical screen qualifies the new instrument on every registered
content/prefix/delay condition. It does not guarantee that all future sessions
will succeed: zero failures in 32 gives an approximate one-sided 95% binomial
upper failure bound of **8.94%** under independent, identical-attempt assumptions.
Serial captures on reused sources do not establish broad network reliability.
Every actual-run gate remains mandatory in the fresh causal validation.

The next authorized step is a **new untouched prefix-memory panel**, registered
after this qualification, using the qualified M4R instrument and common 0 ms
setup delay. Freeze new allocation, protocols and analysis before its first
capture. Test history and convergence only; fit no predictors or controllers.
M4R supplies no history-effect result, native common-support qualification,
conditional action value or independent content/network evidence.

## Preservation

All session seals were verified before instrumentation decoding. The two private
namespaces were freshly downloaded and checked at object and member level:

- `native-prefix-instrumentation-m4r-feasibility-20261014-01`, revision
  **`688882694783f886c248d12a55e37a4dbb6d99d6`**, **217 files**.
- `native-prefix-instrumentation-m4r-qualification-20261014-01`, revision
  **`ea46a8cf143fdb78c2f597050ec85619332dd96a`**, **1,418 files**.

Receipts are in `docs/storage-receipts/`. They bind the full scientific
registration, protocols, capture indexes and gate hashes. Raw evidence,
incremental streams, complete registration, overall qualification, source copies
and coordinator logs remain external and archived. Zero evidence was pruned.
The original licensed media remain external. Every tracked file at `472ed01`,
including M3 and the failed M4 study, remains unchanged.

The complete overall gate is `reports/native-prefix-instrumentation-m4r-overall.json`.
Instrumentation summaries and the standalone clock/readiness figure are
`reports/native-prefix-instrumentation-m4r-reporting.json` and
`reports/native-prefix-instrumentation-m4r-qualification.png`.
