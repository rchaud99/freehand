"""The real camera: ArUco markers on the sheet give the true page -> photo map of every frame; the model only ever
sees an interior crop (no markers, no paper edges).

Page frame: a US-letter sheet in page mm (origin top-left, x right, y down), as in the simulator. Four 20 mm ArUco
markers (DICT_4X4_50, ids 40-43) sit 8 mm in from the corners; their 16 corners at known page positions pin down the
homography H_frame (page mm -> full camera frame px) for every photo.

The crop is a square window of the full frame, resampled to 960 x 960 px, placed around the work area; H_crop =
S @ T @ H_frame. For the 3D view a pose is needed: the principal point is taken as the frame centre and the focal
length is estimated from the homography itself (Zhang's two constraints on a plane: r1 . r2 = 0, |r1| = |r2|).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from freehand.camera3d.belief import corners_from_H
from freehand.camera3d.env import WORK_AREA
from freehand.camera3d.pose import FRAME, Pose, pose_from_homography, project

LETTER_W, LETTER_H = 215.9, 279.4
DICT = cv2.aruco.DICT_4X4_50
MARKER_MM = 20.0
MARKER_INSET_MM = 8.0
MARKER_IDS = (40, 41, 42, 43)  # top-left, top-right, bottom-right, bottom-left
CROP_MARGIN_MM = 14.0  # the crop covers the work area plus this much
EDGE_CLEARANCE_MM = 3.0  # no paper edge within this of the crop
MARKER_CLEARANCE_MM = 3.0  # no marker within this of the crop


def marker_positions() -> dict[int, np.ndarray]:
    """Page-mm positions of each marker's 4 corners (ArUco order: TL, TR, BR, BL of the marker)."""
    s, i = MARKER_MM, MARKER_INSET_MM
    tl = {40: (i, i), 41: (LETTER_W - i - s, i), 42: (LETTER_W - i - s, LETTER_H - i - s), 43: (i, LETTER_H - i - s)}
    return {m: np.array([[x, y], [x + s, y], [x + s, y + s], [x, y + s]], float) for m, (x, y) in tl.items()}


@dataclass
class Detection:
    H: np.ndarray  # page mm -> full frame px
    n_markers: int
    rms_px: float  # reprojection error of the marker corners


def detect(frame: np.ndarray) -> Detection | None:
    """Find the sheet's markers in a full frame; None if fewer than 2 are visible."""
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT), cv2.aruco.DetectorParameters())
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    corners, ids, _ = det.detectMarkers(gray)
    if ids is None:
        return None
    pos = marker_positions()
    page, img = [], []
    for c, i in zip(corners, ids.ravel(), strict=True):
        if int(i) in pos:
            page.append(pos[int(i)])
            img.append(c.reshape(4, 2))
    if len(page) < 2:
        return None
    P, Q = np.vstack(page), np.vstack(img).astype(np.float64)
    H, _ = cv2.findHomography(P, Q, 0)
    if H is None:
        return None
    rms = float(np.sqrt(np.mean(np.sum((project(H, P) - Q) ** 2, axis=1))))
    return Detection(H / H[2, 2], len(page), rms)


def focal_from_homography(H, cx: float, cy: float) -> float | None:
    """Focal length (px) of the camera that induced the plane homography H, given the principal point (square
    pixels, no skew). Least squares over Zhang's two constraints; None if the view is too frontal to tell."""
    T = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1.0]])
    G = T @ np.asarray(H, float)
    h1, h2 = G[:, 0], G[:, 1]
    # with K = diag(f, f, 1) and x = 1/f^2:  a1 x + c1 = 0 (r1 . r2 = 0),  a2 x + c2 = 0 (|r1| = |r2|)
    a = np.array([h1[0] * h2[0] + h1[1] * h2[1], h1[0] ** 2 + h1[1] ** 2 - h2[0] ** 2 - h2[1] ** 2])
    c = np.array([h1[2] * h2[2], h1[2] ** 2 - h2[2] ** 2])
    aa = float(a @ a)
    if aa < 1e-18:
        return None
    x = -float(a @ c) / aa
    if x <= 0:
        return None
    return float(1.0 / np.sqrt(x))


