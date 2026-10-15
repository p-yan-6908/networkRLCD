# Publication edition: the negative result

[Read the paper](networkRLCD-negative-result-publication.pdf) ·
[LaTeX source](main.tex) ·
[Publication review](../../docs/PUBLICATION_READINESS_RD1.md)

**Scientific stopping decision:** RD1 at `050e4f4`. This is a publication pass,
with evidence through completed PO1 (`f109ab2`), not a successor study. The
earlier `paper/main.tex`, RD1 edition at `paper/negative-result/`, all reports,
protocols, receipts and reserved allocations are unchanged.

The central contribution is the distinction between bounded native causal
findings and the prerequisites that did not qualify: reproducible conditional
state, internal causal observability, robust synthetic action discrimination
and useful calibrated uncertainty. No new effect is estimated or pooled.
The paper proposes no successor and keeps the PO1 stop exact.

## Traceability and checks

- [Claim map](../../data/publication-readiness-rd1/claim-traceability.json):
  43 manuscript blocks, frozen source hashes and locators, classifications,
  and independence units. Project references are pinned at `050e4f4`.
- [Preservation inventory](../../data/publication-readiness-rd1/prior-files-sha256.json):
  all 1,698 files tracked at `02c3693`, including RD1's sources and PDF.
- [Verification receipt](../../reports/publication-readiness-rd1-audit.json)
  and [build receipt](../../reports/publication-readiness-rd1-paper-build.json).

Run the publication verification, which reads committed documents and reports
without accessing raw sessions or fitting anything:

```sh
python tools/audit_publication_readiness_rd1.py
```

This checks provenance and copied numbers; it is not an automated proof of the
manual causal interpretation. It does not regenerate or alter old freezes.

## Building the document

From the repository root, choose an external build directory:

```sh
mkdir -p ~/.cache/networkrlcd/publication-readiness-rd1/paper-build
cd paper/negative-result-publication
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory="$HOME/.cache/networkrlcd/publication-readiness-rd1/paper-build" main.tex
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory="$HOME/.cache/networkrlcd/publication-readiness-rd1/paper-build" main.tex
```

The committed PDF is hash-bound in the build receipt. A local rebuild may have
different PDF metadata; no scientific pipeline or `make paper-evidence` is
needed. Raw native data remain private and licensed media remain external;
publication of sources and summary reports is not a public raw-data release.
