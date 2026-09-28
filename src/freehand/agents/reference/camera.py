"""Reference agents of Freehand A (raw camera view). Pixel perception noise 1 px.

  CamOracle    knows the camera
  CamNaive     assumes the first camera pose H1 forever
  CamAdaptive  re-measures all its own marks in the current photo every turn and fits page-mm -> pixels from
               commanded ends: similarity from 1 stroke, affine from 2, homography from 3+ (a generic prior before
               any mark)
"""
from __future__ import annotations

import cv2
import numpy as np

from freehand.agents.base import Agent, code_reply
from freehand.seeding import AGENT_SEEDS
from freehand.sim.camera import A_AREA, CAM_H, CAM_W, project

PIX_SD = 1.0                  # pixel perception noise
PRIOR_PX_PER_MM = 6.0


def fit_mm_to_px(mm, px):
    """Page-mm -> pixel map from correspondences: similarity (2 pts), affine (3-5), homography (6+)."""
    mm, px = np.asarray(mm, float), np.asarray(px, float)
    n = len(mm)
    if n >= 6:
        H, _ = cv2.findHomography(mm, px, 0)
        if H is not None:
            return H, "homography"
    if n >= 3:
        A = np.zeros((2 * n, 6))
        y = px.reshape(-1)
        A[0::2, 0:2], A[0::2, 2] = mm, 1
        A[1::2, 3:5], A[1::2, 5] = mm, 1
        p = np.linalg.lstsq(A, y, rcond=None)[0]
        return np.array([[p[0], p[1], p[2]], [p[3], p[4], p[5]], [0, 0, 1.0]]), "affine"
    A = np.zeros((2 * n, 4))
    y = px.reshape(-1)
    A[0::2] = np.c_[mm[:, 0], -mm[:, 1], np.ones(n), np.zeros(n)]
    A[1::2] = np.c_[mm[:, 1], mm[:, 0], np.zeros(n), np.ones(n)]
    a, b, tx, ty = np.linalg.lstsq(A, y, rcond=None)[0]
    return np.array([[a, -b, tx], [b, a, ty], [0, 0, 1.0]]), "similarity"


def prior_camera() -> np.ndarray:
    """A generic guess before any mark: the working area's centre at the photo's centre, 6 px/mm, no rotation."""
    ax0, ay0, ax1, ay1 = A_AREA
    c = np.array([(ax0 + ax1) / 2, (ay0 + ay1) / 2])
    s = PRIOR_PX_PER_MM
    return np.array([[s, 0, CAM_W / 2 - s * c[0]], [0, s, CAM_H / 2 - s * c[1]], [0, 0, 1.0]])


class _CamBase(Agent):
    def __init__(self):
        self.rng = np.random.default_rng(AGENT_SEEDS["camera_agents"])

    def target_px(self, obs):
        return project(obs["priv"]["H"], obs["priv"]["open_ends"]) + self.rng.normal(0, PIX_SD, (2, 2))


class CamOracle(_CamBase):
    name = "oracle"

    def act(self, obs):
        H = obs["priv"]["H"]
        return code_reply(project(np.linalg.inv(H), self.target_px(obs)), "Aiming through the true camera map.")


class CamNaive(_CamBase):
    name = "naive"

    def act(self, obs):
        Ho = obs["priv"]["H_old"]
        return code_reply(project(np.linalg.inv(Ho), self.target_px(obs)), "Assuming the first camera pose.")


class CamAdaptive(_CamBase):
    name = "adaptive"

    def act(self, obs):
        H = obs["priv"]["H"]
        mm, px = [], []
        for s in obs["priv"]["strokes"]:              # re-measure every own mark in the current photo
            for c, e in ((s["cmd"][0], s["ink_ends"][0]), (s["cmd"][-1], s["ink_ends"][1])):
                mm.append(c)
                px.append(project(H, [e])[0] + self.rng.normal(0, PIX_SD, 2))
        Hh, kind = (prior_camera(), "prior") if not mm else fit_mm_to_px(mm, px)
        cmd = project(np.linalg.inv(Hh), self.target_px(obs))
        return code_reply(cmd, f"Camera map fitted from {len(mm) // 2} own marks ({kind}).",
                          memory=f"{len(mm) // 2} marks; map {kind}")
