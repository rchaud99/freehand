"""A page of hand-drawn open squares.

Each square is drawn "by a person" as one wobbly three-sided stroke, so one side is open; the open corners are the
free ends of that stroke, and closing the square means joining them with one straight stroke.

`make_page(seed, ...)` draws everything from the `page.layout` stream of the seed, so the page depends only on the
seed and the page spec (count, area, sizes, gap), never on the model, arm, perturbation or run order.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from freehand import seeding
from freehand.sim.geometry import REGION
from freehand.sim.plotter import densify, smooth_path_noise

SIDES = ("top", "right", "bottom", "left")
DEFAULT_N_RANGE = (10, 16)          # square count when not given: integers in [10, 16)
DEFAULT_SIZE_RANGE = (20.0, 40.0)   # side length, mm
DEFAULT_GAP_MM = 9.0                # minimum clearance between squares
DEFAULT_MARGIN_MM = 16.0            # margin inside the reachable region (keeps any perturbed stroke on the page)
PLACEMENT_TRIES = 200_000
CORNER_SD_MM = 0.6                  # a person misplaces corners a little
HAND_WOBBLE_SD_MM = 0.35
HAND_WOBBLE_LEN_MM = 6.0


@dataclass
class Square:
    idx: int                 # 1-based, the order the squares are done in
    x0: float
    y0: float
    side: float
    missing: str
    ink: list                # the person's three-sided stroke (page mm)
    open_ends: list          # [[x, y], [x, y]]: free ends of that stroke, the corners to join

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x0 + self.side, self.y0 + self.side)

    def to_dict(self) -> dict:
        return asdict(self)


def hand_square(x0: float, y0: float, s: float, missing: str, rng: np.random.Generator) -> np.ndarray:
    """Three sides as one continuous hand stroke, starting and ending at the open side's corners."""
    tl, tr, br, bl = (x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)
    ring = {"top": [tr, br, bl, tl], "right": [br, bl, tl, tr], "bottom": [bl, tl, tr, br], "left": [tl, tr, br, bl]}
    corners = np.array(ring[missing], float) + rng.normal(0, CORNER_SD_MM, (4, 2))
    pts = densify(corners)
    pts = pts + smooth_path_noise(len(pts), 0.25, HAND_WOBBLE_LEN_MM, HAND_WOBBLE_SD_MM, rng)
    pts[0], pts[-1] = corners[0], corners[-1]
    return pts


def make_page(seed: int, n_squares: int | None = None, area: tuple | None = None,
              size_range: tuple = DEFAULT_SIZE_RANGE, gap: float = DEFAULT_GAP_MM) -> list[Square]:
    """Place `n_squares` non-overlapping open squares.

    area: (x_lo, y_lo, x_hi, y_hi) the squares must lie in; default the reachable region minus a 16 mm margin.
    Raises RuntimeError if the squares cannot be placed (the seed is then unusable for this spec).
    """
    rng = seeding.rng(seed, "page.layout")
    n = int(n_squares or rng.integers(*DEFAULT_N_RANGE))
    if area is None:
        x_lo, y_lo, x_hi, y_hi = REGION
        margin = DEFAULT_MARGIN_MM
    else:
        (x_lo, y_lo, x_hi, y_hi), margin = area, 0.0
    boxes: list[tuple[float, float, float]] = []
    for _ in range(PLACEMENT_TRIES):
        if len(boxes) == n:
            break
        s = rng.uniform(*size_range)
        x0 = rng.uniform(x_lo + margin, x_hi - margin - s)
        y0 = rng.uniform(y_lo + margin, y_hi - margin - s)
        if all(x0 > b[0] + b[2] + gap or b[0] > x0 + s + gap or y0 > b[1] + b[2] + gap or b[1] > y0 + s + gap
               for b in boxes):
            boxes.append((x0, y0, s))
    if len(boxes) < n:
        raise RuntimeError(f"could not place {n} squares on page seed {seed}")
    squares = []
    for i, (x0, y0, s) in enumerate(boxes):
        missing = SIDES[rng.integers(0, 4)]
        ink = hand_square(x0, y0, s, missing, rng)
        squares.append(Square(i + 1, round(x0, 2), round(y0, 2), round(s, 2), missing, ink.tolist(),
                              [ink[0].tolist(), ink[-1].tolist()]))
    return squares


def far_apart_order(squares: list[Square]) -> list[Square]:
    """Reorder so each square is as far as possible from the previous one (greedy from the first); renumber 1..n."""
    rest = list(squares[1:])
    order = [squares[0]]

    def centre(q: Square) -> np.ndarray:
        return np.array([q.x0 + q.side / 2, q.y0 + q.side / 2])

    while rest:
        nxt = max(rest, key=lambda q: np.linalg.norm(centre(q) - centre(order[-1])))
        rest.remove(nxt)
        order.append(nxt)
    return renumber(order)


def renumber(squares: list[Square]) -> list[Square]:
    """Copies of the squares numbered 1..n in the given order."""
    out = []
    for i, q in enumerate(squares):
        d = asdict(q)
        d["idx"] = i + 1
        out.append(Square(**d))
    return out
