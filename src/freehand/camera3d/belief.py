"""A model's belief about the camera, and how far it is from the truth.

The belief is four page points (where the model thinks the photo's corners are). Together with the photo's corner
pixels they fix a homography H_belief (page mm -> px). The headline error is the *aim error*: if the model aimed at
what it sees using its belief, how far (mm) from the intended page point would the pen go, averaged over a grid on
the work area. It is 0 for the true camera and does not depend on how the belief is parameterised.
"""

from __future__ import annotations

import numpy as np

from freehand.camera3d.env import WORK_AREA
from freehand.camera3d.pose import project
from freehand.camera3d.prompt import CORNER_PX, CORNERS

MATCH_MM = 3.0  # a belief this close (aim error) is "matched": good enough to close a square on the first stroke
GRID_N = 7


def corners_from_H(H) -> np.ndarray:
    """The page points (4 x 2, mm) a camera map puts at the photo's corners, in CORNERS order."""
    return project(np.linalg.inv(H), [CORNER_PX[c] for c in CORNERS])


def _cross2(a, b) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def H_from_corners(corners_mm) -> np.ndarray | None:
    """The homography page mm -> px from four believed corner positions, or None if they are degenerate (not a
    convex quadrilateral in the photo's corner order)."""
    q = np.asarray(corners_mm, float).reshape(4, 2)
    if not np.isfinite(q).all():
        return None
    # the corners go round the photo clockwise (image y down); the page quad must go round consistently
    cross = [_cross2(q[(i + 1) % 4] - q[i], q[(i + 2) % 4] - q[(i + 1) % 4]) for i in range(4)]
    if not (all(c > 1e-6 for c in cross) or all(c < -1e-6 for c in cross)):
        return None
    return homography_4pt(q, np.array([CORNER_PX[c] for c in CORNERS], float))


def homography_4pt(src, dst) -> np.ndarray | None:
    """The homography mapping four points exactly onto four others (float64; cv2's version works in float32)."""
    A, b = [], []
    for (x, y), (u, v) in zip(np.asarray(src, float), np.asarray(dst, float), strict=True):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    try:
        h = np.linalg.solve(np.array(A), np.array(b))
    except np.linalg.LinAlgError:
        return None
    return np.append(h, 1.0).reshape(3, 3)


def work_grid(n: int = GRID_N) -> np.ndarray:
    x0, y0, x1, y1 = WORK_AREA
    return np.array([[x, y] for y in np.linspace(y0, y1, n) for x in np.linspace(x0, x1, n)], float)


def aim_error_mm(H_true, H_belief) -> float:
    """Mean page distance (mm) between a work-area point and where a model aiming at its pixel would command.
    inf if there is no usable belief."""
    if H_belief is None:
        return float("inf")
    p = work_grid()
    try:
        q = project(np.linalg.inv(H_belief), project(H_true, p))
    except np.linalg.LinAlgError:
        return float("inf")
    e = np.linalg.norm(q - p, axis=1)
    return float(e.mean()) if np.isfinite(e).all() else float("inf")


def turns_to_match(errors: list[float], start: int = 0, threshold: float = MATCH_MM) -> int | None:
    """Strokes from `start` until the belief first comes within `threshold` and stays there for the rest of the
    stretch (errors[start:]); None if it never does."""
    seg = errors[start:]
    for i in range(len(seg)):
        if all(e <= threshold for e in seg[i:]):
            return i + 1
    return None


IMPLIED_WINDOW = 5  # strokes


def _pair_ends(cmd, target) -> tuple[np.ndarray, np.ndarray]:
    """A stroke's two commanded ends matched to the target's two free ends (either direction)."""
    c, g = np.asarray(cmd, float), np.asarray(target, float)
    if np.linalg.norm(c - g, axis=1).sum() > np.linalg.norm(c[::-1] - g, axis=1).sum():
        c = c[::-1]
    return c, g


def implied_camera(true_pose, strokes: list[dict], targets: list) -> np.ndarray | None:
    """The camera under which the agent's recent strokes would have been perfect.

    Each commanded end (page mm) is paired with the free end it was aiming at. An affine map A (target -> command)
    is fitted to those pairs by least squares; if the camera were H_true @ inv(A), every command would have landed
    exactly on its target, so that is the camera the strokes imply. Affine (6 parameters) rather than a full camera
    fit, because a handful of short strokes clustered around a few squares cannot pin down perspective: a full fit
    swings wildly. Needs at least 2 strokes whose ends are not all on one line. Returns page mm -> px, or None."""
    if len(strokes) < 2:
        return None
    cmd, tgt = [], []
    for s, g in zip(strokes, targets, strict=True):
        c, gg = _pair_ends(s["cmd"], g)
        cmd += c.tolist()
        tgt += gg.tolist()
    c_a, g_a = np.array(cmd, float), np.array(tgt, float)
    if np.linalg.matrix_rank(g_a - g_a.mean(0), tol=1.0) < 2:
        return None
    X = np.c_[g_a, np.ones(len(g_a))]
    coef, *_ = np.linalg.lstsq(X, c_a, rcond=None)  # 3 x 2: command = [x y 1] @ coef
    A = np.vstack([coef.T, [0.0, 0.0, 1.0]])
    if abs(np.linalg.det(A[:2, :2])) < 0.2:  # degenerate fit
        return None
    H = np.asarray(true_pose.H) @ np.linalg.inv(A)
    return H / H[2, 2]


def implied_window(rec_turns: list[dict], squares: dict, idx: int, window: int = IMPLIED_WINDOW):
    """The strokes (and their targets) of turn idx and the turns before it at the same camera pose."""
    pose = rec_turns[idx]["pose"]
    sel = [rec_turns[j] for j in range(max(0, idx - window + 1), idx + 1) if rec_turns[j]["pose"] == pose]
    return [t["stroke"] for t in sel], [squares[t["stroke"]["square"]]["open_ends"] for t in sel]
