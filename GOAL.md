# Project objective and compute permission

## Objective
Build a complete, reproducible experimental framework for **Calibrated Reinforcement Learning for Safe Real-Time Media Adaptation**, verified by end-to-end CLI experiments, deterministic behavioral tests, saved models and per-step evidence, calibration diagnostics, seed-cluster uncertainty estimates, ablations, publication-quality plots and LaTeX tables, and a documented methodology with primary research references.

The controller must use only causal network telemetry to select bitrate, FEC and media mode; output an explicitly defined calibrated probability of next-step safety; and invoke a deterministic conservative fallback when confidence is low, telemetry is invalid/stale, or a separately reported support guard rejects the observation. Compare with heuristic and GCC-like controllers and the identical ungated RL policy on paired ID and held-out OOD traces. Measure QoE, latency, loss, stability, calibration, robustness and fallback behavior.

## Compute permission (user instruction)
**Modal CLI may be used for GPU training if required.** Prefer the reproducible CPU implementation for the current small models. GPU use is optional, not a requirement. Do not claim GPU runs occurred unless they actually did. Record the Modal image, hardware, dependency versions, seeds, job identifiers, commands and cost/runtime information for any future remote runs. Keep credentials outside the repository. No paid GPU jobs have been launched as of this note.

## Constraints and boundaries
- Work in `.`; preserve user changes.
- Research relevant papers, including through the Hugging Face CLI.
- Separate training, safety-model fitting, calibration and test data. Never tune on test/OOD results.
- Preserve causal observations, identical exogenous traces across methods, auditable configs/seeds and truthful reporting of all comparisons, including negative findings.
- This is a fluid-simulator research framework, not a WebRTC implementation, production GCC reproduction, codec benchmark, or certified safety guarantee. Never describe synthetic evidence as real-network validation.
- Do not invent results, citations, statistical significance or completed large-scale experiments. Label smoke/demo runs as such. Do not publish or upload private artifacts without a separate request.

## Iteration and verification policy
Maintain `docs/acceptance.md`. Trace the config -> scenario -> telemetry -> controller -> simulator -> metrics -> report execution path before edits. Implement end to end, then run the smallest relevant tests and direct behavioral probes. Inspect failures before changing code; check public CLI registrations, configs and emitted artifacts mechanically. Use immutable experiment directories and record source/config/checkpoint hashes. Escalate compute only when measured runtime or model scale justifies it.

## Blocked stop condition
If dependencies, data access, compute access or a defensible scientific design block progress, stop with the evidence collected, attempted paths, exact blocker and next input required. Do not substitute fabricated results for missing experiments.

This file records the requested project objective; it does not activate persistent agent goal mode.
