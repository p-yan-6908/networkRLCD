# V13 execution: support failed; action study closed

The unchanged registration at `6b8471a` was executed in its frozen order.
All **32/32** original support checks completed and were sealed. There were
no capture failures, replacements, changed inputs, extra attempts or gate
changes. All individual sessions passed native continuous-BWE eligibility,
history timing, common conditioning/readback, TURN/TCP, bidirectional media,
exact measured-rate replay, actual-run clock alignment and terminal cleanup.

The all-panel support gate nevertheless **failed**. Six of sixteen
content/profile contexts exceeded the registered **0.25-octave** difference
between their two fresh census repeats. All four cells passed the separate
profile-range and SD checks, but only **one of four** passed every support
condition. V13 is closed as a support-design failure, with no action-effect
result. Its **64 randomized action sessions remain unrun**.

## Cell and family support

The following BWE ranges describe the four profile census means per cell,
not population support or action effects. Each mean combines the two
registered continuous log2-BWE measurements at the 18-second decision window.

| Content | Measured-rate family | Census range (kbps) | Range (octaves) | SD (octaves) | Repeatable profiles | Complete cell |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Kampar boating | AT&T LTE driving 2016 | 1097–2487 | 1.180 | 0.532 | 2/4 | Fail |
| Kampar boating | Verizon EVDO driving | 322–1109 | 1.785 | 0.828 | 4/4 | Pass |
| Volga lock | AT&T LTE driving 2016 | 1170–2588 | 1.145 | 0.502 | 1/4 | Fail |
| Volga lock | Verizon EVDO driving | 324–998 | 1.622 | 0.708 | 3/4 | Fail |

The LTE family qualified repeatability in **3/8** content/profile contexts;
EVDO qualified **7/8**. Repeatability is a property of this selected recipe
and finite panel. Directions, windows, repeats and crossed content remain
nested in two bundles from **one Mahimahi measurement program**.

The observed four-cell support intersection is empty: the largest lower
endpoint is 1170.398 kbps and the smallest upper endpoint is 998.410 kbps
(a 0.229-octave gap). The separately registered 0.5-octave common-support
criterion therefore also fails. Even a future repeatability repair would
not by itself establish cross-family conditional-value stability here.

## Outcome-free diagnosis

Every session's SHA-256 seal was verified before the diagnostic projected
sender timestamps, BWE feature zero/validity, qualification and native
cap/jitter readback. It reproduced the unchanged `[18000,18300]` ms window,
eleven samples, span ≥900 ms, gaps ≤250 ms and `[240000,3800000]` bps bounds.
There were **zero eligibility-range failures** and no missing contexts.
All decisions retained the 4 Mbps ceiling and zero jitter target; no action
was assigned. The 500 kbps normalization remains a continuous-state unit,
with no binary membership or post hoc threshold.

| Failed context | Repeat BWE geometric means (kbps) | Difference (octaves) | Largest within-history range (octaves) |
| --- | ---: | ---: | ---: |
| Kampar / LTE downlink upper | 2504, 1902 | 0.397 | 0.121 |
| Kampar / LTE uplink lower | 1224, 984 | 0.315 | 0.029 |
| Volga / LTE downlink lower | 2312, 2898 | 0.326 | 0.015 |
| Volga / LTE uplink lower | 1002, 1366 | 0.447 | 0.033 |
| Volga / LTE uplink upper | 1412, 1704 | 0.271 | 0.125 |
| Volga / EVDO uplink upper | 907, 1099 | 0.278 | 0.043 |

The qualifying one-second histories are much smoother than the fresh-session
differences in most failed contexts. Local history smoothness does not ensure
repeatable census conditioning. Gross clock or replay faults did not explain
the failure: all 36 ticks and all four held-out clock markers qualified in
each run, with maximum held-out interval width **3.031 ms** under the original
50 ms limit. All queues drained with the registered conservation checks.

These variables do not distinguish estimator initialization, probing,
content-dependent sending demand, rate history or other session dynamics
as causal mechanisms. No encode/delivery/quality outcome, per-hold relay
cost, alternative source window or alternative decision time was used to
select a repair.

## Scientific decision and next step

No primary or secondary effect was estimated. V13 cannot establish a PSNR
gradient, delivery/QoE benefit, conditional action value or policy advantage.
No controller was fitted, tuned or promoted. V10 remains closed; V3–V12 and
all prior freezes are unchanged and unpooled.

The next experiment is a separately preregistered **M1 support-only reliability
diagnostic**, documented in `NATIVE_BWE_RELIABILITY_M1_PLAN.md`. It reuses
these now-observed content clips under one explicitly synthetic constant
service level, with four fresh sessions per clip. It asks whether the same
18-second native BWE measurement is repeatable even under steady service.
It cannot reopen V13, supply independent confirmation, fix measured-family
overlap or justify learning a controller. New confirmatory sources remain
necessary after the measurement-design problem is resolved.

## Preservation

- Confirmatory protocol SHA-256:
  `cc4c7a7c7275c726e47462b3bef006039fbc681232d5aae8088e961a7be95bc5`.
- Support protocol SHA-256:
  `e8483ae1a80600cbbbc2d584a96b596e3dd9672dcab44fd062fe98d028843dfa`.
- Capture index SHA-256:
  `0d9e3801f4c6cd4f560b878daee0e3317934eaa1886b590988fc4838c5c58d73`.
- Official gate SHA-256:
  `d760e812c861b874aeb252eb06f3af2eeedcf734a687d6efb770ab069d21ed3f`.
- Compact gate, support projection and execution summary:
  `reports/native-v13-support-census-gate.json`,
  `reports/native-v13-support-census-summary.json`,
  `reports/native-v13-execution-result.json`.
- Raw evidence is retained outside the repository and in the private dataset
  `p-yan/networkrlcd-results-archive`, namespace
  `native-continuous-validation-v13-support-20261014-01`, pinned revision
  `a1747a078970311eadff407059187db0aad1fa55`.
- `docs/storage-receipts/native-continuous-validation-v13-support-20261014-01.json`
  records fresh-download verification of every archive object and **1,381
  files**. Session integrity verification covered 1,312 sealed session files;
  the archive additionally preserves panels, protocol, index, gate and seals.
  No local evidence or licensed original was deleted.
