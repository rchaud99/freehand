"""Validation of results files against the JSON Schemas in results/schemas/ (documented in docs/results_format.md)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from freehand.results import layout

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
KINDS = ("manifest", "summary", "turn", "index_entry")


@lru_cache(maxsize=8)
def validator(kind: str) -> Draft202012Validator:
    if kind not in KINDS:
        raise KeyError(kind)
    with open(SCHEMA_DIR / f"{kind}.schema.json") as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def errors(kind: str, obj) -> list[str]:
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator(kind).iter_errors(obj), key=lambda e: list(e.absolute_path))
    ]


def validate(kind: str, obj) -> None:
    errs = errors(kind, obj)
    if errs:
        raise ValueError(f"invalid {kind}: " + "; ".join(errs[:5]) + (" ..." if len(errs) > 5 else ""))


def validate_run(run_dir: Path, max_turn_lines: int | None = None) -> list[str]:
    """Every schema error in a run directory (manifest, every summary.json, every episode.jsonl line)."""
    out: list[str] = []
    mf = run_dir / "manifest.json"
    if mf.exists():
        out += [f"manifest.json {e}" for e in errors("manifest", json.loads(mf.read_text()))]
    else:
        out.append("manifest.json missing")
    for ed in layout.iter_episode_dirs(run_dir):
        rel = ed.relative_to(run_dir)
        out += [f"{rel}/summary.json {e}" for e in errors("summary", json.loads((ed / "summary.json").read_text()))]
        jl = ed / "episode.jsonl"
        if not jl.exists():
            out.append(f"{rel}/episode.jsonl missing")
            continue
        with open(jl) as f:
            for n, line in enumerate(f, 1):
                if max_turn_lines is not None and n > max_turn_lines:
                    break
                out += [f"{rel}/episode.jsonl:{n} {e}" for e in errors("turn", json.loads(line))]
    return out
