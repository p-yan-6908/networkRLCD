# M6/M6R feature-availability clarification

The frozen plans' statement that native packet-loss and end-to-end delivered-
throughput counters were not retained in M5 is too broad. The **100 ms sender
observation ABI** retains RTP bytes sent, RTCP RTT and encode counters/features,
but no native packet-loss or received-byte series. That is the feature stream
used by the registered sender candidates.

The recorder schema separately retains **coarse phase-end receiver snapshots**,
including `received_mbps` and cumulative `packets_lost`, alongside media-progress
and other snapshot fields. They are not a regular sender-side history series.
Their schema is visible in the frozen recorder; no new receiver snapshot values,
QoE, quality or action outcomes were decoded to make this clarification.

M6R's actual registered candidates remain unchanged: RTP **send** rate is not
delivered throughput; relay **forwarded wire** rate is not receiver delivery or
timely-quality; relay overflow is not native end-to-end packet loss. None of
these measurements is relabeled to fill an unavailable sender feature.

The phase-end receiver statistics are excluded from the frozen candidate code.
Using receiver-assisted rate/loss information in a future study would require
prospectively defined observations, source timestamps and availability/feedback
checks at the matching cutoff. It cannot be substituted into the chosen M6R
state or used to retune this validation. The original plans, calipers, selected
state, native allocation and all qualification gates remain byte-for-byte
unchanged. This clarification corrects the availability description only.
