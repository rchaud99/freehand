"""Rendering: the simulated photo of the page and the overlays the agent sees.

The rectified view is built the way the real rig's loop builds it: a page at 4 px/mm, a blue 10 mm grid (labels every
50 mm) and a dashed red rectangle around the reachable region. The photo itself is simulated: grey paper (median grey
~189, as on the real sheet), a soft illumination gradient, paper texture, a few faint ghost marks, sensor noise, and
ink ~0.55 mm wide at grey ~60 with slight lens blur. All randomness comes from the `page.paper` and
`page.highlight` streams, so a page looks the same on every turn except for new ink.

Rendering is deterministic for a fixed OpenCV/numpy build (pinned in pyproject.toml / requirements.lock). The
portable guarantee of a suite is its *data* hash (squares, targets, perturbations); image hashes are pinned in the
tests for the locked environment only.
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from freehand import seeding
from freehand.sim.geometry import CROP_PX_PER_MM, LETTER_H, LETTER_W, PX, PX_PER_MM, REGION, SS
from freehand.sim.page import Square

GREEN = (40, 150, 40)                 # current-square outline (BGR)
GRID_LIGHT, GRID_HEAVY, GRID_LABEL = (235, 210, 170), (210, 160, 90), (170, 90, 20)
REGION_RED = (0, 0, 220)
INK_WIDTH_MM = 0.55
GHOST_WIDTH_MM = 0.5
HIGHLIGHT_MARGIN_MM = (4, 7)          # jittered so the outline does not give the corners away
CROP_MIN_MM = 60.0
CROP_MARGIN_MM = 12.0


# ---------------------------------------------------------------- overlays
def grid_view(rect: np.ndarray, step_mm: int = 10) -> np.ndarray:
    """The page with a labelled mm grid (blue, so it is obviously not ink). Unchanged from the rig's camera.py."""
    img = rect.copy()
    h, w = img.shape[:2]
    for x in range(0, w + 1, step_mm * PX_PER_MM):
        mm = x // PX_PER_MM
        heavy = mm % 50 == 0
        cv2.line(img, (x, 0), (x, h), GRID_HEAVY if heavy else GRID_LIGHT, 2 if heavy else 1)
        if heavy:
            cv2.putText(img, str(mm), (x + 3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GRID_LABEL, 1, cv2.LINE_AA)
    for y in range(0, h + 1, step_mm * PX_PER_MM):
        mm = y // PX_PER_MM
        heavy = mm % 50 == 0
        cv2.line(img, (0, y), (w, y), GRID_HEAVY if heavy else GRID_LIGHT, 2 if heavy else 1)
        if heavy:
            cv2.putText(img, str(mm), (3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GRID_LABEL, 1, cv2.LINE_AA)
    return img


def region_rect(view: np.ndarray, region: tuple = REGION) -> np.ndarray:
    """The rig loop's dashed red rectangle around the reachable region."""
    x_lo, y_lo, x_hi, y_hi = region

    def px(v: float) -> int:
        return int(round(v * 4))

    for i in range(px(x_lo), px(x_hi), 24):
        cv2.line(view, (i, px(y_lo)), (min(i + 12, px(x_hi)), px(y_lo)), REGION_RED, 2)
        cv2.line(view, (i, px(y_hi)), (min(i + 12, px(x_hi)), px(y_hi)), REGION_RED, 2)
    for j in range(px(y_lo), px(y_hi), 24):
        cv2.line(view, (px(x_lo), j), (px(x_lo), min(j + 12, px(y_hi))), REGION_RED, 2)
        cv2.line(view, (px(x_hi), j), (px(x_hi), min(j + 12, px(y_hi))), REGION_RED, 2)
    return view


def highlight_margin(seed: int, sq: Square) -> float:
    return float(seeding.rng(seed, "page.highlight", sq.idx).uniform(*HIGHLIGHT_MARGIN_MM))


def highlight(view: np.ndarray, sq: Square, seed: int) -> np.ndarray:
    """Green outline + number around the current square (an overlay, like the grid)."""
    m = highlight_margin(seed, sq)
    x0, y0, x1, y1 = sq.bbox
    p0 = (int(round((x0 - m) * PX)), int(round((y0 - m) * PX)))
    p1 = (int(round((x1 + m) * PX)), int(round((y1 + m) * PX)))
    cv2.rectangle(view, p0, p1, GREEN, 2, cv2.LINE_AA)
    cv2.putText(view, f"#{sq.idx}", (p0[0], p0[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2, cv2.LINE_AA)
    return view


def outline_polygon(view: np.ndarray, box_px: np.ndarray, idx: int) -> np.ndarray:
    """The current-square outline drawn as a polygon in image space (raw camera and stale-rectified views)."""
    cv2.polylines(view, [np.round(box_px).astype(np.int32)], True, GREEN, 2, cv2.LINE_AA)
    top = box_px[np.argmin(box_px[:, 1])]
    cv2.putText(view, f"#{idx}", (int(top[0]) - 10, int(top[1]) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2,
                cv2.LINE_AA)
    return view


# ---------------------------------------------------------------- the photo
def _smooth_noise(shape, sigma_px: float, rng: np.random.Generator) -> np.ndarray:
    z = rng.normal(0, 1, shape).astype(np.float32)
    z = cv2.GaussianBlur(z, (0, 0), sigma_px)
    return z / (z.std() + 1e-6)


def polys_alpha(polys, shape_hw, width_mm: float) -> np.ndarray:
    """Antialiased coverage (0..1) of polylines (page mm) on an image of shape_hw at PX px/mm."""
    h, w = shape_hw
    g = np.zeros((h * SS, w * SS), np.uint8)
    for p in polys:
        P = np.round(np.asarray(p) * PX * SS).astype(np.int32)
        cv2.polylines(g, [P], False, 255, max(1, int(round(width_mm * PX * SS))), cv2.LINE_AA)
    return cv2.resize(g, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


@lru_cache(maxsize=8)
def _paper(seed: int):
    """Paper, ghost marks, ink-tone field and sensor noise for one page (fixed across turns)."""
    rng = seeding.rng(seed, "page.paper")
    h, w = int(round(LETTER_H * PX)), int(round(LETTER_W * PX))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    gx, gy = rng.uniform(-1, 1, 2)
    light = 189 + 10 * (gx * (xx / w - 0.5) + gy * (yy / h - 0.5)) - 6 * ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2)
    tex = 2.0 * _smooth_noise((h, w), 6, rng) + 1.2 * _smooth_noise((h, w), 1.2, rng)
    paper = np.repeat((light + tex)[..., None], 3, 2)
    paper[..., 2] += 1.0
    paper[..., 0] -= 1.0
    ghosts = []
    for _ in range(rng.integers(3, 7)):
        pts = [rng.uniform([10, 10], [LETTER_W - 10, LETTER_H - 10])]
        for _ in range(rng.integers(2, 6)):
            pts.append(np.clip(pts[-1] + rng.normal(0, 18, 2), 5, [LETTER_W - 5, LETTER_H - 5]))
        ghosts.append(pts)
    ga = polys_alpha(ghosts, (h, w), GHOST_WIDTH_MM) * rng.uniform(0.04, 0.08)
    paper = paper * (1 - ga[..., None]) + 120 * ga[..., None]
    tone = 58 + 10 * _smooth_noise((h, w), 20, rng)
    noise = rng.normal(0, 1.8, (h, w, 3)).astype(np.float32)
    return paper.astype(np.float32), tone.astype(np.float32), noise


def render_rect(seed: int, ink_polys) -> np.ndarray:
    """The simulated rectified photo (no overlays)."""
    paper, tone, noise = _paper(seed)
    h, w = paper.shape[:2]
    a = polys_alpha(ink_polys, (h, w), INK_WIDTH_MM)[..., None] * 0.97
    img = paper * (1 - a) + tone[..., None] * a
    img = cv2.GaussianBlur(img, (0, 0), 0.6) + noise
    return np.clip(img, 0, 255).astype(np.uint8)


def all_ink(squares: list[Square], plot_ink) -> list:
    return [s.ink for s in squares] + list(plot_ink)


def render_view(seed: int, squares: list[Square], plot_ink, current: Square | None = None) -> np.ndarray:
    """What the agent sees in the calibrated (B) view: photo + grid + reachable region + current-square outline."""
    view = region_rect(grid_view(render_rect(seed, all_ink(squares, plot_ink))))
    if current is not None:
        highlight(view, current, seed)
    return view


def png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return buf.tobytes()


# ---------------------------------------------------------------- stale rectification (L6 camera bump)
def _warp_matrix(W) -> np.ndarray:
    S = np.diag([PX, PX, 1.0])
    return S @ np.vstack([np.asarray(W, float), [0, 0, 1.0]]) @ np.linalg.inv(S)


def warp_rect(rect: np.ndarray, W) -> np.ndarray:
    """A rectified page image as a camera with stale rectification shows it: page mm -> displayed mm by W (2x3)."""
    M = _warp_matrix(W)[:2]
    h, w = rect.shape[:2]
    return cv2.warpAffine(rect, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def render_view_warp(seed: int, squares: list[Square], plot_ink, current: Square | None, W) -> np.ndarray:
    """Rectified view after the camera moved under a stale rectification: the page appears transformed by W under a
    grid that still claims page mm. The outline follows the square in the image (the harness tracks it)."""
    view = region_rect(grid_view(warp_rect(render_rect(seed, all_ink(squares, plot_ink)), W)))
    if current is not None:
        W3 = np.vstack([np.asarray(W, float), [0, 0, 1.0]])
        m = highlight_margin(seed, current)
        x0, y0, x1, y1 = current.bbox
        box = np.c_[[[x0 - m, y0 - m], [x1 + m, y0 - m], [x1 + m, y1 + m], [x0 - m, y1 + m]], np.ones(4)] @ W3[:2].T
        outline_polygon(view, box * PX, current.idx)
    return view


# ---------------------------------------------------------------- crop_px output mode
def crop_view(seed: int, squares: list[Square], plot_ink, sq: Square, W=None):
    """Magnified crop (12 px/mm) around the current square: square + 12 mm margin, at least 60 mm, with its own
    5/10 mm grid labelled in page mm. Returns (image, (x0_mm, y0_mm), side_mm).

    W (L6 camera bump): the crop is cut from the same stale-rectified image as `render_view_warp`, around where the
    square appears, and its grid still claims page mm."""
    rect = render_rect(seed, all_ink(squares, plot_ink))
    x0, y0, x1, y1 = sq.bbox
    if W is not None:
        rect = warp_rect(rect, W)
        corners = np.c_[[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.ones(4)] @ np.asarray(W, float).T
        (x0, y0), (x1, y1) = corners.min(0), corners.max(0)
    c = ((x0 + x1) / 2, (y0 + y1) / 2)
    L = max(CROP_MIN_MM, sq.side + 2 * CROP_MARGIN_MM)
    cx0 = float(np.floor(np.clip(c[0] - L / 2, 0, LETTER_W - L)))
    cy0 = float(np.floor(np.clip(c[1] - L / 2, 0, LETTER_H - L)))
    s = CROP_PX_PER_MM / PX
    crop = rect[int(cy0 * PX):int((cy0 + L) * PX), int(cx0 * PX):int((cx0 + L) * PX)]
    crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    draw_crop_grid(crop, cx0, cy0, L)
    return crop, (cx0, cy0), L


def draw_crop_grid(crop: np.ndarray, cx0: float, cy0: float, L: float) -> np.ndarray:
    h, w = crop.shape[:2]
    for mm in np.arange(np.ceil(cx0 / 5) * 5, cx0 + L + 0.01, 5):
        X = int(round((mm - cx0) * CROP_PX_PER_MM))
        heavy = mm % 10 == 0
        cv2.line(crop, (X, 0), (X, h), GRID_HEAVY if heavy else GRID_LIGHT, 2 if heavy else 1)
        if heavy:
            cv2.putText(crop, f"{mm:.0f}", (X + 3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, GRID_LABEL, 1, cv2.LINE_AA)
    for mm in np.arange(np.ceil(cy0 / 5) * 5, cy0 + L + 0.01, 5):
        Y = int(round((mm - cy0) * CROP_PX_PER_MM))
        heavy = mm % 10 == 0
        cv2.line(crop, (0, Y), (w, Y), GRID_HEAVY if heavy else GRID_LIGHT, 2 if heavy else 1)
        if heavy:
            cv2.putText(crop, f"{mm:.0f}", (3, Y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, GRID_LABEL, 1, cv2.LINE_AA)
    return crop
