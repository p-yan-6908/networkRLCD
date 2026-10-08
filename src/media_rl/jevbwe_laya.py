"""Optional local-only Laya benchmark. No SDK/checkpoint import at module import.

Same causal numeric state and six actions, typed Choice. Offline event forecasts
are scored only on factual arms; never interpreted as observed counterfactuals.
"""

import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

import numpy as np

from .jevbwe import FEATURES, LAGS_MS, RATIOS, SCALES, STATE_DIM
from .jevbwe_experiment import dump, dump_gzip
from .jevbwe_rlcd import NumericModel, calibrate_binary, calibrate_choice
from .jevbwe_rlcd_experiment import arrays, choice_skill, inspect_data, seal, skill, sources

LAYA_ABI = "jevbwe_laya_typed_v1"
SDK_VERSION = "0.3.20"
MODEL_ID = "convaiinnovations/laya"
REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"
KEYS = ("r060", "r070", "r080", "r090", "r100", "r105")


def typed_request(state, config, *, diagnostics=False):
    state = np.asarray(state, dtype=float)
    if state.shape != (STATE_DIM,) or not np.isfinite(state).all():
        raise ValueError("same finite causal numeric history required for Laya")
    width = 2 * len(FEATURES) + 1
    payload = dict(
        abi=LAYA_ABI,
        feature_names=list(FEATURES),
        feature_scales=list(SCALES),
        lags_ms=list(LAGS_MS),
        layout="13 (normalized value, presence/freshness mask) pairs then causal snapshot age seconds",
        history=state.reshape(len(LAGS_MS), width).tolist(),
        action_ratios=dict(zip(KEYS, RATIOS)),
        event_threshold_qoe=config.success_qoe,
        outcome_attribution=f"encoder target within 5% of request, then issued RTT/2, then {config.study.credit_window_ms} ms delivered QoE; switch penalty only in utility event",
    )
    questions = {
        "bitrate": dict(
            type="choice",
            instructions=(
                "Report the distribution of the chosen bitrate action conditional on its settled utility QoE "
                "meeting the threshold, under a uniform randomized six-action intervention. This is NOT a "
                "probability each action is optimal. Use only supplied causal network/encoder history."
            ),
            criteria={
                key: f"Apply {ratio:.2f} times current BWE, fixed FEC/media mode and safety bounds."
                for key, ratio in zip(KEYS, RATIOS)
            },
        )
    }
    if diagnostics:
        for prefix, label in (
            ("u", "utility after requested-cap switch penalty"),
            ("d", "delivered QoE before the switch penalty"),
        ):
            for key, ratio in zip(KEYS, RATIOS):
                questions[f"{prefix}_{key}"] = dict(
                    type="choice",
                    instructions=(
                        f"If the next requested bitrate is {ratio:.2f} times BWE, will encoder-settled "
                        f"{label} be at least {config.success_qoe}? Forecast only; other arm outcomes are unobserved."
                    ),
                    criteria={
                        "A": "The settled event would fall below the threshold.",
                        "B": "The settled event would meet or exceed the threshold.",
                    },
                )
    return dict(state=payload, questions=questions)


def decode(response, *, diagnostics=False):
    answers = response.get("answers", {})

    def distribution(key, expected):
        answer = answers.get(key, {})
        p = answer.get("probabilities", {})
        if answer.get("type") != "choice" or set(p) != set(expected):
            raise ValueError("Laya must return typed probabilities for the exact options")
        values = np.asarray([p[k] for k in expected], dtype=float)
        # SDK rounds to four places. Reject zero support, do not silently smooth
        # quantized zeros into evidence for factual action discrimination.
        if not np.isfinite(values).all() or np.any(values <= 0) or abs(values.sum() - 1) > 0.001:
            raise ValueError("invalid/zero-support/truncated Laya distribution")
        return values / values.sum()

    p, q = distribution("bitrate", KEYS), {}
    if diagnostics:
        for prefix in ("u", "d"):
            q[prefix] = np.asarray([distribution(f"{prefix}_{key}", ("A", "B"))[1] for key in KEYS])
    return p, q


class LocalLaya:
    def __init__(self, model_dir, config, *, device="cpu"):
        root = Path(model_dir).resolve()
        if not root.is_dir():
            raise ValueError("explicit existing local Laya checkpoint required; no auto-download")
        try:
            version = importlib.metadata.version("laya")
        except importlib.metadata.PackageNotFoundError as error:
            raise ValueError("optional benchmark needs laya==0.3.20; not a default dependency") from error
        if version != SDK_VERSION:
            raise ValueError("requires inspected laya==0.3.20 SDK")
        files = {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file() and ".cache" not in p.parts
        }
        if not files or not any(name.endswith((".safetensors", ".pt", ".bin")) for name in files):
            raise ValueError("local checkpoint weights/file hashes required")
        self.identity = dict(
            abi=LAYA_ABI,
            kind="local_pretrained_laya",
            sdk_version=version,
            model_id=MODEL_ID,
            operator_claimed_revision=REVISION,
            local_file_sha256=files,
            remote_revision_verified=False,
            device=device,
            pretrained_weights_changed=False,
        )
        self.config = config
        old = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "USE_TF")}
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", USE_TF="0")
        try:
            import laya

            self.agent = laya.load(str(root), device=device, fast=False)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.last_request = self.last_response = None

    def predict(self, state, *, diagnostics=False):
        request = typed_request(state, self.config, diagnostics=diagnostics)
        encoded = json.dumps(request["state"], sort_keys=True, separators=(",", ":"), allow_nan=False)
        max_len, head_max_len = 8192, 512
        if len(self.agent.tok.encode(encoded, add_special_tokens=False)) > max_len - head_max_len - 32:
            raise ValueError("Laya would truncate shared causal history; refuse benchmark")
        response = self.agent.predict(
            encoded, request["questions"], max_len=max_len, head_max_len=head_max_len
        )
        self.last_request, self.last_response = request, response
        return decode(response, diagnostics=diagnostics)


