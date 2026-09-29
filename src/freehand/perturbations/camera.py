"""Freehand A: the camera is uncalibrated, and may move.

The plotter never changes; the agent sees a raw camera frame through a homography H (page mm -> px):
  transfer  pose H1 from the start, moved to H2 after the change square P (the agent must re-anchor)
  fresh     the same later squares, at H2 from the start, with no old marks (the no-transfer baseline); the episode
            works on squares P+1.. renumbered from 1 and has no change point
  static    H1 throughout (no move)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from freehand.perturbations.base import Params, Perturbation
from freehand.sim import camera
from freehand.sim.page import Square, renumber

CAMERA_MODES = ("transfer", "fresh", "static")
LEGACY_COND = {"transfer": "cam_transfer", "fresh": "cam_fresh", "static": "cam_static"}


@dataclass(frozen=True)
class CameraMoveParams(Params):
    mode: str = "transfer"

    def __post_init__(self):
        if self.mode not in CAMERA_MODES:
            raise ValueError(f"camera_move mode must be one of {CAMERA_MODES}")


class CameraMove(Perturbation):
    type_name, params_cls, family, level = "camera_move", CameraMoveParams, "camera", "A"
    summary = "raw uncalibrated camera view; the camera moves (Freehand A)"
    params: CameraMoveParams

    def __init__(self, seed, params=None, *, name=None, step=0):
        super().__init__(seed, params, name=name, step=step)
        self.H1 = camera.make_camera(self.seed, 1)
        self.H2 = camera.make_camera(self.seed, 2)

    @property
    def mode(self) -> str:
        return self.params.mode

    @property
    def legacy_cond(self) -> str:
        return LEGACY_COND[self.mode]

    @property
    def knob(self):
        return self.mode

    def episode_squares(self, squares: list[Square], perturb_after: int) -> tuple[list[Square], int]:
        """(the squares this episode works on, its change point)."""
        if self.mode == "fresh":
            return renumber(squares[perturb_after:]), 0
        return squares, perturb_after

    def view_H(self, active: bool) -> np.ndarray:
        if self.mode == "fresh":
            return self.H2
        if self.mode == "transfer" and active:
            return self.H2
        return self.H1

    def changes_view(self) -> bool:
        return self.mode == "transfer"

    def describe(self):
        return {**super().describe(), "H1": self.H1.tolist(), "H2": self.H2.tolist()}
