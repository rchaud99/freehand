"""Writing a run: the manifest (atomic rewrites), the run log, and one EpisodeWriter per episode."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from freehand.results import index, layout
from freehand.results.provenance import provenance

MANIFEST_SCHEMA = "freehand.run_manifest/1"
log = logging.getLogger("freehand.run")  # progress lines; the CLI prints them to stdout


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_json_atomic(path: Path, obj: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, default=_json_default)
        f.write("\n")
    os.replace(tmp, path)


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


class EpisodeWriter:
    """Sink for one episode: episode.jsonl (appended and flushed every turn), images/ (optional), summary.json."""

    def __init__(self, directory: Path, save_images: bool = False, labels: dict | None = None):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.save_images = save_images
        self.labels = labels or {}
        self._log = open(self.dir / "episode.jsonl", "w")  # noqa: SIM115 - kept open, flushed every turn
        self.summary: dict | None = None

    def image(self, name: str, img: np.ndarray) -> None:
        d = self.dir / "images"
        d.mkdir(exist_ok=True)
        cv2.imwrite(str(d / name), img)

    def turn(self, rec: dict) -> None:
        self._log.write(json.dumps(rec, default=_json_default) + "\n")
        self._log.flush()

    def finish(self, summary: dict) -> None:
        self._log.close()
        self.summary = summary
        write_json_atomic(self.dir / "summary.json", summary)


class RunWriter:
    """Creates results/<experiment>/<run_id>/ and keeps its manifest current (thread-safe)."""

    def __init__(
        self,
        root: Path,
        experiment: str,
        config: dict,
        config_text: str,
        kind: str = "experiment",
        run_id: str | None = None,
    ):
        self.root = root
        self.run_id = run_id or layout.make_run_id(config_text)
        self.dir = layout.run_dir(root, experiment, self.run_id)
        if self.dir.exists():
            raise FileExistsError(f"{self.dir} already exists")
        self.dir.mkdir(parents=True)
        (self.dir / "episodes").mkdir()
        (self.dir / "config.yaml").write_text(config_text)
        self.lock = threading.Lock()
        self.manifest: dict[str, Any] = {
            "schema": MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "experiment": experiment,
            "kind": kind,
            "status": "running",
            "created_utc": utc_now(),
            "started_utc": utc_now(),
            "ended_utc": None,
            "provenance": provenance(),
            "config": config,
            "config_sha256": "sha256:" + hashlib.sha256(config_text.encode()).hexdigest(),
            "suites": {},
            "models": {},
            "arms": {},
            "budget": {},
            "options": {},
            "cells": [],
            "counts": {},
            "output_modes": {},
            "resumes": [],
            "notes": [],
        }
        self._log = open(self.dir / "run.log", "a")  # noqa: SIM115 - the run log lives as long as the run

    @classmethod
    def reopen(cls, run_dir: Path) -> RunWriter:
        """Continue writing an existing run (resume)."""
        self = cls.__new__(cls)
        self.dir = run_dir
        self.root = run_dir.parent.parent
        self.lock = threading.Lock()
        with open(run_dir / "manifest.json") as f:
            self.manifest = json.load(f)
        self.run_id = self.manifest["run_id"]
        self._log = open(run_dir / "run.log", "a")  # noqa: SIM115 - closed by finish()
        return self

    # ------------------------------------------------------------------ manifest
    def save(self) -> None:
        with self.lock:
            self.manifest["counts"] = dict(Counter(c["status"] for c in self.manifest["cells"]))
            write_json_atomic(self.dir / "manifest.json", self.manifest)

    def set(self, **fields) -> None:
        with self.lock:
            self.manifest.update(fields)
        self.save()

    def update_cell(self, cell_id: str, **fields) -> None:
        with self.lock:
            cell = next(c for c in self.manifest["cells"] if c["id"] == cell_id)
            cell.update(fields)
        self.save()

    def log(self, msg: str) -> None:
        line = f"{utc_now()} {msg}"
        with self.lock:
            if not self._log.closed:  # an episode abandoned by a second Ctrl-C may log after finish()
                self._log.write(line + "\n")
                self._log.flush()
        log.info(line)

    # ------------------------------------------------------------------ lifecycle
    def index_event(self, event: str) -> None:
        m = self.manifest
        index.append(
            self.root,
            {
                "event": event,
                "run_id": self.run_id,
                "experiment": m["experiment"],
                "kind": m["kind"],
                "path": str(self.dir.relative_to(self.root)),
                "status": m["status"],
                "cells": len(m["cells"]),
                "counts": m.get("counts", {}),
                "spend_usd": (m.get("budget") or {}).get("spent_this_run"),
                "suites": sorted(m.get("suites", {})),
                "models": sorted(m.get("models", {})),
                "git_commit": (m["provenance"].get("git") or {}).get("commit"),
                "git_dirty": (m["provenance"].get("git") or {}).get("dirty"),
                "fake_models": bool((m.get("options") or {}).get("fake_models")),
            },
        )

    def finish(self, status: str) -> None:
        self.set(status=status, ended_utc=utc_now())
        self.index_event("finished")
        self._log.close()
