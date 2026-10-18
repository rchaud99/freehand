"""The Freehand A world: open squares on a large sheet, a pen plotter that is never perturbed, and a physical camera
above the page that the agent must learn from its own marks, and re-learn after it moves.

The sheet is larger than the camera's view in every direction, so no paper edge or corner is ever in the photo: the
only way to learn the page-to-photo map is from ink whose page position is known, i.e. one's own strokes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

from freehand import seeding
from freehand.camera3d.pose import FRAME, Pose, project, sample_pose
from freehand.sim import plotter
from freehand.sim.geometry import PX, REGION
from freehand.sim.page import Square, far_apart_order, make_page, renumber
from freehand.sim.render import all_ink, highlight_margin, outline_polygon, render_rect

WORK_AREA = (60.0, 80.0, 156.0, 196.0)  # page mm; where the squares are
N_SQUARES = 8
SIZE_RANGE = (16.0, 26.0)
GAP_MM = 8.0
MOVE_AFTER = 4  # the camera moves after this square
CAP_STROKES_PER_SQUARE = 4
PAD_MM = 260  # the rendered sheet extends this far beyond the letter-sized texture (mirrored), so no edge shows
VIGNETTE = 0.10
NOISE_SD = 1.5


@dataclass
class Spec:
    """Everything that defines an episode's world; the same spec and seed give the same world on any machine."""

    seed: int
    n_squares: int = N_SQUARES
    move_after: int = MOVE_AFTER  # 0: the camera never moves
    cap_strokes: int = CAP_STROKES_PER_SQUARE
    # fresh: the no-transfer baseline. The episode starts at the SECOND camera pose and works only on the squares
    # after `move_after` (renumbered from 1; the others are not on the page), with none of the agent's own ink.
    fresh: bool = False

    @property
    def n_episode_squares(self) -> int:
        return self.n_squares - self.move_after if self.fresh else self.n_squares

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "n_squares": self.n_squares,
            "move_after": self.move_after,
            "cap_strokes": self.cap_strokes,
            "fresh": self.fresh,
            "work_area": list(WORK_AREA),
        }


@lru_cache(maxsize=8)
def _sheet(seed: int) -> np.ndarray:
    """The blank paper texture, extended by mirroring so the camera never sees an edge (float32, grey)."""
    blank = render_rect(seed, []).astype(np.float32)
    p = int(PAD_MM * PX)
    return cv2.copyMakeBorder(blank, p, p, p, p, cv2.BORDER_REFLECT_101)


@lru_cache(maxsize=1)
def _vignette() -> np.ndarray:
    yy, xx = np.mgrid[0:FRAME, 0:FRAME].astype(np.float32)
    r2 = ((xx - FRAME / 2) ** 2 + (yy - FRAME / 2) ** 2) / (FRAME / 2) ** 2
    return (1 - VIGNETTE * r2)[..., None]


def render_photo(seed: int, squares: list[Square], ink: list, H: np.ndarray, current: Square | None) -> np.ndarray:
    """The camera photo (BGR uint8, FRAME x FRAME): the inked sheet seen through H, the current square outlined."""
    inked = render_rect(seed, all_ink(squares, ink)).astype(np.float32)
    sheet = _sheet(seed).copy()
    p = int(PAD_MM * PX)
    sheet[p : p + inked.shape[0], p : p + inked.shape[1]] = inked
    # padded-texture px -> page mm -> frame px
    to_mm = np.array([[1.0 / PX, 0, -PAD_MM], [0, 1.0 / PX, -PAD_MM], [0, 0, 1.0]])
    img = cv2.warpPerspective(sheet, np.asarray(H) @ to_mm, (FRAME, FRAME), flags=cv2.INTER_AREA)
    noise = np.asarray(seeding.rng(seed, "camera.noise").normal(0, NOISE_SD, img.shape), np.float32)
    view = np.clip(img * _vignette() + noise, 0, 255).astype(np.uint8)
    if current is not None:
        m = highlight_margin(seed, current)
        x0, y0, x1, y1 = current.bbox
        outline_polygon(
            view, project(H, [[x0 - m, y0 - m], [x1 + m, y0 - m], [x1 + m, y1 + m], [x0 - m, y1 + m]]), current.idx
        )
    return view


