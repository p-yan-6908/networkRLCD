# V2a inventory failure and V2b technical continuation

The committed V2 output-path continuation captured and sealed all 64 peers, but
its final frozen raw-inventory check rejected Chromium runtime artifacts that
the runner had placed under the raw root's `TMPDIR`: 64 `SingletonCookie`
symlinks and 64 `SingletonSocket` Unix sockets. This does not pass the
registered inventory gate. The run is excluded from all action or endpoint
analysis; the independent wire audit was not run and no outcome values were
opened.

The complete regular-file inventory contains 323 files totaling 668,346,026
bytes. A forensic inventory also records every symlink target and socket path
without following them. The inventory was independently recomputed and
reverified against the unchanged external raw tree. The unqualified capture and
its receipts remain at:

- Raw bytes: `/home/agent/.cache/networkrlcd/working/v2a/`
- Failure receipt: [capture-failure.json](../reports/native-turn-action-assay-v2a/capture-failure.json)
- Forensic inventory: [failed-raw-inventory.json](../reports/native-turn-action-assay-v2a/failed-raw-inventory.json)

V2b keeps the inventory rule intact. Its only capture-source change places
Chromium's ephemeral `TMPDIR` in a short, private system-temporary directory;
the runner removes that directory before enumerating raw evidence. The 64
trial assignments, seeds, action arms, outcomes, estimator, confidence family,
and claim limits are unchanged. A distinct raw path and report path prevent
overwrite, and the new specification pins both prior technical failures and
their inventories. V2a is not pooled with V2b and contributes no efficacy
estimate.

V2b is still factual development evidence on the same local TURN/TCP path. It
cannot support real-network, learned-policy, safety or promotion claims.
Its separately committed specification is
[native_turn_probe_v2_action_assay_inventory_continuation.json](../configs/native_turn_probe_v2_action_assay_inventory_continuation.json).
Reproduce only from that specification:

    uv run --frozen python -m media_rl.native_turn_probe_v2 \
      --spec configs/native_turn_probe_v2_action_assay_inventory_continuation.json \
      --raw-out /home/agent/.cache/networkrlcd/working/v2b \
      --report-out reports/native-turn-action-assay-v2b

After capture, require the original full inventory gate, independent wire
replay, and registered contrast analysis. Preserve both prior failures and all
unarchived raw bytes.
