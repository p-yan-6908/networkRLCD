"""Full stateful Python/JS mapping on synthetic loops; not native performance."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from test_native_action import bundle, observation, supported

from media_rl.native_presentation_feedback import presentation_packet
from media_rl.native_readback_guard import ReadbackGuardPolicy, receive_readback_packet
from media_rl.native_repair5_study import _close

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("guarded", [False, True])
@pytest.mark.parametrize("supported_cells", [False, True])
def test_full_actor_scores_history_ack_reset_and_rejection_state_parity(tmp_path, guarded, supported_cells):
    b = bundle()
    if supported_cells:
        supported(b, context="ready")
        supported(b, context="delayed")
    p = ReadbackGuardPolicy(b, guarded)
    descriptors = [dict(now=0, forward=None, returned=0, age=0, bwe=1000000)]
    for i, (forward, returned, age) in enumerate(
        [
            (90, 40, 30),
            (119.999, 30, 30),
            (120, 30, 30),
            (150, 0, 30),
            (70, 200, 30),
            (130, 30, 500),
            (130, 30, 500.000001),
            (90, 40, 0),
            (120, 0, 0),
            (70, 30, 0),
            (130, 30, 30),
            (90, 40, 30),
        ]
    ):
        descriptors.append(
            dict(
                now=1000 + i * 200,
                forward=forward,
                returned=returned,
                age=age,
                bwe=1000000 if i % 3 else 600000,
            )
        )
    descriptors.append(dict(now=6000, forward=90, returned=30, age=20, bwe=1000000))
    expected, cap = [], 450000
    for i, c in enumerate(descriptors):
        obs = observation(c["now"], cap=cap, bwe=c["bwe"])
        if c["forward"] is None:
            fb, side = None, None
        else:
            born = c["now"] - c["age"] - c["returned"] - c["forward"]
            a = receive_readback_packet(
                presentation_packet(i + 1, i + 1, born + c["forward"]),
                born,
                c["now"] - c["age"],
                guarded=guarded,
            )
            fb, side = a["canonical"], a["presentation"]
            fb["presented_fps"] = 30
            before = deepcopy((p.state.__dict__, p.last_change, p.hold_until))
            forged = dict(side, readback_ms=c["now"] + 1)
            with pytest.raises(ValueError):
                p.observe(obs, fb, forged)
            assert (p.state.__dict__, p.last_change, p.hold_until) == before
        d = p.observe(obs, fb, side)
        expected.append(d)
        cap = d["encoder_max_bitrate_bps"]
        p.acknowledge(cap, c["now"] + 1)
    assert expected[-1]["history_reset"]
    assert all(
        d["encoder_max_bitrate_bps"] == d["canonical_decision"]["encoder_max_bitrate_bps"]
        for d in expected
        if not d["fallback"]
    )
    inp = tmp_path / "input.json"
    inp.write_text(json.dumps(dict(bundle=b, guarded=guarded, descriptors=descriptors)))
    node = r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const a=JSON.parse(fs.readFileSync(process.argv[1])),m=await import(process.argv[2]),wire=await import(process.argv[3]);
const p=new m.RepairPolicy(a.bundle,a.guarded),out=[];let cap=450000;
for(const [i,c] of a.descriptors.entries()){
 const features=Array(16).fill(0);features[0]=c.bwe/4e6;features[7]=cap/4e6;features[8]=1;features[9]=1;
 const obs={sample_ms:c.now,features,content_features:[.2,.1,1]};let fb=null,side=null;
 if(c.forward!==null){const born=c.now-c.age-c.returned-c.forward,a1=wire.receivePresentationPacket(wire.presentationPacket(i+1,i+1,born+c.forward),born,c.now-c.age,null,a.guarded);fb=a1.canonical;side=a1.presentation;fb.presented_fps=30;
  const before=JSON.stringify([p.state,p.lastChange,p.holdUntil]);assert.throws(()=>p.observe(obs,fb,{...side,readback_ms:c.now+1}));assert.equal(JSON.stringify([p.state,p.lastChange,p.holdUntil]),before);
 }
 const d=p.observe(obs,fb,side);out.push(d);cap=d.encoder_max_bitrate_bps;p.acknowledge(cap,c.now+1);
}
process.stdout.write(JSON.stringify(out));
"""
    q = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            node,
            str(inp),
            (ROOT / "benchmarks/native_rtc/readback_guard_control.mjs").as_uri(),
            (ROOT / "benchmarks/native_rtc/readback_guard.mjs").as_uri(),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    _close(json.loads(q.stdout), expected)