@dataclass
class StrokeResult:
    stroke: int
    square: int
    attempt: int
    cmd: list  # [[x, y], [x, y]] as executed (clamped)
    cmd_raw: list  # as requested
    ink_ends: list
    closed: bool
    end_err_mm: list
    clamped: bool
    pose: int  # 1 or 2: the camera pose while this stroke was drawn


@dataclass
class World:
    spec: Spec
    squares: list[Square] = field(init=False)
    poses: list[Pose] = field(init=False)
    ink: list = field(default_factory=list)
    strokes: list[StrokeResult] = field(default_factory=list)
    current: int = 1  # index (1-based) of the square being worked on; n + 1 when done
    attempts: int = 0  # strokes on the current square
    outcomes: dict = field(default_factory=dict)  # square idx -> "first" | "closed" | "abandoned"

    def __post_init__(self):
        s = self.spec
        self.squares = far_apart_order(make_page(s.seed, s.n_squares, WORK_AREA, SIZE_RANGE, GAP_MM))
        if s.fresh:
            if not s.move_after:
                raise ValueError("a fresh episode needs move_after > 0 (it starts at the pose after the move)")
            self.squares = renumber(self.squares[s.move_after :])
        p1 = sample_pose(s.seed, 1, WORK_AREA)
        self.poses = [p1, sample_pose(s.seed, 2, WORK_AREA, avoid=p1)]

    # ---------------------------------------------------------------- state
    @property
    def done(self) -> bool:
        return self.current > len(self.squares)

    @property
    def pose_no(self) -> int:
        """1 before the move, 2 after it (the move happens when square `move_after` is finished)."""
        m = self.spec.move_after
        if self.spec.fresh:
            return 2
        return 2 if m and self.current > m else 1

    @property
    def pose(self) -> Pose:
        return self.poses[self.pose_no - 1]

    @property
    def H(self) -> np.ndarray:
        return self.pose.H

    @property
    def square(self) -> Square | None:
        return None if self.done else self.squares[self.current - 1]

    def photo(self) -> np.ndarray:
        return render_photo(self.spec.seed, self.squares, self.ink, self.H, self.square)

    # ---------------------------------------------------------------- action
    def draw(self, start, end) -> StrokeResult:
        """Draw one straight stroke (page mm). Returns what happened; advances to the next square when the current
        one closes or runs out of strokes."""
        if self.done:
            raise RuntimeError("episode is over")
        raw = [[float(start[0]), float(start[1])], [float(end[0]), float(end[1])]]
        x_lo, y_lo, x_hi, y_hi = REGION
        cmd = [[min(max(x, x_lo), x_hi), min(max(y, y_lo), y_hi)] for x, y in raw]
        clamped = cmd != raw
        sq = self.square
        assert sq is not None
        pose_no = self.pose_no
        n = len(self.strokes) + 1
        ink = plotter.land(np.array(cmd), plotter.PlotterMap(), self.spec.seed, n)
        self.ink.append(ink)
        closed, errs, _ = plotter.closure(ink, sq.open_ends)
        self.attempts += 1
        res = StrokeResult(
            n, sq.idx, self.attempts, cmd, raw, [ink[0].tolist(), ink[-1].tolist()], closed, errs, clamped, pose_no
        )
        self.strokes.append(res)
        if closed or self.attempts >= self.spec.cap_strokes:
            self.outcomes[sq.idx] = ("first" if self.attempts == 1 else "closed") if closed else "abandoned"
            self.current += 1
            self.attempts = 0
        return res
