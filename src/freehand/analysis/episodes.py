"""Loading episode summaries from one or more run directories (new runs and imported legacy runs alike)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from freehand.results import layout


@dataclass
class Episode:
    dir: Path
    run: Path
    summary: dict

    @property
    def labels(self) -> dict:
        return self.summary.get("labels", {})

    @property
    def agent(self) -> str:
        return self.summary["agent"]["name"]

    @property
    def kind(self) -> str:
        return self.summary["agent"]["kind"]

    @property
    def perturbation(self) -> str:
        return self.labels.get("perturbation") or self.summary["perturbation"].get("name")

    @property
    def arm(self) -> str:
        return self.labels.get("arm") or self.summary["arm"]["name"]

    @property
    def seed(self) -> int:
        return self.summary["seed"]

    @property
    def page_key(self) -> tuple:
        """Episodes with the same key share page, rule, change point and caps (so references apply)."""
        s = self.summary
        return (
            self.labels.get("suite") or "legacy-page",
            self.perturbation,
            self.seed,
            s["n_squares"],
            s["perturb_after"],
            (s.get("setup") or {}).get("cap_strokes"),
        )

    @property
    def cell_key(self) -> tuple:
        """One cell of a design: the same page (suite or legacy page), rule, change point, agent, arm and seed."""
        return (*self.page_key, self.agent, self.arm)

    def turns(self) -> list[dict]:
        p = self.dir / "episode.jsonl"
        if not p.exists():
            return []
        with open(p) as f:
            return [json.loads(line) for line in f if line.strip()]


def load_episodes(run_dirs: list[Path], allow_replicates: bool = False, keep_identical: bool = False) -> list[Episode]:
    """All episodes of the runs, in order. Identical repeats of one (agent, rule, arm, seed) across runs are dropped
    (the first run wins, as the historical summaries did: e.g. the deterministic references). DIFFERING repeats raise
    ValueError unless allow_replicates=True (then all are kept): silently picking one would bias a summary."""
    out: list[Episode] = []
    seen: dict[tuple, Episode] = {}
    for run in run_dirs:
        for d in layout.iter_episode_dirs(run):
            if d.parent.name.startswith("check__"):
                continue  # output-mode gate episodes are not results
            ep = Episode(d, run, json.loads((d / "summary.json").read_text()))
            prev = seen.get(ep.cell_key)
            if prev is not None:
                same = (
                    prev.summary["strokes"] == ep.summary["strokes"]
                    and prev.summary["squares_result"] == ep.summary["squares_result"]
                )
                if same and not keep_identical:
                    continue
                if not allow_replicates:
                    raise ValueError(
                        f"conflicting repetitions of {ep.cell_key} in {prev.run} and {run}; "
                        "pass them separately or allow replicates explicitly"
                    )
            seen.setdefault(ep.cell_key, ep)
            out.append(ep)
    return out
