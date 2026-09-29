"""`freehand import-legacy` on a verbatim copy of three historical episode logs (fixtures/legacy_copy)."""

import json
import sqlite3
from pathlib import Path

from freehand import cli
from freehand.analysis.rescore import rescore_runs
from freehand.legacy.convert import stop_of
from freehand.llm import Ledger, RequestCache
from freehand.replay import replay_run
from freehand.results.schema import validate_run

FIXTURE = Path(__file__).parent / "fixtures" / "legacy_copy"


def _legacy_cache(path: Path) -> None:
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE cache (key TEXT PRIMARY KEY, model TEXT, route TEXT, settings TEXT, request TEXT, "
        "response TEXT, text TEXT, thoughts TEXT, usage TEXT, cost REAL, model_version TEXT, latency REAL, "
        "ts REAL)"
    )
    db.execute("CREATE TABLE spend (ts REAL, key TEXT, model TEXT, cost REAL, tag TEXT)")
    db.execute("INSERT INTO cache VALUES ('k1','m','r','{}','{}','{}','t',NULL,'{}',0.5,'v',1.0,1.0)")
    db.execute("INSERT INTO spend VALUES (1.0,'k1','m',0.5,'pilot2')")
    db.commit()
    db.close()


def test_import_convert_match_replay_and_merge(results_root, tmp_path):
    src = tmp_path / "copy"
    import shutil

    shutil.copytree(FIXTURE, src)
    _legacy_cache(src / "cache.sqlite")
    before = {p: p.read_bytes() for p in src.rglob("*") if p.is_file()}
    assert cli.main(["import-legacy", "--source", f"working={src}", "--merge-cache"]) == 0
    assert {p: p.read_bytes() for p in src.rglob("*") if p.is_file()} == before  # originals untouched
    run = results_root / "legacy/working/runs/pilot2_20260927_150151"
    assert (run / "original").is_symlink()
    assert (run / "original").resolve() == src.resolve() / "runs/pilot2_20260927_150151"
    m = json.loads((run / "manifest.json").read_text())
    assert m["kind"] == "legacy" and len(m["cells"]) == 3
    assert {c["suite"] for c in m["cells"]} == {"legacy-b8-v0", "legacy-a8-v0"}  # pages regenerate exactly
    assert not list(run.glob("episodes/*/*/*/page.json"))
    assert validate_run(run) == []
    r = replay_run(run)
    assert r["exact_episodes"] == 3 and r["closure_mismatches"] == 0
    s = json.loads((run / "episodes/claude-opus-5.5/offset10__silent/s7/summary.json").read_text())
    assert s["legacy"]["original_metrics"]["post_strokes_total"] == s["metrics"]["post_strokes_total"]
    assert rescore_runs([run])["episodes"] == 3
    cache, ledger = RequestCache(results_root / "cache/llm_cache.sqlite"), Ledger(results_root / "ledger.sqlite")
    assert cache.get("k1")["cost"] == 0.5 and ledger.spent(tag="pilot2") == 0.5
    # idempotent: re-importing and re-merging adds nothing
    assert cli.main(["import-legacy", "--source", f"working={src}", "--merge-cache"]) == 0
    assert cache.count() == 1 and Ledger(results_root / "ledger.sqlite").spent(tag="pilot2") == 0.5
    # --force re-converts in place: a run is not a duplicate of itself (it used to become an empty manifest)
    assert cli.main(["import-legacy", "--source", f"working={src}", "--force"]) == 0
    m2 = json.loads((run / "manifest.json").read_text())
    assert m2["legacy"]["duplicate_of"] is None and len(m2["cells"]) == 3
    assert replay_run(run)["exact_episodes"] == 3


def test_stop_classification():
    assert stop_of(None) == ("complete", None)
    assert stop_of("RuntimeError: episode cost cap $3.00 reached")[0] == "capped"
    assert stop_of("BudgetExceeded: cap $25.00 [x]")[1]["kind"] == "budget"
    assert stop_of("RuntimeError: openrouter HTTP 403: key limit")[1]["kind"] == "provider"
