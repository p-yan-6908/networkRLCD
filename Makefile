.PHONY: setup test smoke pilot paper-run improve tune-threshold policy-randomization-v4 safety-shield-v5 action-calibration-v6 uncertainty-shield-v7 resume-uncertainty-shield-v7 budget-shield-v8 delay-budget-v9 paper paper-evidence paper-status jevbwe-typed-smoke jevbwe-typed jevbwe-typed-audit jevbwe-typed-broad jevbwe-typed-broad-test jevbwe-typed-evidence paper-pdf
setup:
	uv sync --frozen --extra dev

test:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run pytest -q

smoke:
	uv run media-rl run --config configs/smoke.json --out results/smoke-new
	uv run media-rl audit --run results/smoke-new

pilot:
	uv run media-rl run --config configs/demo.json --out results/pilot-new

paper-run:
	uv run media-rl run --config configs/paper.json --out results/paper

improve:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl improve --config configs/improve_v2.json --models results/paper-v1 --out results/improvement-v2

tune-threshold:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl tune-threshold --config configs/threshold_select_v3.json --models results/paper-v1 --out results/threshold-selection-v3

policy-randomization-v4:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl policy-randomization --config configs/policy_randomization_v4.json --models results/paper-v1 --out results/policy-randomization-v4

safety-shield-v5:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl safety-shield --config configs/safety_shield_v5.json --models results/paper-v1 --out results/action-shield-v5

action-calibration-v6:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl calibrate-actions --config configs/action_calibration_v6.json --models results/paper-v1 --out results/action-calibration-v6/candidate-models
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl safety-shield --config configs/selection_calibration_v6.json --models results/action-calibration-v6/candidate-models --reference-models results/paper-v1 --out results/action-calibration-v6/final-campaign --no-plots

uncertainty-shield-v7:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl uncertainty-shield --config configs/uncertainty_shield_v7.json --models results/action-calibration-v6/candidate-models --out results/uncertainty-shield-v7

resume-uncertainty-shield-v7:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl uncertainty-shield --config configs/uncertainty_shield_v7.json --models results/action-calibration-v6/candidate-models --resume-from results/uncertainty-shield-v7 --out results/uncertainty-shield-v7/final-campaign

budget-shield-v8:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl budget-shield --config configs/budget_shield_v8.json --models results/action-calibration-v6/candidate-models --out results/budget-shield-v8 --no-plots

delay-budget-v9:
	OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run media-rl delay-budget --config configs/delay_budget_v9.json --models results/action-calibration-v6/candidate-models --out results/delay-budget-v9 --no-plots

paper-evidence:
	uv run media-rl export-paper --run results/paper-v1-evaluation --out paper/generated-scaleup
	uv run media-rl export-paper --run results/improvement-v2/test --out paper/generated-followup --macro-prefix Followup
	uv run media-rl export-paper --run results/threshold-selection-v3/test --out paper/generated-threshold --macro-prefix Threshold
	uv run media-rl export-paper --run results/policy-randomization-v4/test --out paper/generated-randomization --macro-prefix Random
	uv run media-rl export-paper --run results/action-shield-v5/test --out paper/generated-shield --macro-prefix Shield
	uv run media-rl export-paper --run results/action-calibration-v6/final-campaign/test --out paper/generated-action-calibration-v6 --macro-prefix ActionCal
	uv run media-rl export-paper --run results/uncertainty-shield-v7/final-campaign/test --out paper/generated-uncertainty-shield-v7 --macro-prefix Disagreement
	uv run media-rl export-paper --run results/budget-shield-v8/test --out paper/generated-budget-shield-v8 --macro-prefix Budget
	uv run media-rl export-paper --run results/delay-budget-v9/test --out paper/generated-delay-budget-v9 --macro-prefix DelayBudget
	uv run --frozen .tools/export_native_frame_paper.py
	uv run --frozen .tools/export_native_training_paper.py
	uv run --frozen .tools/export_native_development_paper.py
	uv run --frozen .tools/export_native_cadence_paper.py
	uv run --frozen .tools/export_native_model_v3_paper.py
	uv run --frozen .tools/export_native_temporal_v4_paper.py
	uv run --frozen .tools/export_native_context_v5_paper.py

# Root of the typed-control run directories. The tracked result summaries occupy results/, and a
# run refuses to write into an existing directory, so regenerate with TYPED=results/regen.
TYPED ?= results

jevbwe-typed-smoke:
	uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_smoke_v2.json --out $(TYPED)/jevbwe-typed-smoke-new

# Main study, estimator diagnosis, summaries ablation and the legacy-estimator replication.
# About two hours on 8 cores; output directories must not exist.
jevbwe-typed:
	uv run --frozen jevbwe-typed diagnose --config configs/jevbwe_typed_v2.json --out $(TYPED)/jevbwe-typed-v2-diagnosis
	uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v2.json --out $(TYPED)/jevbwe-typed-v2
	uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v2_no_summaries.json --out $(TYPED)/jevbwe-typed-v2-ablation-no-summaries --splits validation
	uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v2_legacy.json --out $(TYPED)/jevbwe-typed-v2-legacy

# Replay and audit of the frozen V2 test panel (about 15 minutes). Adds files beside the frozen
# ones and never rewrites them: decision records, identity checks and the family-level audit.
jevbwe-typed-audit:
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v2 --split test
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v2 --split test --robustness $(TYPED)/jevbwe-typed-v2-legacy

# Broadened training (V3). Train and read the development panel first; see docs/JEVBWE_TYPED_V3_BROAD.md.
jevbwe-typed-broad:
	uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v3_broad.json --out $(TYPED)/jevbwe-typed-v3-broad --splits validation,development
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v3-broad --split development
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v3-broad --split development --reference $(TYPED)/jevbwe-typed-v2

# The untouched test families of V3: evaluated once; the evaluate command refuses to recompute.
jevbwe-typed-broad-test:
	uv run --frozen jevbwe-typed evaluate --run $(TYPED)/jevbwe-typed-v3-broad --splits test
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v3-broad --split test
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v3-broad --split test

jevbwe-typed-evidence:
	uv run --frozen jevbwe-typed export --run $(TYPED)/jevbwe-typed-v2 --diagnosis $(TYPED)/jevbwe-typed-v2-diagnosis --ablation $(TYPED)/jevbwe-typed-v2-ablation-no-summaries --robustness $(TYPED)/jevbwe-typed-v2-legacy --broadened $(TYPED)/jevbwe-typed-v3-broad --out paper/generated-jevbwe-typed-v2

# Compile from the exported evidence already under paper/generated-*; does not re-export the
# nine archived studies, whose pruned results must be restored first (see ARCHIVED_RESULTS.md).
paper-pdf:
	@mkdir -p paper/build
	cd paper && ../.tools/tectonic --untrusted --keep-logs --keep-intermediates --outdir build main.tex

paper-status:
	uv run media-rl status --run results/paper-v1-evaluation

paper: paper-evidence
	@mkdir -p paper/build
	@if command -v latexmk >/dev/null 2>&1; then \
		cd paper && latexmk -pdf -outdir=build main.tex; \
	elif test -x .tools/tectonic; then \
		cd paper && ../.tools/tectonic --untrusted --keep-logs --keep-intermediates --outdir build main.tex; \
	else \
		echo 'Install latexmk or place a supported Tectonic binary at .tools/tectonic'; exit 1; \
	fi
