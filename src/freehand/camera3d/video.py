"""Videos of Freehand A episodes: what the model sees, and where it thinks the page is, in 3D.

The 3D view shows the true scene (the page, its ink, the camera and its field of view) from a slowly orbiting
viewpoint. The model's belief (four page points at the photo's corners) is a homography; with the camera's
intrinsics it decomposes into a pose, i.e. "the page is *there* relative to me". Placing that believed page in front of
the true camera gives a plane (translucent blue) inside the camera's field of view. It lies exactly on the real page
when the belief is right, and floats, tilts or slides when it is wrong. (The blue quad's corners are always on the
camera's four corner rays: they are the photo's corners, where the model says they are.)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from freehand.camera3d.belief import (
    MATCH_MM,
    H_from_corners,
    aim_error_mm,
    corners_from_H,
    implied_camera,
    implied_window,
    work_grid,
)
from freehand.camera3d.pose import Pose, pose_from_homography, project

FPS = 30
STEP_S = 0.8  # seconds per stroke
GLIDE = 0.5  # fraction of a step over which the blue plane glides to its new place
ORBIT_DEG = 14.0  # the viewpoint swings this much either side
ORBIT_PERIOD_S = 26.0
PHOTO_FRAC = 0.44  # the inset photo's side, as a fraction of the panel height
# colours (BGR)
BG = (24, 20, 17)
PANEL_EDGE = (52, 46, 42)
PAPER = (226, 231, 235)
PAPER_EDGE = (190, 196, 200)
INK = (70, 70, 70)
OWN_INK = (30, 30, 30)
TRUE = (250, 250, 250)
RAY = (150, 150, 150)
BLUE = (255, 150, 40)
BLUE_FILL = (255, 140, 30)
BLUE_GRID = (240, 185, 120)
ORANGE = (40, 150, 255)
ORANGE_FILL = (30, 140, 255)
GOLD = (80, 180, 235)
RED = (90, 90, 235)
GREEN = (110, 200, 90)
MUTED = (160, 160, 160)
WHITE = (245, 245, 245)
FONT = cv2.FONT_HERSHEY_SIMPLEX

DISPLAY = {
    "claude-opus-5.5": "Claude Opus 5.5",
    "gpt-6-astra": "GPT-6 Astra",
    "gpt-6-sol": "GPT-6 Sol",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "estimator": "Code estimator (ideal learner)",
    "oracle": "Oracle",
}


# ---------------------------------------------------------------- episode data
@dataclass
class Episode:
    dir: Path
    rec: dict
    poses: list[Pose]
    photos: list[Path]
    name: str
    _implied: dict = field(default_factory=dict)

    @property
    def turns(self) -> list[dict]:
        return [t for t in self.rec["turns"] if t.get("stroke")]

    @property
    def n(self) -> int:
        return len(self.turns)

    def pose_no_at(self, s: int) -> int:
        """The true camera (1 or 2) for the photo after stroke s (seen before stroke s + 1)."""
        if s < self.n:
            return int(self.turns[s]["pose"])
        m = self.rec["spec"]["move_after"]
        last_sq = self.turns[-1]["stroke"]["square"] if self.turns else 0
        return 2 if m and (last_sq > m or (last_sq == m and self.rec["outcomes"].get(str(m)))) else 1

    def pose_at(self, s: int) -> Pose:
        return self.poses[self.pose_no_at(s) - 1]

    def belief_at(self, s: int):
        """The belief (4 x 2 mm) reported while looking at photo s; the last one after the end."""
        if not self.turns:
            return None
        b = self.turns[min(s, self.n - 1)].get("belief")
        return None if b is None else np.asarray(b, float)

    def error_at(self, s: int):
        return None if not self.turns else self.turns[min(s, self.n - 1)].get("aim_error_mm")

    def implied_at(self, s: int):
        """The camera implied by the agent's strokes (the one under which its last few strokes, up to the one it is
        about to make after photo s, would have been perfect), page mm -> px; None with fewer than 2 strokes at this
        pose."""
        if not self.turns:
            return None
        idx = min(s, self.n - 1)
        if idx not in self._implied:
            sq = {q["idx"]: q for q in self.rec["squares"]}
            strokes, targets = implied_window(self.turns, sq, idx)
            self._implied[idx] = implied_camera(self.poses[self.turns[idx]["pose"] - 1], strokes, targets)
        return self._implied[idx]

    def implied_error_at(self, s: int):
        H = self.implied_at(s)
        if H is None:
            return None
        return aim_error_mm(self.poses[self.turns[min(s, self.n - 1)]["pose"] - 1].H, H)

    def photo(self, s: int) -> np.ndarray:
        return _read(str(self.photos[min(s, len(self.photos) - 1)]))


@lru_cache(maxsize=256)
def _read(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    return np.asarray(img)


def load_episode(d: Path) -> Episode:
    d = Path(d)
    rec = json.loads((d / "episode.json").read_text())
    poses = [Pose.from_dict(p) for p in rec["poses"]]
    photos = sorted((d / "photos").glob("*.png"))
    return Episode(d, rec, poses, photos, DISPLAY.get(rec["agent"], rec["agent"]))


# ---------------------------------------------------------------- drawing helpers
_FONT_FILES = ("/System/Library/Fonts/Avenir Next.ttc", "/System/Library/Fonts/HelveticaNeue.ttc")
_FACES = {"regular": 7, "medium": 5, "demi": 2, "bold": 0, "italic": 4, "medium_italic": 6}


@lru_cache(maxsize=64)
def _font(px: int, weight: str):
    from PIL import ImageFont

    for f in _FONT_FILES:
        try:
            return ImageFont.truetype(f, px, index=_FACES[weight] if "Avenir" in f else 0)
        except OSError:
            continue
    return None


def text(img, s, org, px=18, color=WHITE, weight="medium", anchor="ls"):
    """Draw text (BGR colour) with the system font; OpenCV's Hershey font if none is available."""
    font = _font(int(px), weight)
    if font is None:
        cv2.putText(img, s, (int(org[0]), int(org[1])), FONT, px / 32, color, 1, cv2.LINE_AA)
        return
    from PIL import Image, ImageDraw

    x, y = int(org[0]), int(org[1])
    left, top, right, bottom = font.getbbox(s, anchor=anchor)
    x0, y0 = max(0, x + left - 2), max(0, y + top - 2)
    x1, y1 = min(img.shape[1], x + right + 2), min(img.shape[0], y + bottom + 2)
    if x1 <= x0 or y1 <= y0:
        return
    tile = Image.fromarray(np.ascontiguousarray(img[y0:y1, x0:x1]))
    ImageDraw.Draw(tile).text((x - x0, y - y0), s, font=font, fill=tuple(int(c) for c in color), anchor=anchor)
    img[y0:y1, x0:x1] = np.asarray(tile)


