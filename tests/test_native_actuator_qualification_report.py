"""The N1 evidence exporter: numbers come from the registered records, wording from the verdict alone."""

import copy
import json
import re

import pytest

from media_rl import native_actuator_qualification as qualification
from media_rl import native_actuator_qualification_explore as explore
from media_rl import native_actuator_qualification_panel as panel
from media_rl import native_actuator_qualification_report as report

QUALIFIED, NOT_SEPARABLE, INCONCLUSIVE = qualification.VERDICTS


@pytest.fixture(scope="module")
def records(tmp_path_factory):
    root = tmp_path_factory.mktemp("n1") / "dry"
    panel.dry_run(root)
    paths = dict(
        final=root / "final.json",
        public=root / "interim-public.json",
        protocol=root / "plan" / "protocol.json",
    )
    return paths, {name: json.loads(path.read_text()) for name, path in paths.items()}


def rows(loaded, **changes):
    final = copy.deepcopy(loaded["final"])
    final.update(changes)
    return report.macros(final, loaded["public"], loaded["protocol"], 0, [])


def test_mock_rows_never_reach_the_paper(records, tmp_path):
    paths, _ = records
    with pytest.raises(ValueError, match="mock rows"):
        report.export(**paths, out=tmp_path / "evidence")
    assert not (tmp_path / "evidence").exists()


def test_export_reads_every_number_from_the_records(records, tmp_path):
    paths, loaded = records
    result = report.export(**paths, out=tmp_path / "evidence", allow_mock=True)
    text = (tmp_path / "evidence" / "evidence.tex").read_text()
    names = re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", text)
    assert result["macros"] == len(names) == len(set(names)) and all(n.startswith("NOne") for n in names)
    primary = loaded["final"]["primary"]
    assert f"\\newcommand{{\\NOneLowerMean}}{{{report.signed(primary['mean_contrasts'][0])}}}" in text
    assert f"\\newcommand{{\\NOneUpperLow}}{{{report.signed(primary['lower_bounds'][1])}}}" in text
    assert f"\\newcommand{{\\NOneSources}}{{{primary['sources']}}}" in text
    for name in ("n1_primary", "n1_regimes", "n1_complexity", "n1_sources"):
        table = (tmp_path / "evidence" / f"{name}.tex").read_text()
        assert table.startswith("\\begin{tabular}") and table.rstrip().endswith("\\end{tabular}")
    assert (tmp_path / "evidence" / "n1_sources.tex").read_text().count("\\\\") == primary["sources"] + 1
    provenance = json.loads((tmp_path / "evidence" / "provenance.json").read_text())
    assert {str(p) for p in paths.values()} <= set(provenance)


def test_the_verdict_alone_selects_the_outcome_wording(records):
    _, loaded = records
    assert loaded["final"]["verdict"] == QUALIFIED
    for verdict in qualification.VERDICTS:
        made = rows(loaded, verdict=verdict, designation=None)
        assert made["NOneVerdict"] == report.VERDICT_NAME[verdict]
        assert made["NOneOutcomeSentence"] == report.OUTCOME[verdict]
        assert made["NOneConsequenceSentence"] == report.CONSEQUENCE[verdict]
        assert made["NOneAbstractSentence"] == " " + report.ABSTRACT[verdict]
        assert made["NOneConclusionSentence"] == " " + report.CONCLUSION[verdict]
    assert rows(loaded)["NOneDesignationSentence"] == report.DESIGNATION[False]
    flagged = rows(loaded, designation=qualification.HETEROGENEOUS)
    assert flagged["NOneDesignationSentence"] == report.DESIGNATION[True]
    assert rows(loaded, verdict=NOT_SEPARABLE)["NOneDesignationSentence"] == report.DESIGNATION[None]


def test_a_failed_support_gate_is_reported_as_inconclusive_only(records):
    _, loaded = records
    failed = rows(loaded, verdict=INCONCLUSIVE, designation=None, capture_support_passed=False)
    assert failed["NOneOutcomeSentence"] == report.UNSUPPORTED and failed["NOneSupport"] == "failed"
    assert failed["NOneConsequenceSentence"] == report.CONSEQUENCE[INCONCLUSIVE]
    with pytest.raises(ValueError, match="capture-support"):
        rows(loaded, capture_support_passed=False)


