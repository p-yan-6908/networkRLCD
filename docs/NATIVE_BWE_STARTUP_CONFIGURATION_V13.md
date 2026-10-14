# Additional startup/configuration audit (outcome-free)

This append-only audit supplements the frozen V13 development diagnosis. It
does not change the V12 or V13 registrations or qualify any new source. It
uses recorder source configuration and the already checksum-verified clock/
BWE projection; no queue/drop/delivery/quality outcome is opened.

The inherited recorder initializes relay service at **5 Mbps** before the
first measured trace phase. During connection establishment the encoder
ceiling is **300 kbps**, then becomes **4 Mbps** before sender measurement
begins. Those setup conditions differ from the first source-rate sample.
The first measured BWE therefore belongs to an estimator with a pre-existing
setup history, not an estimator initialized from trace capacity. The first
phase is clock-mapped separately and early BWE can still reflect prior
traffic/feedback. The audit does not identify how much of the early BWE
spike arises from setup, probing or other GCC behavior.

The queue configuration is **30,000 wire bytes per direction**, with **25 ms
one-way propagation**. These are design parameters, not observed occupancy.
They imply the following full-buffer serialization times if a buffer were
full and a rate persisted:

| Scheduled rate | Full-buffer serialization time |
| --- | ---: |
| 22 kbps (Irish trough) | 10.91 s |
| 64 kbps (Murcia early plateau) | 3.75 s |
| 240 kbps | 1.00 s |
| 300 kbps (new source-screen floor) | 0.80 s |
| 5 Mbps setup service | 0.048 s |

Thus a one-second throughput trough can correspond to a much longer
possible queue/feedback history than its input duration. This makes a rate
average particularly poor evidence of settled observed BWE. It is a
configuration-derived mechanism compatible with the observed history
dependence, not a claim that any particular buffer filled or packet was
dropped. Establishing that causal mechanism would require a separate
preregistered experiment; the current support diagnosis does not inspect
delivery/drop telemetry to establish it.

V13 retains these transport/queue parameters. Its source screen removes
zero/deep-trough windows prospectively, and its native census measures actual
continuous BWE after longer conditioning. Those choices limit one source of
unsupported history, while the unchanged action-range and new repeated-state/
variation gates retain authority. They cannot guarantee qualification.
