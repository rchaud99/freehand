"""The perturbation interface.

A perturbation is the hidden rule that silently changes the tool after the change point. Its life cycle in an
episode:

    p = registry.build("rot13", {"type": "L2_rotation"}, seed)   # parameters drawn from named seed streams
    ... squares 1..P use the calibrated tool ...
    p.start(n0)                  # switched on; n0 = number of the first affected stroke
    ink = p.land(cmd, seed, n)   # every later stroke lands through the rule
    cmd = p.oracle_cmd(target, n)  # what an all-knowing agent would command (reference agents only)

`expected(dense_pts, n)` is the noise-free landing of a dense commanded path; `land` adds the plotter's seeded scatter.
Stateful rules (command memory, latent mode) update their state in `land` only, never in `expected`/`oracle_cmd`,
so querying the oracle never changes the world.

Attributes the episode reads:
  family       "plotter" (the pen misbehaves) or "camera" (Freehand A: the view changes)
  tol          closure tolerance in mm (L7 tightens it)
  prompt_extra an extra system-prompt line (L7 only)
  warp         2x3 page-mm -> displayed-mm map once a stale-rectification camera bump is active (L6), else None
  legacy_map   True for the historical plotter-map conditions (offset5 ... rot13 via `make_map`); the episode then
               reports `compensation_frac` and the B reference agents are used, exactly as in the pilots
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar

import numpy as np

from freehand.sim import plotter
from freehand.sim.geometry import TOL_MM


@dataclass(frozen=True)
class Params:
    """Base of the typed parameter dataclasses. Subclasses validate in __post_init__."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Params:
        d = dict(d or {})
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"{cls.__name__}: unknown parameter(s) {sorted(unknown)}; expected {sorted(known)}")
        for k, v in list(d.items()):
            if isinstance(v, list):
                d[k] = tuple(v)
        return cls(**d)


@dataclass(frozen=True)
class NoParams(Params):
    pass


class Perturbation:
    """Identity rule (the historical `levels.Scenario` base); subclasses override `expected` / `oracle_cmd`."""

    type_name: ClassVar[str] = "identity"
    params_cls: ClassVar[type[Params]] = NoParams
    family: ClassVar[str] = "plotter"
    level: ClassVar[str] = "?"               # historical level label (L2rot, L3 ... X_ARX)
    reference_level: ClassVar[str | None] = None   # which ideal estimator (LAdaptive level) fits this rule
    legacy_map: ClassVar[bool] = False
    summary: ClassVar[str] = "no change"

    tol: float = TOL_MM
    prompt_extra: str = ""
    warp = None
    variant: str = ""

    def __init__(self, seed: int, params: Params | None = None, *, name: str | None = None, step: int = 0):
        self.seed = int(seed)
        self.params = params if params is not None else self.params_cls()
        self.name = name or self.type_name
        self.step = step            # ladder rung (0-based); provenance only
        self.n0: int | None = None

    # ------------------------------------------------------------------ historical knob and names
    @property
    def knob(self):
        """The historical `knob` value (levels.KNOBS entry); recorded in describe() for comparability."""
        return 0

    @property
    def legacy_cond(self) -> str:
        """The condition string the historical code recorded as `pert` (e.g. "L3_k2")."""
        return f"{self.level}{self.variant}_k{self.step + 1}"

    @property
    def key(self) -> str:
        return f"{self.level}{self.variant}:{self.knob}"

    # ------------------------------------------------------------------ rule
    def start(self, n0: int) -> None:
        self.n0 = n0

    def expected(self, pts: np.ndarray, n: int) -> np.ndarray:
        return pts

    def land(self, cmd, seed: int, n: int) -> np.ndarray:
        return plotter.land(cmd, plotter.FunctionMapper(lambda p: self.expected(p, n)), seed, n)

    def oracle_cmd(self, target, n: int) -> np.ndarray:
        return np.asarray(target, float)

    # ------------------------------------------------------------------ episode hooks
    def current_map(self, active: bool) -> plotter.PlotterMap:
        """The plotter map the B reference agents see (identity unless this is a legacy plotter-map change)."""
        return plotter.PlotterMap()

    def describe(self) -> dict[str, Any]:
        """Everything needed to reconstruct the rule: the historical keys plus type/name/params."""
        return {"level": self.level, "variant": self.variant, "step": self.step + 1, "knob": _jsonable(self.knob),
                "tol": self.tol, "prompt_extra": self.prompt_extra, "type": self.type_name, "name": self.name,
                "params": _jsonable(self.params.to_dict())}


def _jsonable(v):
    if isinstance(v, tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, np.generic):
        return v.item()
    return v
