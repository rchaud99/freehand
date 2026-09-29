"""The quote bank: every note, memory entry and reasoning summary of the model episodes that talks about the change.

Rule (deterministic, documented): a field is included when it matches QUOTE_RX, the union of the two historical
mention screens (plotter and camera wording) plus hypothesis/measurement words (probe, landed, appeared, scale, map,
estimate, fit, affine, transform, Jacobian, px/mm, correct, rule, pattern, hypothesis).

Provenance: the historical reports/quote_bank/all_quotes.csv (3,273 rows, 91 episodes) was built by an unrecorded
procedure. On those 91 episodes this rule recovers 98% of its rows (3,207) and adds ~740 more, so it is a superset
to curate from, not a reproduction (docs/provenance/MIGRATION.md).

An episode repeated in a later run is listed once, under the first run given: episodes with the same name and the
same quoted texts are duplicates (sonnet_pilot carries pilot2's three Opus episodes for comparison, and the second
first-pilot run repeats the first one's Flash episode).
"""

from __future__ import annotations

import csv
import gzip
import io
import re
from pathlib import Path

from freehand.analysis.episodes import load_episodes
from freehand.episode.mentions import MENTION_A, MENTION_B

_EXTRA = (
    r"prob\w*|landed|appeared|scale\w*|\bmap\b|estimat\w*|jacobian|affine|transform\w*|px/mm|mm/px|"
    r"correct\w*|hypothes\w*|rule|pattern|fit\w*"
)
QUOTE_RX = re.compile(rf"(?:{MENTION_B.pattern})|(?:{MENTION_A.pattern})|\b(?:{_EXTRA})\b", re.I)
COLUMNS = ["run", "episode", "turn", "square", "attempt", "change_active", "field", "text"]
MAX_CHARS = 1500  # as in the historical bank: whitespace collapsed, text cut at 1,500 characters
FIELDS = ("note", "memory", "thoughts")


def episode_label(ep) -> str:
    lab = ep.summary.get("labels", {})
    return lab.get("original_episode") or f"{ep.agent}__{ep.perturbation}__{ep.arm}__s{ep.seed}"


def quotes(run_dirs: list[Path], fields: tuple[str, ...] = FIELDS):
    seen: set[tuple] = set()
    for ep in load_episodes(run_dirs, allow_replicates=True, keep_identical=True):
        if ep.kind != "model":
            continue
        run = ep.summary.get("labels", {}).get("run") or ep.run.name
        rows = []
        for t in ep.turns():
            a = t.get("action") or {}
            for field, text in (
                ("note", a.get("note", "")),
                ("memory", a.get("memory", "")),
                ("thoughts", (t.get("reply") or {}).get("thoughts") or ""),
            ):
                text = str(text or "")
                if field in fields and text and QUOTE_RX.search(text):  # match the full text, store it normalised
                    rows.append(
                        {
                            "run": run,
                            "episode": episode_label(ep),
                            "turn": t["turn"],
                            "square": t["square"],
                            "attempt": t["attempt"],
                            "change_active": t.get("change_active"),
                            "field": field,
                            "text": " ".join(text.split())[:MAX_CHARS],
                        }
                    )
        key = (episode_label(ep), tuple((r["turn"], r["field"], r["text"]) for r in rows))
        if rows and key in seen:  # the same episode, copied into a later run
            continue
        seen.add(key)
        yield from rows


def write_quote_bank(run_dirs: list[Path], out_csv: Path, fields: tuple[str, ...] = FIELDS) -> int:
    """Write the bank as CSV (gzip-compressed, deterministically, when the name ends in .gz)."""
    bad = set(fields) - set(FIELDS)
    if bad:
        raise ValueError(f"unknown quote fields {sorted(bad)}; choose from {FIELDS}")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fh = open(out_csv, "wb")  # noqa: SIM115
    # no name or time in the gzip header, so the same bank gives the same bytes
    raw = gzip.GzipFile(filename="", fileobj=fh, mode="wb", mtime=0) if out_csv.suffix == ".gz" else fh
    n = 0
    with fh, raw, io.TextIOWrapper(raw, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for row in quotes(run_dirs, fields):
            w.writerow(row)
            n += 1
    return n
