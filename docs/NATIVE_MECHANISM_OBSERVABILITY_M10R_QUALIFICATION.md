# M10R prospective instrumentation qualification

Scientific preregistration `597f3eac529930a329dde9c4b017e7d9217bfe12`.
All four fresh originals pass unchanged clocks, TURN/TCP, readback, initialization,
replay, actual sampling and cleanup, plus registered mechanism receipt/schema
and post-cutoff persistence gates. No future labels or mechanism associations
were evaluated. The separate eight-original development panel is unopened at
this decision. M10 remains failed and its development allocation untouched.

```json
{
  "qualified_originals": 4,
  "cleanup_duration_ms_range": [
    1324.3875699999917,
    1460.0590489999886
  ],
  "post_cutoff_persistence_ack_ms_range": [
    322.2999999821186,
    377.7000000178814
  ],
  "maximum_main_native_gap_ms": 88.30000001192093,
  "maximum_relay_receipt_gap_ms": 125.5,
  "maximum_relay_ack_ms": 26.900000005960464,
  "maximum_full_clock_width_ms": 1.163474583059724,
  "maximum_beginning_clock_width_ms": 2.182921955477525,
  "optional_channels_qualified_every_original": {
    "observed_feedback_counter_age": true,
    "rtcp_rtt": true
  },
  "minimum_rtcp_available_fraction": 1.0,
  "minimum_observed_age_available_fraction": 1.0,
  "development_unopened_at_decision": true,
  "future_labels_read": false,
  "receiver_outcomes_read": false
}
```
