"""Replay: re-simulate an episode from its logged commands and check that everything logged is reproduced.

Default (fast): every logged command goes back through the rule (stateful rules included, in order) and the plotter
noise; the ink end points must match the log exactly (< 1e-6 mm) and so must every closure verdict.

--render: also re-renders every observation the agent was given (page photo, raw camera frame, stale-rectified view,
crop) and checks its sha256 against the one logged for the turn: proof that the images the model saw are regenerated
bit for bit (which is why runs do not store images by default). Replayed images can be written to a directory.

Works on new runs and on legacy runs converted by `freehand import-legacy` (their summaries carry the historical
rule and, where no suite reproduces the page, a page.json).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from freehand.episode.world import World
from freehand.llm.messages import sha256_hex
from freehand.perturbations import from_describe
from freehand.results import layout
from freehand.sim import closure, png_bytes
from freehand.sim.page import Square
from freehand.suites import load_suite
from freehand.suites.generate import episode_setup
from freehand.suites.generate import page as suite_page

EXACT_MM = 1e-6


@dataclass
class EpisodeReplay:
    path: str
    strokes: int = 0
    max_endpoint_error: float = 0.0
    closure_mismatches: int = 0
    images_checked: int = 0
    image_mismatches: int = 0
    error: str | None = None
    details: list = field(default_factory=list)

    @property
    def exact(self) -> bool:
        return self.error is None and self.max_endpoint_error < EXACT_MM and not self.closure_mismatches \
            and not self.image_mismatches


def load_episode(ep_dir: Path) -> tuple[dict, list[dict]]:
    summary = json.loads((ep_dir / "summary.json").read_text())
    turns = []
    jl = ep_dir / "episode.jsonl"
    if jl.exists():
        with open(jl) as f:
            turns = [json.loads(line) for line in f if line.strip()]
    return summary, turns


def episode_world(ep_dir: Path, summary: dict) -> tuple[list[Square], object, int]:
    """(squares, fresh rule, change square) for an episode: page.json if present, else regenerated from the suite."""
    labels = summary.get("labels", {})
    seed = summary["seed"]
    page_file = ep_dir / "page.json"
    if page_file.exists():
        squares = [Square(**d) for d in json.loads(page_file.read_text())]
        pert = from_describe(summary["perturbation"], seed)
        return squares, pert, summary["perturb_after"]
    suite = load_suite(labels["suite"])
    if "perturbation" not in labels and str(labels.get("purpose", "")).startswith("output-mode gate"):
        # a K1 output-mode check (experiments.runner._k1_gate): the page's first squares, no change
        squares = suite_page(suite, seed)[:summary["n_squares"]]
        return squares, from_describe(summary["perturbation"], seed), summary["perturb_after"]
    st = episode_setup(suite, seed, labels["perturbation"], labels.get("max_squares"))
    if labels.get("seed_hash") and st.seed_hash != labels["seed_hash"]:
        raise RuntimeError(f"suite {suite.id} seed {seed} no longer regenerates the logged data (seed hash differs)")
    return st.squares, st.perturbation, st.perturb_after


def replay_episode(ep_dir: Path, render: bool = False, image_out: Path | None = None) -> EpisodeReplay:
    res = EpisodeReplay(str(ep_dir))
    try:
        summary, turns = load_episode(ep_dir)
        squares, pert, P = episode_world(ep_dir, summary)
        if render:
            _replay_turns(res, summary, turns, squares, pert, P, image_out)
        else:
            _replay_strokes(res, summary, squares, pert, P)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


def _check(res: EpisodeReplay, s: dict, ink, sq: Square, tol: float) -> None:
    err = float(np.abs(np.array([ink[0], ink[-1]]) - np.array(s["ink_ends"])).max())
    closed, _, _ = closure(ink, sq.open_ends, tol)
    res.strokes += 1
    res.max_endpoint_error = max(res.max_endpoint_error, err)
    if closed != s["closed"]:
        res.closure_mismatches += 1
        res.details.append({"stroke": s["stroke"], "closure": [s["closed"], closed]})


def _replay_strokes(res, summary, squares, pert, P) -> None:
    by_idx = {q.idx: q for q in squares}
    tol = summary["setup"]["tol_mm"]
    ps = summary.get("perturb_stroke")
    world = World(summary["seed"], squares, pert, P)
    for s in summary["strokes"]:
        n = s["stroke"]
        if ps is not None and n >= ps and not world.active and P > 0:
            world.perturb_stroke = ps
            world._activate(ps)
        world.stroke_no = n - 1
        ink = world.land(s["cmd"])
        _check(res, s, ink, by_idx[s["square"]], tol)


def _replay_turns(res, summary, turns, squares, pert, P, image_out) -> None:
    """Turn by turn, re-rendering each observation and comparing image hashes."""
    by_idx = {q.idx: q for q in squares}
    tol = summary["setup"]["tol_mm"]
    world = World(summary["seed"], squares, pert, P)
    strokes = {s["turn"]: s for s in summary["strokes"]}
    current = None
    if image_out:
        image_out.mkdir(parents=True, exist_ok=True)
    for t in turns:
        if current is not None and t["square"] != current:
            world.end_square(current)
        current = t["square"]
        sq = by_idx[t["square"]]
        for img in t["prompt"]["images"]:
            view = world.crop(sq)[0] if img["name"].endswith("_crop.png") else world.render(sq)
            res.images_checked += 1
            if sha256_hex(png_bytes(view)) != img["sha256"]:
                res.image_mismatches += 1
                res.details.append({"turn": t["turn"], "image": img["name"]})
            if image_out:
                cv2.imwrite(str(image_out / img["name"]), view)
        s = strokes.get(t["turn"])
        if s is not None:
            ink = world.land(s["cmd"])
            _check(res, s, ink, sq, tol)
    if image_out:
        for name, img in world.final_views().items():
            cv2.imwrite(str(image_out / f"{name}.png"), img)


def replay_run(run_dir: Path, render: bool = False, limit: int | None = None, image_dir: Path | None = None) -> dict:
    rows = []
    for i, ep in enumerate(layout.iter_episode_dirs(run_dir)):
        if limit is not None and i >= limit:
            break
        out = image_dir / ep.relative_to(run_dir) if image_dir else None
        rows.append(replay_episode(ep, render=render, image_out=out))
    return {"run": str(run_dir), "episodes": len(rows), "strokes": sum(r.strokes for r in rows),
            "exact_episodes": sum(r.exact for r in rows),
            "max_endpoint_error_mm": max((r.max_endpoint_error for r in rows), default=0.0),
            "closure_mismatches": sum(r.closure_mismatches for r in rows),
            "images_checked": sum(r.images_checked for r in rows),
            "image_mismatches": sum(r.image_mismatches for r in rows),
            "errors": [{"path": r.path, "error": r.error} for r in rows if r.error],
            "inexact": [r.path for r in rows if not r.exact and not r.error]}


__all__ = ["EpisodeReplay", "replay_episode", "replay_run"]