def text_width(s, px=18, weight="medium") -> int:
    font = _font(int(px), weight)
    return int(font.getlength(s)) if font is not None else int(len(s) * px * 0.55)


def _pts(p) -> np.ndarray:
    return np.round(np.asarray(p) * 16).astype(np.int32)  # 4 fractional bits for cv2's sub-pixel drawing


def _poly(img, pts, color, thick=1, closed=True):
    cv2.polylines(img, [_pts(pts)], closed, color, thick, cv2.LINE_AA, shift=4)


def _line(img, a, b, color, thick=1):
    cv2.line(img, tuple(_pts(a)), tuple(_pts(b)), color, thick, cv2.LINE_AA, shift=4)


def _fill(img, pts, color, alpha):
    over = img.copy()
    cv2.fillPoly(over, [_pts(pts)], color, cv2.LINE_AA, shift=4)
    cv2.addWeighted(over, alpha, img, 1 - alpha, 0, img)


# ---------------------------------------------------------------- the 3D viewpoint
class Director:
    """A pinhole camera looking at the scene from an oblique angle (world frame: page mm, z into the table).
    `centre_x`: where the target lands horizontally, as a fraction of the width (room for the photo inset)."""

    def __init__(self, size, target, azimuth_deg, elevation_deg, dist, fov_deg=34.0, centre_x=0.5, centre_y=0.5):
        w, h = size
        f = (w / 2) / np.tan(np.radians(fov_deg) / 2)
        self.K = np.array([[f, 0, w * centre_x], [0, f, h * centre_y], [0, 0, 1.0]])
        az, el = np.radians(azimuth_deg), np.radians(elevation_deg)
        target = np.asarray(target, float)
        eye = target + dist * np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), -np.sin(el)])
        fwd = (target - eye) / np.linalg.norm(target - eye)
        x = np.cross(fwd, [0, 0, -1.0])
        x /= np.linalg.norm(x)
        self.R = np.stack([x, np.cross(fwd, x), fwd])
        self.t = -self.R @ eye

    def __call__(self, X) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, float))
        if X.shape[1] == 2:
            X = np.c_[X, np.zeros(len(X))]
        p = (X @ self.R.T + self.t) @ self.K.T
        return p[:, :2] / np.maximum(p[:, 2:3], 1e-6)


