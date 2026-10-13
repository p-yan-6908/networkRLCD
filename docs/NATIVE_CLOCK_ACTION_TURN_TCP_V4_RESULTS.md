# TURN/TCP action V4 gate result

V4 completed all 32 registered sessions and sealed each one. The hash-only
integrity command passed before any outcome inspection:

- protocol SHA256: 1937b2a88ca08f1a7d25382a09aacab36c80c28bcac79404add1f5346b739a2c
- capture-index SHA256: 78221a758a856f05de66a49cd07bad9d38f9a5e35ae33f6f54fb29c513f0798a
- actual-run gate SHA256: 059933b7f0c1b37121b77adb2cf9358548c0cead861c569107a63a17e6e0abb0

The outcome-blind gate failed, so sender observations, frame-quality outcomes,
and per-hold relay offers were not opened. V4 produces no per-hold cost/QoE
estimate and no controller result.

## Actual-run clock checks

Twenty-nine sessions passed the seven-marker held-out mapping check. Three
missed coverage: two at marker m0002, the high-phase request, and one at marker
m0004, the collapse-phase request. Their widest feasible intervals were
4.095 ms, 4.191 ms, and 3.395 ms, all below the 50 ms width limit. The
independent coverage requirement still failed for those sessions.

## TURN and queue checks

All 32 sessions completed relay-only TURN/TCP gathering and connected with
nominated pairs. The managed-policy hash was unchanged in all 32 sessions.
Queue source checks, send-error checks, capacity bounds, and byte-conservation
checks passed for all sessions.

The V4 plan also required zero overflow drops. Eight sessions recorded
accounted A-to-B queue overflow: 82 packets and 89,360 wire bytes total. This
violated the registered V4 transport gate, so V4 remains unqualified and none
of those drops is interpreted as a treatment effect. The gate's transport
qualification count is 24/32.

The outcome-blind, machine-readable evidence is
[native-clock-action-turntcp-v4-gate-diagnostic-only.json](../reports/native-clock-action-turntcp-v4-gate-diagnostic-only.json)
(SHA256 390bfb7fc961e7df30708e2a3b8cac123a71ad5067c815935f3895b820cf8ad5).
It contains only capture status, policy, marker, ICE, queue-ledger, and gate
diagnostics. No sender or frame outcome files were read.

V4's zero-overflow rule was too strict for a study whose delivery-cost endpoint
includes queue loss. A future independent registration must preserve drops as
accounted delivery outcomes while still requiring exact queue accounting,
bounded service, no unexpected endpoints, and no send errors. It must also
improve the marker arrangement around phase boundaries. V4 will remain frozen
and excluded.
