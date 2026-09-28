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
        return (self.labels.get("suite") or "legacy-page", self.perturbation, self.seed, s["n_squares"],
                s["perturb_after"], s["setup"]["cap_strokes"])

    @property
    def cell_key(self) -> tuple:
        return (self.agent, self.perturbation, self.arm, self.seed)

    def turns(self) -> list[dict]:
        p = self.dir / "episode.jsonl"
        if not p.exists():
            return []
        with open(p) as f:
            return [json.loads(line) for line in f if line.strip()]


def load_episodes(run_dirs: list[Path]) -> list[Episode]:
    """All episodes of the runs, in order. Identical repeats of one (agent, rule, arm, seed) across runs are dropped
    (the first run wins, as the historical summaries did); differing repeats are all kept as replicates."""
    out: list[Episode] = []
    seen: dict[tuple, Episode] = {}
    for run in run_dirs:
        for d in layout.iter_episode_dirs(run):
            if d.parent.name.startswith("check__"):
                continue                       # output-mode gate episodes are not results
            ep = Episode(d, run, json.loads((d / "summary.json").read_text()))
            prev = seen.get(ep.cell_key)
            if prev is not None and prev.summary["strokes"] == ep.summary["strokes"] \
                    and prev.summary["squares_result"] == ep.summary["squares_result"]:
                continue
            seen.setdefault(ep.cell_key, ep)
            out.append(ep)
    return out