@dataclass(frozen=True)
class Framing:
    target: tuple
    azimuth: float
    elevation: float
    dist: float
    centre_x: float
    page: tuple  # (x0, y0, x1, y1) of the sheet drawn
    centre_y: float = 0.56


def framing(ep: Episode, size, inset: bool, hero: bool = False) -> Framing:
    """A fixed viewpoint for the whole episode that keeps both cameras, their views and the page in frame at every
    point of the orbit (and clear of the photo inset)."""
    w, h = size
    foots = [corners_from_H(p.H) for p in ep.poses]
    cents = [p.centre for p in ep.poses]
    allf = np.vstack(foots)
    lo, hi = allf.min(0) - 18, allf.max(0) + 18
    page = (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))
    keys = np.vstack(
        [
            np.c_[allf, np.zeros(len(allf))],
            *[c[None] for c in cents],
            [[lo[0], lo[1], 0], [hi[0], lo[1], 0], [hi[0], hi[1], 0], [lo[0], hi[1], 0]],
        ]
    )
    target = keys.mean(0)
    target[2] = min(c[2] for c in cents) * 0.4
    if hero:  # frame only the cameras and their views; the sheet may run off the edges
        keys = np.vstack([np.c_[allf, np.zeros(len(allf))], *[c[None] for c in cents]])
    el = 30.0
    cx = 0.36 if inset and not hero else 0.5
    xmax = (1 - PHOTO_FRAC * h / w - 0.03) if inset and not hero else 0.97
    xmin, ymin, cy = (0.02, 0.24, 0.62) if hero else (0.03, 0.2, 0.56)
    # Look across each camera's direction, never along it: a plane facing a camera (the typical wrong belief) is
    # edge-on when seen along the camera's azimuth.
    mid = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2])
    cam_az = [np.degrees(np.arctan2(c[1] - mid[1], c[0] - mid[0])) for c in cents]

    def across(a: float) -> float:
        return min(abs(np.sin(np.radians(a + d - ca))) for ca in cam_az for d in (-ORBIT_DEG, 0.0, ORBIT_DEG))

    az = max(
        np.arange(0.0, 360.0, 5.0), key=lambda a: (round(across(a), 2), -abs(((a - cam_az[0] - 70) + 180) % 360 - 180))
    )
    for dist in np.arange(300.0, 3000.0, 15.0):
        ok = True
        for daz in (-ORBIT_DEG, 0, ORBIT_DEG):
            D = Director(size, target, az + daz, el, dist, centre_x=cx, centre_y=cy)
            p = D(keys)
            if (
                p[:, 0].min() < xmin * w
                or p[:, 0].max() > xmax * w
                or p[:, 1].min() < ymin * h
                or p[:, 1].max() > 0.97 * h
            ):
                ok = False
                break
        if ok:
            break
    return Framing(tuple(target), float(az), el, float(dist), cx, page, cy)


