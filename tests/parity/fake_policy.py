"""The scripted fake model of the parity cases: aims near the true corners (1.2 mm noise), sometimes replies with
no JSON, keeps a growing notepad, and answers in crop pixels when asked. Depends only on the last user message."""
from __future__ import annotations

import json
import re

import numpy as np

UNPARSEABLE_P = 0.08
AIM_SD_MM = 1.2


def make_policy(open_ends_by_idx: dict, seed: int, crop: bool = False):
    def policy(system, messages):
        text = " ".join(p.get("text", "") for p in messages[-1]["parts"])
        k = int(re.search(r"Current square: #(\d+)", text).group(1))
        used = int(re.search(r"Strokes used on this square: (\d+)", text).group(1))
        rng = np.random.default_rng([seed, k, used, len(messages)])
        e = np.asarray(open_ends_by_idx[k]) + rng.normal(0, AIM_SD_MM, (2, 2))
        if crop:
            m = re.search(r"page x (\d+) to \d+ mm, y (\d+) to", text)
            e = (e - [float(m.group(1)), float(m.group(2))]) * 12
        if rng.uniform() < UNPARSEABLE_P:
            return "I cannot decide."
        note = "Joining the free ends." if used == 0 else "Previous stroke landed off; maybe an offset, aiming again."
        memory = f"square {k}, attempt {used + 1}; {len(messages)} messages so far " + "w " * (3 * k)
        return json.dumps({"action": "draw", "strokes": [e.round(1).tolist()], "note": note, "memory": memory})
    return policy
