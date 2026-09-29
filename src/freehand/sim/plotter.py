"""The simulated plotter: where commanded ink actually lands, and when a stroke closes a square.

Landing model (page mm), estimated from the real rig (historical `estimate_scatter.py` -> `scatter_estimate.json`):

    ink = M(command) + stroke_offset + wobble
    stroke_offset ~ N(0, 0.30^2) per axis, one per stroke     (turn-to-turn offset SD measured 0.29 / 0.32)
    wobble: smooth along the stroke, SD 0.40 per axis          (within-stroke residual <= 0.69, an upper bound)

so each ink end lands within about 0.5 mm per axis of M(command). M is the plotter map (identity, or a perturbation).
The noise is seeded by (page seed, stroke number) through the `landing` stream, so a perturbed episode and its
unperturbed twin share their scatter stroke for stroke.

Closure: a stroke closes the current square when both ends of its ink land within `tol` of the two open corners (either
order) and the ink is roughly straight (max deviation from its end-to-end chord <= tol). With 0.5 mm end scatter a
perfectly aimed stroke closes with probability ~0.997 at tol = 2 mm; a 5 mm offset never does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from freehand import seeding
from freehand.sim.geometry import CENTRE, TOL_MM

DENSIFY_STEP_MM = 0.25  # commanded polylines are sampled every 0.25 mm before mapping


class Mapper(Protocol):
    def apply(self, pts: np.ndarray) -> np.ndarray: ...


@dataclass
class Landing:
    """Scatter of the pen (see module docstring). `bias_mm` is 0 in simulation (the rig showed ~(-0.47, -0.46))."""

    sd_stroke: float = 0.30
    sd_wobble: float = 0.40
    wobble_len_mm: float = 4.0
    bias_mm: tuple = (0.0, 0.0)


@dataclass
class PlotterMap:
    """A global plotter map about the page centre: none | offset | rotation | scale."""

    kind: str = "none"
    dx: float = 0.0
    dy: float = 0.0
    theta_deg: float = 0.0
    scale: float = 1.0

    def apply(self, pts):
        pts = np.asarray(pts, float)
        c = np.array(CENTRE)
        if self.kind == "none":
            return pts.copy()
        if self.kind == "offset":
            return pts + [self.dx, self.dy]
        if self.kind == "rotation":
            t = math.radians(self.theta_deg)
            R = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
            return c + (pts - c) @ R.T
        if self.kind == "scale":
            return c + (pts - c) * self.scale
        raise ValueError(f"unknown plotter map kind {self.kind!r}")

    def inverse(self, pts):
        pts = np.asarray(pts, float)
        c = np.array(CENTRE)
        if self.kind == "none":
            return pts.copy()
        if self.kind == "offset":
            return pts - [self.dx, self.dy]
        if self.kind == "rotation":
            return PlotterMap("rotation", theta_deg=-self.theta_deg).apply(pts)
        if self.kind == "scale":
            return c + (pts - c) / self.scale
        raise ValueError(f"unknown plotter map kind {self.kind!r}")


class FunctionMapper:
    """Adapts a function of dense points to the `Mapper` protocol."""

    def __init__(self, f):
        self.f = f

    def apply(self, pts):
        return self.f(np.asarray(pts, float))


def smooth_path_noise(n: int, step_mm: float, len_mm: float, sd: float, rng: np.random.Generator) -> np.ndarray:
    """n x 2 Gaussian noise, smoothed along the path with a kernel of about len_mm, rescaled to SD `sd`."""
    k = max(2, int(len_mm / step_mm))
    w = rng.normal(0, 1, (n + 4 * k, 2))
    ker = np.exp(-0.5 * (np.arange(-2 * k, 2 * k + 1) / k) ** 2)
    ker /= ker.sum()
    w = np.stack([np.convolve(w[:, i], ker, mode="same") for i in range(2)], 1)[2 * k : 2 * k + n]
    return w / (w.std() + 1e-9) * sd


def densify(poly, step: float = DENSIFY_STEP_MM) -> np.ndarray:
    """A polyline resampled so consecutive points are at most `step` mm apart (vertices kept)."""
    poly = np.asarray(poly, float)
    out = [poly[0]]
    for a, b in zip(poly[:-1], poly[1:], strict=False):
        n = max(1, int(np.linalg.norm(b - a) / step))
        out.extend(a + (b - a) * (i / n) for i in range(1, n + 1))
    return np.array(out)


def land(poly, pmap: Mapper, seed: int, stroke_no: int, L: Landing | None = None) -> np.ndarray:
    """Commanded polyline (page mm) -> the ink actually laid, densely sampled."""
    L = L or Landing()
    rng = seeding.rng(seed, "landing", stroke_no)
    pts = pmap.apply(densify(poly))
    off = rng.normal(0, L.sd_stroke, 2) + np.array(L.bias_mm)
    return pts + off + smooth_path_noise(len(pts), DENSIFY_STEP_MM, L.wobble_len_mm, L.sd_wobble, rng)


def closure(ink, open_ends, tol: float = TOL_MM) -> tuple[bool, list[float], float]:
    """(closed, end_errors_mm, straight_dev_mm) for one ink polyline against a square's two open corners."""
    ink = np.asarray(ink, float)
    a, b = ink[0], ink[-1]
    p, q = np.asarray(open_ends, float)
    e1 = (np.linalg.norm(a - p), np.linalg.norm(b - q))
    e2 = (np.linalg.norm(a - q), np.linalg.norm(b - p))
    errs = e1 if max(e1) <= max(e2) else e2
    chord = b - a
    length = np.linalg.norm(chord)
    dev = (
        0.0
        if length < 1e-6
        else float(np.abs(chord[0] * (ink[:, 1] - a[1]) - chord[1] * (ink[:, 0] - a[0])).max() / length)
    )
    return bool(max(errs) <= tol and dev <= tol), [round(float(e), 3) for e in errs], round(dev, 3)


def poly_len(p) -> float:
    """Length of a polyline in mm."""
    p = np.asarray(p, float)
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 0.0
