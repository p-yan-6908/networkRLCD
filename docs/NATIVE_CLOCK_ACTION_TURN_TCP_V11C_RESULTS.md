# V11C capture and gate result

V11C was preregistered at commit `19f528a` with protocol SHA-256
`25a5bc102cb38cd50bb467dc547b901bde287fc703790fc44ee725cfc62665b3`. Its
separate zero-terminal-rate technical smoke passed TURN/media, clock, trace,
action assignment/readback, and terminal-cleanup checks. The smoke read no
frame-quality or treatment outcome telemetry.

The 64-session capture index is complete and all 64 session directories passed
file-checksum verification. Forty-two sessions sealed normally; 22 are
preserved as failed. The failures comprise 20 recorder native-media-validity
errors, one browser runtime exception, and one session interrupted when the
execution environment was replaced. That in-progress session was sealed as
failed and was not replayed. A committed recovery helper verified the prior 34
session seals and ran only the remaining registered IDs in the original order.

All 42 sealed sessions passed the unchanged TURN transport, actual-run clock,
measured-trace replay, action-assignment/readback, and terminal-cleanup gates.
The overall V11C gate fails because the registered acceptance requires all 64
sessions to seal. The analyzer was not run. No action effect, frame-quality,
delivery, QoE, or per-hold relay outcome was read; no controller was fitted or
promoted.

The technical capture failures were concentrated in the Vienna measured-rate
families (16 Vienna 5G and five Vienna LTE session attempts, counting the
interrupted attempt); one UCC 5G attempt also failed. The selected Vienna 5G
source windows contain 7–12 zero-service seconds per 18-second profile. This is
a plausible media-validity limitation to check against source traces, not an
outcome finding. V3–V10, the V11/V11A/V11B commissioning evidence, and V11C
remain separate and unpooled.

The complete raw capture, including failures and seals, is retained locally at
`~/.cache/networkrlcd/native-clock-action-turntcp-v11c/` and was copied to the
private archive without pruning. The pinned receipt is
[`docs/storage-receipts/native-clock-action-turntcp-v11c-20261013-01.json`](storage-receipts/native-clock-action-turntcp-v11c-20261013-01.json):
revision `b1497fa425f59c3b796d9ce5354ee58a0afe9667`, 2,727 inventoried files,
90,142,720 archive bytes, verified shard SHA-256, and a successful fresh
download probe. The archive excludes the separately licensed source clips.

The next validation step is an outcome-blind screen of alternative windows from
the same pinned measured sources, followed by technical smoke coverage of the
selected family/profile combinations. It must retain the existing media and
clock acceptance criteria and freeze a fresh protocol before any new action
capture. V10 remains closed; no controller fitting or threshold retuning is
indicated by this failed capture.
