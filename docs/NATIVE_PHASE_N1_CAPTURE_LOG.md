# Native Phase N1: capture log

A procedural record of the N1 capture. It holds no outcome: no rate, no contrast, no variance
and nothing labelled by arm. Outcomes are read only through the registered `interim` and
`final` routines of the [preregistration](NATIVE_PHASE_N1_ACTUATOR_QUALIFICATION.md).

## 2026-10-09: before the first capture

- Go-ahead and importer's assertion: recorded in the
  [acquisition log](NATIVE_PHASE_N1_ACQUISITION_LOG.md).
- Sealed plan: `results/native-actuator-qualification-n1-plan/protocol.json`, 21 sources,
  stage one is planned positions 0 to 12, `outcomes_observed` false.
- Machine: Apple M1, 8 cores, 8 GB, macOS 27.0 (26A428), on mains power.
- Browser and runtime: Google Chrome 154.0.8037.98 (`--headless=new`, a fresh temporary
  profile per peer), Node v26.8.2.
- The collector runs one peer at a time. Nothing else heavy is run on the machine during the
  capture. The owner's own desktop session, including a Chrome window, stays open; that
  background load is not controlled.
