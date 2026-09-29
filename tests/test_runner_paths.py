"""Runner paths: the budget cap, stop rules that keep every cell, resume of a budget-stopped episode."""
import json

import yaml

from freehand.experiments import Runner, RunOptions, parse_experiment

CONFIG = {"name": "paths", "budget": {"tag": "paths", "cap_usd": 5.0, "episode_cap_usd": 1.0}, "workers": 1,
          "models": ["fake"], "arms": {"silent": None, "nomemory": None},
          "blocks": [{"suite": "smoke-v1", "seeds": [1], "perturbations": ["rot13", "identity"],
                      "references": ["oracle"], "arms": ["silent", "nomemory"]}]}


def _jsonl(path):
    with open(path) as f:
        return [json.loads(x) for x in f]


def _exp():
    return parse_experiment(CONFIG, yaml.safe_dump(CONFIG))


def test_budget_cap_holds_and_every_cell_keeps_a_status(results_root):
    d = Runner(_exp(), RunOptions(fake_models=True, max_usd=0.03)).run()
    m = json.loads((d / "manifest.json").read_text())
    assert m["budget"]["spent_this_run"] <= 0.03
    states = {c["id"]: c["status"] for c in m["cells"]}
    assert len(states) == 6
    assert "stopped" in states.values() and "not_run_budget" in states.values()
    stopped = next(c for c in m["cells"] if c["status"] == "stopped")
    assert stopped["stop"]["kind"] == "budget"
    assert m["status"] == "partial"


def test_resume_replays_logged_replies_then_continues(results_root):
    d = Runner(_exp(), RunOptions(fake_models=True, max_usd=0.03)).run()
    before = json.loads((d / "manifest.json").read_text())
    stopped = next(c for c in before["cells"] if c["status"] == "stopped")
    old = _jsonl(d / stopped["episode_dir"] / "episode.jsonl")
    Runner(_exp(), RunOptions(fake_models=True, max_usd=2.0)).resume(d)
    after = json.loads((d / "manifest.json").read_text())
    assert after["status"] == "complete" and after["resumes"]
    new = _jsonl(d / stopped["episode_dir"] / "episode.jsonl")
    assert len(new) > len(old)
    assert all(t["reply"].get("replayed") for t in new[:len(old)])
    assert [t["stroke"]["ends"] for t in new[:len(old)] if t["stroke"]] == \
        [t["stroke"]["ends"] for t in old if t["stroke"]]


def test_episode_cost_cap_is_capped_not_failed(results_root):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["budget"]["episode_cap_usd"] = 0.01
    exp = parse_experiment(cfg, yaml.safe_dump(cfg))
    d = Runner(exp, RunOptions(fake_models=True)).run()
    m = json.loads((d / "manifest.json").read_text())
    models = [c for c in m["cells"] if c["kind"] == "model"]
    capped = [c for c in models if c["status"] == "capped"]
    assert capped and all(c["stop"]["kind"] == "episode_cost_cap" for c in capped)
    assert all(c["status"] in ("complete", "capped") for c in models)
    assert m["status"] == "complete"                    # capped = inconclusive, not a failure


def test_resume_recovers_an_episode_whose_process_died(results_root):
    """A crashed process leaves a partial episode.jsonl (last line cut off) and no summary: resume replays the
    complete lines and finishes the episode (the working copy's late resume fix)."""
    d = Runner(_exp(), RunOptions(fake_models=True)).run()
    m = json.loads((d / "manifest.json").read_text())
    cell = next(c for c in m["cells"] if c["kind"] == "model" and c["perturbation"] == "rot13")
    ep = d / cell["episode_dir"]
    full = _jsonl(ep / "episode.jsonl")
    lines = (ep / "episode.jsonl").read_text().splitlines()
    (ep / "episode.jsonl").write_text("\n".join(lines[:3]) + "\n" + lines[3][:40])     # cut mid-line
    (ep / "summary.json").unlink()
    cell["status"] = "running"
    (d / "manifest.json").write_text(json.dumps(m))
    Runner(_exp(), RunOptions(fake_models=True)).resume(d)
    again = _jsonl(ep / "episode.jsonl")
    assert [t["reply"].get("replayed", False) for t in again[:4]] == [True, True, True, False]
    assert [t["stroke"]["ends"] for t in again if t["stroke"]] == [t["stroke"]["ends"] for t in full if t["stroke"]]
    assert json.loads((d / "manifest.json").read_text())["status"] == "complete"