def test_precision_futility_is_worded_as_information_not_effect(records):
    _, loaded = records
    plain = report.interim_sentence(loaded["final"], 12, 21)
    assert "no extension" in plain
    futile = copy.deepcopy(loaded["final"])
    futile["interim"]["precision_futility"] = True
    sentence = report.interim_sentence(futile, 12, 21)
    assert "says nothing about the effect" in sentence and "21" in sentence
    extended = copy.deepcopy(loaded["final"])
    extended["primary"]["rule"]["total"] = 18
    assert "6 reserve sources" in report.interim_sentence(extended, 12, 21)


def test_refuses_records_that_do_not_belong_together(records, tmp_path):
    paths, loaded = records
    with pytest.raises(ValueError, match="prescribed"):
        report.macros(
            loaded["final"], dict(loaded["public"], prescribed_total_sources=15), loaded["protocol"], 0, []
        )
    with pytest.raises(ValueError, match="quality claim"):
        rows(loaded, QoE_claims=True)
    with pytest.raises(ValueError, match="registered N1 final"):
        rows(loaded, verdict="promising")
    other = tmp_path / "protocol.json"
    other.write_text(json.dumps(dict(loaded["protocol"], extra=1)))
    with pytest.raises(ValueError, match="do not belong together"):
        report.export(paths["final"], paths["public"], other, tmp_path / "evidence", allow_mock=True)


def test_titles_outside_the_latin_font_are_elided_not_transliterated():
    assert report.typeset("G.E.M.【愛如意】MV (HD) 鄧紫棋") == "G.E.M. [\\ldots] MV (HD) [\\ldots]"
    assert report.typeset("Brajkovič na startu 12°") == "Brajkovič na startu 12°"
    assert report.typeset("Joy & Heron") == "Joy \\& Heron"
    assert report.typeset("8200호대 서울 출발") == "8200 [\\ldots]"


def test_sources_carry_their_commons_page_numbers(records):
    _, loaded = records
    names = loaded["final"]["sources"]
    pool = dict(sources=[dict(cluster_id=n, candidate_id=f"commons-{i + 100}") for i, n in enumerate(names)])
    table = report.table_sources(loaded["final"], loaded["protocol"], pool)
    assert "1 & 100 & " in table and f"{len(names)} & {len(names) + 99} & " in table
    assert " & n/a & " in report.table_sources(loaded["final"], loaded["protocol"])


def test_regime_reading_counts_the_tests_that_clear_the_margin(records):
    _, loaded = records
    final = copy.deepcopy(loaded["final"])
    made = report.macros(final, loaded["public"], loaded["protocol"], 0, [])
    assert (
        made["NOneRegimeTests"] == "8"
        and made["NOneRegimeEstablished"] == "8"
        and made["NOneRegimeOpen"] == "none"
    )
    final["secondary"]["regime_map"]["queue-building"]["holm_p_values"][1] = 0.2
    made = report.macros(final, loaded["public"], loaded["protocol"], 0, [])
    assert made["NOneRegimeEstablished"] == "7"
    assert made["NOneRegimeOpen"] == "the upper difference under the queue-building schedule"


def exploratory_rows(sources=4, peers=6):
    """Synthetic rows: the top ratio helps under the free schedule and hurts under the others."""
    rows = []
    for s in range(sources):
        for regime in explore.REGIMES:
            for peer in range(peers):
                for epoch in range(6):
                    arm, held = (epoch + peer + s) % 3, regime != explore.REGIMES[0]
                    rows.append(
                        dict(
                            cluster_id=f"source-{s}",
                            trial_id=f"{s}-{regime}-{peer}",
                            network_regime=regime,
                            epoch=epoch,
                            arm=arm,
                            complete=True,
                            base_bwe_bps=1e6 * (1 + 0.05 * epoch * (arm + 1)),
                            encoder_bps=1e6 * (0.5 + 0.1 * arm + 0.01 * s),
                            utility=30 + (-1.0 - 0.1 * s if held else 2.0 + 0.1 * s) * arm,
                            ontime_fraction=0.9 - (0.05 + 0.01 * s) * arm * held,
                        )
                    )
    return rows


