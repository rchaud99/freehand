"""Ink and token metrics (docs/benchmark_ladder.md, "Ink metrics").

Per episode:
  ink_total_mm        length of all landed plotter ink
  ink_wasted_mm       ink that is not part of a closing stroke (misses, probes, corrections)
  ink_wasted_ratio    wasted / total
  ink_post_mm / ink_post_wasted_mm   the same, counting only strokes on post-change squares
  tokens_in / tokens_cached_in / tokens_out / tokens_reasoning, cost
Reads new turn records (`stroke.ink_len_mm`) and historical ones (the logged `ink` polyline, rounded to 0.001 mm).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from freehand.sim.plotter import poly_len


def _stroke_ink(t: Mapping) -> tuple[bool, float] | None:
    """(closed, ink length) of a turn's stroke, or None if the turn drew nothing."""
    s = t.get("stroke")
    if s:
        return bool(s["closed"]), float(s["ink_len_mm"])
    d = t.get("drawn")
    if d and t.get("ink"):
        return bool(d["closed"]), poly_len(t["ink"])
    return None


def _usage(t: Mapping) -> dict:
    return (t.get("reply") or {}).get("usage") or {}


def ink_metrics(turns: list[Mapping[str, Any]], perturb_after: int, cost_original: float = 0.0) -> dict[str, Any]:
    tot = wasted = post = post_w = 0.0
    tin = tout = treas = tcached = 0
    for t in turns:
        u = _usage(t)
        tin += u.get("input_tokens", 0) or 0
        tout += u.get("output_tokens", 0) or 0
        treas += u.get("reasoning_tokens", 0) or 0
        tcached += u.get("cached_input_tokens", 0) or 0
        s = _stroke_ink(t)
        if s is None:
            continue
        closed, length = s
        tot += length
        if not closed:
            wasted += length
        if t["square"] > perturb_after:
            post += length
            if not closed:
                post_w += length
    return {"ink_total_mm": round(tot, 1), "ink_wasted_mm": round(wasted, 1),
            "ink_wasted_ratio": round(wasted / tot, 3) if tot else None,
            "ink_post_mm": round(post, 1), "ink_post_wasted_mm": round(post_w, 1),
            "tokens_in": tin, "tokens_cached_in": tcached, "tokens_out": tout, "tokens_reasoning": treas,
            "cost": round(cost_original, 4)}