def believed_pose(true: Pose, belief_mm) -> Pose | None:
    """The rigid camera pose that best explains the belief where it matters: over the work area, the page points the
    model believes it sees at each pixel (least-squares reprojection, PnP, with the true intrinsics). A plain
    decomposition of the corner homography is unstable: the photo's corners extrapolate far outside the work area, so
    a small aim error there can turn into a wildly tilted plane."""
    Hb = H_from_corners(belief_mm)
    if Hb is None:
        return None
    img = project(true.H, work_grid())
    obj = project(np.linalg.inv(Hb), img)
    if not np.isfinite(obj).all():
        return None
    guess = pose_from_homography(Hb, true.K)
    rvec0 = cv2.Rodrigues(guess.R)[0] if guess is not None else None
    ok, rvec, tvec = cv2.solvePnP(
        np.c_[obj, np.zeros(len(obj))].astype(np.float64),
        img.astype(np.float64),
        true.K,
        None,
        rvec0,
        guess.t.reshape(3, 1).astype(np.float64) if guess is not None else None,
        useExtrinsicGuess=guess is not None,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not ok:
        return None
    return Pose(true.K, cv2.Rodrigues(rvec)[0], tvec.reshape(3))


def believed_plane_world(true: Pose, belief_mm):
    """Where the model thinks the page is, expressed in the world through the TRUE camera: a 3x3 map from (x, y, 1)
    on the believed page to world points. None if the belief is unusable or puts the page behind the camera."""
    pb = believed_pose(true, belief_mm)
    if pb is None:
        return None
    A = np.c_[pb.R[:, 0], pb.R[:, 1], pb.t]  # (x, y, 1) on the believed page -> camera coordinates
    if ((A @ np.c_[np.asarray(belief_mm), np.ones(4)].T)[2] <= 1.0).any():
        return None
    return true.R.T @ np.c_[A[:, :2], A[:, 2] - true.t]  # camera coordinates -> world (true pose)


def _implied_quad(ep: Episode, s: int, true: Pose):
    """World corners (4 x 3) of the view of the stroke-implied camera, placed through the true camera."""
    H = ep.implied_at(s)
    if H is None or s >= ep.n + 1:
        return None
    corners = corners_from_H(H)
    pb = believed_pose(true, corners)  # the rigid camera closest to the implied map over the work area
    if pb is None:
        return None
    A = np.c_[pb.R[:, 0], pb.R[:, 1], pb.t]
    cam = (A @ np.c_[corners, np.ones(4)].T).T
    if (cam[:, 2] <= 1.0).any():
        return None
    return (true.R.T @ (cam - true.t).T).T


def _apply(M, xy) -> np.ndarray:
    xy = np.atleast_2d(np.asarray(xy, float))
    return (M @ np.c_[xy, np.ones(len(xy))].T).T


def _clip_line_to_quad(quad, a, b):
    """The part of segment a-b inside a convex quad (page mm), or None."""
    t0, t1 = 0.0, 1.0
    d = b - a
    q = np.asarray(quad, float)
    area2 = sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4))
    for i in range(4):
        p0, p1 = q[i], q[(i + 1) % 4]
        e = p1 - p0
        n = np.array([-e[1], e[0]]) * np.sign(area2)  # inward normal
        den, num = n @ d, n @ (a - p0)
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        tt = -num / den
        if den > 0:
            t0 = max(t0, tt)
        else:
            t1 = min(t1, tt)
        if t0 > t1:
            return None
    return np.array([a + d * t0, a + d * t1])


def _pose_lerp(a: Pose, b: Pose, k: float) -> Pose:
    """A pose between two (for the camera-move animation): centres lerped, rotations blended and re-orthonormalised."""
    Ca, Cb = a.centre, b.centre
    M = a.R * (1 - k) + b.R * k
    U, _, Vt = np.linalg.svd(M)
    R = U @ Vt
    C = Ca * (1 - k) + Cb * k
    return Pose(a.K, R, -R @ C)