def test_exploratory_macros_are_marked_and_count_what_is_established():
    described = explore.explore(exploratory_rows())
    made = report.exploratory_macros(described)
    assert all(name.startswith("NOneExp") for name in made)
    assert made["NOneExpHeldSchedules"] == "3" and made["NOneExpHeldUtilityEstablished"] == "3"
    assert made["NOneExpUtilityContrasts"] == "12" and made["NOneExpLowerBetter"] == "9"
    assert made["NOneExpFreeBestTop"] == "4" and made["NOneExpFreeUtility"].startswith("$+$4.")
    assert made["NOneExpSchedules"] == "4" and made["NOneExpEarlyAhead"] == "1"
    assert made["NOneExpLaterCells"] == "8" and made["NOneExpLaterLowerBetter"] == "6"
    for table in (report.table_exploratory(described), report.table_exploratory_holds(described)):
        assert table.startswith("\\begin{tabular}") and table.rstrip().endswith("\\end{tabular}")
    assert report.table_exploratory(described).count("\\\\") == 2 + 1 + len(explore.REGIMES)


def test_exploratory_description_must_be_of_the_analysed_rows(records, tmp_path):
    paths, _ = records
    described = dict(explore.explore(exploratory_rows()), rows_sha256="0" * 64)
    path = tmp_path / "exploratory.json"
    path.write_text(json.dumps(described))
    with pytest.raises(ValueError, match="not of the analysed capture"):
        report.export(**paths, out=tmp_path / "evidence", allow_mock=True, exploratory=path)
    path.write_text(json.dumps(dict(described, exploratory=False)))
    with pytest.raises(ValueError, match="exploratory description of native rows"):
        report.export(**paths, out=tmp_path / "evidence", allow_mock=True, exploratory=path)


def conditional_rows():
    """Synthetic rows with a pre-hold state: a stalled estimate makes the low ratio the better one."""
    rows = []
    for s in range(5):
        for peer in range(8):
            for epoch in range(6):
                arm, stalled = (epoch + peer + s) % 3, (epoch * 7 + peer * 3 + s) % 3 == 0
                present = dict(status="present")
                rows.append(
                    dict(
                        cluster_id=f"source-{s}",
                        trial_id=f"{s}-{peer}",
                        network_regime=explore.REGIMES[peer % 4],
                        epoch=epoch,
                        arm=arm,
                        complete=True,
                        base_bwe_bps=1e6 * (0.5 if stalled else 1.0 + 0.2 * epoch),
                        encoder_bps=5e5,
                        utility=30.0 + (2.0 + 0.1 * s if stalled else -1.0) * (2 - arm) / 2,
                        ontime_fraction=0.9,
                        state=dict(
                            rtt_trend_ms=dict(present, value=0.0),
                            rtt_ms=dict(present, value=40.0 + epoch + peer),
                            loss_fraction=dict(present, value=0.0),
                            jitter_ms=dict(present, value=3.0 + (peer * 5 + epoch) % 7),
                        ),
                    )
                )
    return rows


def test_second_pass_macros_are_marked_and_skip_signals_that_flag_too_few_holds():
    passed = explore.conditional(conditional_rows())
    made = report.conditional_macros(passed)
    assert all(name.startswith("NOneCond") for name in made)
    assert made["NOneCondSignals"] == "5" and made["NOneCondUnusable"] == "2"  # trend and loss never rise
    assert "NOneCondTrendFlagged" not in made and "NOneCondGrowthFlagged" in made
    assert made["NOneCondCandidates"] == str(len(passed["candidates"]))
    assert made["NOneCondCandidateSentence"].startswith("The rule named ")
    table = report.table_conditional(passed)
    assert table.count("too few holds") == 2 and table.count("\\\\") == 1 + 5


def test_titles_are_made_safe_for_latex():
    assert report.escape("A_b & 50% #1 {x}") == "A\\_b \\& 50\\% \\#1 (x)"
