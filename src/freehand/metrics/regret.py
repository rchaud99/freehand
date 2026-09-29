"""Normalised regret against the reference agents on the same page, rule, change point and caps.

    regret = (agent - ideal estimator) / (naive - ideal estimator)

0 = as good as the ideal estimator (`adaptive`), 1 = as bad as never adapting (`naive`); < 0 beats the estimator,
> 1 is worse than never adapting. Undefined (None) where naive and ideal coincide (no change to adapt to).
"""

from __future__ import annotations

REGRET_EPS = 1e-6


def regret(agent: float | None, ideal: float | None, naive: float | None, digits: int = 3) -> float | None:
    if agent is None or ideal is None or naive is None:
        return None
    span = naive - ideal
    if span <= REGRET_EPS:
        return None
    return round((agent - ideal) / span, digits)
