"""The results tree (outside git; root = $FREEHAND_RESULTS or <repo>/results):

    results/
      index.jsonl                         append-only: one line per run event (started / finished / imported)
      ledger.sqlite                       every paid call: cost, budget tag, run id
      cache/llm_cache.sqlite              the request cache (shared by all runs; hits cost nothing)
      <experiment>/<run_id>/
        manifest.json                     provenance + the status of every planned cell
        config.yaml                       the experiment config exactly as run
        run.log                           human-readable progress
        episodes/<agent>/<condition>/s<seed>/
          episode.jsonl                   one line per turn
          summary.json                    the episode's outcome, scores and metrics
          images/                         only with --save-images (replay regenerates them otherwise)
        report/                           `freehand report` output
      legacy/<origin>/<run>/              historical runs indexed by `freehand import-legacy`

run_id = UTC timestamp + "-" + the first 6 hex of the config's sha256, e.g. 20260928T174501Z-3f9a2c.
condition = "<perturbation>__<arm>" (reference agents use the arm "code").
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

SAFE = re.compile(r"[^A-Za-z0-9._+-]")
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")


def safe(name: str) -> str:
    """A filesystem-safe path component."""
    s = SAFE.sub("_", str(name)).strip("._")
    if not s:
        raise ValueError(f"cannot make a path component from {name!r}")
    return s


def make_run_id(config_text: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{hashlib.sha256(config_text.encode()).hexdigest()[:6]}"


def run_dir(root: Path, experiment: str, run_id: str) -> Path:
    return root / safe(experiment) / run_id


def condition(perturbation: str, arm: str) -> str:
    return f"{perturbation}__{arm}"


def episode_dir(run: Path, agent: str, perturbation: str, arm: str, seed: int) -> Path:
    return run / "episodes" / safe(agent) / safe(condition(perturbation, arm)) / f"s{int(seed)}"


def iter_episode_dirs(run: Path):
    """Every episode directory (one with a summary.json) under a run."""
    yield from sorted(p.parent for p in (run / "episodes").glob("*/*/*/summary.json"))
