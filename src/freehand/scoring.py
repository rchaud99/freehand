"""First-stroke scoring, including interrupted episodes (the corrected scorer of the 2026-09-28 review).

The primary metric is the first-try learning curve after the change: for each post-change square, did its FIRST
stroke close it (1), miss (0), or was the square never attempted (None)?

  * A square whose first stroke missed is an observed miss, EVEN IF the episode stopped before the square's final
    record was written. (The older objective-pilot scorer read only the per-square results, which a stopped episode
    never wrote for its last square, so such a miss silently disappeared.)
  * A square never attempted stays unknown (None). Unknowns are excluded from the observed rate and counted
    separately (coverage); fixed-budget attainment divides hits by ALL planned squares and must not be described as
    an observed error rate.

Works on any episode-like mapping with `perturb_after`, `n_squares`, `strokes` ({square, closed} in execution order)
and optionally `squares_result` ({square, strokes, first_try}): the historical episode.json and the new summary.json.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

RUN_LENGTH = 3  # "squares to 3 first-try hits in a row"


def first_try_curve(ep: Mapping[str, Any], start: int | None = None) -> list[int | None]:
    start = ep["perturb_after"] + 1 if start is None else start
    first: dict[int, int] = {}
    for stroke in ep.get("strokes", []):
        q = stroke["square"]
        if q not in first:
            first[q] = int(bool(stroke["closed"]))
    # Support older summaries lacking stroke records, without replacing an observed failed first attempt just
    # because the episode later stopped.
    for result in ep.get("squares_result", []):
        if result.get("strokes", 0) > 0:
            first.setdefault(result["square"], int(bool(result["first_try"])))
    return [first.get(q) for q in range(start, ep["n_squares"] + 1)]


def first_try_summary(ep: Mapping[str, Any], start: int | None = None) -> dict[str, Any]:
    curve = first_try_curve(ep, start)
    seen = [v for v in curve if v is not None]
    hits = sum(seen)
    return {
        "curve": curve,
        "planned": len(curve),
        "attempted": len(seen),
        "unobserved": len(curve) - len(seen),
        "hits": hits,
        "observed_rate": hits / len(seen) if seen else None,
        "coverage": len(seen) / len(curve) if curve else None,
        "fixed_budget_attainment": hits / len(curve) if curve else None,
    }


def later_first_try(ep: Mapping[str, Any]) -> dict[str, Any]:
    """First-try summary over the squares AFTER the first post-change square (e.g. squares 6-20 when the change
    follows square 4): the transfer measure of the objective/informed pilots."""
    return first_try_summary(ep, ep["perturb_after"] + 2)


def squares_to_run(curve: list[int | None], run: int = RUN_LENGTH) -> int | None:
    """Post-change squares until `run` first-try hits in a row (None if never)."""
    run_len = 0
    for i, v in enumerate(curve):
        run_len = run_len + 1 if v == 1 else 0
        if run_len == run:
            return i + 1
    return None


def legacy_squares_result_curve(ep: Mapping[str, Any], start: int | None = None) -> list[int | None]:
    """The OLD objective-pilot curve (per-square results only). Kept only to show what rescoring changed."""
    start = ep["perturb_after"] + 1 if start is None else start
    res = {s["square"]: s for s in ep.get("squares_result", [])}
    return [(1 if res[q]["first_try"] else 0) if q in res else None for q in range(start, ep["n_squares"] + 1)]