def render_scene(ep: Episode, s: int, frac: float, t: float, size, fr: Framing, move_k: float | None = None):
    """The 3D view after stroke s, `frac` of the way into the next step, at time t (seconds, for the orbit).
    move_k: during the camera-move animation, how far the camera has travelled (0..1)."""
    w, h = size
    img = np.full((h, w, 3), BG, np.uint8)
    true = ep.pose_at(s)
    shown = true if move_k is None else _pose_lerp(ep.poses[0], ep.poses[1], move_k)
    D = Director(
        size,
        fr.target,
        fr.azimuth + ORBIT_DEG * np.sin(2 * np.pi * t / ORBIT_PERIOD_S),
        fr.elevation,
        fr.dist,
        centre_x=fr.centre_x,
        centre_y=fr.centre_y,
    )

    # the sheet, the person's squares, the agent's strokes, the current square
    x0, y0, x1, y1 = fr.page
    sheet = D([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    cv2.fillPoly(img, [_pts(sheet)], PAPER, cv2.LINE_AA, shift=4)
    _poly(img, sheet, PAPER_EDGE, 1)
    for sq in ep.rec["squares"]:
        _poly(img, D(np.asarray(sq["ink"])[::2]), INK, 1, closed=False)
    for tr in ep.turns[:s]:
        _poly(img, D(np.asarray(tr["stroke"]["ink_ends"])), OWN_INK, 2, closed=False)
    if s < ep.n:
        cur = next(q for q in ep.rec["squares"] if q["idx"] == ep.turns[s]["stroke"]["square"])
        m = 3.0
        a, b, c = cur["x0"] - m, cur["y0"] - m, cur["side"] + 2 * m
        _poly(img, D([[a, b], [a + c, b], [a + c, b + c], [a, b + c]]), GOLD, 2)

    # the believed page (translucent blue plane with its 20 mm grid), gliding from the previous belief
    b_now, b_prev = ep.belief_at(s), ep.belief_at(max(s - 1, 0))
    belief = None
    if b_now is not None:
        k = 1.0 if (b_prev is None or s == 0) else min(1.0, frac / GLIDE)
        k = k * k * (3 - 2 * k)
        belief = b_now if b_prev is None else b_prev + (b_now - b_prev) * k
    # during a camera move the old belief rides along with the camera (the model has not seen the new photo yet)
    M = believed_plane_world(shown, belief) if belief is not None else None
    quad = None
    if M is not None and belief is not None:
        quad = D(_apply(M, belief))
        _fill(img, quad, BLUE_FILL, 0.30)
        lo, hi = belief.min(0), belief.max(0)
        for gx in np.arange(np.ceil(lo[0] / 20) * 20, hi[0], 20):
            seg = _clip_line_to_quad(belief, np.array([gx, lo[1] - 1]), np.array([gx, hi[1] + 1]))
            if seg is not None:
                _poly(img, D(_apply(M, seg)), BLUE_GRID, 1, closed=False)
        for gy in np.arange(np.ceil(lo[1] / 20) * 20, hi[1], 20):
            seg = _clip_line_to_quad(belief, np.array([lo[0] - 1, gy]), np.array([hi[0] + 1, gy]))
            if seg is not None:
                _poly(img, D(_apply(M, seg)), BLUE_GRID, 1, closed=False)

    # the camera implied by its strokes (translucent orange): the world quad of that camera's view, gliding
    oquad = None
    if move_k is None:
        now_q, prev_q = _implied_quad(ep, s, shown), _implied_quad(ep, max(s - 1, 0), shown)
        if now_q is not None:
            k = 1.0 if (prev_q is None or s == 0) else min(1.0, frac / GLIDE)
            k = k * k * (3 - 2 * k)
            oquad = D(now_q if prev_q is None else prev_q + (now_q - prev_q) * k)
            _fill(img, oquad, ORANGE_FILL, 0.22)

    # the true view: the camera's corner rays down to its footprint on the page (on top of the blue plane)
    C = shown.centre
    foot = corners_from_H(shown.H)
    Cp, fp = D(C)[0], D(foot)
    for q in fp:
        _line(img, Cp, q, RAY, 1)
    _poly(img, fp, TRUE, 2)
    if oquad is not None:
        _poly(img, oquad, ORANGE, 2)
    if quad is not None:
        _poly(img, quad, BLUE, 2)

    # the camera body: its image plane carries the photo it took
    photo = ep.photo(s)
    rays = np.c_[foot, np.zeros(4)] - C
    zc = rays @ shown.R[2]
    pp = D(C + rays * (34.0 / zc)[:, None])
    src = np.array([[0, 0], [photo.shape[1], 0], [photo.shape[1], photo.shape[0]], [0, photo.shape[0]]], np.float32)
    warped = cv2.warpPerspective(
        photo, cv2.getPerspectiveTransform(src, pp.astype(np.float32)), (w, h), flags=cv2.INTER_AREA
    )
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [_pts(pp)], 255, cv2.LINE_AA, shift=4)
    a = (mask.astype(np.float32) / 255)[..., None]
    img[:] = (img * (1 - a) + warped * a).astype(np.uint8)
    _poly(img, pp, (230, 230, 230), 1)
    for q in pp:
        _line(img, Cp, q, (230, 230, 230), 1)
    return img


# ---------------------------------------------------------------- panels
def _sparkline(img, ep: Episode, s: int, box, n_max: int, frac: float, u: float = 1.0):
    x0, y0, w, h = box
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (36, 32, 30), -1)
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), PANEL_EDGE, 1)
    top_mm = 30.0
    pad_t, pad_b = int(22 * u), int(8 * u)

    def Y(e):
        return y0 + pad_t + (h - pad_t - pad_b) * (1 - min(e, top_mm) / top_mm)

    def X(i):
        return x0 + 8 + (w - 16) * i / max(n_max - 1, 1)

    _line(img, (x0 + 4, Y(MATCH_MM)), (x0 + w - 4, Y(MATCH_MM)), GREEN, 1)
    text(img, f"match ({MATCH_MM:g} mm)", (x0 + w - 6, Y(MATCH_MM) - 4), 12 * u, GREEN, anchor="rs")
    ts = ep.turns
    pts = []
    for i in range(min(s + 1, len(ts))):
        if i > 0 and ts[i]["pose"] != ts[i - 1]["pose"]:
            _line(img, (X(i - 0.5), y0 + pad_t - 4), (X(i - 0.5), y0 + h - 4), RED, 1)
        e = ts[i].get("aim_error_mm")
        pts.append((X(i), Y(top_mm if e is None else e)))
    opts = []
    for i in range(min(s + 1, len(ts))):
        e = ep.implied_error_at(i)
        if e is not None:
            opts.append((X(i), Y(e)))
    if len(opts) > 1:
        _poly(img, np.array(opts), ORANGE, max(2, int(2 * u)), closed=False)
    if len(pts) > 1:
        _poly(img, np.array(pts), BLUE, max(2, int(2 * u)), closed=False)
    if pts:
        cv2.circle(img, (int(pts[-1][0]), int(pts[-1][1])), int(4 * u), BLUE, -1, cv2.LINE_AA)
    text(img, "camera error, mm:", (x0 + 8, y0 + int(16 * u)), 12 * u, MUTED)
    lx = x0 + 8 + text_width("camera error, mm:", 12 * u) + int(8 * u)
    text(img, "says", (lx, y0 + int(16 * u)), 12 * u, BLUE, "demi")
    text(img, "does", (lx + text_width("says", 12 * u, "demi") + int(8 * u), y0 + int(16 * u)), 12 * u, ORANGE, "demi")


