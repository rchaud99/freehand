"""Experiment configs (configs/experiments/*.yaml) and the cell plan they expand to.

    name: informed_pilot                   # results go to results/<name>/<run_id>/
    description: ...
    preregistration: docs/preregistration.md, Addendum 9
    budget:
      tag: informed_pilot                  # spend is capped per tag across every run that uses it
      cap_usd: 20.0                        # hard cap for the tag (ledger spend + in-flight reservations)
      episode_cap_usd: 4.0                 # per model episode; `capped` = inconclusive, not a failure
      episode_cap_mode: turn               # turn: checked before each turn (pilots) | reservation: per call
                                           # (the model study)
      balance_check: true                  # lower the cap to what the OpenRouter balance / key limit still covers
    workers: 6
    order: priority                        # priority (as listed) | shuffle (seeded; spreads a budget stop over arms)
    shuffle_seed: 281026
    on_error: continue                     # continue | stop (mark every cell not yet started `not_run_after_error`)
    arms:                                  # presets by name, or inline {preset: ..., overrides} / full definitions
      informed_objective: {preset: informed_objective}
    models:                                # registry ids or OpenRouter slugs, optionally with overrides
      - opus
      - {id: flash-genai, output_mode: crop_px}
    blocks:                                # each block is a cartesian product
      - suite: legacy-objective-v0
        seeds: [10]                        # or dev | test | all
        perturbations: [rot13, L3shear, L6cam]
        references: [oracle, naive, adaptive]   # free code agents (arm "code"), run first
        models: all                        # or a subset of the ids above; [] for references only
        arms: [informed_objective]
        episode_cap_usd: 4.0               # optional per-block override
        max_squares: null                  # optional: only the first k squares of each page
        render: true                       # false: headless (references only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from freehand import paths
from freehand.agents.arms import Arm, arm_from_config, get_arm
from freehand.agents.reference import REFERENCE_NAMES, supports
from freehand.llm.registry import ModelSpec, Registry, load_registry
from freehand.suites import SuiteSpec, load_suite
from freehand.suites.generate import perturbation as build_perturbation

ORDERS = ("priority", "shuffle")
ON_ERROR = ("continue", "stop")
EPISODE_CAP_MODES = ("turn", "reservation")
DEFAULT_WORKERS = 4


@dataclass(frozen=True)
class BudgetSpec:
    tag: str
    cap_usd: float
    episode_cap_usd: float | None = None
    episode_cap_mode: str = "turn"
    balance_check: bool = True


@dataclass(frozen=True)
class Block:
    suite: SuiteSpec
    seeds: list[int]
    perturbations: list[str]
    references: list[str]
    models: list[str]
    arms: list[str]
    episode_cap_usd: float | None
    max_squares: int | None
    render: bool


@dataclass
class Cell:
    id: str
    kind: str                   # model | reference
    agent: str                  # reference name, or the model's agent name (slug after the vendor)
    model: str | None           # registry id / slug (models only)
    suite: str
    perturbation: str
    arm: str
    seed: int
    block: int
    episode_cap_usd: float | None = None
    max_squares: int | None = None
    render: bool = True

    def to_manifest(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "agent": self.agent, "model": self.model, "suite": self.suite,
                "perturbation": self.perturbation, "arm": self.arm, "seed": self.seed, "block": self.block,
                "episode_cap_usd": self.episode_cap_usd, "max_squares": self.max_squares, "status": "planned"}


@dataclass
class Experiment:
    name: str
    description: str
    budget: BudgetSpec
    models: dict[str, ModelSpec]
    arms: dict[str, Arm]
    blocks: list[Block]
    workers: int = DEFAULT_WORKERS
    order: str = "priority"
    shuffle_seed: int = 281026
    on_error: str = "continue"
    preregistration: str = ""
    notes: str = ""
    raw: dict = field(default_factory=dict)
    text: str = ""
    path: Path | None = None

    def cells(self) -> list[Cell]:
        out: list[Cell] = []
        for bi, b in enumerate(self.blocks):
            for pert in b.perturbations:
                for ref in b.references:
                    for seed in b.seeds:
                        out.append(Cell(f"{b.suite.id}:{ref}:{pert}:code:s{seed}", "reference", ref, None,
                                        b.suite.id, pert, "code", seed, bi, None, b.max_squares, b.render))
            for mid in b.models:
                spec = self.models[mid]
                for pert in b.perturbations:
                    for arm in b.arms:
                        for seed in b.seeds:
                            out.append(Cell(f"{b.suite.id}:{spec.agent_name}:{pert}:{arm}:s{seed}", "model",
                                            spec.agent_name, mid, b.suite.id, pert, arm, seed, bi,
                                            b.episode_cap_usd if b.episode_cap_usd is not None
                                            else self.budget.episode_cap_usd, b.max_squares, True))
        ids = [c.id for c in out]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"experiment {self.name}: duplicate cells {sorted(dup)[:3]}")
        dirs = [(c.agent, c.perturbation, c.arm, c.seed) for c in out]
        if len(set(dirs)) != len(dirs):
            raise ValueError(f"experiment {self.name}: two blocks use the same perturbation name on different "
                             "suites for the same agent/arm/seed; rename one (episode folders would collide)")
        return out


def _seeds(suite: SuiteSpec, sel) -> list[int]:
    if sel in (None, "all"):
        return suite.all_seeds()
    if sel in ("dev", "test"):
        return list(suite.seeds[sel])
    seeds = [int(s) for s in sel]
    stray = [s for s in seeds if s not in suite.all_seeds()]
    if stray:
        raise ValueError(f"seeds {stray} are not in suite {suite.id} (add them to the suite file, re-freeze it)")
    return seeds


def _model_entries(entries, registry: Registry) -> dict[str, ModelSpec]:
    out = {}
    for e in entries or []:
        e = {"id": e} if isinstance(e, str) else dict(e)
        mid = e.pop("id")
        spec = registry.resolve(mid).with_overrides(**e)
        if mid in out:
            raise ValueError(f"model {mid} listed twice")
        out[mid] = spec
    return out


def parse_experiment(d: dict, text: str = "", path: Path | None = None, registry: Registry | None = None) \
        -> Experiment:
    known = {"name", "description", "preregistration", "budget", "workers", "order", "shuffle_seed", "on_error",
             "arms", "models", "blocks", "notes"}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"experiment config: unknown keys {sorted(unknown)}")
    for k in ("name", "budget", "blocks"):
        if k not in d:
            raise ValueError(f"experiment config: missing `{k}`")
    registry = registry or load_registry()
    b = d["budget"]
    budget = BudgetSpec(tag=b.get("tag", d["name"]), cap_usd=float(b.get("cap_usd", 0.0)),
                    episode_cap_usd=b.get("episode_cap_usd"), episode_cap_mode=b.get("episode_cap_mode", "turn"),
                    balance_check=bool(b.get("balance_check", True)))
    if budget.episode_cap_mode not in EPISODE_CAP_MODES:
        raise ValueError(f"budget.episode_cap_mode must be one of {EPISODE_CAP_MODES}")
    models = _model_entries(d.get("models"), registry)
    arms: dict[str, Arm] = {}
    for name, cfg in (d.get("arms") or {}).items():
        arms[name] = arm_from_config(name, cfg) if cfg else get_arm(name)
    blocks = []
    for i, bd in enumerate(d["blocks"]):
        bad = set(bd) - {"suite", "seeds", "perturbations", "references", "models", "arms", "episode_cap_usd",
                         "max_squares", "render"}
        if bad:
            raise ValueError(f"block {i}: unknown keys {sorted(bad)}")
        suite = load_suite(bd["suite"])
        perts = list(bd.get("perturbations") or suite.perturbation_names())
        for p in perts:
            if p not in suite.perturbations:
                raise ValueError(f"block {i}: suite {suite.id} has no perturbation {p!r}")
        seeds = _seeds(suite, bd.get("seeds"))
        refs = list(bd.get("references") or [])
        for r in refs:
            if r not in REFERENCE_NAMES:
                raise ValueError(f"block {i}: unknown reference agent {r!r}")
            for p in perts:
                if not supports(r, build_perturbation(suite, p, seeds[0] if seeds else 0)):
                    raise ValueError(f"block {i}: reference {r} does not apply to {p} ({suite.id})")
        bm = bd.get("models", "all")
        bmodels = list(models) if bm == "all" else list(bm or [])
        for m in bmodels:
            if m not in models:
                raise ValueError(f"block {i}: model {m!r} is not in the experiment's models list")
        barms = list(bd.get("arms") or ([] if not bmodels else list(arms)))
        for a in barms:
            if a not in arms:
                arms[a] = get_arm(a)
        render = bool(bd.get("render", True))
        if not render and bmodels:
            raise ValueError(f"block {i}: render: false is for reference-only blocks")
        blocks.append(Block(suite, seeds, perts, refs, bmodels, barms, bd.get("episode_cap_usd"),
                            bd.get("max_squares"), render))
    exp = Experiment(name=d["name"], description=(d.get("description") or "").strip(), budget=budget,
                     models=models, arms=arms, blocks=blocks, workers=int(d.get("workers", DEFAULT_WORKERS)),
                     order=d.get("order", "priority"), shuffle_seed=int(d.get("shuffle_seed", 281026)),
                     on_error=d.get("on_error", "continue"), preregistration=d.get("preregistration", ""),
                     notes=d.get("notes", "") or "", raw=d, text=text, path=path)
    if exp.order not in ORDERS:
        raise ValueError(f"order must be one of {ORDERS}")
    if exp.on_error not in ON_ERROR:
        raise ValueError(f"on_error must be one of {ON_ERROR}")
    if exp.workers < 1:
        raise ValueError("workers must be >= 1")
    for spec in exp.models.values():
        for a in exp.arms.values():
            mode = a.output_mode or spec.output_mode
            if mode == "crop_px" and any(bl.suite.track == "camera" for bl in exp.blocks if spec.id in bl.models):
                raise ValueError(f"{spec.id}: crop_px is not available on the camera track")
    exp.cells()                                   # validates uniqueness
    return exp


def load_experiment(ref: str | Path, registry: Registry | None = None) -> Experiment:
    p = Path(ref)
    if not p.exists():
        p = paths.experiments_dir() / f"{ref}.yaml"
    if not p.exists():
        known = sorted(x.stem for x in paths.experiments_dir().glob("*.yaml"))
        raise FileNotFoundError(f"no experiment config {ref!r}; known: {known}")
    text = p.read_text()
    return parse_experiment(yaml.safe_load(text), text, p, registry)