class LayaModel(NumericModel):
    def __init__(self, artifact, backend):
        super().__init__(artifact)
        self.backend = backend

    def policy_forecast(self, state):
        p, _ = self.backend.predict(state)
        log_p = np.log(p) / self.artifact["laya_choice_calibration"]["temperature"]
        p = np.exp(log_p - np.max(log_p))
        return None, p / p.sum()  # no invented online binary-event predictions


def prepare(config, training_path, backend, out):
    training_path, out = Path(training_path), Path(out)
    if out.exists():
        raise FileExistsError(out)
    artifact = json.loads((training_path / "model.json").read_text())
    if artifact["source_sha256"] != sources() or artifact["fitting_hash"] != config.fitting_hash():
        raise ValueError("Laya must use the same frozen numeric study/source contract")
    data = {
        role: json.loads(gzip.decompress((training_path / f"{role}_cohorts.json.gz").read_bytes()))
        for role in ("train", "calibration", "qualification")
    }
    support = inspect_data(data)
    if not support["known_randomization_and_positivity"]:
        raise ValueError("Laya requires known factual arm propensities")
    out.mkdir(parents=True)
    observations, raw_log = {}, []
    for role in ("calibration", "qualification"):
        observations[role] = []
        for row in data[role]:
            if row["censored"]:
                continue
            p, q = backend.predict(row["state"], diagnostics=True)
            observations[role].append(dict(row=row, p=p, q=q))
            raw_log.append(
                dict(
                    role=role,
                    episode=row["episode"],
                    command_ms=row["command_ms"],
                    request=backend.last_request,
                    response=backend.last_response,
                )
            )
    dump_gzip(out / "typed_requests_and_responses.json.gz", raw_log)
    dump(out / "backend_identity.json", backend.identity)
    reports, calibrations = {}, {}

    class LoggedNet:
        def __init__(self, logits):
            self.logits = logits

        def __call__(self, x):
            return self.logits[np.rint(x[:, 0] * len(self.logits)).astype(int)]

    for prefix, target in (("u", "reward"), ("d", "delivered_reward")):
        cal_obs, qual_obs = observations["calibration"], observations["qualification"]
        _, a, y, mu = arrays([o["row"] for o in cal_obs], target, config)
        logits = np.asarray([np.log(o["q"][prefix] / (1 - o["q"][prefix])) for o in cal_obs])
        conditional_cal = calibrate_binary(logits[np.arange(len(a)), a], y, mu)
        blind_cal = calibrate_binary(logits.mean(axis=1), y, mu)
        qlogits = np.asarray([np.log(o["q"][prefix] / (1 - o["q"][prefix])) for o in qual_obs])
        # Index-only inputs for scoring already logged immutable forecasts, NOT new model requests.
        indexed = []
        for i, o in enumerate(qual_obs):
            state = [0.0] * STATE_DIM
            state[0] = i / len(qual_obs)
            indexed.append({**o["row"], "state": state})
        temp = dict(temperature=1.0, method="diagnostic_event_forecast")
        reports[target] = skill(
            indexed,
            LoggedNet(qlogits),
            LoggedNet(qlogits),
            np.zeros(STATE_DIM),
            np.ones(STATE_DIM),
            dict(binary=conditional_cal, choice=temp),
            dict(binary=blind_cal, choice=temp),
            target,
            config,
        )
        calibrations[target] = dict(conditional=conditional_cal, blind=blind_cal)
    cal_obs = observations["calibration"]
    _, a, y, mu = arrays([o["row"] for o in cal_obs], "reward", config)
    choice = calibrate_choice(np.asarray([o["p"] for o in cal_obs]), a, y, mu)
    qobs = observations["qualification"]
    probabilities = np.exp(np.log(np.asarray([o["p"] for o in qobs])) / choice["temperature"])
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    reports["choice"] = choice_skill([o["row"] for o in qobs], probabilities, config)
    interval = reports["choice"]["episode_gain_interval"]
    choice_passed = reports["choice"]["passed"]
    qualified = (
        support["no_outcome_dependent_censoring"]
        and choice_passed
        and all(r["passed"] for r in reports.values())
    )
    positive = [o["row"] for o in cal_obs if o["row"]["reward"] >= config.success_qoe]
    laya_artifact = dict(artifact)
    laya_artifact.update(
        laya_abi=LAYA_ABI,
        laya_backend=backend.identity,
        laya_choice_calibration=choice,
        action_value_passed=bool(qualified),
        supports_causal_discrimination=bool(qualified),
        numeric_policy_used=False,
        laya_forecast_qualification=reports,
        laya_event_calibration=calibrations,
        calibration_rows=[sum(r["action_index"] == a for r in positive) for a in range(6)],
        calibration_episodes=[
            len({r["episode"] for r in positive if r["action_index"] == a}) for a in range(6)
        ],
    )
    dump(out / "model.json", laya_artifact)
    dump(
        out / "qualification.json",
        dict(
            qualification=reports,
            known_randomization=support,
            choice_vs_uniform_interval=interval,
            choice_passed=bool(choice_passed),
            weights_changed=False,
            promoted=False,
        ),
    )
    seal(out)
    return LayaModel(laya_artifact, backend)
