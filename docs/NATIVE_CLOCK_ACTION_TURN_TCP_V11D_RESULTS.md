# Native clock/action V11D results

## Capture and qualification

The frozen V11D panel captured all 64 planned sessions; all 64 sealed and no
session failed. The technical smoke passed relay-only TURN/TCP, the actual-run
clock marker check, rate replay, assignment/readback, and terminal queue drain.
Its pre-cleanup queue held `54.995` wire bytes and was empty after cleanup.

The main all-session gate passed transport, clocks, all 18 measured-rate ticks,
assignment/readback, and cleanup in every session. Each session covered all four
held-out clock markers. Across the 64 runs, feasible affine slopes ranged from
`0.999796` to `1.000249`; the widest held-out clock interval was `3.474 ms`
against the registered `50 ms` maximum. Per-hold relay joins were computed only
after this gate passed.

The registered protocol SHA-256 is
`db3d5c8bd440b04c4e28c2d6c196ce946b87dd3ba9d060ef0a9a07bf46db1e50`; the
capture index SHA-256 is
`00b17973205196231bdeaf19fdd2e43519112d7f08cbf0c4779e5c797fdac1b5`; the
all-session gate SHA-256 is
`b85af79677da69d874e22d47faef92a9be35a3136a82468eb039c84754134381`.

## Conditional action effects

V9's timely-PSNR interaction was `+0.508 dB` across its generated-scene clusters.
V11D does **not** meet its registered replication rule. Only 9 of 16 crossed
cells met the four state/action hold-count minimum,
below the required 13. Of those nine, only seven had timely-PSNR observations
in every state/action bucket. No missing metric was imputed.

Within those seven estimable cells, the equal-weight PSNR effect of bitrate
ratio `1.05` versus `0.65` was `+0.761 dB` below 500 kbps BWE and `+0.152 dB`
at or above 500 kbps. The registered high-minus-low interaction was therefore
`−0.609 dB`, opposite V9's `+0.508 dB` direction. The NordicDat campaign mean
was `−0.419 dB` across four estimable cells; the Rome campaign mean was
`−0.862 dB` across three. The rule's direction also failed its source checks:
none of the three estimable content means and neither campaign mean was
positive; one of the three estimable family means was positive. Vižanice had no
estimable content mean, and NordicDat operator-1 LTE had no estimable family
mean. This is not a population-level estimate, and seven primary cells do not
satisfy the registered coverage requirement.

| Measure (`1.05 − 0.65`) | Below 500 kbps BWE | At/above 500 kbps BWE | High-minus-low interaction | Estimable cells |
| --- | ---: | ---: | ---: | ---: |
| Timely sampled RGB PSNR | +0.761 dB | +0.152 dB | −0.609 dB | 7 |
| On-time fraction | +0.072 | −0.069 | −0.142 | 9 |
| Guaranteed relay wire bytes per hold | +9,578 bytes | +9,263 bytes | −316 bytes | 9 |
| Guaranteed dropped wire bytes per hold | +5.6 bytes | +41.5 bytes | +35.9 bytes | 9 |

The on-time interaction was negative in both campaigns: `−0.184` for NordicDat
(five estimable cells) and `−0.089` for Rome (four). The relay wire-byte
interaction was heterogeneous: `−8,708` bytes for NordicDat and `+10,175` for
Rome. The dropped-byte interaction was zero for NordicDat and `+80.7` for Rome;
the four network families are not independent replicates. These measures are
local queue outcomes under replayed measured rates, not live-network cost or
human QoE.

The evidence does not establish a stable conditional action value over fixed
`0.65`: PSNR effects were positive in both BWE states in the seven observed
cells but were larger in the low-BWE state, while on-time and drop effects were
mixed. V10 remains closed, and no controller was fitted or promoted.

## Analysis failure and recovery

The first run of the frozen summarizer failed while averaging a metric whose
value was undefined in a cell that met the hold-count rule. That attempt and its
exact error are preserved in
[`reports/native-clock-action-turntcp-v11d-analysis-failure.json`](../reports/native-clock-action-turntcp-v11d-analysis-failure.json).
The recovery analysis uses a separately versioned tool,
[`tools/analyze_native_clock_action_v11d.py`](../tools/analyze_native_clock_action_v11d.py),
and leaves the registered capture code, protocol, endpoints, and gates
unchanged. It reports unestimable cells, performs no imputation, and applies the
13-cell threshold to estimable primary PSNR interactions. Its detailed report
is [`reports/native-clock-action-turntcp-v11d-analysis-final.json`](../reports/native-clock-action-turntcp-v11d-analysis-final.json).

V11D remains separate from V3–V10, V11C, archived result shards, and
synthetic-controller evidence. It represents four network-family strata from
two measurement campaigns; trace windows and campaign subsegments are nested.
