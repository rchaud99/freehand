"""`freehand export-data`: a sanitised, deterministic data bundle of finished runs, for a data release.

The bundle holds, per run, only what the analyses need:

    <name>/README.md                        what the bundle is and how to use it
    <name>/SHA256SUMS                       one line per file
    <name>/runs/<run>/manifest.json
    <name>/runs/<run>/episodes/<agent>/<condition>/s<seed>/{episode.jsonl, summary.json[, page.json]}
                                            (page.json: only for the few historical pages no suite regenerates)

Left out: images, `original` symlinks, the request cache, the spend ledger, run logs and reports. Absolute paths
are replaced by neutral provenance (`<source>:<container>/<run>`), and the export refuses to write anything that
still looks like a local path. The tar.gz is byte-reproducible: sorted entries, fixed mtimes, owners and modes.

`freehand figures <name>/runs/* --out DIR`, `freehand replay <name>/runs/<run>` and `freehand validate` work on the
extracted bundle from a clone of this repository (the suites regenerate the pages).
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from typing import Any

from freehand import __version__, paths
from freehand.errors import FreehandError
from freehand.results.layout import iter_episode_dirs, require_run_dir

# The four runs behind docs/figures (the objective, informed and stateless pilots and informed_models).
FIGURE_RUNS = ("informed_pilot", "informed_models", "objective_pilot", "stateless_pilot")
DEFAULT_NAME = "freehand_figure_runs_v1"
PAGE_FILES = ("episode.jsonl", "page.json")  # copied verbatim when present; summary.json is sanitised
TAR_MTIME = 1_790_640_000  # 2026-09-29T00:00:00Z: a fixed mtime, so the archive is reproducible
LOCAL_PATH = re.compile(r"(/Users/|/home/|/private/|/var/folders/|/tmp/|[A-Za-z]:\\\\)")


class UnsafeExport(FreehandError):
    """The export would contain a local path."""


def figure_run_dirs(root: Path | None = None) -> list[Path]:
    """The imported historical runs behind docs/figures, in FIGURE_RUNS order."""
    base = (root or paths.results_root()) / "legacy" / "working" / "runs"
    out = []
    for name in FIGURE_RUNS:
        found = sorted(base.glob(f"{name}_2*"))
        if len(found) != 1:
            raise FreehandError(
                f"expected one imported {name} run under {base}, found {len(found)}; "
                "run `freehand import-legacy` first, or pass the run directories"
            )
        out.append(found[0])
    return out


def _neutral(legacy: dict, run: str, episode: str | None = None) -> str:
    where = f"{legacy.get('source', 'legacy')}:{legacy.get('container', 'runs')}/{legacy.get('run', run)}"
    return f"{where}/episodes/{episode}" if episode else where


def sanitise_manifest(m: dict[str, Any], run: str) -> dict[str, Any]:
    m = json.loads(json.dumps(m))
    lg = m.get("legacy")
    if isinstance(lg, dict) and "original_path" in lg:
        lg["original_path"] = _neutral(lg, run)
    return m


def sanitise_summary(s: dict[str, Any], run: str) -> dict[str, Any]:
    s = json.loads(json.dumps(s))
    lg = s.get("legacy")
    if isinstance(lg, dict) and "original_dir" in lg:
        lg["original_dir"] = _neutral({**lg, "run": lg.get("run", run)}, run, Path(lg["original_dir"]).name)
    return s


def _check(name: str, data: bytes) -> None:
    m = LOCAL_PATH.search(data.decode("utf-8", errors="replace"))
    if m:
        raise UnsafeExport(f"{name} still contains a local path ({m.group(0)}...); not exporting it")


def _dump(obj: Any) -> bytes:
    return (json.dumps(obj, indent=1) + "\n").encode()


def collect(run_dirs: list[Path], name: str) -> dict[str, bytes]:
    """{archive path: bytes} of the bundle (sanitised and checked)."""
    files: dict[str, bytes] = {}
    runs = []
    for d in run_dirs:
        d = require_run_dir(d)
        run = d.name
        if f"{name}/runs/{run}/manifest.json" in files:
            raise FreehandError(f"two runs are named {run}")
        m = json.loads((d / "manifest.json").read_text())
        files[f"{name}/runs/{run}/manifest.json"] = _dump(sanitise_manifest(m, run))
        n = 0
        for ep in iter_episode_dirs(d):
            rel = ep.relative_to(d).as_posix()
            s = json.loads((ep / "summary.json").read_text())
            files[f"{name}/runs/{run}/{rel}/summary.json"] = _dump(sanitise_summary(s, run))
            for f in PAGE_FILES:
                if (ep / f).is_file():
                    files[f"{name}/runs/{run}/{rel}/{f}"] = (ep / f).read_bytes()
            n += 1
        runs.append((run, m.get("experiment"), n))
    for k, v in files.items():
        _check(k, v)
    files[f"{name}/README.md"] = _readme(name, runs).encode()
    sums = "".join(f"{hashlib.sha256(v).hexdigest()}  {k[len(name) + 1 :]}\n" for k, v in sorted(files.items()))
    files[f"{name}/SHA256SUMS"] = sums.encode()
    return files


def _readme(name: str, runs: list[tuple[str, Any, int]]) -> str:
    rows = "\n".join(f"| `runs/{r}` | {e} | {n} |" for r, e, n in runs)
    return f"""# {name}

