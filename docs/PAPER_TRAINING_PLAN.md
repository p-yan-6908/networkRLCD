# RLCD paper and training campaign

## Historical V1/V2 training checkpoint

Current status: nine studies are complete; V8 and V9 are not promoted. V9 recovers burst-loss quality relative to V8 but still fails nominal QoE. See `docs/verification.md` and `docs/DELAY_BUDGET_V9.md`. The budgets, test counts and toolchain notes below describe the earlier V1/V2 campaign, not the latest workspace.

- V1 evaluation **finished**: 19,800 episodes, 11,880,000 intervals; all **358 artifacts** audited. Canonical run: `results/paper-v1-evaluation/`. The interrupted original run is preserved, not analyzed.
- The later improvement request is tracked separately in `docs/IMPROVEMENT_V2.md`. Three fixed policy seeds were reused unchanged; safety refits, validation selection, and 1,188 fresh-test episodes completed. All **218 final artifacts** audited.
- The stress predictor improves stress Brier/NLL on identical states, but the validation-selected controller regresses against matched v1. **Do not promote it or claim improved closed-loop performance.** The locked choice and all negative outcomes remain recorded.
- The paper now analyzes both completed studies using separate exports. `make paper` rebuilds `paper/build/main.pdf`; `paper/pilot-archived.tex` preserves the earlier draft. Runtime launch/PID references below are historical, not active-job claims.
- Verification: 42 passing tests. No GPU/Modal job was required.


## Scope and frozen decisions

RLCD is the project label for the implemented calibrated RL media controller (`calibrated` in the method registry), not a claim to reproduce a separately established algorithm. Keep the existing Double DQN, safety ensemble, calibration and runtime gate unchanged for this campaign. The user's request is to start substantive paper writing and model training, not to assume a successful result.

Run the existing `configs/paper.json` protocol: ten model seeds, 160 policy-training episodes × 600 intervals per seed, 40 independent safety-fit episodes, 40 independent calibration episodes, three safety predictors, 64 hidden units, and 30 safety-fit epochs. Train/calibration are ID-only. Evaluation comprises 20 test seeds × 11 scenarios × 9 methods × 10 model seeds = 19,800 episodes and 11,880,000 intervals. Policy training comprises 960,000 transitions total. Do not tune on this evaluation.

The first four test seeds overlap the earlier pilot. Therefore this is a frozen paper-scale descriptive follow-up, not a wholly new untouched confirmatory trace panel. Any later model/hyperparameter changes require a separately documented training/validation design and fresh final test panel.

## Acceptance ledger for this request

- [x] Review training -> risk fitting -> calibration -> evaluation path; pass existing tests and audit pilot evidence before launch.
- [x] Launch the ten-seed frozen campaign, record its process/log/config, and verify actual checkpoint progress.
- [x] Develop the paper beyond a scaffold: problem formulation, RLCD algorithm, explicit hypotheses, related runtime assurance, experimental design, and evidence-linked pilot findings including negative results.
- [x] Produce auditable generated paper numbers from an audited completed run; never import partial scale-up metrics as complete results.
- [x] Add/verify a lightweight status/report surface for long-running work without changing learned-policy behavior.
- [x] Verify new tests and manuscript artifact/citation contracts; compile the manuscript if a suitable TeX toolchain is available.

## Historical launch/interruption record (superseded by completion above)

