"""The simulated world of one episode: the page, the ink laid so far, the stroke counter and the change.

The change switches on after the change square P (at the start when P = 0): from then on every stroke lands through
the perturbation (plotter family) or the camera shows the new pose (camera family, `transfer` mode).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from freehand.perturbations.base import Perturbation
from freehand.perturbations.camera import CameraMove
from freehand.sim import camera, plotter, render
from freehand.sim.geometry import PX
from freehand.sim.page import Square


class World:
    def __init__(self, seed: int, squares: list[Square], perturbation: Perturbation, perturb_after: int):
        self.seed = seed
        self.squares = squares
        # duck-typed: plotter-map, scenario and camera rules expose different hooks (legacy_map / is_camera)
        self.pert: Any = perturbation
        self.perturb_after = perturb_after
        self.plot_ink: list[np.ndarray] = []
        self.stroke_no = 0
        self.active = False
        self.is_camera = isinstance(perturbation, CameraMove)
        self.perturb_stroke: int | None = 1 if perturb_after == 0 else None
        if perturb_after == 0 and not self.is_camera:
            self._activate(1)

    # ------------------------------------------------------------------ the change
    def _activate(self, n0: int) -> None:
        self.active = True
        self.pert.start(n0)

    def end_square(self, sq_idx: int) -> None:
        """Called after each square; switches the change on after square P."""
        if sq_idx == self.perturb_after:
            self.perturb_stroke = self.stroke_no + 1
            self._activate(self.stroke_no + 1)

    @property
    def view_kind(self) -> str:
        return "raw" if self.is_camera else "rect"

    @property
    def scen_on(self) -> bool:
        """The historical `scen_on`: a ladder/discriminating rule is active (never for plotter-map or camera)."""
        return self.active and not self.pert.legacy_map and not self.is_camera

    @property
    def warp(self):
        return self.pert.warp if self.scen_on else None

    @property
    def H(self):
        return self.pert.view_H(self.active) if self.is_camera else None

    @property
    def H_old(self):
        return self.pert.H1 if self.is_camera else None

    @property
    def change_active(self) -> bool:
        if self.is_camera:
            return self.active and self.pert.changes_view()
        if self.pert.legacy_map:
            return self.active and self.pert.map.kind != "none"
        return self.active

    def current_map(self) -> plotter.PlotterMap:
        return self.pert.current_map(self.active)

    def view_H_record(self):
        """The page-mm -> image-px map of the current view, for the turn log (None for the plain rectified view)."""
        if self.H is not None:
            return np.asarray(self.H).tolist()
        if self.warp is not None:
            return (np.diag([PX, PX, 1.0]) @ np.vstack([self.warp, [0, 0, 1.0]])).tolist()
        return None

    # ------------------------------------------------------------------ observation
    def render(self, current: Square | None) -> np.ndarray:
        if self.is_camera:
            return camera.render_raw(self.seed, self.squares, self.plot_ink, self.H, current)
        if self.warp is not None:
            return render.render_view_warp(self.seed, self.squares, self.plot_ink, current, self.warp)
        return render.render_view(self.seed, self.squares, self.plot_ink, current)

    def crop(self, sq: Square):
        return render.crop_view(self.seed, self.squares, self.plot_ink, sq, self.warp)

    def final_views(self) -> dict[str, np.ndarray]:
        out = {"final": render.render_view(self.seed, self.squares, self.plot_ink, None)}
        if self.is_camera:
            out["final_raw"] = camera.render_raw(self.seed, self.squares, self.plot_ink, self.H, None)
        return out

    # ------------------------------------------------------------------ action
    def land(self, cmd) -> np.ndarray:
        """Execute one (already clamped) stroke; returns the dense ink polyline."""
        self.stroke_no += 1
        if self.active and not self.is_camera:
            ink = self.pert.land(cmd, self.seed, self.stroke_no)
        else:
            ink = plotter.land(cmd, plotter.PlotterMap(), self.seed, self.stroke_no)
        self.plot_ink.append(ink)
        return ink

    def compensation_frac(self, cmd, open_ends) -> float | None:
        """Plotter-map conditions: how far the command moved from the target towards the ideal compensation
        (0 = none, 1 = full), projected on the needed correction."""
        if not (self.pert.legacy_map and self.active and self.pert.map.kind != "none"):
            return None
        tgt = np.asarray(open_ends)
        ends = np.array([cmd[0], cmd[-1]])
        if np.linalg.norm(ends - tgt[::-1]).sum() < np.linalg.norm(ends - tgt).sum():
            ends = ends[::-1]
        need = (self.pert.map.inverse(tgt) - tgt).mean(0)
        return float(np.dot((ends - tgt).mean(0), need) / max(np.dot(need, need), 1e-9))
