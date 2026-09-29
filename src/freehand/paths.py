"""Where things live: the repository root, the configs, and the results tree.

Nothing here is hardcoded to a machine. The results root is `$FREEHAND_RESULTS` when set, else `<repo>/results`
(gitignored). The configs directory is `$FREEHAND_CONFIG_DIR` when set, else `<repo>/configs`.
"""

from __future__ import annotations

import os
from pathlib import Path

RESULTS_ENV = "FREEHAND_RESULTS"
CONFIG_ENV = "FREEHAND_CONFIG_DIR"
PACKAGE_DIR = Path(__file__).resolve().parent


def _looks_like_repo(p: Path) -> bool:
    return (p / "pyproject.toml").is_file() and (p / "configs").is_dir()


def repo_root() -> Path:
    """The checkout this package runs from (editable install), else the nearest repo above the working dir."""
    for start in (PACKAGE_DIR, Path.cwd().resolve()):
        for p in (start, *start.parents):
            if _looks_like_repo(p):
                return p
    raise FileNotFoundError(
        "Could not find the Freehand repository (a directory with pyproject.toml and configs/). "
        "Install with `pip install -e .` from a clone, or set FREEHAND_CONFIG_DIR and FREEHAND_RESULTS."
    )


def config_dir() -> Path:
    env = os.environ.get(CONFIG_ENV)
    return Path(env).expanduser().resolve() if env else repo_root() / "configs"


def results_root() -> Path:
    env = os.environ.get(RESULTS_ENV)
    if env:
        return Path(env).expanduser().resolve()
    try:
        return repo_root() / "results"
    except FileNotFoundError:
        return Path.cwd().resolve() / "results"


def cache_path(root: Path | None = None) -> Path:
    return (root or results_root()) / "cache" / "llm_cache.sqlite"


def ledger_path(root: Path | None = None) -> Path:
    return (root or results_root()) / "ledger.sqlite"


def index_path(root: Path | None = None) -> Path:
    return (root or results_root()) / "index.jsonl"


def suites_dir() -> Path:
    return config_dir() / "suites"


def experiments_dir() -> Path:
    return config_dir() / "experiments"


def models_file() -> Path:
    return config_dir() / "models.toml"
