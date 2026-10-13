"""Boundary and blinding checks for the prospective V12 validation."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analysis = load("v12_analysis_test", "tools/analyze_native_v12.py")
runner = analysis.runner


class V12DesignTests(unittest.TestCase):
    def test_missing_quality_remains_undefined(self):
        hold = {"source_frames": 10, "on_time_frames": 0, "psnr_frames": 0,
                "psnr_sum_db": 0, "relay": {"guaranteed_wire_bytes": 1000, "guaranteed_dropped_wire_bytes": 28}}
        result = analysis.bucket([hold])
        self.assertIsNone(result["mean_ontime_psnr_db"])
        self.assertEqual(result["on_time_fraction"], 0)
        self.assertEqual(result["mean_guaranteed_wire_bytes_per_window"], 1000)

    def test_original_frame_weighting_is_preserved(self):
        holds = [{"source_frames": n, "on_time_frames": n, "psnr_frames": n,
                  "psnr_sum_db": n * psnr, "relay": {"guaranteed_wire_bytes": 1000, "guaranteed_dropped_wire_bytes": 0}}
                 for n, psnr in ((9, 20), (1, 40))]
        self.assertEqual(analysis.bucket(holds)["mean_ontime_psnr_db"], 22)

    def test_failed_qualification_prevents_any_outcome_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "verify_registration"), mock.patch.object(runner, "read", return_value={}), \
                    mock.patch.object(runner, "gate", return_value={"passed": False}), \
                    mock.patch.object(analysis, "load_hold", side_effect=AssertionError("outcome opened")) as loader:
                with self.assertRaisesRegex(ValueError, "before any outcome file"):
                    analysis.analyze(Path(tmp) / "analysis.json")
                loader.assert_not_called()

    def test_native_development_readbacks_pass_stricter_sender_gate(self):
        root = runner.DEVELOPMENT_ROOT
        if not (root / "protocol.json").exists():
            self.skipTest("sealed native development evidence not restored")
        protocol = json.loads((root / "protocol.json").read_text())
        for trial in protocol["trials"]:
            result = runner.sender_gate(root / "sessions" / trial["id"], trial, protocol)
            self.assertTrue(result["passed"], trial["id"])

    def test_logged_propensity_or_arm_tamper_is_rejected(self):
        root = runner.DEVELOPMENT_ROOT
        if not (root / "protocol.json").exists():
            self.skipTest("sealed native development evidence not restored")
        protocol = json.loads((root / "protocol.json").read_text())
        trial = next(t for t in protocol["trials"] if not t["support_only"])
        original = json.loads((root / "sessions" / trial["id"] / "sender_observations.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            for field, replacement in (("arm", 99), ("propensity", .4)):
                sender = copy.deepcopy(original)
                for row in sender["decisions"]:
                    if row.get("actuator_assignment"):
                        row["actuator_assignment"][field] = replacement
                path = Path(tmp) / "sender_observations.json"
                path.write_text(json.dumps(sender))
                self.assertFalse(runner.sender_gate(Path(tmp), trial, protocol)["passed"])


if __name__ == "__main__":
    unittest.main()
