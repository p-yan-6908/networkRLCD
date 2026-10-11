.PHONY: setup test smoke pilot paper-run improve tune-threshold policy-randomization-v4 safety-shield-v5 action-calibration-v6 uncertainty-shield-v7 resume-uncertainty-shield-v7 budget-shield-v8 delay-budget-v9 paper paper-evidence paper-status jevbwe-typed-smoke jevbwe-typed jevbwe-typed-audit jevbwe-typed-broad jevbwe-typed-broad-test jevbwe-typed-baselines jevbwe-typed-replication jevbwe-typed-factual jevbwe-typed-population jevbwe-typed-population-test jevbwe-typed-crossover jevbwe-typed-headroom jevbwe-typed-b1-forecast jevbwe-typed-factual-unseen jevbwe-typed-followup-evidence jevbwe-typed-evidence native-n1-evidence paper-pdf
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

# Tuned reactive rules replayed on the frozen V3 panels (about three minutes); analysis only.
# See docs/JEVBWE_TYPED_BASELINE_AUDIT.md.
jevbwe-typed-baselines:
	uv run --frozen jevbwe-typed baselines --run $(TYPED)/jevbwe-typed-v3-broad --out $(TYPED)/typed-baseline-audit-v1

# One evaluation of the frozen V3 models on the registered population panel; nothing is refitted
# and the transfer command refuses to recompute. See docs/JEVBWE_TYPED_V3_REPLICATION.md.
jevbwe-typed-replication:
	uv run --frozen jevbwe-typed transfer --run $(TYPED)/jevbwe-typed-v3-broad --registration configs/jevbwe_typed_v3_replication.json --out $(TYPED)/jevbwe-typed-v3-replication
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v3-replication --split test
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v3-replication --split test
	uv run --frozen jevbwe-typed baselines --run $(TYPED)/jevbwe-typed-v3-replication --out $(TYPED)/jevbwe-typed-v3-replication-baselines
# Factual-only supervision against a rollout-labelled control on shared rows (development study,
# about an hour on 8 cores and under 4 GB). See docs/JEVBWE_TYPED_FACTUAL_V1.md.
jevbwe-typed-factual:
	uv run --frozen jevbwe-typed factual --run $(TYPED)/jevbwe-typed-v3-broad --settings configs/jevbwe_typed_factual_v1.json --out $(TYPED)/typed-factual-v1
# Population training (V4): train, then read the development panel paired with the V3 replication.
# About three hours on 8 cores. The development registration names the trained model files by
# hash and is written after training. See docs/JEVBWE_TYPED_V4_POPULATION.md.
jevbwe-typed-population:
	uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v4_population.json --out $(TYPED)/jevbwe-typed-v4-population --splits validation
	uv run --frozen jevbwe-typed register --run $(TYPED)/jevbwe-typed-v4-population --name jevbwe-typed-v4-development --panel r --seeds 29301-29316 --protocol docs/JEVBWE_TYPED_V4_POPULATION.md --out $(TYPED)/jevbwe-typed-v4-development-registration.json
	uv run --frozen jevbwe-typed transfer --run $(TYPED)/jevbwe-typed-v4-population --registration $(TYPED)/jevbwe-typed-v4-development-registration.json --out $(TYPED)/jevbwe-typed-v4-development
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v4-development --split test
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v4-development --split test --reference $(TYPED)/jevbwe-typed-v3-replication
	uv run --frozen jevbwe-typed baselines --run $(TYPED)/jevbwe-typed-v4-development --out $(TYPED)/jevbwe-typed-v4-development-baselines
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v4-population --split validation

# The sealed panel: V4 and the frozen V3 models, once each, on identical traces (about 2.5 hours).
# Run only after configs/jevbwe_typed_v4_test.json has been committed with the frozen hashes.
jevbwe-typed-population-test:
	uv run --frozen jevbwe-typed transfer --run $(TYPED)/jevbwe-typed-v4-population --registration configs/jevbwe_typed_v4_test.json --out $(TYPED)/jevbwe-typed-v4-test
	uv run --frozen jevbwe-typed transfer --run $(TYPED)/jevbwe-typed-v3-broad --registration configs/jevbwe_typed_v3_on_sealed.json --out $(TYPED)/jevbwe-typed-v3-on-sealed
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v4-test --split test
	uv run --frozen jevbwe-typed rescore --run $(TYPED)/jevbwe-typed-v3-on-sealed --split test
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v3-on-sealed --split test
	uv run --frozen jevbwe-typed audit --run $(TYPED)/jevbwe-typed-v4-test --split test --reference $(TYPED)/jevbwe-typed-v3-on-sealed
	uv run --frozen jevbwe-typed baselines --run $(TYPED)/jevbwe-typed-v4-test --out $(TYPED)/jevbwe-typed-v4-test-baselines
	uv run --frozen jevbwe-typed baselines --run $(TYPED)/jevbwe-typed-v3-on-sealed --out $(TYPED)/jevbwe-typed-v3-on-sealed-baselines
