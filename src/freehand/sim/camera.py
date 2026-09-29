"""Freehand A: an uncalibrated, movable camera.

The agent sees a raw camera frame (no grid, no reachable-region box, paper edges out of view) of the page through a
homography H (page mm -> frame px). Its commands are still in page mm, so it must learn H from its own marks, and
re-learn it when the camera moves.
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from freehand import seeding
from freehand.sim.geometry import LETTER_H, LETTER_W, PX
from freehand.sim.page import Square
from freehand.sim.render import all_ink, highlight_margin, outline_polygon, render_rect

CAM_W = CAM_H = 960                          # raw camera frame, px
A_AREA = (48.0, 72.0, 168.0, 207.0)          # where camera-track squares live (page mm): every pose sees all of it
A_SIZES = (18.0, 30.0)                       # while the paper edges stay out of frame
A_GAP_MM = 8.0
POSE_TRIES = 5000
POSE_ROT_DEG = 25.0                          # rotation +- this
POSE_MM_ACROSS = (CAM_W / 6.6, CAM_W / 5.4)  # mm seen across the frame (5.4-6.6 px/mm)
POSE_SHIFT_MM = 12.0
POSE_CORNER_JITTER = 0.09                    # perspective: corner jitter as a fraction of the view
PAPER_EDGE_CLEARANCE_MM = 4.0
WORK_MARGIN_MM = 6.0
FRAME_CLEARANCE_PX = 25
VIGNETTE = 0.10
RAW_NOISE_SD = 1.5


def project(H, pts) -> np.ndarray:
    """Apply a 3x3 homography to N x 2 points."""
    pts = np.asarray(pts, np.float64).reshape(-1, 2)
    p = np.c_[pts, np.ones(len(pts))] @ np.asarray(H).T
    return p[:, :2] / p[:, 2:3]


def make_camera(seed: int, tag: int, area: tuple = A_AREA, tries: int = POSE_TRIES) -> np.ndarray:
    """A random camera pose as a homography page-mm -> raw-frame px. The frame back-projects to a quadrilateral
    strictly inside the sheet (paper edges hidden) that contains the whole working area."""
    rng = seeding.rng(seed, "camera.pose", tag)
    frame = np.array([[0, 0], [CAM_W, 0], [CAM_W, CAM_H], [0, CAM_H]], np.float32)
    ax0, ay0, ax1, ay1 = area
    m = WORK_MARGIN_MM
    work = np.array([[ax0 - m, ay0 - m], [ax1 + m, ay0 - m], [ax1 + m, ay1 + m], [ax0 - m, ay1 + m]], np.float64)
    c0 = np.array([(ax0 + ax1) / 2, (ay0 + ay1) / 2])
    e = PAPER_EDGE_CLEARANCE_MM
    for _ in range(tries):
        L = rng.uniform(*POSE_MM_ACROSS)
        th = np.radians(rng.uniform(-POSE_ROT_DEG, POSE_ROT_DEG))
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        sq = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * L / 2
        quad = (c0 + rng.uniform(-POSE_SHIFT_MM, POSE_SHIFT_MM, 2) + sq @ R.T
                + rng.uniform(-POSE_CORNER_JITTER, POSE_CORNER_JITTER, (4, 2)) * L)
        if quad[:, 0].min() < e or quad[:, 1].min() < e or quad[:, 0].max() > LETTER_W - e \
                or quad[:, 1].max() > LETTER_H - e:
            continue                                               # an edge of the paper would show
        H = cv2.getPerspectiveTransform(quad.astype(np.float32), frame)
        w = project(H, work)
        c = FRAME_CLEARANCE_PX
        if w[:, 0].min() < c or w[:, 1].min() < c or w[:, 0].max() > CAM_W - c or w[:, 1].max() > CAM_H - c:
            continue                                               # part of the work would be out of view
        return H.astype(np.float64)
    raise RuntimeError(f"no camera pose found for seed {seed}, pose {tag}")


@lru_cache(maxsize=1)
def _vignette() -> np.ndarray:  # float32 (H, W, 1)
    yy, xx = np.mgrid[0:CAM_H, 0:CAM_W].astype(np.float32)
    r2 = ((xx - CAM_W / 2) ** 2 + (yy - CAM_H / 2) ** 2) / (CAM_W / 2) ** 2
    return (1 - VIGNETTE * r2)[..., None]


def render_raw(seed: int, squares: list[Square], plot_ink, H, current: Square | None = None) -> np.ndarray:
    """The raw camera photo: the simulated page seen through H. The current square gets the same green outline and
    number, drawn in image space."""
    rect = render_rect(seed, all_ink(squares, plot_ink))
    S = np.diag([1.0 / PX, 1.0 / PX, 1.0])                     # rect px -> mm
    img = cv2.warpPerspective(rect, np.asarray(H) @ S, (CAM_W, CAM_H), flags=cv2.INTER_AREA,
                              borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    noise = seeding.rng(seed, "camera.noise").normal(0, RAW_NOISE_SD, img.shape)
    img = img * _vignette() + noise.astype(np.float32)  # type: ignore[attr-defined]  # an array (size=shape)
    view = np.clip(img, 0, 255).astype(np.uint8)
    if current is not None:
        m = highlight_margin(seed, current)
        x0, y0, x1, y1 = current.bbox
        box = project(H, [[x0 - m, y0 - m], [x1 + m, y0 - m], [x1 + m, y1 + m], [x0 - m, y1 + m]])
        outline_polygon(view, box, current.idx)
    return view
