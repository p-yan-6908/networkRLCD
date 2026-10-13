# TURN/TCP action V3 diagnostic result

V3 is preserved as a failed acquisition. Its registered protocol hash is
a599601b5182ca4e3de24ec3a93cd422f0afba11c7de613d7196433f2affd4d6 and its
capture-index hash is
2fac8af41adcc378b63951f3e84b30919462abda5a28c779aa6ca120d96257d8.
The raw capture remains at
/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v3/.

The hash-only integrity command passed for the full inventory: 32 planned,
zero sealed, 32 failed, and no outcome telemetry was read by that command.
The sessions did reach and complete the registered schedule. Their uniform
collector failure was the post-run guard:

> media bypassed the selected TURN relay or did not progress through the owned queue

The code inspection identified why that guard rejected every session: the
assertion required remote_candidate_type on each phase snapshot, while the
snapshot object recorded only remote_candidate_address. The condition was
therefore false regardless of the valid candidate-type evidence recorded
before the phase loop. V3 remains failed; no session was reclassified and no
treatment estimate was produced.

## Checksum-verified diagnostics

All 32 sessions completed relay-only ICE gathering with one TURN/TCP candidate
per peer. Both peers connected with nominated/succeeded TURN-backed pairs, and
all 32 policy checks preserved the same managed-policy hash,
10ee54ed22fc23337096004f8248d6ea977f059149386e0f9e70c4b77d9db6b5.

Queue-event diagnostics show forwards in both directions in all 32 sessions:

- A to B: 30,726 total; 743–1,219 per session.
- B to A: 15,403 total; 448–497 per session.

These are whole-session transport checks. They are not per-hold delivery-cost
estimates and do not qualify the panel for treatment analysis.

The V3-specific five-marker held-out affine check passed for 29 of 32 sessions.
Three sessions missed full held-out coverage: scene 01 repetition 1 at ratio
0.65, scene 00 repetition 1 at ratio 0.65, and scene 01 repetition 0 at ratio
0.65. The widest feasible held-out interval was 5.2921 ms, under the 50 ms
limit; the independent full-coverage criterion still failed for those
sessions. No per-hold relay join was made.

The machine-readable, outcome-blind diagnostic is
[native-clock-action-turntcp-v3-diagnostic-only.json](../reports/native-clock-action-turntcp-v3-diagnostic-only.json)
(SHA256 bce4517a5e6003516b01168eeb15c486e934acdd867185c2dcc26001e4b477e4).
It contains only checksum-verified marker, ICE, policy, and queue-event
diagnostics. Sender observations and frame-quality outcomes were not examined.

## TURN/TCP media preflights

The direct relay-only TURN/TCP preflight passed with 32 encoded and decoded
video frames in each direction and unchanged managed policy. Its output hash is
b34ffed02189b4865268c37d701a75252ce2fc19ec5210cb9882bf7cc2d71aaa.

The first owned-queue preflight connected and delivered 14 decoded frames in
each direction, but stopped at 48 and 52 forwarded packets, below its separate
100-packet minimum. That failed attempt is preserved at
/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v1.json
(SHA256 c19408caee9dadea359ec32f9542c2c36269a84e0ac75839c1b9348a9ef151fa).

The second preflight waited for both media and queue floors and passed. It
gathered relay-only candidates on both peers, selected nominated TURN-backed
pairs, decoded 39 and 40 frames, and forwarded 113 and 114 packets in the two
directions. The queue reported zero drops, unexpected sources, and send errors;
byte conservation was within 3e-11 bytes. The policy hash remained unchanged.
Its output is
/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v2.json
(SHA256 a45a8e2a9fec3303a8c09afb8d44896b8b642692fbc43a37d9917e768c345061).
No bitrate action, per-hold cost, or QoE was evaluated by either preflight.

## Follow-up

A fresh independent V4 panel is registered with new scene and assignment-order
seeds. It records the missing phase candidate-type field, checks queue
forwarding in both directions, and uses seven actual-run clock markers with
four fit markers and three held-out markers. V3 remains unchanged and excluded.
The V4 results will be analyzed only after every planned session passes its
checksum, transport, media, policy, and actual-run clock gates.
