# Current manuscript: the negative-result edition

**Entry point:** [main.tex](main.tex), *History dependence without qualified
common support: limits of learned native bitrate control*.

This edition implements the completed-PO1 research decision at
[RD1](../../docs/RESEARCH_DECISION_RD1.md). It replaces the controller-centric
framing with a bounded negative result and its identification implications.
It is a retrospective synthesis of frozen results, not a new experiment,
meta-analysis, state search or controller proposal. The existing
`paper/main.tex`, generated evidence and every old freeze remain byte-identical.
They are earlier editions, not the current scientific decision.

The new evidence table is rendered from committed report values by
`tools/synthesize_research_decision_rd1.py`. Source documents, machine-readable
reports and storage receipts are hash-bound in
`data/research-decision-rd1/evidence-ledger.json`. The claim ledger separates
local supported effects, unsuccessful registered recipes, unestimable targets,
causal-observability limits, practical admission limits and synthetic failures.
No independent sample size is obtained by adding studies or nested observations.

The PDF is built outside the repository:

```sh
cd /workspace/networkRLCD-a135/paper/negative-result
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=/home/agent/.cache/networkrlcd/research-decision-rd1/paper-build main.tex
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=/home/agent/.cache/networkrlcd/research-decision-rd1/paper-build main.tex
```

The build directory must already exist. No capture, analysis, archive restore,
model training, old evidence regeneration or `make paper-evidence` is required.
The pinned RD1 archive retains the PDF, source edition, compile logs, source
inventory and preservation audit. Its receipt is
`docs/storage-receipts/research-decision-rd1-20261015-01.json`.

No successor is selected. The paper leaves two conditional changes in premise:
a genuinely admitted and qualified instrumented fixture, or an independently
justified episode/sequence estimand. Neither opens an existing panel or waives
the PO1 stop. See the paper's admission requirements before proposing new work.