# Factual supervision trained on the population pool and scored on both read population panels
# (about an hour; needs the V4 run and its two transfers). See docs/JEVBWE_TYPED_FACTUAL_V2.md.
jevbwe-typed-factual-unseen:
	uv run --frozen jevbwe-typed factual --run $(TYPED)/jevbwe-typed-v4-population --settings configs/jevbwe_typed_factual_v2.json --panel $(TYPED)/jevbwe-typed-v4-development --panel $(TYPED)/jevbwe-typed-v4-test --out $(TYPED)/typed-factual-v2-unseen

# Hindsight headroom under truncated option sets (about twenty minutes; needs the V4 run; no model).
jevbwe-typed-headroom:
	uv run --frozen jevbwe-typed headroom --run $(TYPED)/jevbwe-typed-v4-population --settings configs/jevbwe_typed_headroom_v1.json --out $(TYPED)/typed-headroom-v1

jevbwe-typed-b1-forecast:
	uv run --frozen python -m media_rl.typed_bitrate_b1_forecast --settings configs/jevbwe_typed_b1_forecast_v1.json --out $(TYPED)/typed-b1-forecast-v1

# Per-link crossover identification on the development pool (about five minutes; needs the V4 run).
# See docs/JEVBWE_TYPED_CROSSOVER_V1.md.
jevbwe-typed-crossover:
	uv run --frozen jevbwe-typed crossover --run $(TYPED)/jevbwe-typed-v4-population --settings configs/jevbwe_typed_crossover_v1.json --out $(TYPED)/typed-crossover-v1

jevbwe-typed-followup-evidence:
	uv run --frozen jevbwe-typed followup --baselines $(TYPED)/typed-baseline-audit-v1 --replication $(TYPED)/jevbwe-typed-v3-replication --replication-baselines $(TYPED)/jevbwe-typed-v3-replication-baselines --factual $(TYPED)/typed-factual-v1 --factual-unseen $(TYPED)/typed-factual-v2-unseen --crossover $(TYPED)/typed-crossover-v1 --headroom $(TYPED)/typed-headroom-v1 --forecast $(TYPED)/typed-b1-forecast-v1 --validation TypedPopVal $(TYPED)/jevbwe-typed-v4-population --panel TypedPopDev $(TYPED)/jevbwe-typed-v4-development $(TYPED)/jevbwe-typed-v4-development-baselines --panel TypedPop $(TYPED)/jevbwe-typed-v4-test $(TYPED)/jevbwe-typed-v4-test-baselines --panel TypedSeal $(TYPED)/jevbwe-typed-v3-on-sealed $(TYPED)/jevbwe-typed-v3-on-sealed-baselines --out paper/generated-jevbwe-typed-followup

jevbwe-typed-evidence:
	uv run --frozen jevbwe-typed export --run $(TYPED)/jevbwe-typed-v2 --diagnosis $(TYPED)/jevbwe-typed-v2-diagnosis --ablation $(TYPED)/jevbwe-typed-v2-ablation-no-summaries --robustness $(TYPED)/jevbwe-typed-v2-legacy --broadened $(TYPED)/jevbwe-typed-v3-broad --out paper/generated-jevbwe-typed-v2

# Native Phase N1: macros and tables from the registered final analysis. Mock rows are refused.
N1 ?= results
native-n1-evidence:
	uv run --frozen python -m media_rl.native_actuator_qualification_report --final $(N1)/native-actuator-qualification-n1-final.json --public $(N1)/n1-interim-public.json --protocol $(N1)/native-actuator-qualification-n1-plan/protocol.json --pool acquisition/native-n1/pool-and-plan.json --exploratory $(N1)/native-actuator-qualification-n1-exploratory.json --conditional $(N1)/native-actuator-qualification-n1-conditional.json --dynamics $(N1)/native-actuator-qualification-n1-dynamics/report.json --flags $(N1)/native-phase-b1-flag-composition.json --binding $(N1)/native-actuator-qualification-n1-dynamics/binding.json --delivery $(N1)/native-actuator-qualification-n1-delivery/report.json --delivery-first-hold $(N1)/native-actuator-qualification-n1-delivery/first_hold.json --out paper/generated-native-n1

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
