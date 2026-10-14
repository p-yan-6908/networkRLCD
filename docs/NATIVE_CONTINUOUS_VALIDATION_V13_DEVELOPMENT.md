# V13 instrument qualification and untouched registration

Six new development sessions used **reused V11D cicada content** (G. Edward
Johnson, CC BY 4.0) and **synthetic** 0.35/1.2 Mbps constants. All six sealed
and passed their registered instrument gates: continuous-range/history
support at 18–18.3 seconds, TURN/TCP media, actual-run clocks, exact 36 ticks,
action/readback and terminal conservation/cleanup. Maximum held-out clock
width was **2.682823 ms**. Four randomized development caps were exercised;
two census sessions assigned no action. No outcome file was decoded.

| Synthetic link | Census geometric-mean BWE | Slot 0 pre-action history BWE | Slot 1 pre-action history BWE |
| --- | ---: | ---: | ---: |
| 0.35 Mbps | 293.680 kbps | 344.163 kbps | 387.353 kbps |
| 1.2 Mbps | 1,313.970 kbps | 1,278.133 kbps | 1,300.461 kbps |

These are instrument/support variables, not treatment effects. The experiment
does **not** qualify the new measured census's range, repeatability or actual
state agreement. In particular, one synthetic low-link action history differs
from its single census state by about 0.40 octaves and would fail the future
0.25-octave agreement gate. That gate remains unchanged. A single census per
link also does not test the two-repeat requirement. The registered measured
census and complete action-run gate retain authority; this development pass
is no guarantee that the new scientific panel will qualify.

The official development gate is
`reports/native-v13-development-qualification.json`. Its six raw captures and
the complete V11D/V12 support-only projection were archived in private
`p-yan/networkrlcd-results-archive`, namespace
`native-continuous-validation-v13-development-20261014-01`, at revision
**`47513fde932807b93ee5db352c03a576c7fe1a67`**. A fresh remote download verified
every archive object and all **264 files**. Licensed originals/clips were not
uploaded; local evidence remains retained. See the matching storage receipt.

The new confirmatory registration contains **32 original support checks**
and **64 randomized action sessions**, with four crossed cells, two new
productions, eight fixed rate profiles and two trace collection bundles from
one measurement program. Both capture directories remain untouched. No
V13 measured support, native action or outcome has been observed. The main
protocol binds every file from `a7ea1b0`; all 1,225 anchor files remain byte
identical, including prior freezes and failures.
