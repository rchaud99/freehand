"""Provenance recorded in every run manifest: git state, a hash of the source, package versions, platform."""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from freehand import __version__, paths

PACKAGES = ("numpy", "opencv-python-headless", "matplotlib", "requests", "PyYAML", "jsonschema")
SOURCE_GLOBS = ("src/freehand/**/*.py", "src/freehand/**/*.txt", "src/freehand/**/*.toml", "src/freehand/**/*.json",
                "configs/**/*.yaml", "configs/**/*.toml", "pyproject.toml")


def git_state(root: Path | None = None) -> dict:
    root = root or paths.repo_root()

    def git(*args: str) -> str | None:
        try:
            r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "dirty": bool(status) if status is not None else None,
            "branch": git("rev-parse", "--abbrev-ref", "HEAD")}


def source_hash(root: Path | None = None) -> str:
    """sha256 over (relative path, content) of the package source, prompts, schemas and configs."""
    root = root or paths.repo_root()
    h = hashlib.sha256()
    files = sorted({p for g in SOURCE_GLOBS for p in root.glob(g) if p.is_file() and "__pycache__" not in p.parts})
    for p in files:
        h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def package_versions() -> dict:
    out = {"python": sys.version.split()[0], "freehand": __version__}
    for name in PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def platform_info() -> dict:
    return {"system": platform.system(), "release": platform.release(), "machine": platform.machine()}


def provenance() -> dict:
    return {"git": git_state(), "source_sha256": source_hash(), "packages": package_versions(),
            "platform": platform_info()}
