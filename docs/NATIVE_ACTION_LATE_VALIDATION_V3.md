# Frozen late forecasts / prospective role-disjoint validation V3

## Actual result: necessary training gain did not replicate

The [V2 temporal repair](NATIVE_ACTION_LATE_CREDIT_V2.md) passed the fixed 1%
conditional-versus-matched-blind *training-development* criterion on its exact
old physical folds (+1.4258% / +6.8950%). This new prospective check freezes a
complete all-training **forecast** ensemble before collecting independent
reserved-role labels. **It fails replication; no model is promoted.**

**24 conventional native Chrome/VP8 peers, 80 factual late cohorts / 971 requests,
four genuinely new physical contexts** complete. No validation-time fit, neural
native action, selected calibration, reward-window change or threshold relaxation
occurred. These auxiliary forecasts are not a trained deployable actor, and their
late-window miss fractions are not safety confidence for early/transient/all
requests.

| Actual prospective corpus | Conditional utility MSE | Matched blind MSE | Action-information skill | Action-prior utility / risk skill |
|---|---:|---:|---:|---:|
| Pooled, 80 cohorts / 971 requests | 0.0072622373 | 0.0073014165 | **+0.5366%: fails 1%** | +56.7295% / +57.3616% |
| Held-out Sintel, 40 / 485 | 0.0039856968 | 0.0038983529 | **−2.2405%: fails** | +78.8509% / +87.1775% |
| Entirely unseen Big Buck Bunny, 40 / 486 | 0.0105320360 | 0.0106974778 | **+1.5466%** | +28.4763% / +21.0479% |

The exact **256 four-physical-group resamples** give an empirical percentile
interval of **[−6.7420%, +2.5261%]**, crossing zero. Four physical groups are small;
this is not a coverage guarantee or proof of significance. Conditional late-fraction risk
error is also worse than blind: pooled **0.0525245 vs 0.0485215**, Sintel
**0.0173654 vs 0.0161808**, BBB **0.0876113 vs 0.0807957**. The old prior proxy is
again green while the necessary action-information/replication gate is **false**.
Do not use proxy utility/risk skill as native/learning/SOTA acceptance.

**Risk score semantics:** saved legacy `*_risk_brier` fields are actually
request-weighted squared error against a **late-cohort mean miss fraction**.
They are not request-level Bernoulli Brier or selected confidence calibration.
The actual read-only identity probe in
`results/jobs/native-action-late-validation-final-audit-v3.json` finds omitted
within-cohort variance **0.0491127307**. Adding this same constant to each model
for identical constant-per-cohort predictions gives true request-level Brier
**0.1016372205 conditional vs 0.0976342529 blind**. The error ordering remains
harmful, but relative skill ratios are not interchangeable. All original field
names/values/criteria and false flags remain frozen, never silently rewritten.
Neither score calibrates early/transient/all requests or native chosen actions.

This identifies a real **out-of-training-context action-value generalization
blocker**, not merely missing verifier plumbing. The versioned temporal repair
remains a positive development result, not established transferable action value.

## Six all-training models frozen first

`src/media_rl/native_action_late_forecast.py` provides `plan`, `freeze`, `audit`.
It uses the exact old compact fitter/predict code objects with a distinct
`native_late_forecast_candidate_v3_auxiliary` ABI. Six once-only full-training
models—three conditional / three matched blind—use all **160/1944/eight-group**
V2 factual train rows, unchanged **92 causal summaries + three proposal inputs,
8 hidden units, 786 parameters, L2=0.01, 1,200 updates, seeds 6601/6602/6603,
loss/request weighting/group bootstrap**. No old cross-validation model is
refitted, no validation/calibration/diagnostic/test label enters fitting, and no
encoder target/QP is added to actor state.

