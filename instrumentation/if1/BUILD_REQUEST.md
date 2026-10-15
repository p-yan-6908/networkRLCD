# IF1 bounded builder request

This is a design artifact. There is no IF1 C++ patch, binary or completed build.
Run the frozen feasibility gate before checkout, dependency installation or
compilation. An admitted builder is required; Docker in this runtime does not
provide more disk or memory.

## Pinned inputs

- Chromium154.0.8037.57:
  `73c14f6228d7cd537c855007e8f88678969cc0eb`.
- Its DEPS-pinned WebRTC:
  `3a8b0c76e6b7bf0e72141047f82eb2c3f4862c8d`.
- Depot_tools:
  `382c208a9973e1a6c0867b6d8664dc6dc9116e30`;
  disable its automatic updating for this build.
- Chromium's compiler package:
  `llvmorg-24-init-3796-g20e97c4b-27`. GN, sysroot, libraries and other CIPD
  instances must resolve from these exact DEPS/hooks, then enter the artifact
  manifest with their resolved IDs and SHA256. Do not replace Clang with GCC.
- Both control and instrumented binaries use the accompanying identical
  `args.gn`, same host/package inventory and dependencies. Seal the unmodified
  control before applying the diagnostic patch. Preserve both binary hashes,
  full patch, command log, dependency lock, tool versions and build outcomes.

Use a dedicated external checkout. A shallow/no-history checkout may reduce
history storage; it does not waive the admission gate. No data, source tree or
build artifact goes into the project cache or any previous capture directory.
Do not install a third-party binary and call it an IF1 build.

## Implementation scope

One native PC-scoped diagnostic context, explicit lifetime/transport/controller/
pacer/SSRC registry, producer hooks from `hook-map.json`, and one experimental
PeerConnection-bound Blink snapshot endpoint. Use the existing per-PC Environment
construction to carry context. Ordinary file logs, guessed trace identities and
an allowlist bypass do not implement this interface.

Maximum28 production files and2000 handwritten changed lines (generated bindings
excluded), eight engineer-hours, one initial build plus one compiler-repair cycle,
six total build wall-hours and120GB incremental external peak. No algorithm,
field-trial, estimator initialization, encoder, network or managed-policy change.
Missing ingress-to-consumption lineage or real pacer debt cannot be replaced
with proxies to stay under budget. Stop if the scope cannot fit.

## Admission and runtime

Require130GB free (120GB peak plus10GB reserve), >=16GiB memory limit and four
effective CPU cores for the bounded build. Official pinned Linux instructions
independently require at least100GB free. Record actual cgroup limits. Do not
prune frozen evidence to create build space, provision a paid runner, change
cloud configuration or dispatch a workflow as a resource workaround.

Preserve proxy/CA trust when fetching dependencies. A new container must follow
the session's proxy and CA instructions; never disable TLS verification. Record
exact hostname/response for a failed dependency. A builder may be separate from
the acquisition runtime; its artifact still needs verified provenance and all
new native qualification gates on the actual acquisition host.

## Alternatives and scope

The official WebRTC development page estimates a6.4GB Linux checkout. A standalone
libwebrtc harness is not ruled out by Chromium's100GB requirement. It has no
Chromium/Blink bridge, browser scheduling or managed-browser acquisition path.
Building a new sender/receiver, media, signaling, clock and TURN harness would
be a separately named experimental target requiring its own bounded plan and
all fresh qualification. It is not a drop-in build of IF1 and cannot qualify
Chromium timing or inherit browser support claims. No such substitution is
made after the IF1 resource decision.
