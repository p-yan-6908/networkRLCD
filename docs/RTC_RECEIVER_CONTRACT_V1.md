# Receiver feature contract V1 — reject a misleading bridge, not certify one

## Next blocker and actual outcome

The [published-model replay](PUBLISHED_RTC_PEERS_V1.md) established authentic ONNX
inference, not a compatible receiver. This iteration removes its **shape-only
semantic-validation blind spot** through an opt-in, spec-checked inference entrypoint.
It does **not** implement or certify the original packet-to-feature extractor.

- All **2,074 released public observations / 20,603 active monitor cells** pass the
  documented aggregate checks in original float64 and model float32 precision.
- **Four concrete port-error witnesses** fail: milliseconds labelled bps, a
  nonconditional lost-packet formula, fixed corpus media priors, and a normalized
  rather than raw delay-ratio numerator.
- **512 actual spec-checked ONNX predictions**, 256 per original model, remain exactly
  equal to the preserved original predictions. Invalid units are rejected **before
  the actual model call**, without changing hidden/cell state.
- Actual full-trace oracle-label poisoning does not change audited observations.
  Native 64-input history is rejected, not padded or repurposed.
- **52 new portable unit cases** pass; the 48 adjacent published-peer cases pass.
  Existing native/peer code, CLI, dependency lock, fitting roles and outcomes are not
  edited. All **21 prior final-receipt bindings** remain byte-identical.

No new closed-loop, causal extraction, calibrated risk, native controller quality or
SOTA result is claimed. Monitor cells overlap and are **not** 20,603 independent
statistical samples. The public trace is an interoperability/algebra probe, not a
new holdout or a basis for adaptation/model selection.

## Original contract and source inspection

Primary sources:

