# V13 sources

`sources.json` pins two new licensed video productions and original packet
service traces from two Mahimahi collection bundles. The bundles share one
measurement program; profiles, directions, overlapping windows and repetitions
are nested. New native content/network combinations remain untouched.

The network derivatives retain GPLv3 and their complete upstream source URLs,
Git blob SHA-1, local SHA-256 and service-opportunity semantics.
`LICENSE-network-GPL-3.0.txt` preserves the upstream distribution license.
Kampar and Volga video derivatives retain their respective CC BY 4.0/3.0
attribution and rights. Originals and 45-second clips remain outside Git.

The source helper's operational selection is a nineteen-bin geometric-mean
hint, indices `[0,19)`, with every full 36-second rate in `[0.3,10]` Mbps.
Its comment describing that hint as wholly pre-decision is imprecise: source
bin 18 straddles the native 18-second decision boundary. The scientific
registration explicitly documents this distinction. This input-only hint is
never a support measurement or a treatment-effect covariate. Continuous
state comes from the separately recorded eleven native pre-action samples
and is frozen from the outcome-free support census.

Full byte/provenance verification is provided by
`tools/prepare_native_v13_sources.py`; the frozen scientific workflow is in
`docs/NATIVE_CONTINUOUS_VALIDATION_V13_PLAN.md`.