- Launched the frozen CPU job with shell launcher PID **14017**. That original launcher later hit its 3600-second command timeout; its PID is historical, not a live process. See the interruption record at `results/jobs/paper-v1-interruption.md`.
- All **10/10 policy + safety + calibration bundles completed**. Each policy performed **23,969 gradient updates** on **96,000 transitions**; total policy transitions: **960,000**. Every seed has 24,000 calibration samples and both label classes; all calibrators used Platt scaling.
- Direct probes compared each calibrator's *fit-set* NLL with its raw fit-set NLL and checked non-increase. This is an optimization sanity check, not out-of-sample calibration evidence. Safe-label prevalence is high (roughly 98.8–99.9%); rare-failure uncertainty deserves explicit attention in the scale-up analysis.
- Hash probes confirmed that training, networks, safety calibration, controller, environment, scenario and config source files are unchanged from the launch snapshot. Only paper/read-only evidence tooling changed during the campaign.
- Original evaluation was **interrupted by the one-hour command limit** after five logged model-seed blocks. The incomplete `results/paper-v1/steps.csv.gz` is preserved and is not paper evidence. Replacement evaluation was launched as detached local PID **17191**, reusing all trained checkpoints and restarting evaluation from the beginning in **`results/paper-v1-evaluation/`**. It proceeds to reporting automatically, but is not interactively supervised after this response.
- Added `media-rl status --run ...` (read-only progress, not liveness) and `media-rl export-paper --run ... --out ...` (complete-run integrity checks and data-linked tables/macros/figures). All **38 tests passed**.
- `paper/main.tex` is now a substantive RLCD draft and compiled to a **9-page PDF** at `paper/build/main.pdf` with the isolated Tectonic 0.15.0 engine. The final TeX log contains no missing-reference, undefined-command, overfull or underfull box warnings. Generated pilot evidence is pinned in `paper/generated/provenance.json`.

Monitoring:

```sh
uv run media-rl status --run results/paper-v1-evaluation
cat results/jobs/paper-v1-evaluation.log
ps -p "$(cat results/jobs/paper-v1-evaluation.pid)" -o pid,etime,command
```

Completion update: the replacement evaluation finished, passed audit, and was exported to `paper/generated-scaleup`. The current manuscript deliberately replaces pilot-specific claims. The launch/monitoring commands below are retained as historical reproduction instructions.

## Execution and compute

Command:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1 \
  uv run --frozen media-rl run --config configs/paper.json --out results/paper-v1
```

Artifacts: `results/paper-v1/`. External live log: `results/jobs/paper-v1.log`. Launcher PID: `results/jobs/paper-v1.pid`. External files avoid changing the immutable experiment directory before initialization and after its manifest is finalized. Each finished seed writes an inference checkpoint plus calibration and training CSVs. Training is not resumable mid-seed; do not overwrite or pretend to resume an interrupted run.

CPU is appropriate: tiny NumPy networks and Python simulation dominate; a GPU would not automatically accelerate this implementation. Modal remains permitted if a future measured bottleneck requires a GPU-compatible trainer; no paid job is authorized by this plan beyond the user's existing optional permission, and no GPU job is implied by a CPU run.

## Durable evaluation recovery

The initial one-hour runner deadline was insufficient for the full 11.88-million-interval matrix. No model retraining or hyperparameter change was performed. The recovery command is:

```sh
nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONUNBUFFERED=1 \
  .venv/bin/python -m media_rl evaluate --config configs/paper.json \
  --models results/paper-v1 --out results/paper-v1-evaluation \
  > results/jobs/paper-v1-evaluation.log 2>&1 < /dev/null &
echo $! > results/jobs/paper-v1-evaluation.pid
```

This is an ordinary detached local process, not a persistent agent. It may still fail or be stopped if the machine shuts down. The replacement run has no partial-resume mechanism; interruption would require a new output directory again. No unlogged CPU/GPU cloud service is involved. To stop it deliberately, inspect the PID and command first, then send the process a termination signal; keep the partial artifacts for diagnosis.

## Paper integrity

The completed paper now uses audited `results/paper-v1-evaluation/` and the separately audited follow-up in `results/improvement-v2/test/`; pilot exports remain archived. Keep pilot and scale-up evidence unmistakably separate. The primary contrast is RLCD versus its identical ungated RL policy; heuristic/GCC-like/safe control remain mandatory baselines. Calibration claims must include same-state NLL/Brier as well as ECE, ID and OOD, and may be negative. No deployment guarantee, optimality-confidence interpretation, packet-level latency claim, or baseline-superiority claim is permitted without corresponding evidence.

## Stop/report policy

If the job fails, preserve the log/checkpoints and report the exact exception and completed seeds. If the response ends while the job is running, explicitly report that state and the monitoring paths; do not imply continued interactive supervision or completed evaluation. TeX/toolchain unavailability must be reported rather than claiming the manuscript compiled.
