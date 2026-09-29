"""The global, append-only run index: results/index.jsonl.

One JSON line per event ("started", "finished", "imported"); lines are never rewritten. The current state of a run
is its latest line. Appends take an exclusive file lock, so concurrent runs can share one results root.
"""
from __future__ import annotations

import fcntl
import json
from datetime import UTC, datetime
from pathlib import Path

from freehand import paths


def append(root: Path | None, entry: dict) -> None:
    p = paths.index_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": datetime.now(UTC).isoformat(timespec="seconds"), **entry}, sort_keys=True)
    with open(p, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read(root: Path | None = None) -> list[dict]:
    p = paths.index_path(root)
    if not p.exists():
        return []
    out = []
    with open(p) as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{p}:{n}: corrupt index line ({e})") from None
    return out


def latest(root: Path | None = None) -> list[dict]:
    """The latest entry of every run, oldest run first."""
    runs: dict[str, dict] = {}
    first_seen: dict[str, int] = {}
    for i, e in enumerate(read(root)):
        key = _run_key(e)
        first_seen.setdefault(key, i)
        runs[key] = e
    return sorted(runs.values(), key=lambda e: first_seen[_run_key(e)])


def _run_key(e: dict) -> str:
    return str(e.get("run_id") or e.get("path"))
