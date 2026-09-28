"""Everything that defines one episode (apart from the agent)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from freehand.agents.arms import Arm, get_arm
from freehand.perturbations.base import Perturbation
from freehand.sim.page import Square

CAP_STROKES = 12          # strokes per square
CAP_TURNS = 14            # turns per square (turns without a valid stroke count here)


@dataclass
class EpisodeConfig:
    seed: int
    squares: list[Square]               # the squares this episode works through, in order
    perturbation: Perturbation
    perturb_after: int                  # the change switches on after this square (0: from the start)
    arm: Arm = field(default_factory=lambda: get_arm("silent"))
    output_mode: str = "page_mm"        # page_mm | crop_px (models only)
    cap_strokes: int = CAP_STROKES
    cap_turns: int = CAP_TURNS
    cost_cap: float | None = None       # stop (status "capped") once the episode's spend reaches this, checked per turn
    render: bool = True                 # False: headless (reference agents only)
    labels: dict[str, Any] = field(default_factory=dict)   # suite, run, cell ids ... copied into the summary

    def __post_init__(self):
        if self.perturb_after < 0 or self.perturb_after > len(self.squares):
            raise ValueError(f"perturb_after must be in [0, {len(self.squares)}]")
        if self.cap_strokes < 1 or self.cap_turns < self.cap_strokes:
            raise ValueError("need cap_strokes >= 1 and cap_turns >= cap_strokes")

    @property
    def n_squares(self) -> int:
        return len(self.squares)

    @property
    def tol(self) -> float:
        return self.perturbation.tol
