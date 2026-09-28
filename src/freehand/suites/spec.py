"""Suite files: configs/suites/<id>.yaml.

A suite freezes everything that makes two runs comparable: the page generator and its spec, the change schedule,
the named perturbations with their parameters, the episode caps, and explicit seed lists split into `dev` (public,
tune on these) and `test` (held out: report on these, never tune). `data_hash` pins the generated data; `freehand
suite verify` and the test suite recompute it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from freehand import paths
from freehand.perturbations import validate_spec

TRACKS = ("plotter", "camera")
ORDERS = ("placement", "far_apart")
SCHEDULES = ("fixed", "study-v1")
GENERATORS = ("freehand-page-v1",)
SPLITS = ("dev", "test")


@dataclass(frozen=True)
class PageSpec:
    n_squares: int | None = None             # None: drawn from the page stream (10-15 squares)
    area: tuple | None = None                # None: reachable region minus a 16 mm margin
    size_range_mm: tuple = (20.0, 40.0)
    gap_mm: float = 9.0
    order: str = "placement"                 # placement | far_apart (each square far from the previous one)

    def __post_init__(self):
        if self.order not in ORDERS:
            raise ValueError(f"page.order must be one of {ORDERS}")
        if self.n_squares is not None and self.n_squares < 1:
            raise ValueError("page.n_squares must be >= 1")
        if self.area is not None and len(self.area) != 4:
            raise ValueError("page.area must be [x_lo, y_lo, x_hi, y_hi] in mm")


@dataclass(frozen=True)
class SuiteSpec:
    id: str
    version: int
    description: str
    track: str
    page: PageSpec
    change_after: int | None                 # None when the schedule draws it per seed
    schedule: str
    perturbations: dict[str, dict]
    seeds: dict[str, list[int]]
    cap_strokes: int = 12
    cap_turns: int = 14
    generator: str = "freehand-page-v1"
    data_hash: str | None = None
    legacy: bool = False
    notes: str = ""
    path: Path | None = field(default=None, compare=False)

    def all_seeds(self) -> list[int]:
        return [s for split in SPLITS for s in self.seeds.get(split, [])]

    def split_of(self, seed: int) -> str | None:
        return next((k for k in SPLITS if seed in self.seeds.get(k, [])), None)

    def perturbation_names(self) -> list[str]:
        return list(self.perturbations)


def _tuple(v):
    return tuple(v) if isinstance(v, list) else v


def parse_suite(d: dict[str, Any], path: Path | None = None) -> SuiteSpec:
    known = {"id", "version", "description", "track", "page", "change", "perturbations", "seeds", "episode",
             "generator", "data_hash", "legacy", "notes"}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"suite {d.get('id')}: unknown top-level keys {sorted(unknown)}")
    for k in ("id", "version", "track", "page", "change", "perturbations", "seeds"):
        if k not in d:
            raise ValueError(f"suite file {path}: missing `{k}`")
    if d["track"] not in TRACKS:
        raise ValueError(f"suite {d['id']}: track must be one of {TRACKS}")
    if d.get("generator", "freehand-page-v1") not in GENERATORS:
        raise ValueError(f"suite {d['id']}: unknown generator {d.get('generator')}")
    p = d["page"]
    page = PageSpec(n_squares=p.get("n_squares"), area=_tuple(p.get("area")) if p.get("area") not in (None, "default")
                    else None, size_range_mm=_tuple(p.get("size_range_mm", [20.0, 40.0])),
                    gap_mm=float(p.get("gap_mm", 9.0)), order=p.get("order", "placement"))
    ch = d["change"]
    schedule = ch.get("schedule", "fixed")
    if schedule not in SCHEDULES:
        raise ValueError(f"suite {d['id']}: change.schedule must be one of {SCHEDULES}")
    after = ch.get("after_square")
    if schedule == "fixed" and not isinstance(after, int):
        raise ValueError(f"suite {d['id']}: a fixed schedule needs an integer change.after_square")
    perts = dict(d["perturbations"])
    for name, spec in perts.items():
        params = spec.get("params")
        if params == "from_schedule" or (isinstance(params, dict) and "from_schedule" in params):
            if schedule == "fixed":
                raise ValueError(f"suite {d['id']}: {name} takes params from the schedule, but it is fixed")
            continue
        validate_spec(name, spec)
        if d["track"] == "camera" and spec["type"] != "camera_move":
            raise ValueError(f"suite {d['id']}: the camera track only takes camera_move perturbations")
        if d["track"] == "plotter" and spec["type"] == "camera_move":
            raise ValueError(f"suite {d['id']}: camera_move needs the camera track")
    seeds = {k: [int(s) for s in (d["seeds"].get(k) or [])] for k in SPLITS}
    extra = set(d["seeds"]) - set(SPLITS)
    if extra:
        raise ValueError(f"suite {d['id']}: seed splits must be {SPLITS}, got {sorted(extra)}")
    flat = seeds["dev"] + seeds["test"]
    if len(flat) != len(set(flat)):
        raise ValueError(f"suite {d['id']}: a seed appears twice")
    ep = d.get("episode", {}) or {}
    return SuiteSpec(id=d["id"], version=int(d["version"]), description=d.get("description", "").strip(),
                     track=d["track"], page=page, change_after=after if schedule == "fixed" else None,
                     schedule=schedule, perturbations=perts, seeds=seeds,
                     cap_strokes=int(ep.get("cap_strokes", 12)), cap_turns=int(ep.get("cap_turns", 14)),
                     generator=d.get("generator", "freehand-page-v1"), data_hash=d.get("data_hash"),
                     legacy=bool(d.get("legacy", False)), notes=d.get("notes", "") or "", path=path)


def suite_path(suite_id: str) -> Path:
    return paths.suites_dir() / f"{suite_id}.yaml"


def load_suite(ref: str | Path) -> SuiteSpec:
    """A suite by id (configs/suites/<id>.yaml) or by path."""
    p = Path(ref)
    if not (p.suffix in (".yaml", ".yml") and p.exists()):
        p = suite_path(str(ref))
    if not p.exists():
        known = sorted(x.stem for x in paths.suites_dir().glob("*.yaml"))
        raise FileNotFoundError(f"no suite {ref!r}; known suites: {known}")
    with open(p) as f:
        d = yaml.safe_load(f)
    s = parse_suite(d, p)
    if s.id != p.stem:
        raise ValueError(f"suite file {p.name} declares id {s.id!r}; they must match")
    return s


def list_suites() -> list[SuiteSpec]:
    return [load_suite(p) for p in sorted(paths.suites_dir().glob("*.yaml"))]