The logged episodes behind the Freehand study figures, exported by `freehand export-data` (freehand
{__version__}). Each episode is its `episode.jsonl` (one line per turn: the prompt's state text and image hashes, the
model's reply, the command, where the ink landed, the closure verdict) and its `summary.json` (status, first-try
scores, metrics, ink, tokens, cost). Each run keeps its `manifest.json`. Formats: docs/results_format.md in the
repository.

| Run | Experiment | Episodes |
|---|---|---:|
{rows}

Not included: observation images (`freehand replay --render` regenerates them bit for bit), the request cache, the
spend ledger and run logs. A `page.json` is included for the few historical episodes whose page no suite
regenerates (here: a K1 output-mode check). Local paths in the provenance fields were replaced by
`<copy>:<container>/<run>`.

From a clone of the repository (`pip install -e .`), with this folder extracted to `data/{name}`:

    freehand figures data/{name}/runs/* --out figures     # the study figures and informed_summary.csv
    freehand replay data/{name}/runs/<run>                # re-simulate every stroke: 0 mismatches expected
    freehand validate data/{name}/runs/<run>              # JSON Schema check

`SHA256SUMS` lists every file (`cd {name} && shasum -a 256 -c SHA256SUMS`).
"""


def write_tar_gz(files: dict[str, bytes], out: Path) -> str:
    """Write a byte-reproducible .tar.gz; returns its sha256."""
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        dirs = sorted({p for k in files for p in _parents(k)})
        for d in dirs:
            ti = tarfile.TarInfo(d)
            ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, TAR_MTIME
            tar.addfile(ti)
        for k in sorted(files):
            ti = tarfile.TarInfo(k)
            ti.size, ti.mode, ti.mtime = len(files[k]), 0o644, TAR_MTIME
            tar.addfile(ti, io.BytesIO(files[k]))
    tmp = out.with_name(out.name + ".tmp")
    with open(tmp, "wb") as f, gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    tmp.replace(out)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def _parents(key: str) -> list[str]:
    parts = key.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]


def export_data(run_dirs: list[Path] | None, out: Path, name: str | None = None) -> dict:
    name = name or out.name.removesuffix(".tar.gz").removesuffix(".tgz")
    dirs = run_dirs or figure_run_dirs()
    files = collect(dirs, name)
    sha = write_tar_gz(files, out)
    episodes = sum(1 for k in files if k.endswith("/summary.json"))
    return {
        "out": str(out),
        "sha256": sha,
        "bytes": out.stat().st_size,
        "runs": [d.name for d in dirs],
        "episodes": episodes,
        "files": len(files),
    }
