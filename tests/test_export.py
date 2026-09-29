"""`freehand export-data`: a sanitised, byte-reproducible bundle that the analyses run on unchanged."""

import json
import tarfile

import pytest

from freehand import cli
from freehand.analysis.figures import study_rows
from freehand.replay import replay_run
from freehand.results.export import UnsafeExport, collect, sanitise_manifest, sanitise_summary
from freehand.results.schema import validate_run


def _fake_run(results_root):
    assert cli.main(["run", "smoke", "--fake-models", "--workers", "1"]) == 0
    return next(p for p in (results_root / "smoke").iterdir() if p.is_dir())


def test_bundle_is_reproducible_and_runs_like_the_original(results_root, tmp_path):
    d = _fake_run(results_root)
    (d / "episodes" / "oracle" / "rot13__code" / "s1" / "images").mkdir()  # never exported
    out1, out2 = tmp_path / "a" / "bundle_v1.tar.gz", tmp_path / "b" / "bundle_v1.tar.gz"
    assert cli.main(["export-data", str(d), "--out", str(out1)]) == 0
    assert cli.main(["export-data", str(d), "--out", str(out2)]) == 0
    assert out1.read_bytes() == out2.read_bytes()  # byte-reproducible
    with tarfile.open(out1) as tar:
        names = tar.getnames()
        tar.extractall(tmp_path / "x", filter="data")
    assert all(n.startswith("bundle_v1") for n in names)
    assert not any("images" in n or n.endswith(".png") or "run.log" in n or "config.yaml" in n for n in names)
    run = tmp_path / "x" / "bundle_v1" / "runs" / d.name
    assert validate_run(run) == []
    r = replay_run(run)
    assert r["episodes"] == 10 and r["exact_episodes"] == 10 and not r["errors"]
    assert [x["later_first_try"] for x in study_rows([run])] == [x["later_first_try"] for x in study_rows([d])]
    sums = (tmp_path / "x" / "bundle_v1" / "SHA256SUMS").read_text().splitlines()
    assert len(sums) == len([n for n in names if n.endswith((".json", ".jsonl", ".md"))])


def test_local_paths_are_replaced_or_refused():
    m = {"legacy": {"source": "working", "container": "runs", "original_path": "/home/someone/x/runs/pilot_1"}}
    assert sanitise_manifest(m, "pilot_1")["legacy"]["original_path"] == "working:runs/pilot_1"
    s = {"legacy": {"source": "working", "run": "pilot_1", "original_dir": "/home/someone/runs/pilot_1/episodes/e1"}}
    assert sanitise_summary(s, "pilot_1")["legacy"]["original_dir"] == "working:runs/pilot_1/episodes/e1"


def test_export_refuses_a_run_that_still_holds_a_local_path(results_root, tmp_path):
    d = _fake_run(results_root)
    m = json.loads((d / "manifest.json").read_text())
    m["notes"] = ["copied from /var/folders/xy/elsewhere"]
    (d / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(UnsafeExport, match="local path"):
        collect([d], "b")
