# Fallback growth-hold V1 — signals-only preflight

## Mechanism to test

The completed [action-outcome live panel](NATIVE_ACTION_LIVE_V1.md) has large stable-link quality/deadline variation even when every actually selected cap follows continuous 85%-BWE fallback. Failed stable peers encode about 29 fps but have hundreds of identified-late requests and larger native buffering. This is a measured system/control blocker, **not evidence that the neural weights caused it**.

Code inspection shows that canonical `ActionPolicy` uses sender congestion to veto neural selection, but the resulting fallback can still increase its cap with BWE. A separately declared **growth-hold overlay** tests that gap plus already causal presentation-ACK delay. No threshold is searched or fitted from those quality results.

## Fixed rule and boundaries

`native_action_fallback_guard.py: growth_hold_action` and `action_fallback_guard.mjs: growthHoldAction` consume an **already raw-replay-verified canonical decision**:

1. Keep every accepted neural proposal exactly unchanged.
2. During fallback, if the original `sender_congestion` hold is active **or** a **fresh** received presentation ACK has capture-request-to-received delay >= the original **120-ms context cutoff**, return `min(canonical_fallback_cap, actual_acknowledged_own_cap)`.
3. Otherwise keep the canonical cap. Always preserve native zero receiver target and integer [150,000,4,000,000] cap domain. Existing fallback decreases are never blocked; output never exceeds the canonical proposal.

Use only normalized sender and causal ACK features; no receiver pixels, relay capacity, future readback/miss/utility labels, movie timestamp or phase. Freshness uses the original <=500-ms feedback validity flag. No new history, backoff factor, learned weights, risk/support limit, calibration role, BWE budget, dwell or reset recipe changes. Guard metadata is explicit and never grants neural-action credit or safety certification to a modified fallback.

This document records the **immutable-input preflight**, not a new qualified RLCD model or an intervention in the existing 16 completed runs. A [separate versioned live comparison](NATIVE_ACTION_GUARD_V1.md) now imports the primitive in new files and registers only plan/study/audit, never calibrate/promote. Its 24-peer native comparison now completes and raw-replays but fails collapse repeatability and loses descriptively against every reference; rate holding might preserve deadlines or instead harm encoder throughput/quality, and mathematical monotonicity alone cannot decide.

## Evidence and coverage

- **Software:** 15 Python and three Node tests pass, plus lint. They cover exact cutoff, fresh/stale ACK semantics, original sender hold without ACK, unmodified accepted-neural and decreasing-fallback outputs, nonfinite/domain/identity rejection, zero target and input immutability.
- **Signals-only predeclared replay:** `results/jobs/native-action-fallback-growth-hold-preflight-plan.json` fixes the one rule, code hashes, complete ordered input panel and original cutoffs before processing. `native_action_fallback_guard_preflight.py` reads only sealed sender records, not frame/miss/quality labels. The proof checks **2,721 recorded inputs in Python/JS**, from all **16 peers / two physical groups**.
- **Intervention coverage:** on the eight actuating-model peers' **1,358 original actual inputs**, **365 (26.88%)** produce a held-growth intent. Accepted neural-proposal changes and blocked canonical decreases are **both zero**. Conventional-peer rows are explicitly canonical shadows on conventional histories, not actually selected actions.
- **Preservation:** all **618 saved native files** are unchanged; fitting is absent and existing weights/collector bindings are unchanged. **Zero guarded native actions were executed by this preflight.** Following the old actual caps/ACKs means these are off-policy intents, not guarded closed-loop trajectories, causal performance effects or proof of repeatability.
- **Extracted package:** `results/jobs/native-action-fallback-growth-hold-package-proof.json` verifies both exported APIs on four real recorded boundary cases (held growth, unchanged fallback, accepted neural action, canonical decrease), exact declared Python/JS guard bytes, unchanged V2 SHA and three canonical hashes. Wheel SHA `4e9471f988589707316bd9db6e2f8b725d98fb62d1f660e6187c3cb6d12b19a1`.
- **Fresh-source feasibility:** `results/jobs/native-action-fallback-growth-hold-source-inventory.json` scans 46 prior recorded-role inputs. Tears of Steel has **zero** unused declared 20-second slots; Sintel has **17** (540–880 s). This is an inventory, **not a reservation**, new independence or a validation allocation. Recompute before freezing any new plan; do not recycle the failed panel or silently expand into prior-role clips.

## Actual next step / completion audit

The implementation and signals-only mapping are verified, but **the measured repeatability/deadline blocker is not removed**. The [new live integration](NATIVE_ACTION_GUARD_V1.md) completes all 24 guard/unchanged-alias/BWE peers on two unused Sintel segments and fully raw-replays 1,002 unchanged saved files. It verifies 1,007 actual held-growth steps without neural credit, but both mappings fail collapse repeatability and the guard loses to unchanged V2 and both BWE references; it is not adopted. Preserve every earlier collector/checkpoint and failed panel, log canonical proposal and overlay/readback separately, and count modified fallback as **zero learned credit**.

Check all requests, stable/collapse/variable/high-phase quality/delivery, the original 3-utility/15-pp alias spans, 10-ms inference p99, neural risk/support/dwell/BWE guards and genuine use. Even a positive small native pilot would still require selected-policy calibration and larger role/model-disjoint validation/final tests, representative measured paths/devices/content and strongest compatible genuine peers. No fit, deployment qualification, promotion, native guard gain or SOTA claim is made. **Goal remains unachieved.**
