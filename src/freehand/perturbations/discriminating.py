"""Discriminating-tier rules (ported from the Codex publication copy's `perturbations.py`).

These are designed so that local patching (correct each square by its observed miss) does NOT work well:
  * command memory: executed endpoints low-pass the commanded ones, with state persisting across strokes, so a
    correction changes the state the next command starts from;
  * latent mirror mode: whether the NEXT stroke is mirrored depends on where the previous command started, so the
    correction flips the mode;
  * smooth cross-axis warp: a sinusoidal x(y) deformation; globally affine fits miss it and long vertical strokes
    need a curved inverse.
Each rule is deterministic apart from the plotter's seeded ink noise, and its state advances once per executed
stroke (including failed strokes).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from freehand import seeding
from freehand.perturbations.base import Params, Perturbation
from freehand.sim import plotter
from freehand.sim.geometry import CENTRE, LETTER_H, LETTER_W

MIRROR_THRESHOLD_RANGE_MM = (85, 130)    # seeded threshold when not given
WARP_INVERSE_STEP_MM = 2.0               # polyline resolution of the curved inverse command


@dataclass(frozen=True)
class CommandMemoryParams(Params):
    gains: tuple = (0.82, 0.72)

    def __post_init__(self):
        a = np.asarray(self.gains, float)
        if a.shape != (2,) or not np.all((a > 0) & (a <= 1)):
            raise ValueError("command_memory gains must contain two gains in (0, 1]")


class CommandDynamics(Perturbation):
    """Endpoint low-pass dynamics persisting across strokes (a first-order ARX rule)."""
    type_name, params_cls, level = "command_memory", CommandMemoryParams, "X_ARX"
    summary = "firmware smooths commands; state persists across strokes (ARX)"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        self.alpha = np.asarray(self.params.gains, float)
        self.state = np.array(CENTRE)

    @property
    def knob(self):
        return tuple(self.params.gains)

    def start(self, n0):
        super().start(n0)
        self.state = np.array(CENTRE)

    def expected(self, pts, n):
        state = self.state.copy()
        out = []
        for p in np.asarray(pts, float):
            state = state + self.alpha * (p - state)
            out.append(state.copy())
        return np.array(out)

    def land(self, cmd, seed, n):
        executed = self.expected(cmd, n)
        self.state = executed[-1].copy()
        return plotter.land(executed, plotter.PlotterMap(), seed, n)

    def oracle_cmd(self, target, n):
        prev = self.state.copy()
        cmds = []
        for t in np.asarray(target, float):
            cmds.append(prev + (t - prev) / self.alpha)
            prev = t
        return np.array(cmds)


@dataclass(frozen=True)
class LatentMirrorParams(Params):
    threshold_mm: float | None = None      # None: drawn from the seed's `mirror.threshold` stream


class LatentMirror(Perturbation):
    """The previous command's start side sets the NEXT stroke's mirror mode (x -> page width - x)."""
    type_name, params_cls, level = "latent_mirror", LatentMirrorParams, "X_MODE"
    summary = "a latent mirror mode flipped by where the previous stroke started"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        t = self.params.threshold_mm
        self.threshold = (float(seeding.rng(self.seed, "mirror.threshold").uniform(*MIRROR_THRESHOLD_RANGE_MM))
                          if t is None else float(t))
        self.mirrored = False

    @property
    def knob(self):
        return self.threshold

    def start(self, n0):
        super().start(n0)
        self.mirrored = False

    def expected(self, pts, n):
        out = np.asarray(pts, float).copy()
        if self.mirrored:
            out[:, 0] = LETTER_W - out[:, 0]
        return out

    def land(self, cmd, seed, n):
        ink = plotter.land(cmd, plotter.FunctionMapper(lambda p: self.expected(p, n)), seed, n)
        self.mirrored = bool(cmd[0][0] < self.threshold)
        return ink

    def oracle_cmd(self, target, n):
        return self.expected(target, n)          # a reflection is its own inverse


@dataclass(frozen=True)
class WarpParams(Params):
    amplitude_mm: float = 8.0

    def __post_init__(self):
        if not self.amplitude_mm >= 0:
            raise ValueError("smooth_warp amplitude_mm must be >= 0")


class CrossAxisWarp(Perturbation):
    """Invertible nonlinear cross-axis deformation: x += a * sin(2 pi y / H + phase)."""
    type_name, params_cls, level = "smooth_warp", WarpParams, "X_WARP"
    summary = "smooth sinusoidal x(y) warp; globally affine fits miss it"

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        self.phase = float(seeding.rng(self.seed, "warp.phase").uniform(-np.pi, np.pi))

    @property
    def knob(self):
        return float(self.params.amplitude_mm)

    def expected(self, pts, n):
        out = np.asarray(pts, float).copy()
        out[:, 0] += self.knob * np.sin(2 * np.pi * out[:, 1] / LETTER_H + self.phase)
        return out

    def oracle_cmd(self, target, n):
        t = plotter.densify(target, step=WARP_INVERSE_STEP_MM)     # a polyline inverse straightens vertical strokes
        t[:, 0] -= self.knob * np.sin(2 * np.pi * t[:, 1] / LETTER_H + self.phase)
        return t

    def describe(self):
        return {**super().describe(), "phase": self.phase}


FAMILY_OF_TYPE = {"command_memory": "arx", "latent_mirror": "mode", "smooth_warp": "warp"}
