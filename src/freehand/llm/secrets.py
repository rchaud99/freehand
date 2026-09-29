"""API keys: read from the environment, else from `<repo>/.env`. Nothing else is consulted.

Keys are read into memory only when a live call needs them and are never printed, logged or written to results.
"""
from __future__ import annotations

import os

from freehand import paths
from freehand.llm.errors import MissingKeyError

OPENROUTER_KEY = "OPENROUTER_API_KEY"
GEMINI_KEY = "GEMINI_API_KEY"


def _from_dotenv(name: str) -> str | None:
    try:
        f = paths.repo_root() / ".env"
    except FileNotFoundError:
        return None
    if not f.is_file():
        return None
    with open(f) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):]
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def get_key(name: str) -> str:
    """The key `name` from the environment or <repo>/.env; raises MissingKeyError (without the value) otherwise."""
    v = os.environ.get(name) or _from_dotenv(name)
    if not v:
        raise MissingKeyError(f"{name} is not set: export it or add `{name}=...` to <repo>/.env "
                              "(see .env.example). Cached requests replay without a key.")
    return v
