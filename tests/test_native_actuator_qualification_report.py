"""The N1 evidence exporter: numbers come from the registered records, wording from the verdict alone."""

import copy
import json
import re

import pytest

from media_rl import native_actuator_qualification as qualification
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


def test_titles_are_made_safe_for_latex():
    assert report.escape("A_b & 50% #1 {x}") == "A\\_b \\& 50\\% \\#1 (x)"
