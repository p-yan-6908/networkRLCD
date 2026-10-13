# V2 acquisition startup failure and technical continuation

The first capture attempt for the committed
[V2 action assay](NATIVE_TURN_ACTION_ASSAY_V2.md) stopped before it created a
peer. Chromium failed to create its singleton Unix socket because the nested
temporary path exceeded the platform socket-path limit. The browser DevTools
endpoint never opened, the probe page never ran, and the attempt recorded zero
native action assignments, peer manifests, wire events or outcomes. This is an
acquisition startup failure, not an efficacy result.

The failed attempt remains separate at
`/home/agent/.cache/networkrlcd/working/native-turn-action-assay-v2/`. Its
three-file, 58,813-byte inventory was verified against the committed partial
inventory. The receipt, inventory and original spec are retained under
`reports/native-turn-action-assay-v2/` and
`configs/native_turn_probe_v2_action_assay.json`. No files in the failed raw
root were replaced or removed.

The technical continuation changes only the external output roots, shortening
the nested temporary path. It retains the same committed capture and analysis
sources, six action assignments, all 64 scene/trace/repetition cells, action
seeds, randomized trial order, endpoints and inference rules. Its separate
specification pins the prior failure and inventory hashes, and the runner
requires its unique fresh raw/report roots. This is a new full acquisition
after a pre-observation startup failure; the failed attempt contributes no peer
and no data to the registered contrast family.

The continuation writes raw evidence under
`/home/agent/.cache/networkrlcd/working/v2a/` and compact output under
`reports/native-turn-action-assay-v2a/`. It remains a single-host factual
development assay and cannot support real-network, learned-policy, safety or
promotion claims.

Reproduce the continuation only with its committed specification:

    uv run --frozen python -m media_rl.native_turn_probe_v2 \
      --spec configs/native_turn_probe_v2_action_assay_technical_continuation.json \
      --raw-out /home/agent/.cache/networkrlcd/working/v2a \
      --report-out reports/native-turn-action-assay-v2a

Then run the V2 independent wire audit and action analysis using that raw path,
compact report and the same commands documented in the V2 protocol. Preserve
the failed acquisition and its negative technical result alongside any
continuation result.