The canonical cache is regenerated from both unchanged training parents and
must match the exact previously fully audited V2 development receipt
`d33bbf484f15d90af7875ac0d6baad52ca192c0222cdc8c8cfe7ff3ad7c67ddf`.
Prior complete native replay is reused only through that **fixed external SHA**,
not a freshly self-resealed source receipt. Public forecast audit checks every
model's actual geometry, blind action weights, full-training normalization,
recipe/source/credit/provenance and numerical fit error without a new fit.

Frozen source:
- `configs/native_action_late_forecast_v3.json`
- `results/native-action-late-forecast-v3/`
- Candidate manifest:
  `dc8638610653fc97b29287b834057b49a27ca758bb167ffd8a7e5f0286a5febd`

## A discovered data-role blocker and legal remedy

The old source-kind-limited reservation scanner suggested two remaining ToS
slots, but the new **all-role** scanner reads every protocol/config with a
video-source/group declaration, including previously omitted exact-cap and
other legal-role plans. Its frozen snapshot covers **56 input files**.

**Tears of Steel has no free full 20-second reservation.** The initially planned
Sintel/ToS validation therefore correctly fails *before writing its config or
capturing data*. No clip/window is shortened, no exclusion ignored, and no
training/calibration/diagnostic/test footage relabeled. Sintel's first remaining
complete slots are **640–660 / 660–680 seconds**.

