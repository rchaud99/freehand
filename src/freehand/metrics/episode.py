"""Per-episode stroke and turn metrics (the historical `episode.metrics`, with the corrected first-try score).

Inputs are episode-like mappings (historical episode.json or new summary.json) and turn records (historical
turns.jsonl or new episode.jsonl); `mention` flags are read from either layout.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from freehand.scoring import first_try_summary


def _mention(t: Mapping, kind: str) -> bool:
    if f"mention_{kind}" in t:
        return bool(t[f"mention_{kind}"])
    return bool((t.get("mentions") or {}).get(kind))


def episode_metrics(ep: Mapping[str, Any], turns: list[Mapping[str, Any]]) -> dict[str, Any]:
    P = ep["perturb_after"]
    sr = ep["squares_result"]
    pre = [s for s in sr if s["square"] <= P]
    post = [s for s in sr if s["square"] > P]
    ps = ep["perturb_stroke"]
    post_strokes = [s for s in ep["strokes"] if ps is not None and s["stroke"] >= ps]
    first_perfect = None
    for s in post_strokes:
        if s["closed"] and s["attempt"] == 1:
            first_perfect = s["stroke"] - ps + 1
            break
    post_turns = [t for t in turns if t["square"] > P]
    pre_turns = [t for t in turns if t["square"] <= P]

    def first(ts, kinds):
        for i, t in enumerate(ts):
            if any(_mention(t, k) for k in kinds):
                return i + 1
        return None

    first_try = first_try_summary(ep)
    return {
        "pre_first_try_rate": (sum(s["first_try"] for s in pre) / len(pre)) if pre else None,
        "pre_closed_rate": (sum(s["closed"] for s in pre) / len(pre)) if pre else None,
        "pre_strokes_total": sum(s["strokes"] for s in pre),
        "post_squares": len(post),
        "post_complete": len(post) == ep["n_squares"] - P,
        "strokes_to_first_perfect": first_perfect if first_perfect is not None else len(post_strokes) + 1,
        "first_perfect_censored": first_perfect is None,
        "post_strokes_total": len(post_strokes),
        "post_failed_squares": sum(not s["closed"] for s in post),
        "post_first_try_rate": first_try["observed_rate"],
        "post_first_try": first_try,
        "pre_mention_turns": sum(any(_mention(t, k) for k in ("note", "memory", "reasoning")) for t in pre_turns),
        "post_first_mention_turn_note": first(post_turns, ["note"]),
        "post_first_mention_turn_memory": first(post_turns, ["memory"]),
        "post_first_mention_turn_reasoning": first(post_turns, ["reasoning"]),
        "compensation_by_post_stroke": [s["compensation_frac"] for s in post_strokes],
    }
