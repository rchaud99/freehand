"""The quote bank: every note, memory entry and reasoning summary of the model episodes that talks about the change.

Rule (deterministic, documented): a field is included when it matches QUOTE_RX, the union of the two historical
mention screens (plotter and camera wording) plus hypothesis/measurement words (probe, landed, appeared, scale, map,
estimate, fit, affine, transform, Jacobian, px/mm, correct, rule, pattern, hypothesis).

Provenance: the historical reports/quote_bank/all_quotes.csv (3,273 rows, 91 episodes) was built by an unrecorded
procedure. On those 91 episodes this rule recovers 98% of its rows (3,207) and adds ~740 more, so it is a superset
to curate from, not a reproduction (docs/MIGRATION.md).
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from freehand.analysis.episodes import load_episodes
from freehand.episode.mentions import MENTION_A, MENTION_B

_EXTRA = (r"prob\w*|landed|appeared|scale\w*|\bmap\b|estimat\w*|jacobian|affine|transform\w*|px/mm|mm/px|"
          r"correct\w*|hypothes\w*|rule|pattern|fit\w*")
QUOTE_RX = re.compile(rf"(?:{MENTION_B.pattern})|(?:{MENTION_A.pattern})|\b(?:{_EXTRA})\b", re.I)
COLUMNS = ["run", "episode", "turn", "square", "attempt", "change_active", "field", "text"]
MAX_CHARS = 1500          # as in the historical bank: whitespace collapsed, text cut at 1,500 characters


def episode_label(ep) -> str:
    lab = ep.summary.get("labels", {})
    return lab.get("original_episode") or f"{ep.agent}__{ep.perturbation}__{ep.arm}__s{ep.seed}"


def quotes(run_dirs: list[Path]):
    for ep in load_episodes(run_dirs, allow_replicates=True, keep_identical=True):
        if ep.kind != "model":
            continue
        run = ep.summary.get("labels", {}).get("run") or ep.run.name
        for t in ep.turns():
            a = t.get("action") or {}
            for field, text in (("note", a.get("note", "")), ("memory", a.get("memory", "")),
                                ("thoughts", (t.get("reply") or {}).get("thoughts") or "")):
                text = str(text or "")
                if text and QUOTE_RX.search(text):          # match on the full text, store it normalised
                    yield {"run": run, "episode": episode_label(ep), "turn": t["turn"], "square": t["square"],
                           "attempt": t["attempt"], "change_active": t.get("change_active"), "field": field,
                           "text": " ".join(text.split())[:MAX_CHARS]}


def write_quote_bank(run_dirs: list[Path], out_csv: Path) -> int:
    n = 0
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for row in quotes(run_dirs):
            w.writerow(row)
            n += 1
    return n
