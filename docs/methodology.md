# Methodology and implementation contract

This document describes the **legacy `fluid_v1` default and nine-study paper**. The opt-in paced packet/frame backend, 16-feature history policy, conventional demonstrations and new-cohort safety target are separately specified and verified in [REALISM_V10.md](REALISM_V10.md). Their numerical scales, safety targets and trained stress distributions must not be mixed with fluid-paper results. Neither backend is real-network or codec validation.

## 1. State, action and causality

The task is a partially observed, finite-horizon media-control problem. At each interval Δ=0.1 s (configurable), the agent receives a `Telemetry` object: acknowledged wire throughput, RTT, raw loss, jitter, RTT change, the last locally selected bitrate/FEC/mode, feedback age, and a validity bit. Ten fixed-scale features divide Mbps by 4, RTT by 200 ms, jitter by 50 ms and RTT change by 100 ms; see `Telemetry.vector`. Policy inputs are clipped to ±12. Current/future capacity, queue state, scenario identity and outcome labels are **not** observation features.

Feedback delay d means an interval's result is usable no earlier than the decision following that interval (d=1); d>1 withholds it for d−1 more decisions. Missing reports retain old measurements and increase feedback age. Locally known previous actions remain current. Initial telemetry is a fixed prior, not an oracle probe.

An action a=(b,f,m) selects source bitrate b∈{0.15,0.3,0.6,1,1.6,2.5,4} Mbps, redundancy f∈{0,0.1,0.25}, and normal or low-latency media mode. Wire rate w=b(1+f). All methods use the same action space. No-FEC experiments restrict it to f=0 and retrain. The low-latency mode trades a quality multiplier of 0.82 for 8 ms encode delay; normal uses multiplier 1 and 25 ms. These are explicit synthetic parameters, not measured codec performance.

## 2. Fluid network/media transition

Let Q be queued Mbit, C the exogenous capacity in Mbps, B the buffer size in Mbit, and A=wΔ. Service S=min(Q+A,CΔ), overflow D=max(0,Q+A−S−B), and Q′=max(0,Q+A−S)−D. B is multiplied by the trace's buffer scale. Tests check this conservation law. Tail-drop loss is approximated by min(1,D/A), composed with exogenous erasure probability ℓ as p=1−(1−p_drop)(1−ℓ).

For burst intensity z, idealized recoverable fraction r=η(1−0.7z)f/(1+f), η=0.85 by default. Residual loss is max(0,p−r)/(1−r). At C=0, residual loss and deadline miss are forced to 1. Redundancy consumes bottleneck capacity and adds 20f ms coding delay. This model does not implement packet-level erasure blocks or codec-specific protection.

Virtual queue delay is 1000(Q+Q′)/(2 max(C,0.01)) ms. Virtual media latency L is half base RTT + queue delay + exogenous nonnegative jitter + encode/coding delay. The 0.01 Mbps denominator floor keeps stalled-interval diagnostics finite; **outage latency values are virtual penalties, not observed packet delivery times**. No flow/packet/frame identities are tracked. Buffered stale data remains in the network until served/dropped.

Assuming frame completion times uniformly spread across one interval around L, deadline miss fraction d=clip(0.5+(L−deadline)/(1000Δ),0,1). Report loss and deadline miss separately. Timely-goodput proxy is min(b,S/[Δ(1+f)])(1−residual_loss)(1−d); it cannot exceed service, but mixing old/current packets is approximated.

The default per-step synthetic QoE/reward is:

```
quality = log(1 + b/0.15) * (0.82 if low_latency else 1)
reward = quality*(1-residual_loss)*(1-deadline_miss)
         - 0.8*min(L/deadline, 10)
         - 5*residual_loss - 2*deadline_miss
         - 0.15*abs(log(b/previous_bitrate))
```

All reward weights are configurable. Switching includes the initial jump from the fixed initial bitrate. The safety event is **Y=1 iff L≤150 ms, residual_loss≤0.05, and C>0**, with limits configurable. The event is not reward positivity and does not imply zero deadline misses. Safety and QoE can conflict.

## 3. Actual RL optimization

`train_policy` implements Double DQN (van Hasselt et al.). A one-hidden-layer ReLU MLP predicts 42 action values. ε-greedy exploration decays linearly to its floor over the first 80% of training episodes. Uniform replay samples state/action/reward/next-state/terminal transitions. Targets are:

```
y = reward + gamma*(1-terminal)*Q_target(next, argmax_a Q_online(next,a))
```

Huber TD loss, global gradient clipping at norm 10, Adam, and periodically copied target weights are implemented directly in NumPy. The terminal transition never bootstraps. Config files record widths, replay/batch sizes, warmup, update cadence, target cadence, learning rate and gamma. The final checkpoint is used; there is no test-driven early stopping or best-seed selection. Training reward curves reflect exploratory behavior, not evaluation-policy returns.

The `rl` baseline uses **the identical policy checkpoint and greedy proposal** as `calibrated`; no separate favorable training run is substituted. This isolates the runtime gate. It is a standard small Double DQN baseline, not a reproduction of Aurora or PPO.

