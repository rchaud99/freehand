"""Page geometry and the physical constants of the simulated rig.

The page is a US-letter sheet in page millimetres: origin at the top-left corner, x to the right, y downward. The
rectified photo the agent sees is 4 px per mm. The pen can reach the sheet minus a 5 mm inset (the real plotter's
`INSET_MM`, intersected with the calibration's reachable region in `assets/page_calib.json`).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LETTER_W, LETTER_H = 215.9, 279.4  # US letter, mm
PX_PER_MM = 4  # rectified view resolution
PX = PX_PER_MM
SS = 4  # supersampling factor when rasterising ink
CENTRE = (LETTER_W / 2, LETTER_H / 2)  # pivot of rotations, scales and shears
INSET_MM = 5.0  # plotter.py INSET_MM on the real rig
TOL_MM = 2.0  # closure tolerance: both ends within 2 mm, roughly straight
CROP_PX_PER_MM = 12  # crop_px output mode: magnified crop resolution

ASSETS = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=1)
def drawable() -> tuple[float, float, float, float]:
    """The reachable region (x_lo, y_lo, x_hi, y_hi) in page mm (plotter.Plotter.drawable on the real rig)."""
    with open(ASSETS / "page_calib.json") as f:
        c = json.load(f)
    r = c.get("reachable_page_mm", [0, 0, LETTER_W, LETTER_H])
    return (max(INSET_MM, r[0]), max(INSET_MM, r[1]), min(LETTER_W - INSET_MM, r[2]), min(LETTER_H - INSET_MM, r[3]))


REGION = drawable()