To remove that data-access blocker—not tune a result—we import a wholly new
film before any validation label:
- [Official Blender licence/attribution](https://peach.blender.org/about/):
  Creative Commons Attribution 3.0; **(c) copyright 2008, Blender Foundation /
  www.bigbuckbunny.org**.
- [Official download page](https://peach.blender.org/download/) and authoritative
  [ZIP index](https://download.blender.org/peach/bigbuckbunny_movies/).
- Exact original archive:
  `https://download.blender.org/peach/bigbuckbunny_movies/big_buck_bunny_720p_h264.mov.zip`.
  The absent bare-MOV URL returned 404; the actual ZIP download completes and
  its single named original MOV is safely extracted. Original archive/full
  film/credit scroll and attribution are retained locally.
- Video-only **stream-copy** remux: 1280×720, H.264, 24 fps, 596.458 seconds,
  SHA `5960a2ad87a822cbe34719077eb7d05d70b65c8c1b4f6d30191b07813f7b8084`.
  Existing ffprobe/catalog rights/hash validation is used. Nothing is uploaded
  or redistributed; this is not a representative content corpus.
- `.tools/native_late_validation_v3/` contains catalogue, original media,
  actual official index and `ATTRIBUTION.md`. BBB's **60–80 / 80–100-second**
  reservations are validation-only. Its film SHA differs from both original
  training films. ToS supplies a frozen common-native-engine/shadow template
  only, never validation footage or labels.

The data exhaustion is removed for this bounded check, not for arbitrary future
large representative panels. Any future prospective collector must preserve
this comprehensive role reservation snapshot, including the new validation
source ranges; the old limited scanner alone is insufficient.

## Exact prospective contract, no deployed candidate

`src/media_rl/native_action_late_validation.py` supplies public `plan`, `run`,
`audit`; `benchmarks/native_rtc/late_validation_episode.mjs` is an exact
**two-anchor entry-only projection** of the frozen V2 producer: validation role
guard and truthful comment, no controller/measurement-body change. All owned
movie/RGB/source/native-wire/feedback/ACK/observation/readback/inference/PSNR/
150-ms deadline/future-action rules and the entire V2 native raw/cohort code
objects remain unchanged.

The old cohort builder hardcodes a train *metadata* label, not source/ACK/window
eligibility. The new wrapper assigns validation metadata only **after actual
validation-stage/role snapshots and full native/source guards pass**. It never
relabels a captured train peer or uses old train trial outcomes. Inherited train
augmentation/flag metadata is removed from these entirely new runtimes.

`configs/native_action_late_validation_v3.json` binds:
- Frozen candidate SHA **inside each actual native panel snapshot**, not just a
  later report, and actual candidate/config mtime before first raw capture.
- Four disjoint source/network groups, stable and collapse/recovery per film,
  six conventional peers each: both aliases and interleaved fixed450, two
  repetitions, fixed independent seeds/order/nominal capacity variation.
- All existing role-input SHAs and an exactly reconstructed full range snapshot,
  replacement catalogue SHA/rights and original native/code/producer identities.
- Original **32-step seed/epoch-only 300/450/900-kbps holds**, fixed
  **1800–2200-ms after-ACK** factual credit and same-capture **200–600-ms**
  reference. Target/QP/quality is never an eligibility/selection/input gate;
  every eligible missed/zero/censored outcome remains.
- Fixed **1%** utility skill versus both matched blind and train-only action
  prior, nonnegative risk skill versus train-only prior, required **pooled and
  each-film** results and a positive lower physical-group resampling interval.
  No current validation value sets prior means or fits normalization.
- Perfect zero-error blind/prior baselines yield **zero improvement**, not a
  spurious 100% from a zero-denominator floor. Exact ties cannot pass 1%.

This is small reserved-content/domain **forecast validation**, not the original
native-controller validation gate (which requires at least eight groups), not
selected-action confidence calibration and not a representative held-out/final
SOTA test. BBB is a wholly new source-domain; remaining Sintel is late-film.
All complete original native episode metrics remain reported, not just favorable
late windows. All native controllers are conventional; **learned native steps=0**.

## Verification and artifacts

- Six saved full-train forecasts pass actual public source/normalization/shape/
  recipe/numeric audit. The completed V2 CV/source/model/default bytes remain
  unchanged; its old positives/negatives are not overwritten.
- Sixteen targeted Python checks cover exact numerical-code/raw identity,
  786-parameter auxiliary/native-ABI separation, actual-role two-anchor
  projection, complete-role reservations, truthful fresh trial construction,
  fixed priors/per-film/physical-group uncertainty/zero-error semantics,
  original input immutability and **five actual fixed-plan drift rejections**.
- Complete actual public validation audit independently replays **all 24 native
  peers**, every original source/frame/cohort/sidecar record, exact saved
  validation cache, six frozen forecasts, priors, each-film/pooled error,
  256 physical resamples and the unchanged **false** replication flags.
- Independent extracted-wheel / `-I` / temporary-cwd verification is recorded in
  `results/jobs/native-action-late-validation-package-proof-v3.json` and
  **fully passes** the same real native/model/numeric replay, six actual
  native-actor ABI rejections and seven resealed role/threshold/exclusion/
  candidate/native-flag/MSE/actual-actor-feature forgery rejections without
  fitting or collecting data. Actual immutable validation manifest:
  `9832035ec5ebcc9037ecd306e25cc7a10cd3cf6218fc938f506919d8b9fe4fca`.
  The verified scientific replication/native/SOTA flags remain **false**.

Actual data/report: `results/native-action-late-validation-v3/`.
Read-only commands (do not overwrite or recollect):

```sh
.venv/bin/python -m media_rl.native_action_late_forecast audit \
  --run results/native-action-late-forecast-v3
.venv/bin/python -m media_rl.native_action_late_validation audit \
  --run results/native-action-late-validation-v3
```

## Remaining blocker and next defensible boundary

**Out-of-training-context action-value generalization remains blocked.**
Do not refit/tune on these validation labels, change 1%/credit/support/CI criteria,
remove Sintel or weak/censored rows, promote on the green prior proxy, or claim
BBB alone proves replication. Any next model/data hypothesis must be justified
using legal **training-only** evidence, versioned and frozen before another
independent role-disjoint experiment. The original failed validation is immutable.

Selected confidence must eventually cover the actual chosen-action distribution,
including early/transient/all requests; a late-only risk forecaster cannot supply
that safety API. A complete native actor ABI, safe repeated gains including
steady quality, independent/final evidence, representative measured/natural
panels and real original learned-peer closed loops remain missing.
**Defaults/V7 and earlier negative evidence remain unchanged;
`native_deployment_qualified=false`, `SOTA_achieved=false`.**