def _squares_row(img, ep: Episode, s: int, org, px=13, u: float = 1.0):
    """One dot per square: green = closed on the first stroke, amber = closed later, red = abandoned; a red tick
    marks the camera move."""
    state: dict[int, str] = {}
    for tr in ep.turns[:s]:
        st = tr["stroke"]
        if st["closed"]:
            state[st["square"]] = "first" if st["attempt"] == 1 else "closed"
        elif st["attempt"] >= ep.rec["spec"]["cap_strokes"]:
            state[st["square"]] = "abandoned"
    x, y = org
    n, m = ep.rec["spec"]["n_squares"], ep.rec["spec"]["move_after"]
    for i in range(1, n + 1):
        cx = x + int(18 * u) * (i - 1) + (int(10 * u) if m and i > m else 0)
        c = {"first": GREEN, "closed": GOLD, "abandoned": RED}.get(state.get(i, ""), (80, 80, 80))
        cv2.circle(img, (cx, y), int(6 * u), c, -1, cv2.LINE_AA)
        if i == m:
            cx2 = cx + int(14 * u)
            cv2.line(img, (cx2, y - int(9 * u)), (cx2, y + int(9 * u)), RED, max(2, int(2 * u)), cv2.LINE_AA)
    firsts = sum(1 for v in state.values() if v == "first")
    text(img, f"{firsts} of {len(state)} first-try", (x + int(18 * u) * n + int(22 * u), y + int(5 * u)), px, MUTED)


