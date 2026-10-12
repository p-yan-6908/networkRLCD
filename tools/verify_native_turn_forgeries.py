"""Try resealed semantic forgeries against actual native evidence in temporary copies."""

import argparse
import copy
import gzip
import json
import tempfile
from pathlib import Path

from media_rl.native_turn_audit import audit_sender, audit_wire
from media_rl.native_turn_probe import sha, validate_peer


def verify(capture):
    capture = Path(capture)
    trial = json.loads((capture / "spec.json").read_text())["trials"][0]
    root = capture / trial["id"]
    original, _ = validate_peer(root, trial)
    audit_sender(original)
    audit_wire(root, original, trial)
    results = {}
    for kind in (
        "feature",
        "future_encoded_bytes",
        "cap_readback",
        "propensity",
        "meter_counter",
        "sidecar_clock",
        "RGB",
        "wire_service",
    ):
        peer = copy.deepcopy(original)
        if kind == "feature":
            peer["decisions"][10]["observation"]["features"][0] += 0.1
        elif kind == "future_encoded_bytes":
            peer["decisions"][10]["encoded_snapshot"]["total_bytes"] += 100
        elif kind == "cap_readback":
            next(r for r in peer["decisions"] if r["ack_ms"] is not None)["actuation_readback"][
                "encoder_max_bitrate_bps"
            ] += 1
        elif kind == "propensity":
            peer["decisions"][0]["assignment"]["propensity"] = 0.5
        elif kind == "meter_counter":
            peer["encoded_meter"]["events"][0]["total_bytes"] += 1
        elif kind == "sidecar_clock":
            peer["decisions"][10]["encoder_response"]["sample_ms"] += 10
        elif kind == "RGB":
            next(r for r in peer["observations"] if r["quality"] is not None)["quality"]["rgb_mse"] += 1
        with tempfile.TemporaryDirectory(prefix="networkrlcd-turn-forgery-") as temp:
            forged = Path(temp)
            (forged / "peer.json").write_text(json.dumps(peer))
            if kind == "wire_service":
                changed = False
                with gzip.open(root / "events.jsonl.gz", "rt") as raw:
                    with gzip.open(forged / "events.jsonl.gz", "wt") as output:
                        for line in raw:
                            event = json.loads(line)
                            if not changed and event["kind"] == "service":
                                event["service_wire_bytes"] += 1
                                changed = True
                            output.write(json.dumps(event) + "\n")
            else:
                (forged / "events.jsonl.gz").symlink_to((root / "events.jsonl.gz").resolve())
            manifest = json.loads((root / "manifest.json").read_text())
            manifest.update(
                peer_sha256=sha(forged / "peer.json"), events_sha256=sha(forged / "events.jsonl.gz")
            )
            (forged / "manifest.json").write_text(json.dumps(manifest))
            try:
                own, _ = validate_peer(forged, trial)
                audit_sender(own)
                audit_wire(forged, own, trial)
            except ValueError as error:
                results[kind] = dict(resealed=True, rejected=True, reason=str(error))
            else:
                raise ValueError("resealed forgery accepted: " + kind)
    return dict(
        abi="native_turn_probe_v1_resealed_forgery_audit",
        added_after_capture=True,
        trial=trial["id"],
        cases=results,
        source_manifest_sha256=sha(root / "manifest.json"),
        verifier_sha256=sha(__file__),
        original_evidence_modified=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("fresh forgery receipt required")
    receipt = verify(args.capture)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