## 4. Safety confidence, independent calibration and support

A separate classifier predicts P(Y=1 | telemetry, proposed action). Features concatenate telemetry with candidate bitrate/4, redundancy, mode and wire/observed-throughput ratio divided by 5. The denominator is floored at 0.05 Mbps. Features are standardized using safety-fit data only (standard deviation floor 0.05), then clipped to ±12 for prediction.

Safety-fit episodes use ID scenarios and a predeclared repeating mix of greedy RL, deterministic safe and GCC-like behavior. Fifteen percent random actions augment exploration. Every RL proposal and differing executed action is labeled via pure simulator preview. MLP classifiers train binary cross-entropy on episode-level bootstrap resamples. Their average sigmoid probability is the raw score; standard deviation is logged as disagreement, not a Bayesian credible interval.

Calibration uses **new ID trace seeds**, freezes both policy and ensemble, and collects only RL-proposal labels on the same three-way trajectory mix, without random action augmentation. Monotone Platt scaling fits q=σ(exp(a)logit(p)+b) by held-out binary NLL. A temperature variant fixes b=0. Bounds prevent numerical divergence. If fitting fails, identity is recorded; if only one label class appears, the recorded `constant_single_class` calibrator uses Laplace-smoothed prevalence (sum(Y)+1)/(n+2). This is an explicit insufficient-data warning, not evidence of calibration. The single-model ablation uses the first ensemble member with its own separately fitted calibrator on the same calibration set.

No calibration/test overlap is allowed. Namespaced SHA-256-derived seeds distinguish `train`, `risk`, `calibration` and `test` even when user-visible integer seeds coincide. Training/safety/calibration scenarios are restricted to ID families. Calibration is a post-hoc empirical procedure, not a conformal guarantee. Temporal dependence and the gate's altered occupancy distribution can invalidate transfer; evaluate that, do not assume it away.

Support score is RMS standardized distance of the ten **unclipped telemetry** features from the safety-fit mean. Its rejection cutoff is the safety-fit 99.5th percentile. It is a deliberately simple support heuristic, not a learned OOD classifier or safety proof. It does not inspect the scenario name and does not multiply/alter the calibrated probability. Report the support score and probability separately.

## 5. Runtime gate and deterministic fallback

Accept the proposal only when reported q≥τ (default .90), feedback is valid/fresh, and the support guard accepts. Invalid/nonfinite telemetry triggers an emergency deterministic action without evaluating the neural models. Once fallback starts, stay for at least three decisions and require q≥τ+.03 to release; hard rejection always wins. Reasons distinguish low confidence, OOD support, stale/missing telemetry and hysteresis. The probability remains the prediction for the **proposal**, even when a fallback action is executed.

The separate `shielded` candidate ranks the source policy's actions by Q value, tests the top five with the same calibrated one-step safety predictor and telemetry-support test, executes the first accepted alternative, and uses the existing deterministic fallback if none pass. It does not use the gate's hysteresis state or retrain a model. Calibration was fitted for the original proposal distribution, so screening multiple alternatives can induce selection bias; empirical next-step tests do not provide a shield or guarantee.

The conservative controller keeps a wire-rate budget, a running minimum RTT and an RTT-excess congestion estimate. It decreases to min(0.7 budget,0.8 acknowledged throughput) on RTT excess>35 ms, loss>.06 or RTT increase>15 ms; otherwise it probes additively at 0.5 Mbps/s. A persistent probing budget is necessary because ACK throughput is application-limited and discrete ladder rungs otherwise lock. It uses low-latency mode, modest FEC only for moderate loss without congestion, and picks the highest admissible rung. Missing/nonfinite/stale telemetry halves its budget and removes FEC. If no action fits, it selects the minimum-wire low-latency action. It cannot guarantee safety if even that action is infeasible. The fallback's shadow state is updated on every decision for deterministic warm state.

The heuristic baseline uses throughput plus persistent additive probing, queue-triggered backoff, and loss-based FEC. GCC-like uses a delay-overuse/loss detector, multiplicative decrease and additive/multiplicative probing. Its simplified controller omits libwebrtc's packet grouping, trendline/Kalman machinery, probing and transport details: label it **GCC-like**, never production GCC.

## 6. Evaluation-only counterfactuals and limitations

For every evaluated state, preview the proposed action on exactly the same queue and exogenous trace interval, then execute the controller's choice. Preview is pure and cannot mutate the environment or affect controller decisions. `proposal_safe` is the confidence target; `safe` is executed-action outcome. This prevents the common error of scoring rejected low-confidence proposals using successful fallback outcomes. The immediate counterfactual does not identify the full long-run causal effect of rejecting a proposal.

All evidence is simulator-specific. There is no real transport feedback integration, packet scheduler, codec validation, fairness model, competing adaptive flow, human QoE study or deployment certificate. Fixed trace-family shapes and few ID families limit claims of generalization. Synthetic capacity scaling is not a measured Internet trace corpus. The full paper protocol still requires convergence/scale checks, external trace and WebRTC/emulator validation, and sensitivity to simulator assumptions before strong deployment claims.
