"""Re-record fixtures/legacy_parity.json.gz from the ORIGINAL code (provenance; not run by the test suite).

    FREEHAND_LEGACY_A=/path/to/freehand_publish FREEHAND_LEGACY_B=/path/to/freehand_b \
        python -m tests.parity.record_legacy

The legacy sources are copied to a temporary directory first (nothing is written into them); copy B's
simulator import of the neighbouring hardware project is pointed at the bundled grid renderer, as in copy A.
Cases on the discriminating rules, numeric feedback and P = 0 run on copy A, everything else on copy B (see the
glossary in docs/HISTORY.md), which is where each feature was last changed.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "fixtures" / "legacy_parity.json.gz"
B_GRID_IMPORT = ('CTS = os.path.join(os.path.dirname(HERE), "complete_the_shape")\nsys.path.insert(0, CTS)\n'
                 'from camera import grid_view, LETTER_W, LETTER_H, PX_PER_MM  # noqa: E402  (the same overlay loop.py '
                 'shows)')
A_GRID_IMPORT = 'CTS = os.path.join(HERE, "assets")\nfrom render_grid import grid_view, LETTER_W, LETTER_H, PX_PER_MM'

WORKER = r'''
import json, os, sys, tempfile
which, out, parity = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.getcwd()); sys.path.insert(0, parity)
import episode as E, levels, llm, sim
from cases import CASES
from fake_policy import make_policy
X = NB = None
if which == "a":
    import perturbations as X, numeric_baselines as NB
    import model_study as MS
    BLOCK = {"": "", "model_study": MS.PROMPT}
else:
    import objective_pilot as O
    BLOCK = {"": "", "objective": O.OBJECTIVE, "informed": O.INFORMED_OBJECTIVE}

def squares_for(c, cond):
    if c["page"] == "objective":
        return sim.far_apart_order(sim.make_page(c["seed"], 20, size_range=(16.0, 28.0), gap=7.0))
    if c["page"] == "publication":
        return sim.far_apart_order(sim.make_page(c["seed"], 12, area=(55, 80, 160, 205), size_range=(12, 19), gap=4))
    return None

def scenario_for(c):
    s, seed = c.get("scenario"), c["seed"]
    if s:
        return levels.L2Rotation(seed) if s["level"] == "L2rot" else levels.make_scenario(s["level"], s["step"], seed, s["variant"])
    if c.get("x"):
        return levels.Scenario(seed, 0, 0) if c["x"] == "identity" else X.FACTORIES[c["x"]](seed)
    return None

def agent_for(c, sc, squares, store, budget):
    a = c["agent"]
    if a == "fake":
        pol = make_policy({s.idx: s.open_ends for s in squares}, c["seed"], crop=c["output_mode"] == "crop_px")
        ag = E.LLMAgent(llm.FakeAdapter(store, budget, pol, salt=c["id"])); ag.name = "fake-llm"; return ag
    if a == "local_patcher": return X.LocalPatcher()
    if a == "local_broyden": return NB.NumericAgent(NB.LocalBroyden())
    if a == "adaptive_library": return NB.NumericAgent(NB.AdaptiveLibrary())
    if a == "family_estimator": return X.FamilyEstimator(c["x"])
    if sc is None:
        return {x.name: x for x in E.code_agents(E.family(c["cond"]))}[a]()
    return {"oracle": levels.LOracle, "naive": levels.LNaive}.get(a, lambda: levels.LAdaptive(sc.level))()

res = {}
td = tempfile.mkdtemp()
store = llm.Store(os.path.join(td, "c.sqlite")); budget = llm.Budget(store, 1e9, "parity")
for c in CASES:
    if c["legacy"] != which: continue
    sc = scenario_for(c)
    cond = c.get("cond") or sc.name
    sqs = squares_for(c, cond)
    episq = sqs if sqs is not None else E.episode_squares(c["seed"], cond, c["n"], c["P"])
    kw = dict(n_squares=c["n"], perturb_after=c["P"], show_history=c["show_history"], memory=c["memory"],
              disclosure=c["disclosure"], k_prev=c["k_prev"], cost_cap=c["cost_cap"], output_mode=c["output_mode"],
              scenario=sc, squares=sqs, extra_prompt=BLOCK[c["block"]])
    if which == "b": kw["history_landed"] = c["history_landed"]
    else: kw["feedback_mode"] = c["feedback"]
    ep, turns = E.run_episode(agent_for(c, sc, episq, store, budget), c["seed"], cond, os.path.join(td, c["id"]), **kw)
    res[c["id"]] = {"system_prompt": ep["system_prompt"], "stopped": ep["stopped"], "complete": ep["complete"],
        "perturb_stroke": ep["perturb_stroke"], "squares_result": ep["squares_result"], "strokes": ep["strokes"],
        "metrics": ep["metrics"], "cost_original": ep["cost_original"], "metrics_ink": ep["metrics_ink"],
        "turns": [{"turn": t["turn"], "square": t["square"], "attempt": t["attempt"], "state": t["state"],
                   "cache_key": t["reply"].get("cache_key"), "prev_images": t["prev_images"], "notepad_in": t["notepad_in"],
                   "n_history_turns": t["n_history_turns"], "change_active": t["change_active"], "view_H": t["view_H"],
                   "mention": [t["mention_note"], t["mention_memory"], t["mention_reasoning"]], "action": t["action"],
                   "cmd_crop_px": t.get("cmd_crop_px"), "crop": t.get("crop"), "drawn": t.get("drawn")} for t in turns]}
json.dump(res, open(out, "w"), default=float)
'''


def _copy(src: Path, dst: Path, patch_b: bool) -> None:
    for f in list(src.glob("*.py")) + [src / "assets" / "page_calib.json"]:
        if f.exists():
            target = dst / f.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, target)
    if patch_b:
        s = (dst / "sim.py").read_text()
        (dst / "sim.py").write_text(s.replace(B_GRID_IMPORT, A_GRID_IMPORT))


def main() -> None:
    from .comparable import from_legacy
    a, b = Path(os.environ["FREEHAND_LEGACY_A"]), Path(os.environ["FREEHAND_LEGACY_B"])
    out: dict = {}
    with tempfile.TemporaryDirectory() as td:
        for which, src in (("a", a), ("b", b)):
            d = Path(td) / which
            _copy(src, d, patch_b=which == "b")
            if which == "b":
                shutil.copy(a / "render_grid.py", d / "render_grid.py")
                (d / "assets").mkdir(exist_ok=True)
                shutil.copy(a / "assets" / "page_calib.json", d / "assets" / "page_calib.json")
            res = Path(td) / f"{which}.json"
            subprocess.run([sys.executable, "-B", "-c", WORKER, which, str(res), str(HERE)], cwd=d, check=True,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            out.update({k: from_legacy(v) for k, v in json.loads(res.read_text()).items()})
    with gzip.GzipFile(FIXTURE, "wb", mtime=0) as f:
        f.write(json.dumps(out, sort_keys=True).encode())
    print(f"recorded {len(out)} cases -> {FIXTURE}")


if __name__ == "__main__":
    main()
