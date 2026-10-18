"""A physical pinhole camera above the page, and the page-to-photo homography it induces.

World frame: page millimetres, x to the right and y down the sheet (as everywhere in Freehand), and z = x × y points
*into* the table, so a camera above the page has negative z. A pose is (K, R, t) with camera coordinates
X_c = R X_w + t; the camera looks along its +z axis, image x to the right, image y down.

For points on the page (z = 0) the camera is the homography H = K [r1 r2 t] (page mm -> frame px). Given the
intrinsics K, any page-to-photo homography decomposes back into a pose (`pose_from_homography`); that is how a model's
reported belief about the camera becomes a camera in 3D for the video.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from freehand import seeding

FRAME = 960  # square frame, px
FOV_DEG = (38.0, 50.0)  # horizontal field of view
TILT_DEG = (18.0, 38.0)  # optical axis from vertical
ROLL_DEG = 30.0  # rotation about the optical axis, +- this
PX_PER_MM_AT_TARGET = (4.6, 6.0)  # scale where the optical axis meets the page
TARGET_JITTER_MM = 10.0
POSE_TRIES = 20000
FRAME_CLEARANCE_PX = 40  # the work area (plus margin) stays this far inside the frame
MIN_MOVE_MM = 25.0  # the second pose's view differs from the first by at least this (mean over the frame grid)


@dataclass(frozen=True)
class Pose:
    K: np.ndarray  # 3x3 intrinsics
    R: np.ndarray  # 3x3 world -> camera rotation
    t: np.ndarray  # (3,) world -> camera translation

    @property
    def centre(self) -> np.ndarray:
        """The camera centre in world coordinates (z < 0: above the page)."""
        return -self.R.T @ self.t

    @property
    def H(self) -> np.ndarray:
        """Page mm -> frame px."""
        H = self.K @ np.c_[self.R[:, 0], self.R[:, 1], self.t]
        return H / H[2, 2]

    @property
    def tilt_deg(self) -> float:
        """Angle between the optical axis and the page normal."""
        return float(np.degrees(np.arccos(np.clip(abs(self.R[2, 2]), -1.0, 1.0))))

    def to_dict(self) -> dict:
        return {"K": self.K.tolist(), "R": self.R.tolist(), "t": self.t.tolist(), "H": self.H.tolist()}

    @staticmethod
    def from_dict(d: dict) -> Pose:
        return Pose(np.asarray(d["K"], float), np.asarray(d["R"], float), np.asarray(d["t"], float))


def intrinsics(fov_deg: float, size: int = FRAME) -> np.ndarray:
    f = (size / 2) / np.tan(np.radians(fov_deg) / 2)
    return np.array([[f, 0, size / 2], [0, f, size / 2], [0, 0, 1.0]])


def _rot(axis, angle: float) -> np.ndarray:
    """Rodrigues rotation matrix about a unit axis."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k


def look_at_pose(target_mm, tilt_deg: float, azimuth_deg: float, roll_deg: float, px_per_mm: float, fov_deg: float):
    """A camera aimed at `target_mm` on the page, its axis tilted `tilt_deg` from vertical towards `azimuth_deg`,
    rolled about its axis, at the distance that gives `px_per_mm` at the target."""
    K = intrinsics(fov_deg)
    # camera -> world rotation: start looking straight down (+z, into the table) with image axes = page axes, roll
    # about the axis, then tilt about a horizontal axis perpendicular to the azimuth.
    phi = np.radians(azimuth_deg)
    R_cw = _rot((-np.sin(phi), np.cos(phi), 0.0), np.radians(tilt_deg)) @ _rot((0, 0, 1.0), np.radians(roll_deg))
    forward = R_cw[:, 2]
    dist = K[0, 0] / px_per_mm
    target = np.array([target_mm[0], target_mm[1], 0.0])
    C = target - dist * forward
    R = R_cw.T
    return Pose(K, R, -R @ C)


def project(H, pts) -> np.ndarray:
    pts = np.asarray(pts, np.float64).reshape(-1, 2)
    p = np.c_[pts, np.ones(len(pts))] @ np.asarray(H, float).T
    return p[:, :2] / p[:, 2:3]


def frame_grid(n: int = 5, size: int = FRAME) -> np.ndarray:
    """An n x n grid of frame points (px), used to compare two camera maps over the whole view."""
    g = np.linspace(0, size, n)
    return np.array([[x, y] for y in g for x in g], float)


def view_error_mm(H_a, H_b, n: int = 5) -> float:
    """Mean distance on the page (mm) between where two camera maps place the same frame points."""
    g = frame_grid(n)
    return float(np.linalg.norm(project(np.linalg.inv(H_a), g) - project(np.linalg.inv(H_b), g), axis=1).mean())


def sample_pose(seed: int, tag: int, work_area, margin_mm: float = 6.0, avoid: Pose | None = None) -> Pose:
    """A random pose that sees the whole work area (plus a margin) with clearance, looking down from above.

    `avoid`: a pose the new one must differ from by at least MIN_MOVE_MM (the camera move)."""
    rng = seeding.rng(seed, "camera3d.pose", tag)
    x0, y0, x1, y1 = work_area
    m = margin_mm
    work = np.array([[x0 - m, y0 - m], [x1 + m, y0 - m], [x1 + m, y1 + m], [x0 - m, y1 + m]], float)
    centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    c = FRAME_CLEARANCE_PX
    for _ in range(POSE_TRIES):
        pose = look_at_pose(
            centre + rng.uniform(-TARGET_JITTER_MM, TARGET_JITTER_MM, 2),
            rng.uniform(*TILT_DEG),
            rng.uniform(0, 360),
            rng.uniform(-ROLL_DEG, ROLL_DEG),
            rng.uniform(*PX_PER_MM_AT_TARGET),
            rng.uniform(*FOV_DEG),
        )
        w = project(pose.H, work)
        if w.min() < c or w.max() > FRAME - c:
            continue
        if avoid is not None and view_error_mm(pose.H, avoid.H) < MIN_MOVE_MM:
            continue
        return pose
    raise RuntimeError(f"no camera pose found for seed {seed}, pose {tag}")


def pose_from_homography(H, K) -> Pose | None:
    """The camera pose that induces the page->photo homography H under intrinsics K (nearest rotation), with the
    camera above the page. None if H is degenerate."""
    B = np.linalg.inv(K) @ np.asarray(H, float)
    n1, n2 = np.linalg.norm(B[:, 0]), np.linalg.norm(B[:, 1])
    if not np.isfinite(B).all() or n1 < 1e-12 or n2 < 1e-12:
        return None
    lam = 2.0 / (n1 + n2)
    if B[2, 2] * lam < 0:  # the page must be in front of the camera (t_z > 0)
        lam = -lam
    r1, r2, t = B[:, 0] * lam, B[:, 1] * lam, B[:, 2] * lam
    U, _, Vt = np.linalg.svd(np.c_[r1, r2, np.cross(r1, r2)])
    R = U @ Vt
    if np.linalg.det(R) < 0:
        R = U @ np.diag([1, 1, -1]) @ Vt
    return Pose(np.asarray(K, float), R, t)
