"""Calibration-tier rules: global maps and the difficulty ladder (levels 2-7 of docs/benchmark_ladder.md).

Two historical code paths are kept, because their reference agents differ:
  * `PlotterMapChange` (types none / offset / rotation / scale): the pilot conditions offset5, offset10, rot3, rot6,
    scale95, scale73 and the hard-pilot rot13, built like the old `sim.make_map`. Reference agents: the B oracle,
    naive and the offset-then-similarity `adaptive` estimator.
  * Ladder levels L2 (rotation) ... L7 (scarce evidence), ported from the old `levels.py`. Reference agents: the level
    oracle/naive and the level's ideal estimator (`LAdaptive`).
The physics of `rotation` (13 deg) and `L2_rotation` are identical; only the reference estimator differs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from freehand import seeding
from freehand.agents import prompts
from freehand.perturbations.base import NoParams, Params, Perturbation
from freehand.sim import plotter
from freehand.sim.geometry import CENTRE

HOME_MM = (-33.215, 372.533)   # plotter home in page mm (page_calib.json plotter_to_page @ (0, 0)); pen parks here
PROMPT_L7 = prompts.text("v1/blocks/scarce_ink")        # the one extra prompt line of level 7


def map_draws(seed: int) -> tuple[float, float]:
    """(direction angle, sign) of a plotter-map change: the historical make_map draws, in their order."""
    r = seeding.rng(seed, "plotter.map")
    ang = r.uniform(0, 2 * math.pi)
    sign = r.choice([-1.0, 1.0])
    return float(ang), float(sign)


# ---------------------------------------------------------------- legacy plotter-map conditions
@dataclass(frozen=True)
class OffsetParams(Params):
    mm: float = 10.0

    def __post_init__(self):
        if not self.mm >= 0:
            raise ValueError("offset mm must be >= 0")


@dataclass(frozen=True)
class RotationParams(Params):
    degrees: float = 13.0

    def __post_init__(self):
        if not 0 <= self.degrees < 90:
            raise ValueError("rotation degrees must be in [0, 90)")


@dataclass(frozen=True)
class ScaleParams(Params):
    factor: float = 0.95

    def __post_init__(self):
        if not self.factor > 0:
            raise ValueError("scale factor must be > 0")


class PlotterMapChange(Perturbation):
    """A global plotter map switched on at the change point; direction/sign from the `plotter.map` stream."""
    type_name = "none"
    params_cls = NoParams
    legacy_map = True
    kind = "none"
    summary = "no change (plotter-map control)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        self.map = self._make_map()

    def _make_map(self) -> plotter.PlotterMap:
        return plotter.PlotterMap()

    @property
    def knob(self):
        return 0.0

    @property
    def legacy_cond(self) -> str:
        return self.name

    def expected(self, pts, n):
        return self.map.apply(pts)

    def land(self, cmd, seed, n):
        return plotter.land(cmd, self.map, seed, n)

    def oracle_cmd(self, target, n):
        return self.map.inverse(target)

    def current_map(self, active: bool) -> plotter.PlotterMap:
        return self.map if active else plotter.PlotterMap()

    def describe(self):
        return {**super().describe(), "map_after": {"kind": self.map.kind, "dx": self.map.dx, "dy": self.map.dy,
                                                    "theta_deg": self.map.theta_deg, "scale": self.map.scale}}


class OffsetChange(PlotterMapChange):
    type_name, params_cls, kind, summary = "offset", OffsetParams, "offset", "constant shift of every stroke"

    def _make_map(self):
        ang, _ = map_draws(self.seed)
        mag = self.params.mm
        return plotter.PlotterMap("offset", dx=round(mag * math.cos(ang), 3), dy=round(mag * math.sin(ang), 3))

    @property
    def knob(self):
        return self.params.mm


class RotationChange(PlotterMapChange):
    type_name, params_cls, kind, summary = "rotation", RotationParams, "rotation", "rotation about the page centre"

    def _make_map(self):
        _, sign = map_draws(self.seed)
        return plotter.PlotterMap("rotation", theta_deg=sign * self.params.degrees)

    @property
    def knob(self):
        return self.params.degrees


class ScaleChange(PlotterMapChange):
    type_name, params_cls, kind, summary = "scale", ScaleParams, "scale", "uniform scale about the page centre"

    def _make_map(self):
        return plotter.PlotterMap("scale", scale=self.params.factor)

    @property
    def knob(self):
        return self.params.factor


# ---------------------------------------------------------------- ladder levels
class L2Rotation(Perturbation):
    """Level 2: rotation about the page centre, sign from the seed (the objective/informed pilots' `rot13`)."""
    type_name, params_cls, level, reference_level = "L2_rotation", RotationParams, "L2rot", "L2rot"
    summary = "rotation about the page centre (ladder level 2)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        _, sign = map_draws(self.seed)
        self.map = plotter.PlotterMap("rotation", theta_deg=sign * self.params.degrees)

    @property
    def knob(self):
        return self.params.degrees

    def expected(self, pts, n):
        return self.map.apply(pts)

    def oracle_cmd(self, target, n):
        return self.map.inverse(target)


@dataclass(frozen=True)
class AffineParams(Params):
    sx: float = 1.12
    sy: float = 0.90
    shear_deg: float = 7.0

    def __post_init__(self):
        if not (self.sx > 0 and self.sy > 0 and abs(self.shear_deg) < 45):
            raise ValueError("L3 affine needs sx, sy > 0 and |shear_deg| < 45")


class L3Affine(Perturbation):
    """Level 3: anisotropic scale + shear about the page centre (a gantry out of square)."""
    type_name, params_cls, level, reference_level = "L3_affine", AffineParams, "L3", "L3"
    summary = "anisotropic scale + shear (ladder level 3)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        p = self.params
        self.A = np.array([[p.sx, 0], [0, p.sy]]) @ np.array([[1, math.tan(math.radians(p.shear_deg))], [0, 1]])
        self.c = np.array(CENTRE)

    @property
    def knob(self):
        return (self.params.sx, self.params.sy, self.params.shear_deg)

    def expected(self, pts, n):
        return self.c + (pts - self.c) @ self.A.T

    def oracle_cmd(self, target, n):
        return self.c + (np.asarray(target, float) - self.c) @ np.linalg.inv(self.A).T


@dataclass(frozen=True)
class BacklashParams(Params):
    play_mm: float = 3.0

    def __post_init__(self):
        if not self.play_mm >= 0:
            raise ValueError("backlash play_mm must be >= 0")


def play(pts: np.ndarray, b: float, start) -> np.ndarray:
    """Backlash as a play operator per axis: the carriage lags the command by up to b/2."""
    out = np.empty_like(pts)
    cur = np.asarray(start, float).copy()
    for i, p in enumerate(pts):
        cur = np.clip(cur, p - b / 2, p + b / 2)
        out[i] = cur
    return out


def canonical(cmd) -> list:
    """Order a 2-point stroke so it travels +x (mostly horizontal) or -y (mostly vertical), the directions the
    approach from the home position already moves in, so backlash gives one constant offset."""
    a, b = np.asarray(cmd[0], float), np.asarray(cmd[-1], float)
    d = b - a
    if abs(d[0]) >= abs(d[1]):
        return [a, b] if d[0] >= 0 else [b, a]
    return [a, b] if d[1] <= 0 else [b, a]


class L4Backlash(Perturbation):
    """Level 4: backlash; the pen parks at the plotter home before every turn, so the error depends on direction."""
    type_name, params_cls, level, reference_level = "L4_backlash", BacklashParams, "L4", "L4"
    summary = "direction-dependent backlash (ladder level 4)"

    @property
    def knob(self):
        return self.params.play_mm

    def expected(self, pts, n):
        b = self.params.play_mm
        approach = play(np.array([HOME_MM, pts[0]]), b, HOME_MM)[-1]     # travel from home, pen up
        return play(pts, b, approach)

    def oracle_cmd(self, target, n):
        b = self.params.play_mm
        return np.array(canonical(target)) + np.array([b / 2, -b / 2])


@dataclass(frozen=True)
class DriftParams(Params):
    mm_per_stroke: float = 0.7
    skip_prob: float = 0.15
    skip_mm: float = 2.0

    def __post_init__(self):
        if not (self.mm_per_stroke >= 0 and 0 <= self.skip_prob <= 1 and self.skip_mm >= 0):
            raise ValueError("L5 drift needs mm_per_stroke >= 0, 0 <= skip_prob <= 1, skip_mm >= 0")


class L5Drift(Perturbation):
    """Level 5: slow linear drift plus occasional skipped steps (2 mm jumps along one axis)."""
    type_name, params_cls, level, reference_level = "L5_drift", DriftParams, "L5", "L5"
    summary = "linear drift + skipped steps (ladder level 5)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        a = seeding.rng(self.seed, "drift.direction").uniform(0, 2 * math.pi)
        self.dir = np.array([math.cos(a), math.sin(a)])

    @property
    def knob(self):
        return (self.params.mm_per_stroke, self.params.skip_prob)

    def jump(self, k: int) -> np.ndarray:
        r = seeding.rng(self.seed, "drift.skip", k)
        if r.uniform() < self.params.skip_prob:
            v = np.zeros(2)
            v[r.integers(0, 2)] = r.choice([-1.0, 1.0]) * self.params.skip_mm
            return v
        return np.zeros(2)

    def offset(self, n: int) -> np.ndarray:
        k = n - self.n0 + 1
        return self.params.mm_per_stroke * k * self.dir + sum((self.jump(j) for j in range(self.n0, n + 1)),
                                                              np.zeros(2))

    def expected(self, pts, n):
        return pts + self.offset(n)

    def oracle_cmd(self, target, n):
        return np.asarray(target, float) - self.offset(n)


@dataclass(frozen=True)
class AttributionParams(Params):
    camera_shift_mm: float = 5.0
    camera_rot_deg: float = 2.0
    plotter_offset_mm: float = 6.0
    variant: str = "cam"

    def __post_init__(self):
        if self.variant not in ("cam", "plot", "both"):
            raise ValueError("L6 variant must be cam | plot | both")


class L6Attribution(Perturbation):
    """Level 6: the camera was bumped (stale rectification), the plotter changed, or both."""
    type_name, params_cls, level, reference_level = "L6_attribution", AttributionParams, "L6", "L6"
    summary = "camera bumped vs plotter changed vs both (ladder level 6)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        p = self.params
        self.variant = p.variant
        r = seeding.rng(self.seed, "attribution.geometry")
        a1, a2 = r.uniform(0, 2 * math.pi, 2)
        self.cam_on = p.variant in ("cam", "both")
        self.plot_on = p.variant in ("plot", "both")
        c = np.array(CENTRE)
        th = math.radians(p.camera_rot_deg) * r.choice([-1, 1])
        R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
        t = c - R @ c + p.camera_shift_mm * np.array([math.cos(a1), math.sin(a1)])
        self._W = np.c_[R, t]
        self.off = p.plotter_offset_mm * np.array([math.cos(a2), math.sin(a2)]) if self.plot_on else np.zeros(2)

    @property
    def knob(self):
        return (self.params.camera_shift_mm, self.params.camera_rot_deg, self.params.plotter_offset_mm)

    def start(self, n0):
        super().start(n0)
        self.warp = self._W if self.cam_on else None

    def expected(self, pts, n):
        return pts + self.off

    def oracle_cmd(self, target, n):
        return np.asarray(target, float) - self.off

    def describe(self):
        return {**super().describe(), "camera_warp": self._W.tolist() if self.cam_on else None,
                "plotter_offset": self.off.tolist()}


@dataclass(frozen=True)
class ScarceParams(Params):
    tol_mm: float = 1.0
    degrees: float = 13.0

    def __post_init__(self):
        if not self.tol_mm > 0:
            raise ValueError("L7 tol_mm must be > 0")


class L7Scarce(Perturbation):
    """Level 7: scarce evidence. Rotation 13 deg, a tighter closure tolerance and one extra prompt line."""
    type_name, params_cls, level, reference_level = "L7_scarce", ScarceParams, "L7", "L7"
    prompt_extra = PROMPT_L7
    summary = "rotation with a tight tolerance and an ink penalty line (ladder level 7)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        self.tol = self.params.tol_mm
        sign = float(seeding.rng(self.seed, "plotter.map").choice([-1, 1]))    # historical: the FIRST draw
        self.map = plotter.PlotterMap("rotation", theta_deg=self.params.degrees * sign)

    @property
    def knob(self):
        return self.params.tol_mm

    def expected(self, pts, n):
        return self.map.apply(pts)

    def oracle_cmd(self, target, n):
        return self.map.inverse(target)


# ---------------------------------------------------------------- the historical ladder rungs
LADDER_KNOBS = {
    "L3": [(1.06, 0.95, 3.0), (1.12, 0.90, 7.0), (1.20, 0.84, 12.0)],
    "L4": [3.0, 6.0, 10.0],
    "L5": [(0.7, 0.15), (1.2, 0.25), (2.0, 0.35)],
    "L6": [(5.0, 2.0, 6.0), (8.0, 4.0, 9.0), (12.0, 6.0, 12.0)],
    "L7": [1.0, 0.85, 0.75],
}
LADDER_TYPES = {"L3": "L3_affine", "L4": "L4_backlash", "L5": "L5_drift", "L6": "L6_attribution", "L7": "L7_scarce"}


def ladder_params(level: str, step: int, variant: str = "") -> dict:
    """Typed params (as a dict) of ladder rung `step` (0-based) of `level`, from the historical KNOBS."""
    k = LADDER_KNOBS[level][step]
    if level == "L3":
        return {"sx": k[0], "sy": k[1], "shear_deg": k[2]}
    if level == "L4":
        return {"play_mm": k}
    if level == "L5":
        return {"mm_per_stroke": k[0], "skip_prob": k[1]}
    if level == "L6":
        return {"camera_shift_mm": k[0], "camera_rot_deg": k[1], "plotter_offset_mm": k[2], "variant": variant}
    if level == "L7":
        return {"tol_mm": k}
    raise KeyError(level)
