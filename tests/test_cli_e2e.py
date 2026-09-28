"""End to end through the CLI with the offline fake model: `freehand run smoke --fake-models` produces the full
results tree, which validates, reports, replays exactly (including every image) and shows up in `freehand ls`."""
import json

from freehand import cli
from freehand.results import index
from freehand.results.schema import validate_run


def _run_dir(root):
    return next(p for p in (root / "smoke").iterdir() if p.is_dir())


def test_fake_run_produces_the_full_tree(results_root, capsys):
    assert cli.main(["run", "smoke", "--fake-models", "--workers", "1"]) == 0
    d = _run_dir(results_root)
    for f in ("manifest.json", "config.yaml", "run.log"):
        assert (d / f).is_file()
    assert (results_root / "index.jsonl").is_file() and (results_root / "ledger.sqlite").is_file()
    assert (results_root / "cache" / "llm_cache.sqlite").is_file()
    m = json.loads((d / "manifest.json").read_text())
    assert m["status"] == "complete" and m["counts"] == {"complete": 10}
    assert m["suites"]["smoke-v1"]["verified"] and m["budget"]["tag"] == "fake:smoke"
    assert m["provenance"]["git"]["commit"]
    eps = sorted(p.relative_to(d).as_posix() for p in d.glob("episodes/*/*/*"))
    assert "episodes/gemini-3.8-flash/rot13__stateless_numeric/s1" in eps and "episodes/oracle/rot13__code/s1" in eps
    assert not list(d.glob("episodes/*/*/*/images"))                 # images are off by default
    assert validate_run(d) == []
    assert [e["event"] for e in index.read(results_root)] == ["started", "finished"]

    # stateless numeric arm: one fresh request per turn, landed ends in the state block; flash answers in crop px
    turns = [json.loads(x) for x in open(d / "episodes/gemini-3.8-flash/rot13__stateless_numeric/s1/episode.jsonl")]
    assert all(t["prompt"]["n_history_turns"] == 0 and not t["prompt"]["notepad_in"] for t in turns)
    assert any(" landed (" in t["prompt"]["state"] for t in turns)
    assert all(t["command_crop_px"] is not None and t["crop"] is not None for t in turns if t["stroke"])
    mem = [json.loads(x) for x in open(d / "episodes/gemini-3.8-flash/rot13__silent/s1/episode.jsonl")]
    assert mem[-1]["prompt"]["n_history_turns"] == len(mem) - 1

    assert cli.main(["report", str(d)]) == 0
    assert (d / "report" / "report.md").is_file() and (d / "report" / "learning_curves.png").is_file()
    assert cli.main(["replay", str(d), "--render"]) == 0
    out = capsys.readouterr().out
    assert '"image_mismatches": 0' in out and '"closure_mismatches": 0' in out
    assert cli.main(["validate", str(d)]) == 0
    assert cli.main(["ls"]) == 0
    assert "smoke" in capsys.readouterr().out


def test_save_images_and_episode_command(results_root):
    assert cli.main(["episode", "--model", "fake", "--suite", "smoke-v1", "--seed", "1", "--perturbation", "rot13",
                     "--arm", "silent", "--fake-models", "--save-images", "--references", "oracle"]) == 0
    d = next((results_root / "adhoc").iterdir())
    m = json.loads((d / "manifest.json").read_text())
    assert [c["kind"] for c in m["cells"]] == ["reference", "model"]
    assert (d / "episodes/fake-llm/rot13__silent/s1/images/t001.png").is_file()
    assert (d / "episodes/fake-llm/rot13__silent/s1/images/final.png").is_file()


def test_dry_run_of_every_config():
    from freehand import paths
    for p in sorted(paths.experiments_dir().glob("*.yaml")):
        assert cli.main(["run", p.stem, "--dry-run"]) == 0, p.stem
