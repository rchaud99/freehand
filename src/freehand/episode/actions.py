"""Parsing a reply into a stroke, and clamping it to the reachable region."""

from __future__ import annotations

import json
import re

import numpy as np

from freehand.sim.geometry import CROP_PX_PER_MM, REGION

_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def parse_json(text: str | None) -> dict:
    """The outermost {...} of a reply, parsed (models sometimes wrap it in prose or code fences)."""
    m = _JSON_OBJECT.search(text or "")
    if not m:
        raise ValueError("no JSON object in response")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return obj


def first_stroke(action: dict) -> list[list[float]] | None:
    """The first valid stroke of an action (>= 2 finite points), or None. Only the first stroke is ever drawn."""
    for s in action.get("strokes") or []:
        if isinstance(s, dict):
            s = s.get("pts")
        try:
            pts = [[float(p[0]), float(p[1])] for p in s]
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if len(pts) >= 2 and np.isfinite(pts).all():
            return pts
    return None


def clamp(pts, region: tuple = REGION) -> tuple[list[list[float]], list[dict]]:
    """Points clamped into the reachable region, and a log of every clamp."""
    x_lo, y_lo, x_hi, y_hi = region
    out, log = [], []
    for x, y in pts:
        cx, cy = min(max(x, x_lo), x_hi), min(max(y, y_lo), y_hi)
        if (cx, cy) != (x, y):
            log.append({"rule": "clamp", "before": [x, y], "after": [cx, cy]})
        out.append([cx, cy])
    return out, log


def crop_px_to_mm(cmd, origin_mm) -> list[list[float]]:
    """crop_px output mode: pixels of the 12 px/mm crop -> page mm."""
    return [[origin_mm[0] + x / CROP_PX_PER_MM, origin_mm[1] + y / CROP_PX_PER_MM] for x, y in cmd]
