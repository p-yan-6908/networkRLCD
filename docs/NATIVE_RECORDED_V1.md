# Recorded-media native source V1 — repeatability failure, no promotion

## Why this prerequisite was implemented

After the prior 68 generated-content runs, only **four untouched 1,000-frame reservations** remained when all original fitting/development ranges and complete reservations from the latest repeatability/calibration/validation panels were excluded. The locked validation recipe needs eight independent source/schedule groups. We did **not** reuse IDs, shrink reservations, lower that requirement, or fit prior validation labels.

The new `recorded_video_v1` source identifies content by file SHA-256 and reserved clip intervals, independently of generated-scene IDs. It adds local, already recorded movie content to the native collector. This is one live-action/VFX film, **not a representative natural-camera corpus or measured Internet benchmark**. Longer-history actor work has not yet been implemented: the new repeated controls expose a prerequisite reliability/control problem that must be addressed first.

## Source and attribution

- Film: *Tears of Steel* (2012), Blender Foundation. Official [film/license page](https://mango.blender.org/about/) states Creative Commons Attribution 3.0 and asks that the credit scroll be retained.
- Original: [official 720p MOV](https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov), **372,178,639 bytes**, 734.166667 seconds, H.264 1280×534 at 24 fps plus MP3 audio.
- Local original: `data/native_video/tears_of_steel_720p.mov`.
- Local video-only remux: `data/native_video/tears_of_steel_video_only.mp4`. Video packets are copied, not re-encoded; audio is removed. Its SHA-256 is `7e88af2774f38dc74958efa62ed2e38add29e38c628d7fe196ec462a25490809`.
- Immutable descriptor: `data/native_video/tears_of_steel_source.json`. The original full video stream, including credits, remains locally retained; the benchmark observes declared center-cropped segments. No upload, publication, or redistribution was performed.
- `TOS_ABOUT.html` preserves the film-page evidence. **`TOS_COPYRIGHT.txt` is a separate soundtrack CC-BY-NoDerivs notice, not the film license.** Do not conflate these.

The denied Google sample mirror was not bypassed; the actual asset came from Blender's authoritative public source. Large movie files live under `data/`, not inside the packaged Python/browser assets.

## Implemented and verified

- `src/media_rl/native_video.py`: typed catalogs, content SHA binding, disjoint ≥20-second reserved segments, role exclusions including interrupted protocols, independent pre-capture-reference/CRC/deadline/RGB replay.
- `benchmarks/native_rtc/recorded_video.mjs`: source loading/seek, center-crop-fill 640×360, original-source RGB sampling before marker writing and manual capture, and paired receiver RGB quality. Source pixels, clip times, and segment identities are **labels only**, never neural observations.
- CLI: `native-video-source` and `native-plan --video-source`. Existing `native-study`/`native-audit` dispatch the versioned recorded path. Generated-source behavior, risk models/Platt, 0.5/0.2 screens, 16×4 causal sender ABI, packet physics, application 150 ms deadlines and numerical quality formulas are unchanged.
- A parent capture seals one movie copy, catalog/protocol, source implementation hashes, model copies, and every child. Audit verifies the source/implementation hashes and rederives metrics without writes.
- Recorded segment SHA/ranges are not confused with generated-scene IDs; prior seals are checked before ignoring their generated namespace.

Example (new catalog/plan/output paths are required):

```sh
uv run --frozen media-rl native-video-source \
  --video data/native_video/tears_of_steel_video_only.mp4 \
  --out data/native_video/new_source.json \
  --attribution 'Tears of Steel (2012), Blender Foundation; original credit scroll retained' \
  --license-url https://mango.blender.org/about/ \
  --source-url https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov
uv run --frozen media-rl native-plan --model results/native-model-v3/model.json \
  --video-source data/native_video/new_source.json --stage repeatability \
  --groups-per-family 1 --repetitions 2 --out configs/native_recorded_fresh.json
uv run --frozen media-rl native-study --config configs/native_recorded_fresh.json \
  --out results/native-recorded-fresh
uv run --frozen media-rl native-audit --run results/native-recorded-fresh
```

Catalog metadata records the importer's rights assertion; it does not grant rights to an arbitrary user-supplied movie. The current loader hashes a complete source in-browser before playback and uses a Blob. Streaming/bounded-memory improvements are a **next hypothesis**, not a demonstrated fix to the completed outcomes.

## Actual 24-run outcome

`configs/native_recorded_repeatability_v1.json` prospectively froze four movie/schedule groups, two repeated identical-policy aliases and BWE, with two repetitions: **24 actual Chrome/VP8 browser runs**. All models/gates and source identities stayed fixed.

| Condition | Mean utility | Mean on-time opportunities |
|---|---:|---:|
| RLCD alias A | 19.816299 | 54.3433% |
| RLCD alias B | 18.397968 | 48.4872% |
| Native BWE-headroom | 30.204055 | 87.2633% |

Identical RLCD mappings, four runs per source/schedule group:

| Group | Utility span | On-time span |
|---|---:|---:|
| Stable | 2.496442 | 3.8803 pp |
| Collapse | 0.998313 | 3.4733 pp |
| Variable | 0.225397 | 3.0988 pp |
| Brief collapse | **16.455496** | **60.9665 pp** |

The predeclared limits remain utility span ≤3.0, on-time span ≤15 pp, and episode inference p99 ≤10 ms. The **brief-collapse variability fails**, and two inference-tail checks fail: `stable-0-r1-rlcd-b` **10.475 ms**, `variable-0-r1-rlcd-b` **13.304 ms**. The source/control repeatability gate is **false**. No candidate validation/final-test panel or model promotion followed this failure.

### Diagnostics, not a proven causal mechanism

The stable tail-failing episode had a **53.4 ms first inference**; the variable tail-failing episode had a **48.4 ms maximum**, although normal inference samples were mostly below 3 ms. Potential cold JIT/large-source allocation effects are not established causes. Do not drop those samples or weaken the 10 ms gate.

Brief-collapse RLCD outcomes vary from **27.853675 utility / 92.1933% on-time** to roughly **11–13 utility / 31–35%**. Poor runs deliver **zero on-time opportunities during collapse and recovery**. Their early causal GCC/BWE observations and later applied caps differ; the neural mapping is the same, not the histories or packet trajectories. Even BWE's two brief-collapse runs vary (**94.4238% vs 52.7881% on-time**). This is a warning about startup/feedback/control sensitivity, not evidence that one alias improves policy or proof of a specific measurement defect.

## Acceptance evidence and next work

**338 Python tests / 63 native Node tests** pass; Ruff, wheel build and extracted-wheel recorded-source imports pass. Full raw replay verifies all **24** new movie runs. Deep before/after hashes confirm a read-only audit. Repeatability-role labels are refused for fitting with no output created. Native V3/V4 models and the existing V7 selection hash remain unchanged. Prior generated native evidence also still replays.

Next: inspect receiver frame ages/jitter/playout and source-frame progression against sender histories; separate cold inference/source allocation from closed-loop variability using a prospectively declared measurement recipe. Any changed source engine requires new pinned descriptors/plans, fresh segments, all outcomes retained and no after-the-fact relaxation. No longer-history candidate should be called validated through the failed panel. More films, real measured paths, multiple training seeds and compatible published-controller comparisons are still required. **SOTA remains unachieved.**