- [Microsoft challenge data specification](https://www.microsoft.com/en-us/research/academic-program/bandwidth-estimation-challenge/data/)
- [Original MMSys 2024 challenge paper](https://fyy.cs.illinois.edu/files/bwe-challenge-mmsys24.pdf)
- [Original AlphaRTC](https://github.com/OpenNetLab/AlphaRTC), inspected commit
  `d545f81f039ebe3f77ce97c7e72f97e5ab8abe29`
- [Later LLM4Band integration code](https://github.com/WzjCoder/LLM4Band), inspected commit
  `9699441fec56606679809eb5989cd3df3320ad76`

The challenge specifies **15 feature groups × (five 60-ms + five 600-ms intervals)**:
rate (bps), received packet count, received bytes, queuing delay, delay minus 200 ms,
minimum seen delay, mean/interval-minimum delay ratio, mean-minus-interval-minimum
delay, interarrival time, jitter, loss ratio, conditional mean lost packets, and
video/audio/probing packet proportions. For zero-based group `g`, short indices are
`10g..10g+4`, long indices `10g+5..10g+9`.

This layout must not be replaced by RLCD's 16×4 sender history. Ground-truth capacity
and quality/loss labels are explicitly forbidden as model inputs by the challenge.
The original public sample contains those separate fields; this audit reads only
`observations` for feature checks.

The original AlphaRTC README provides per-packet `send_time_ms`, `arrival_time_ms`,
integer RTP payload type, sequence number, SSRC, header/payload/padding lengths, and
scalar bps feedback. Its inspected ONNXInfer header exposes packet ingress and BWE
estimation, not the full extraction implementation; its tree includes compiled
Linux/Windows libraries. Neither this inspection nor the original aggregate-only
sample supplies an authoritative paired packet/150-feature fixture. Limited source
inspection is not proof no such implementation/fixture exists elsewhere.

### Why the tempting later port was not adopted

The later LLM4Band online wrapper is **not** the original Schaferct or Microsoft
extractor. Its inspected `Application/LLM4Band/estimator/estimator.py`:

- uses 60/600 **millisecond** durations but computes `bytes * 8 / duration`, labelled
  bps, omitting the factor 1,000;
- computes `(1 - loss_rate) * received_count` as average lost packets, even when loss
  is zero, unlike the published conditional definition;
- overwrites the final 30 media proportions with a fixed `media_proportion` literal
  (line 222 in the pinned source), rather than observed packet proportions;
- uses delay-minus-200 in the delay-ratio numerator instead of raw mean delay;
- resets the purported minimum-seen delay locally per interval, uses integer payload
  types but compares them to strings, and advances only one interval on a packet gap.

These are source/contract observations, **not** a reproduction or repudiation of
that paper's full evaluation. No downloaded Python, model-training code, pickle or
foreign SDK was executed. AST parsing/literal extraction was used only as data;
negative witnesses modify a copy of the original first observation using the reviewed
formula/literal. They are not claimed original raw-packet fixtures.

## Shipped public API and enforced inference boundary

`src/media_rl/rtc_receiver_contract.py`:

- `receiver_feature_schema()` describes original feature groups, index ranges, units,
  declared tolerances and missing evidence.
- `check_receiver_observation()` returns deterministic documented contradictions.
- `validate_receiver_observation()` raises on a contradiction.
- `audit_receiver_trace()` checks a bounded prefix, both raw/model precision and source
  identities without executing a policy; its output always withholds original readiness.
- `python -m media_rl.rtc_receiver_contract schema` / `audit` are standalone commands.

Known checks cover count/byte integer/nonnegative properties, rate/byte units, zero-
packet byte accounting, delay/queue/minimum and ratio identities, nonnegative duration
statistics, fraction ranges, conditional-loss consistency and count-based media
proportions. Float32 rounding allowances are declared in the schema. No input is
repaired, clamped, renormalized or padded. Invalid shapes/types, nonfinite or non-model-
representable values fail; existing output files are never overwritten.

`src/media_rl/rtc_spec_checked_peer.py` adds **`SpecCheckedRtcPeer`**, an opt-in subclass
of the unchanged `PublishedRtcPeer`. Its `act()` snapshots the caller input once,
validates raw and float32 values, and only then forwards exactly that float32 input
to the original hash-verified CPU model/channel/state implementation. It records
contract-plus-act latency separately from inherited act latency. Original extractor
readiness, causality, closed-loop execution and calibrated auxiliary risk are explicitly
withheld. This is **guarded inference**, not encoder/transport actuation.

The old `PublishedRtcPeer` behavior and old replay artifacts are preserved. Future
peer integration should use the spec-checked entrypoint, but even it cannot detect
an oracle masquerading as a mathematically consistent observation. Original clock,
packet availability and extractor/actuator evidence must be verified independently.

## Executed evidence and safe reproduction

- Frozen contract protocol: `configs/rtc_receiver_contract_v1.json`.
- Actual full-prefix audit: `results/rtc-receiver-contract-v1/audit.json`.
- Source pins, four failures, poisoning and prior preservation:
  `results/jobs/rtc-receiver-contract-evidence-v1.json`.
- Actual guarded predictions/state rejection:
  `results/jobs/rtc-receiver-checked-inference-proof-v1.json` and the two
  `*-checked-inference.json` files in `results/rtc-receiver-contract-v1/`.
- Outside-checkout wheel proof:
  `results/jobs/rtc-receiver-contract-package-proof-v1.json`.

```sh
# Requires only ordinary core dependencies for schema/audit; no ONNX Runtime.
uv run --locked python -m media_rl.rtc_receiver_contract schema
uv run --locked python -m media_rl.rtc_receiver_contract audit \
  --trace .tools/rtc_peer_research_v2/artifacts/02530.json --limit 2074 \
  --out results/rtc-receiver-contract-reproduction/audit.json
```

For guarded model inference, install/use the existing optional `rtc-peers` extra and
construct `SpecCheckedRtcPeer(peer_id, checkpoint_path)`. It accepts only the original
150 numeric receiver fields, never native sender features. Completed canonical
probe scripts/outputs refuse overwrite; use fresh destinations for reproduction.

## Completion audit: what remains uncovered

These checks prove documented aggregate consistency and enforcement before inference,
not all requirements of the active SOTA objective:

1. **Original extractor equivalence:** still missing authoritative matched raw packets
   and observations, exact interval ordering/boundaries/update timing, empty defaults,
   clock normalization/rollover/reset, duplicate/RTX/reordering/loss and negotiated
   packet-type/byte accounting. Aggregate vectors cannot reconstruct these uniquely.
2. **Causal live availability:** actual received packet callbacks/feedback timing and
   available-before-decision observation construction are not verified. Zero minimum-
   delay increases in this sample are a diagnostic, not a clock/reset certificate.
3. **Faithful actuation:** applying a predicted cap above independent Chrome GCC is
   not automatically the original receiver BWE/encoder implementation.
4. **RLCD efficacy:** unstable deadlines, selected confidence calibration, generalization,
   representative grouped/role-disjoint workloads and decisive risk/quality evidence
   against strongest genuine competitors remain open.

Do not invent a faithful bridge from the flawed later port. The next input for the
original-extractor path is an authoritative implementation or paired packet/feature
fixtures with clock, interval and packet-classification semantics. No privileged
installation, paid job, external upload, weaker deadline/risk gate or refitting of
prior development/validation labels is authorized or performed. Goal completion is
**not achieved**.
