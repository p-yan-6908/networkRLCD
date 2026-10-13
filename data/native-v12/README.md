# V12 source attribution and data licenses

The content and rate manifests describe new sources only. Originals and native
clips reside in the external working cache; no original media is included in
this repository. SHA-256, published checksum, revision, attribution and cache
path are attached to each source record.

King Penguins (The Nature Box, 2013) and Shirlan Waterfall (Jacopo188, filmed
2012) are CC BY-SA 3.0. Their silent 30-second, scaled/padded/transcoded clips
are adaptations under the same license. See `content_sources.json` and
[`CC BY-SA 3.0`](https://creativecommons.org/licenses/by-sa/3.0/).

The UCC Irish LTE and University of Murcia measured-throughput datasets are
CC BY 4.0. Their rate excerpts preserve attribution in `network_profiles.json`.
See [UCC's immutable record](https://zenodo.org/records/1219679),
[Murcia's immutable record](https://zenodo.org/records/15516876), and
[`CC BY 4.0`](https://creativecommons.org/licenses/by/4.0/).

NYU-METS database material, including the `nyu_lte` profile excerpts, is
available under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/),
with individual contents under [DbCL 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).
The database attribution is to Lifan Mei et al., *Realtime Mobile Bandwidth
Prediction using LSTM Neural Networks* (2019), and the subsequent Bayesian
fusion paper (2020). The source database and its notice remain available at
the pinned [NYU-METS revision](https://github.com/NYU-METS/Main/tree/886c73b1398457ba5f87faefe7a9ea3755e713f7).
The NYU excerpts retain these terms and are identified individually; the
surrounding original analysis code does not assert ownership of this data.

Rates are application-throughput histories replayed as symmetric local queue
service. Irish gaps and Murcia nominal cadence are explicit representation
assumptions. Sources are not live path traces or simulator data. Independent
campaigns, shared content and nested trace windows remain distinct in every
summary. These source screens contain no new native action outcomes.
