# V11D support diagnosis (development evidence only)

V11D remains a negative, under-covered directional replication. The registered
minimum of two holds in every state/action group and 13 complete crossed cells
is unchanged. Its observed PSNR interaction is not a population estimate. This
diagnosis examines no PSNR, delivery, drop, wire-cost, or other action outcomes.

`tools/diagnose_native_v11d_support.py` verifies the protocol, capture index and
all 2,624 sealed session files, then projects only action assignments, the
pre-action BWE feature, cap readback, and sender timing. It does not call a
session outcome loader. Its machine-readable result is
`reports/native-v11d-support-diagnosis.json`.

## Why coverage failed

All 384 registered holds were assigned correctly; nine of the 16 cells meet
the original count gate. Of the seven failures, four have fewer than four
high-BWE visits, making two observations per action impossible even with
perfect allocation. Three have four or five high-BWE visits, but an arm has
only one observation. These are distinct support and allocation problems.

| Family | Low-BWE holds | High-BWE holds | Complete cells |
| --- | ---: | ---: | ---: |
| Nordic operator 1, 5G-NSA/B20 | 73 | 23 | 3/4 |
| Nordic operator 1, LTE/B20 | 84 | 12 | 0/4 |
| Nordic operator 3, LTE/B3 | 79 | 17 | 2/4 |
| Rome operator 2, LTE | 68 | 28 | 4/4 |

All 64 epoch-zero assignments see exactly 300,000 bps, the browser's startup
BWE value. They occur 2.9–11.8 ms after measurement starts. They therefore
provide low-bin counts before any rate-conditioned steady-state support has
been demonstrated. High-state counts at epochs 1–5 are 36, 9, 15, 12, and 8
out of 64; the first post-startup observation is not representative of later
state support.

The D3 screen-content group has eight high-BWE visits in total across 96 holds;
its three Nordic cells have 1, 1, and 0 high visits. The helicopter group has
only two high visits in Nordic operator-1 LTE. In contrast, the three
allocation-limited cells have high-arm counts 1/3, 1/4, and 3/1.

The source-only trace screen required rate samples on both sides of 0.5 Mbps
inside every six-second block. An application-throughput sample is not a
browser available-outgoing-bitrate observation. BWE adapts over time and can
depend on content and preceding randomized caps. Short crossings and six
fixed hold boundaries therefore cannot ensure state support. The content
association identifies a design weakness; it does not identify a causal
content effect or explain any outcome difference.

## Prospective response

The next validation must qualify the actual pre-action BWE after a common
conditioning period, before drawing a treatment. Pairing both randomized
actions at the same prospectively qualified content/network/state block can
remove arm-count luck. Fresh peer connections and identical pre-treatment
conditioning prevent a prior experimental action from creating the next
state. A fixed support deadline, all-cell count gate, and outcome-blind stop
rule must preserve under-support as a failed validation rather than silently
replace sessions, change thresholds, or select favorable outcomes.

Rate scaling, clamping, repeated looped traces, and imposed synthetic states
would answer a different question. New measured sources must be selected from
their native rate histories, and campaigns, source runs, windows and content
groups remain explicitly nested. V11D is development evidence only.
