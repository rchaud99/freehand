"""`freehand import-legacy`: index the historical runs into results/legacy/ without moving or copying the originals.

For every historical run directory (runs/* and publication/* of each source copy):
  results/legacy/<source>/<runs|publication>/<run name>/
    manifest.json      kind "legacy": original path, content hash, the original manifest if any, one cell per
                       episode with its status, matched suites, and `duplicate_of` when the same episodes were
                       already imported from the other copy
    original ->        symlink to the untouched original directory (images, videos, logs stay there)
    episodes/<agent>/<perturbation>__<arm>/s<seed>/
      summary.json     converted (see legacy/convert.py); + page.json when no legacy suite reproduces the page
      episode.jsonl
The 20+ GB of PNGs are never copied (their sha256 is recorded per turn). Sources are only read. The request caches
(cache.sqlite) are merged into results/cache/llm_cache.sqlite and their spend into results/ledger.sqlite, so every
historical request replays for free.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from freehand import paths
from freehand.legacy.cache_merge import merge
from freehand.legacy.convert import convert_episode
from freehand.legacy.match import SuiteMatcher
from freehand.llm.cache import RequestCache
from freehand.llm.ledger import Ledger
from freehand.results import index, layout
from freehand.results.writer import write_json_atomic

CONTAINERS = ("runs", "publication")
_TS_SUFFIX = re.compile(r"_\d{8}_\d{6}$")


@dataclass
class LegacyRun:
    source: str
    container: str
    name: str
    path: Path
    episode_dirs: list[Path] = field(default_factory=list)

    @property
    def experiment(self) -> str:
        base = _TS_SUFFIX.sub("", self.name).strip("_") or self.name
        return base if self.container == "runs" else f"publication_{base}"

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for d in self.episode_dirs:
            h.update(d.name.encode())
            for f in ("episode.json", "turns.jsonl"):
                p = d / f
                if p.exists():
                    h.update(p.read_bytes())
        return h.hexdigest()


def discover(source: str, root: Path) -> list[LegacyRun]:
    out = []
    for container in CONTAINERS:
        base = root / container
        if not base.is_dir():
            continue
        for run in sorted(p for p in base.iterdir() if p.is_dir()):
            eps_root = run / "episodes"
            if eps_root.is_dir():
                eps = sorted(p for p in eps_root.iterdir() if (p / "episode.json").exists())
            else:           # check folders: episodes directly inside
                eps = sorted(p for p in run.iterdir() if p.is_dir() and (p / "episode.json").exists())
            if eps or eps_root.is_dir() or any(run.glob("*.json*")):
                out.append(LegacyRun(source, container, run.name, run, eps))
    return out


def _cell_status(summary: dict) -> str:
    return summary["status"]


class Importer:
    def __init__(self, sources: dict[str, Path], results_root: Path | None = None, hash_images: bool = True,
                 exclude: list[str] | None = None, only: list[str] | None = None, force: bool = False, log=print):
        self.sources = sources
        self.root = results_root or paths.results_root()
        self.hash_images = hash_images
        self.exclude = exclude or []
        self.only = only or []
        self.force = force
        self.log = log
        self.matcher = SuiteMatcher()
        self.seen: dict[str, str] = {}          # run content hash -> imported path (for duplicates)

    def _selected(self, run: LegacyRun) -> bool:
        if any(fnmatch.fnmatch(run.name, pat) for pat in self.exclude):
            return False
        return not self.only or any(fnmatch.fnmatch(run.name, pat) for pat in self.only)

    def dest(self, run: LegacyRun) -> Path:
        return self.root / "legacy" / layout.safe(run.source) / run.container / run.name

    def _load_seen(self) -> None:
        for mf in (self.root / "legacy").glob("*/*/*/manifest.json"):
            try:
                m = json.loads(mf.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            h = (m.get("legacy") or {}).get("content_sha256")
            if h and not (m.get("legacy") or {}).get("duplicate_of"):
                self.seen.setdefault(h, str(mf.parent.relative_to(self.root)))

    def import_all(self) -> dict:
        self._load_seen()
        stats = Counter()
        for label, root in self.sources.items():
            for run in discover(label, root):
                if not self._selected(run):
                    stats["excluded"] += 1
                    continue
                r = self.import_run(run)
                stats[r] += 1
        return dict(stats)

    def import_run(self, run: LegacyRun) -> str:
        dest = self.dest(run)
        if (dest / "manifest.json").exists() and not self.force:
            return "already_imported"
        chash = run.content_hash()
        dup = self.seen.get(chash) if run.episode_dirs else None
        if dup == str(dest.relative_to(self.root)):
            dup = None                          # --force on a run already imported: it is not its own duplicate
        dest.mkdir(parents=True, exist_ok=True)
        link = dest / "original"
        if not link.exists() and not link.is_symlink():
            os.symlink(run.path, link, target_is_directory=True)
        original_manifest = None
        if (run.path / "manifest.json").exists():
            try:
                original_manifest = json.loads((run.path / "manifest.json").read_text())
            except json.JSONDecodeError:
                original_manifest = None
        cells, suites = [], {}
        if dup is None:
            for ep_dir in run.episode_dirs:
                cell = self._convert(run, ep_dir, dest)
                cells.append(cell)
                if cell.get("suite"):
                    suites.setdefault(cell["suite"], {"data_hash": cell.get("suite_data_hash"), "verified": True,
                                                       "seeds": []})
                    if cell["seed"] not in suites[cell["suite"]]["seeds"]:
                        suites[cell["suite"]]["seeds"].append(cell["seed"])
            if run.episode_dirs:
                self.seen[chash] = str(dest.relative_to(self.root))
        manifest = {
            "schema": "freehand.run_manifest/1", "run_id": f"legacy:{run.source}:{run.container}:{run.name}",
            "experiment": run.experiment, "kind": "legacy", "status": "imported",
            "created_utc": None, "started_utc": None, "ended_utc": None,
            "provenance": {"git": None, "source_sha256": None, "packages": None, "platform": None},
            "config": original_manifest or {}, "config_sha256": None, "suites": suites, "models": {}, "arms": {},
            "budget": ({"tag": original_manifest.get("tag"), **original_manifest.get("budget", {})}
                       if original_manifest else {}),
            "options": {}, "cells": cells, "counts": dict(Counter(c["status"] for c in cells)),
            "legacy": {"source": run.source, "container": run.container, "original_path": str(run.path),
                       "content_sha256": chash, "episodes": len(run.episode_dirs), "duplicate_of": dup,
                       "files": sorted(p.name for p in run.path.iterdir() if p.is_file())}}
        write_json_atomic(dest / "manifest.json", manifest)
        index.append(self.root, {"event": "imported", "run_id": manifest["run_id"], "experiment": run.experiment,
                                 "kind": "legacy", "path": str(dest.relative_to(self.root)), "status": "imported",
                                 "cells": len(cells), "counts": manifest["counts"], "duplicate_of": dup,
                                 "original_path": str(run.path), "suites": sorted(suites)})
        self.log(f"{run.source}/{run.container}/{run.name}: {len(run.episode_dirs)} episodes"
                 + (f" (duplicate of {dup})" if dup else ""))
        return "duplicate" if dup else "imported"

    def _convert(self, run: LegacyRun, ep_dir: Path, dest: Path) -> dict:
        ep = json.loads((ep_dir / "episode.json").read_text())
        match = self.matcher.match(ep)
        summary, recs, page = convert_episode(ep_dir, run.source, run.name, match, self.hash_images)
        pert_label = match["perturbation"] if match else (ep.get("pert") or "none")
        arm = summary["labels"]["arm"]
        d = layout.episode_dir(dest, ep["agent"], pert_label, arm, ep["seed"])
        if (d / "summary.json").exists() and json.loads((d / "summary.json").read_text())["legacy"][
                "original_dir"] != str(ep_dir):
            d = d.parent / f"s{ep['seed']}__{layout.safe(ep_dir.name)}"      # two originals map to one cell
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "episode.jsonl", "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        write_json_atomic(d / "summary.json", summary)
        if page is not None:
            write_json_atomic(d / "page.json", page)
        return {"id": f"{run.name}:{ep_dir.name}", "kind": summary["agent"]["kind"], "agent": ep["agent"],
                "perturbation": pert_label, "arm": arm, "seed": ep["seed"], "suite": match["suite"] if match else None,
                "suite_data_hash": match["suite_data_hash"] if match else None,
                "status": _cell_status(summary), "episode_dir": str(d.relative_to(dest)),
                "original_episode": ep_dir.name, "cost_original_usd": summary["cost"]["usd_original"],
                "first_try": {k: summary["scores"]["first_try"][k] for k in ("hits", "attempted", "planned")}}

    def merge_caches(self) -> list[dict]:
        cache = RequestCache(paths.cache_path(self.root))
        ledger = Ledger(paths.ledger_path(self.root))
        out = []
        for label, root in self.sources.items():
            src = root / "cache.sqlite"
            if src.exists():
                r = merge(src, cache, ledger, f"legacy:{label}")
                out.append(r)
                self.log(f"cache {label}: +{r['cache_rows_added']} of {r['cache_rows_in_source']} rows; "
                         f"spend +{r['spend_rows_added']} of {r['spend_rows_in_source']}")
        cache.close()
        ledger.close()
        return out
