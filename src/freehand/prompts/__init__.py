"""Versioned prompt text.

Every string a model receives lives in a text file under this directory (`v1/...`), never inline in code, so a
prompt change is a visible diff and a new version (`v2/`) can coexist with the one the historical runs used.
Components are addressed by id, e.g. "v1/system/plotter" -> v1/system/plotter.txt. Each file ends with exactly one
newline, which is not part of the text. Per-turn phrases are in v1/turn.toml. Placeholders use string.Template
syntax (${name}).

`tests/test_prompts.py` pins the v1 texts to the strings the historical code sent.
"""

from __future__ import annotations

import string
import tomllib
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
DEFAULT_VERSION = "v1"


@lru_cache(maxsize=256)
def text(pid: str) -> str:
    """The text of component `pid` (e.g. "v1/system/plotter")."""
    f = PROMPTS_DIR / f"{pid}.txt"
    if not f.is_file():
        raise KeyError(f"no prompt component {pid!r} (looked for {f})")
    raw = f.read_text(encoding="utf-8")
    if not raw.endswith("\n") or raw.endswith("\n\n"):
        raise ValueError(f"prompt file {f} must end with exactly one newline")
    return raw[:-1]


def render(pid: str, **values) -> str:
    return string.Template(text(pid)).substitute({k: str(v) for k, v in values.items()})


@lru_cache(maxsize=8)
def phrases(version: str = DEFAULT_VERSION) -> dict[str, str]:
    with open(PROMPTS_DIR / version / "turn.toml", "rb") as f:
        return tomllib.load(f)


def phrase(key: str, version: str = DEFAULT_VERSION, **values) -> str:
    try:
        t = phrases(version)[key]
    except KeyError:
        raise KeyError(f"no turn phrase {key!r} in {version}/turn.toml") from None
    return string.Template(t).substitute({k: str(v) for k, v in values.items()}) if values else t


def component_ids(version: str = DEFAULT_VERSION) -> list[str]:
    return sorted(str(p.relative_to(PROMPTS_DIR).with_suffix("")) for p in (PROMPTS_DIR / version).rglob("*.txt"))


def block_ids(version: str = DEFAULT_VERSION) -> list[str]:
    return sorted(p.stem for p in (PROMPTS_DIR / version / "blocks").glob("*.txt"))
