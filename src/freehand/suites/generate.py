"""Deterministic generation of a suite's data, its hashes, and per-episode setup.

For (suite, seed) everything below is a pure function of the suite file and the seed, drawn from named seed streams
(freehand.seeding), so it is identical on any machine regardless of model, arm, run order or which other
perturbations are run:
  page          squares (position, size, missing side, the hand-drawn ink, the open corners), in episode order
  schedule      the change square P (fixed, or drawn per seed) and any per-seed perturbation parameters
  perturbations every named rule's realised parameters (directions, signs, thresholds, camera homographies)

The seed hash is sha256 of canonical JSON of that data with floats rounded to 1e-6 mm (robust to last-bit float
differences across platforms). The suite hash is sha256 over "<seed>:<seed hash>" lines, dev seeds then test seeds.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from freehand import perturbations as PT
from freehand import seeding
from freehand.perturbations.base import Perturbation
from freehand.sim.camera import A_AREA
from freehand.sim.page import Square, far_apart_order, make_page
from freehand.suites.spec import SuiteSpec

HASH_DECIMALS = 6


# ---------------------------------------------------------------- generation
def page(suite: SuiteSpec, seed: int) -> list[Square]:
    p = suite.page
    area = p.area if p.area is not None else (A_AREA if suite.track == "camera" else None)
    sq = make_page(seed, p.n_squares, area=area, size_range=p.size_range_mm, gap=p.gap_mm)
    return far_apart_order(sq) if p.order == "far_apart" else sq


def study_v1(seed: int) -> dict[str, Any]:
    """The 2026-09-28 baseline/model studies' per-seed configuration (historical `baseline_study.configuration`)."""
    r = seeding.rng(seed, "study.configuration")
    return {"change_after": int(r.integers(2, 6)),
            "arx_gain": [float(r.uniform(.75, .9)), float(r.uniform(.70, .86))],
            "warp_amplitude": float(r.uniform(5, 11)),
            "affine": [float(r.uniform(.96, 1.10)), float(r.uniform(.90, 1.03)), float(r.uniform(-6, 6))]}


def schedule(suite: SuiteSpec, seed: int) -> dict[str, Any]:
    if suite.schedule == "fixed":
        return {"change_after": suite.change_after}
    return study_v1(seed)


_FROM_SCHEDULE = {
    "L3_affine": lambda c: {"sx": c["affine"][0], "sy": c["affine"][1], "shear_deg": c["affine"][2]},
    "command_memory": lambda c: {"gains": c["arx_gain"]},
    "smooth_warp": lambda c: {"amplitude_mm": c["warp_amplitude"]},
}


def resolved_spec(suite: SuiteSpec, name: str, seed: int) -> dict:
    spec = dict(suite.perturbations[name])
    if spec.get("params") == "from_schedule":
        fill = _FROM_SCHEDULE.get(spec["type"])
        if fill is None:
            raise ValueError(f"{spec['type']} cannot take params from the {suite.schedule} schedule")
        spec["params"] = fill(schedule(suite, seed))
    return spec


def perturbation(suite: SuiteSpec, name: str, seed: int) -> Perturbation:
    """A fresh instance (stateful rules carry per-episode state)."""
    if name not in suite.perturbations:
        raise KeyError(f"suite {suite.id} has no perturbation {name!r}; it has {suite.perturbation_names()}")
    return PT.build(name, resolved_spec(suite, name, seed), seed)


def seed_data(suite: SuiteSpec, seed: int) -> dict[str, Any]:
    return {"suite": suite.id, "generator": suite.generator, "seed": seed,
            "page": [s.to_dict() for s in page(suite, seed)],
            "schedule": schedule(suite, seed),
            "perturbations": {n: perturbation(suite, n, seed).describe() for n in suite.perturbations}}


# ---------------------------------------------------------------- hashing
def _canon(x):
    if isinstance(x, float):
        return round(x, HASH_DECIMALS) + 0.0          # + 0.0 folds -0.0 into 0.0
    if isinstance(x, np.floating):
        return _canon(float(x))
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    return x


def canonical_json(obj) -> str:
    return json.dumps(_canon(obj), sort_keys=True, separators=(",", ":"))


def seed_hash(suite: SuiteSpec, seed: int) -> str:
    return hashlib.sha256(canonical_json(seed_data(suite, seed)).encode()).hexdigest()