def test_resume_uses_the_logged_replies_not_the_request_cache(results_root):
    """The informed_models divergence: concurrent episodes with identical early requests each got their own reply,
    but the cache keeps one reply per request. A resume must replay the episode's OWN logged replies. Here the cache
    rows of the stopped episode are overwritten with a different stroke: a cache replay would diverge; a resume
    reproduces the logged strokes exactly and only then calls the model."""
    import sqlite3
    d = Runner(_exp(), RunOptions(fake_models=True, max_usd=0.03)).run()
    before = json.loads((d / "manifest.json").read_text())
    stopped = next(c for c in before["cells"] if c["status"] == "stopped")
    old = _jsonl(d / stopped["episode_dir"] / "episode.jsonl")
    keys = [t["reply"]["cache_key"] for t in old]
    assert keys and all(keys)
    db = sqlite3.connect(results_root / "cache" / "llm_cache.sqlite")
    poison = json.dumps({"action": "draw", "strokes": [[[20.0, 20.0], [21.0, 21.0]]], "note": "sibling's reply"})
    db.executemany("UPDATE cache SET text=? WHERE key=?", [(poison, k) for k in keys])
    db.commit()
    db.close()
    Runner(_exp(), RunOptions(fake_models=True, max_usd=2.0)).resume(d)
    new = _jsonl(d / stopped["episode_dir"] / "episode.jsonl")
    assert [t["reply"]["text"] for t in new[:len(old)]] == [t["reply"]["text"] for t in old]
    assert all(t["reply"]["replayed"] and t["reply"]["cost"] == 0.0 for t in new[:len(old)])
    assert [t["reply"].get("cost_original") for t in new[:len(old)]] == \
        [t["reply"].get("cost_original") for t in old]                      # the episode cap still counts them
    assert [t["stroke"]["ends"] for t in new[:len(old)] if t["stroke"]] == \
        [t["stroke"]["ends"] for t in old if t["stroke"]]
    assert not any(t["reply"].get("replayed") for t in new[len(old):])     # then the live model continues
    assert poison not in [t["reply"]["text"] for t in new]


def _auto_exp():
    cfg = {"name": "k1", "budget": {"tag": "k1", "cap_usd": 5.0, "episode_cap_usd": 1.0}, "workers": 1,
           "models": [{"id": "fake", "output_mode": "auto"}], "arms": {"informed_objective": None},
           "blocks": [{"suite": "smoke-v1", "seeds": [1], "perturbations": ["rot13"], "references": [],
                       "arms": ["informed_objective"]}]}
    return parse_experiment(cfg, yaml.safe_dump(cfg))


def test_cut_short_output_mode_check_stops_the_cell_and_resume_replays_it(results_root):
    """K1 gate: a check cut short decides nothing, leaves the cell `stopped` (not `error`, which resume skips), and
    a resume replays the check's logged replies before continuing it (the working copy's `_checked_mode`)."""
    d = Runner(_auto_exp(), RunOptions(fake_models=True, max_usd=0.02)).run()
    m = json.loads((d / "manifest.json").read_text())
    cell = m["cells"][0]
    assert cell["status"] == "stopped" and cell["stop"]["kind"] == "output_mode_check"
    assert cell["stop"]["check_stop"]["kind"] == "budget"
    assert not m["output_modes"]
    checks = list(d.glob("episodes/*/check__*/s*/episode.jsonl"))
    assert len(checks) == 1
    logged = _jsonl(checks[0])
    assert logged
    Runner(_auto_exp(), RunOptions(fake_models=True, max_usd=2.0)).resume(d)
    m = json.loads((d / "manifest.json").read_text())
    assert m["status"] == "complete" and m["output_modes"]["fake"]["mode"] in ("page_mm", "crop_px")
    again = _jsonl(checks[0])
    assert [t["reply"].get("replayed", False) for t in again[:len(logged)]] == [True] * len(logged)
    assert [t["stroke"]["ends"] for t in again[:len(logged)] if t["stroke"]] == \
        [t["stroke"]["ends"] for t in logged if t["stroke"]]
