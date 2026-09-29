"""`freehand figures`: the study figures and table regenerate from any runs, under both scorers."""
import csv

import yaml

from freehand import cli
from freehand.analysis.figures import TABLE_COLS, model_order, rules_of, study_rows
from freehand.experiments import Runner, RunOptions, parse_experiment

CONFIG = {"name": "figs", "budget": {"tag": "figs", "cap_usd": 5.0, "episode_cap_usd": 0.02}, "workers": 1,
          "models": ["fake"], "arms": {"silent": None, "informed_objective": None},
          "blocks": [{"suite": "smoke-v1", "seeds": [1], "perturbations": ["rot13", "identity"],
                      "references": ["oracle", "naive", "adaptive"], "arms": ["silent", "informed_objective"]}]}


def test_figures_from_a_run(results_root, tmp_path):
    d = Runner(parse_experiment(CONFIG, yaml.safe_dump(CONFIG)), RunOptions(fake_models=True)).run()
    out = tmp_path / "figs"
    assert cli.main(["figures", str(d), "--out", str(out)]) == 0
    for f in ("learning_curves_grid.png", "first_try_bars.png", "informed_summary.csv"):
        assert (out / f).stat().st_size > 0
    with open(out / "informed_summary.csv") as f:
        table = list(csv.reader(f))
    assert table[0] == TABLE_COLS and len(table) == 1 + 2              # one model x two rules, the focus arm
    rows = study_rows([d])
    assert rules_of(rows) == ["rot13", "identity"]                   # historical rules first, then the rest
    assert model_order(rows) == ["fake-llm"]
    assert {r["arm"] for r in rows if r["kind"] == "reference"} == {"code"}
    # the legacy scorer drops an interrupted square whose first stroke missed; the corrected one counts it
    legacy = {(r["perturbation"], r["arm"]): r for r in study_rows([d], "legacy") if r["kind"] == "model"}
    for r in rows:
        if r["kind"] != "model":
            continue
        old = legacy[(r["perturbation"], r["arm"])]
        attempted_new = len([v for v in r["curve"] if v is not None])
        attempted_old = len([v for v in old["curve"] if v is not None])
        assert attempted_new >= attempted_old
        if r["status"] == "complete":
            assert r["curve"] == old["curve"]
    assert any(r["status"] == "capped" for r in rows)                   # the $0.02 episode cap interrupts some


def test_figures_warn_when_the_runs_have_no_such_arm(results_root, tmp_path):
    import warnings

    from freehand.analysis.figures import evidence, write_figures
    d = Runner(parse_experiment(CONFIG, yaml.safe_dump(CONFIG)), RunOptions(fake_models=True)).run()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out = write_figures([d], tmp_path / "f", arm="stateless_numeric")
    assert out["warnings"] and "no episode of the arm 'stateless_numeric'" in str(w[0].message)
    assert "grid" not in out["files"]
    assert evidence(study_rows([d])) == "n = 1 episode per cell, seed 1"
    legacy = write_figures([d], tmp_path / "g", scorer="legacy")
    assert legacy["files"]["table"] == "informed_summary_legacy_scorer.csv"


def test_quote_bank_fields_and_deterministic_gzip(results_root, tmp_path):
    import gzip

    d = Runner(parse_experiment(CONFIG, yaml.safe_dump(CONFIG)), RunOptions(fake_models=True)).run()
    assert cli.main(["quote-bank", str(d), "--out", str(tmp_path / "all.csv")]) == 0
    with open(tmp_path / "all.csv") as f:
        every = list(csv.DictReader(f))
    assert every and "note" in {r["field"] for r in every}
    for name in ("a.csv.gz", "b.csv.gz"):
        assert cli.main(["quote-bank", str(d), "--out", str(tmp_path / name), "--fields", "note,memory"]) == 0
    assert (tmp_path / "a.csv.gz").read_bytes() == (tmp_path / "b.csv.gz").read_bytes()
    with gzip.open(tmp_path / "a.csv.gz", "rt", newline="") as f:
        some = list(csv.DictReader(f))
    assert some == [r for r in every if r["field"] in ("note", "memory")]
    assert cli.main(["quote-bank", str(d), "--out", str(tmp_path / "x.csv"), "--fields", "nope"]) == 2
