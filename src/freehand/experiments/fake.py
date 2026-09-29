"""An offline stand-in model for dry runs and tests (`freehand run --fake-models`, `freehand episode --model fake`).

It reads the current square and stroke count from the state block, aims at the true free ends with some error,
answers in crop pixels when the request carries a crop, never adapts, and keeps a notepad. Its "costs" are
simulated accounting at the fake price, recorded under a separate `fake:` budget tag.
"""

from __future__ import annotations

import json
import re

import numpy as np

from freehand.sim.geometry import CROP_PX_PER_MM
from freehand.sim.page import Square

AIM_SD_MM = 0.8
_SQUARE = re.compile(r"Current square: #(\d+)")
_USED = re.compile(r"Strokes used on this square: (\d+)")
_CROP = re.compile(r"page x (\d+) to \d+ mm, y (\d+) to")


def _match(rx: re.Pattern, text: str) -> str:
    m = rx.search(text)
    if m is None:
        raise ValueError(f"fake model: no {rx.pattern!r} in the turn's state text")
    return m.group(1)


def fake_policy(squares: list[Square], seed: int, aim_sd: float = AIM_SD_MM):
    ends = {s.idx: s.open_ends for s in squares}

    def policy(system: str, messages: list[dict]) -> str:
        text = " ".join(p.get("text", "") for p in messages[-1]["parts"])
        k, used = int(_match(_SQUARE, text)), int(_match(_USED, text))
        rng = np.random.default_rng([seed, k, used, len(messages)])
        e = np.asarray(ends[k]) + rng.normal(0, aim_sd, (2, 2))
        crop = _CROP.search(text)
        if crop:
            e = (e - [float(crop.group(1)), float(crop.group(2))]) * CROP_PX_PER_MM
        note = "Joining the free ends." if used == 0 else "Previous stroke landed off; aiming again."
        return json.dumps(
            {
                "action": "draw",
                "strokes": [e.round(1).tolist()],
                "note": note,
                "memory": f"square {k}, attempt {used + 1}",
            }
        )

    return policy