def model_panel(
    ep: Episode,
    s: int,
    size,
    frac: float = 1.0,
    t: float = 0.0,
    n_max: int | None = None,
    banner: str | None = None,
    fr: Framing | None = None,
    move_k: float | None = None,
    hero: bool = False,
) -> np.ndarray:
    """One agent's panel after stroke s: the 3D scene, the photo it sees, its belief error so far and its squares.
    `hero`: the 3D scene fills the panel, with a small photo and no chart or caption (for a cold open)."""
    w, h = size
    fr = fr or framing(ep, size, inset=True, hero=hero)
    img = render_scene(ep, s, frac, t, size, fr, move_k)
    u = 1.5 if hero else h / 540  # type scale
    # the photo it sees
    ph = int(min(w, h) * 0.30) if hero else int(h * PHOTO_FRAC)
    photo = cv2.resize(ep.photo(s), (ph, ph), interpolation=cv2.INTER_AREA)
    x, y = w - ph - int(14 * u), int(14 * u)
    img[y : y + ph, x : x + ph] = photo
    cv2.rectangle(img, (x - 1, y - 1), (x + ph, y + ph), (210, 210, 210), 1)
    text(img, "what the model sees", (x + 8, y + ph - 8), 13 * u, (60, 60, 60), "demi")
    if not hero:
        _sparkline(img, ep, s, (x, y + ph + int(10 * u), ph, int(h * 0.26)), n_max or max(ep.n, 1), frac, u)
    # labels
    text(img, ep.name, (int(18 * u), int(36 * u)), 24 * u, WHITE, "demi")
    shown_s = min(s, ep.n)
    x0 = int(18 * u)
    text(img, f"{shown_s} strokes drawn", (x0, int(62 * u)), 15 * u, (200, 200, 200))
    x0 += text_width(f"{shown_s} strokes drawn", 15 * u) + int(18 * u)
    for label, err, colour in (("says", ep.error_at(s), BLUE), ("does", ep.implied_error_at(s), ORANGE)):
        val = ("-" if label == "says" else "not yet") if err is None else f"{err:.1f} mm off"
        seg = f"{label}: {val}"
        text(img, seg, (x0, int(62 * u)), 15 * u, GREEN if (err is not None and err <= MATCH_MM) else colour, "demi")
        x0 += text_width(seg, 15 * u, "demi") + int(16 * u)
    _squares_row(img, ep, s, (int(24 * u), int(86 * u)), int(13 * u), u)
    if banner:
        bw = text_width(banner, 18 * u, "bold") + int(22 * u)
        cv2.rectangle(img, (int(16 * u), int(104 * u)), (int(16 * u) + bw, int(136 * u)), RED, -1)
        text(img, banner, (int(27 * u), int(127 * u)), 18 * u, WHITE, "bold")
    # the agent's own note for the stroke it is about to make, as a caption
    if ep.turns and not hero:
        note = (ep.turns[min(s, ep.n - 1)].get("note") or "").strip()
        if note:
            _caption(img, f"\u201c{note}\u201d", (int(18 * u), h - int(16 * u)), int(w * 0.66), 14 * u)
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), PANEL_EDGE, 1)
    return img


def _caption(img, s: str, org, max_w: int, px: float, max_lines: int = 2):
    """Word-wrapped italic caption whose last line sits at org (bottom-left)."""
    words, lines, cur = s.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if text_width(trial, px, "medium_italic") <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;") + "\u2026"
    x, y = org
    lh = int(px * 1.35)
    # a dark backing so the caption stays readable over the paper
    bw = max(text_width(ln, px, "medium_italic") for ln in lines)
    y_top = y - lh * (len(lines) - 1) - int(px * 1.1)
    x0, y0 = max(0, x - int(px * 0.5)), max(0, y_top)
    x1, y1 = min(img.shape[1], x + bw + int(px * 0.5)), min(img.shape[0], y + int(px * 0.45))
    region = img[y0:y1, x0:x1]
    region[:] = (region * 0.25 + np.array(BG) * 0.75).astype(np.uint8)
    for i, ln in enumerate(lines):
        text(img, ln, (x, y - lh * (len(lines) - 1 - i)), px, (215, 215, 215), "medium_italic")


# ---------------------------------------------------------------- composition
class Writer:
    def __init__(self, path: Path, size, fps: int = FPS):
        w, h = size
        self.p = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                f"{w}x{h}",
                "-r",
                str(fps),
                "-i",
                "-",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "18",
                "-preset",
                "medium",
                "-movflags",
                "+faststart",
                str(path),
            ],
            stdin=subprocess.PIPE,
        )

    def write(self, img: np.ndarray, n: int = 1):
        b = np.ascontiguousarray(img).tobytes()
        for _ in range(n):
            self.p.stdin.write(b)  # type: ignore[union-attr]

    def close(self):
        assert self.p.stdin is not None
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise RuntimeError("ffmpeg failed")


def _timeline(ep: Episode, n_steps: int):
    """Per global step: (stroke index to show, whether the camera moves at the start of this step)."""
    out = []
    for g in range(n_steps + 1):
        s = min(g, ep.n)
        moved = 0 < g <= ep.n and ep.pose_no_at(s) != ep.pose_no_at(s - 1)
        out.append((s, moved))
    return out


MOVE_S = 1.2  # the camera-move animation


