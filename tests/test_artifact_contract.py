import json
import re
from pathlib import Path

from test_learning import tiny_config

from media_rl.cli import main
from media_rl.experiment import sha256
from media_rl.scenarios import load_trace
from media_rl.sweeps import build_sweep_report


def test_cli_train_evaluate_trace_and_both_sweeps(tmp_path):
    config = tiny_config()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.to_dict()))
    models = tmp_path / "models"
    main(["train", "--config", str(path), "--out", str(models)])
    assert (models / "source_snapshot/uv.lock").exists()
    assert (models / "source_snapshot/src/media_rl/training.py").exists()
    evaluation = tmp_path / "evaluation"
    main(["evaluate", "--config", str(path), "--models", str(models), "--out", str(evaluation), "--no-plots"])
    assert (evaluation / "training_source/src/media_rl/training.py").exists()
    assert sha256(evaluation / "models/seed_7.json") == sha256(models / "models/seed_7.json")
    main(["report", "--run", str(evaluation), "--no-plots"])
    main(["audit", "--run", str(evaluation)])
    for kind in ["thresholds", "ablations"]:
        dest = tmp_path / kind
        args = ["sweep", "--kind", kind, "--config", str(path), "--out", str(dest), "--no-plots"]
        if kind == "thresholds":
            args += ["--models", str(models)]
        main(args)
        assert (dest / "sweep_summary.csv").exists()
        assert (dest / "table_sweep.tex").exists()
        main(["audit", "--run", str(dest)])
    no_fec = json.loads((tmp_path / "ablations/no_fec/models/seed_7.json").read_text())
    assert len(no_fec["policy"][3]) == 14
    build_sweep_report(tmp_path / "thresholds", plots=True)
    assert (tmp_path / "thresholds/sweep.pdf").stat().st_size > 1000
    trace = tmp_path / "trace.npz"
    main(["trace", "--scenario", "collapse", "--seed", "42", "--steps", "20", "--out", str(trace)])
    assert load_trace(trace).name == "collapse"


def test_paper_citations_and_artifact_paths_exist():
    paper = Path("paper/main.tex").read_text()
    bib = Path("research/references.bib").read_text()
    citations = set(re.findall(r"\\cite\{([^}]+)\}", paper))
    keys = set(re.findall(r"@\w+\{([^,]+)", bib))
    assert citations and citations <= keys
    for path in ["GOAL.md", "README.md", "docs/methodology.md", "docs/experiments.md", "uv.lock"]:
        assert Path(path).stat().st_size > 0
    assert "table_comparison.tex" in paper and "reliability.pdf" in paper
    assert "table_thresholds.tex" in paper and "\\thresholdpath" in paper