@dataclass
class Crop:
    """A square window of the full frame (x0, y0, side, in full-frame px) shown to the model at FRAME x FRAME."""

    x0: float
    y0: float
    side: float

    @property
    def M(self) -> np.ndarray:
        """Full-frame px -> crop px."""
        s = FRAME / self.side
        return np.array([[s, 0, -s * self.x0], [0, s, -s * self.y0], [0, 0, 1.0]])

    def apply(self, frame: np.ndarray) -> np.ndarray:
        return cv2.warpAffine(frame, self.M[:2], (FRAME, FRAME), flags=cv2.INTER_AREA)

    def to_dict(self) -> dict:
        return {"x0": self.x0, "y0": self.y0, "side": self.side}


def choose_crop(H_frame, frame_shape, side: float | None = None) -> Crop:
    """The square window around the work area (plus margin). `side`: keep a given size (after a camera move)."""
    x0, y0, x1, y1 = WORK_AREA
    m = CROP_MARGIN_MM
    pts = project(H_frame, [[x0 - m, y0 - m], [x1 + m, y0 - m], [x1 + m, y1 + m], [x0 - m, y1 + m]])
    lo, hi = pts.min(0), pts.max(0)
    s = float(side if side is not None else max(hi - lo))
    c = (lo + hi) / 2
    h, w = frame_shape[:2]
    cx = float(np.clip(c[0] - s / 2, 0, max(0.0, w - s)))
    cy = float(np.clip(c[1] - s / 2, 0, max(0.0, h - s)))
    return Crop(cx, cy, s)


def crop_problems(H_frame, crop: Crop, frame_shape) -> list[str]:
    """Why a crop would be unfair or broken: markers or paper edges in view, work area cut off, out of frame."""
    probs = []
    h, w = frame_shape[:2]
    if crop.x0 < 0 or crop.y0 < 0 or crop.x0 + crop.side > w or crop.y0 + crop.side > h:
        probs.append("the crop runs off the camera frame")
    Hc = crop.M @ H_frame
    seen = corners_from_H(Hc).astype(np.float32)  # the page quad the crop shows
    e = EDGE_CLEARANCE_MM
    if seen[:, 0].min() < e or seen[:, 1].min() < e or seen[:, 0].max() > LETTER_W - e or seen[:, 1].max() > LETTER_H - e:
        probs.append("the crop would show a paper edge (move the camera closer, or aim it at the squares)")
    m = MARKER_CLEARANCE_MM
    for mid, c in marker_positions().items():
        box = np.array([c[0] + [-m, -m], c[1] + [m, -m], c[2] + [m, m], c[3] + [-m, m]], np.float32)
        area, _ = cv2.intersectConvexConvex(seen, box)
        if area > 0:
            probs.append(f"the crop would show marker {mid} (aim the camera more at the squares)")
    x0, y0, x1, y1 = WORK_AREA
    wa = project(Hc, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    if wa.min() < 20 or wa.max() > FRAME - 20:
        probs.append("part of the work area is outside the crop")
    return probs


def pose_for_crop(H_frame, crop: Crop, frame_shape, focal: float) -> Pose:
    """A physical pose (K, R, t) for the crop view: principal point at the full frame's centre, the given focal
    length, both mapped into crop pixels."""
    h, w = frame_shape[:2]
    K_full = np.array([[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1.0]])
    K = crop.M @ K_full
    p = pose_from_homography(crop.M @ H_frame, K)
    if p is None:
        raise RuntimeError("could not decompose the camera homography")
    return p


def view_error_between(H_measured, pose: Pose) -> float:
    """Mean page distance (mm) between the measured crop homography and the pose's own (the decomposition's
    approximation error; should be well under 1 mm)."""
    from freehand.camera3d.belief import aim_error_mm

    return aim_error_mm(H_measured, pose.H)