def grid_video(
    eps: list[Episode],
    out: Path,
    title: str,
    subtitle: str,
    size=(1920, 1080),
    intro=None,
    outro=None,
    steps: tuple[int, int] | None = None,
    title_px: int = 30,
    top: int = 78,
    hold_end_s: float = 3.0,
    on_frame=None,
    hero: bool = False,
) -> Path:
    """Agents side by side (2 per row), synchronised by stroke number. A camera move plays as a short animation of
    the camera travelling to its new pose, with a banner. `steps`: only strokes g0..g1 (a clip, e.g. a cold open);
    `on_frame(g, f, canvas)` sees every frame (e.g. to save a thumbnail)."""
    W, H = size
    cols, rows = 2, (len(eps) + 1) // 2
    pw, ph = (W - 12) // cols, (H - top - 8) // rows
    psize = (pw - 8, ph - 8)
    frs = [framing(e, psize, inset=True, hero=hero) for e in eps]
    n_max = max(e.n for e in eps)
    tls = [_timeline(e, n_max) for e in eps]
    per = int(FPS * STEP_S)
    move_frames = int(FPS * MOVE_S)
    wr = Writer(out, size)
    if intro is not None:
        for fr_ in intro:
            wr.write(fr_[0], int(FPS * fr_[1]))
    frame_no = 0
    banner_until = [-1.0] * len(eps)
    g0, g1 = steps if steps is not None else (0, n_max)
    for g in range(g0, g1 + 1):
        any_move = any(tl[g][1] for tl in tls)
        last = g == g1
        n_frames = per + (move_frames if any_move else 0) + (int(FPS * hold_end_s) if last else 0)
        for f in range(n_frames):
            t = frame_no / FPS
            canvas = np.full((H, W, 3), BG, np.uint8)
            text(canvas, title, (24, top - 34 if title_px > 30 else 44), title_px, WHITE, "demi")
            text(canvas, subtitle, (24, top - 10), 16 if title_px <= 30 else 22, (190, 190, 190))
            for i in range(len(eps)):
                s, moved = tls[i][g]
                move_k = None
                ff = f
                if any_move:
                    if moved and f < move_frames:
                        k = f / move_frames
                        move_k = k * k * (3 - 2 * k)
                        s_show = max(s - 1, 0)
                    else:
                        s_show = s
                    ff = max(0, f - move_frames)
                    if moved and f == move_frames:
                        banner_until[i] = t + 1.8
                else:
                    s_show = s
                frac = 1.0 if move_k is not None else min(1.0, ff / per)
                banner = "CAMERA MOVED" if (move_k is not None or t < banner_until[i]) else None
                panel = model_panel(eps[i], s_show, psize, frac, t, n_max, banner, frs[i], move_k, hero)
                r, c = divmod(i, cols)
                y0, x0 = top + r * ph + 4, 6 + c * pw + 4
                canvas[y0 : y0 + psize[1], x0 : x0 + psize[0]] = panel
            if on_frame is not None:
                on_frame(g, f, canvas)
            wr.write(canvas)
            frame_no += 1
    if outro is not None:
        for fr_ in outro:
            wr.write(fr_[0], int(FPS * fr_[1]))
    wr.close()
    return out


def single_video(ep: Episode, out: Path, size=(1920, 1080), hero: bool = False) -> Path:
    """One agent full screen, with the camera-move animation (`hero`: big 3D scene, small photo, no chart)."""
    fr = framing(ep, size, inset=True, hero=hero)
    tl = _timeline(ep, ep.n)
    per, move_frames = int(FPS * STEP_S), int(FPS * MOVE_S)
    wr = Writer(out, size)
    frame_no, banner_until = 0, -1.0
    for g in range(ep.n + 1):
        s, moved = tl[g]
        n_frames = (per + (move_frames if moved else 0)) if g < ep.n else FPS * 3
        for f in range(n_frames):
            t = frame_no / FPS
            move_k, s_show, ff = None, s, f
            if moved:
                if f < move_frames:
                    k = f / move_frames
                    move_k, s_show = k * k * (3 - 2 * k), max(s - 1, 0)
                ff = max(0, f - move_frames)
                if f == move_frames:
                    banner_until = t + 1.8
            banner = "CAMERA MOVED" if (move_k is not None or t < banner_until) else None
            frac = 1.0 if move_k is not None else min(1.0, ff / per)
            wr.write(model_panel(ep, s_show, size, frac, t, ep.n, banner, fr, move_k, hero))
            frame_no += 1
    wr.close()
    return out


def card(lines, size=(1920, 1080), x=150, y0=None) -> np.ndarray:
    """A title card: lines of (text, px, colour, weight); an empty text is a gap."""
    W, H = size
    img = np.full((H, W, 3), BG, np.uint8)
    total = sum(int(px * 1.55) for _, px, _, _ in lines)
    y = y0 if y0 is not None else (H - total) // 2 + int(lines[0][1])
    for s, px, color, weight in lines:
        if s:
            text(img, s, (x, y), px, color, weight)
        y += int(px * 1.55)
    return img