# The data hash covers the pages, rules and schedules, but not the episode caps (`episode.cap_strokes` / `cap_turns`),
# which also shape every result. Changing the hash would invalidate every frozen suite, so the caps of the frozen
# suites are pinned here instead and checked wherever the hash is (`suite verify`, every run). A new suite version
# should add its caps to this table when it is frozen.
PINNED_EPISODE_CAPS: dict[str, tuple[int, int]] = {
    sid: (12, 14) for sid in (
        "core-v1", "discriminating-v1", "camera-v1", "smoke-v1", "legacy-a8-v0", "legacy-b8-v0",
        "legacy-baseline-v0", "legacy-controls-v0", "legacy-ladder-v0", "legacy-model-study-v0",
        "legacy-objective-v0")}


def caps_problem(suite: SuiteSpec) -> str | None:
    """Why a frozen suite's episode caps differ from their pinned values (None when they match or are not pinned)."""
    pinned = PINNED_EPISODE_CAPS.get(suite.id)
    if pinned is None or pinned == (suite.cap_strokes, suite.cap_turns):
        return None
    return (f"suite {suite.id}: episode caps (cap_strokes, cap_turns) = ({suite.cap_strokes}, {suite.cap_turns}), "
            f"pinned at {pinned}; the frozen episode rules changed")


def data_hash(suite: SuiteSpec) -> tuple[str, dict[int, str]]:
    per_seed = {s: seed_hash(suite, s) for s in suite.all_seeds()}
    lines = "".join(f"{s}:{h}\n" for s, h in per_seed.items())
    return "sha256:" + hashlib.sha256(lines.encode()).hexdigest(), per_seed


# ---------------------------------------------------------------- episode setup
@dataclass
class EpisodeSetup:
    squares: list[Square]
    perturbation: Perturbation
    perturb_after: int
    seed: int
    seed_hash: str | None = None


def episode_setup(suite: SuiteSpec, seed: int, pert_name: str, max_squares: int | None = None,
                  with_hash: bool = True) -> EpisodeSetup:
    """The squares, fresh rule instance and change square of one episode (camera `fresh` works on squares P+1..)."""
    sq = page(suite, seed)
    P = schedule(suite, seed)["change_after"]
    pert = perturbation(suite, pert_name, seed)
    if hasattr(pert, "episode_squares"):
        sq, P = pert.episode_squares(sq, P)
    if max_squares is not None:
        if max_squares < 1:
            raise ValueError("max_squares must be >= 1")
        sq = sq[:max_squares]
        P = min(P, len(sq))
    return EpisodeSetup(sq, pert, P, seed, seed_hash(suite, seed) if with_hash else None)


def oracle_check(suite: SuiteSpec, seed: int, pert_names: list[str] | None = None) -> dict[str, bool]:
    """Per perturbation: does the oracle close every square without clamping? (reachability, not difficulty)"""
    from freehand.agents.reference import make_reference
    from freehand.episode import EpisodeConfig, MemorySink, run_episode
    out = {}
    for name in pert_names or suite.perturbation_names():
        try:
            st = episode_setup(suite, seed, name, with_hash=False)
        except RuntimeError:
            out[name] = False
            continue
        cfg = EpisodeConfig(seed=seed, squares=st.squares, perturbation=st.perturbation,
                            perturb_after=st.perturb_after, cap_strokes=suite.cap_strokes,
                            cap_turns=suite.cap_turns, render=False)
        s = run_episode(make_reference("oracle", st.perturbation), cfg, MemorySink())
        out[name] = bool(s["complete"] and all(r["closed"] for r in s["squares_result"])
                         and not any(x["clamps"] for x in s["strokes"]))
    return out


# ---------------------------------------------------------------- building a new suite
def scan_seeds(suite: SuiteSpec, start: int, count: int, max_tries: int = 2000) -> list[int]:
    """The first `count` seeds from `start` (in order) that pass the feasibility filter: the page can be placed and
    the oracle closes every square without clamping under every rule. Uses no agent performance."""
    out: list[int] = []
    seed = start
    for _ in range(max_tries):
        if len(out) == count:
            return out
        try:
            page(suite, seed)
        except RuntimeError:
            seed += 1
            continue
        if all(oracle_check(suite, seed).values()):
            out.append(seed)
        seed += 1
    raise RuntimeError(f"only {len(out)} feasible seeds in {max_tries} tries from {start}: {out}")


def freeze(suite: SuiteSpec) -> str:
    """Write the suite's data hash into its YAML file (only the `data_hash:` line changes). Returns the hash."""
    import re
    if suite.path is None:
        raise ValueError("suite has no file")
    h, _ = data_hash(suite)
    text = suite.path.read_text()
    new, n = re.subn(r"(?m)^data_hash:.*$", f"data_hash: {h}", text)
    if n != 1:
        raise ValueError(f"{suite.path} must contain exactly one top-level `data_hash:` line")
    suite.path.write_text(new)
    return h
