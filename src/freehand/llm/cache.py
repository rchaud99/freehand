"""The request cache: sqlite, keyed on the request hash (see messages.request_key).

The table layout is the historical `cache` table, so old caches merge by plain INSERT OR IGNORE
(`freehand import-legacy --merge-cache`). Each row keeps the route, settings, the neutral request, the raw response,
text, reasoning, usage, cost, model version and latency. A cache hit costs nothing.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, model TEXT, route TEXT, settings TEXT,
            request TEXT, response TEXT, text TEXT, thoughts TEXT, usage TEXT, cost REAL, model_version TEXT,
            latency REAL, ts REAL)"""
COLUMNS = (
    "key",
    "model",
    "route",
    "settings",
    "request",
    "response",
    "text",
    "thoughts",
    "usage",
    "cost",
    "model_version",
    "latency",
    "ts",
)
SQLITE_TIMEOUT_S = 60


class RequestCache:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, timeout=SQLITE_TIMEOUT_S)
        self.db.execute(SCHEMA)
        self.db.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM cache WHERE key=?", (key,)).fetchone()
        return dict(zip(COLUMNS, row, strict=True)) if row else None

    def put(
        self,
        key: str,
        model: str,
        route: str,
        settings: dict,
        request: dict,
        raw: dict,
        text: str,
        thoughts: str | None,
        usage: dict,
        cost: float,
        version: str,
        latency: float,
    ) -> None:
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    model,
                    route,
                    json.dumps(settings),
                    json.dumps(request),
                    json.dumps(raw),
                    text,
                    thoughts,
                    json.dumps(usage),
                    cost,
                    version,
                    latency,
                    time.time(),
                ),
            )
            self.db.commit()

    def count(self) -> int:
        with self.lock:
            return int(self.db.execute("SELECT COUNT(*) FROM cache").fetchone()[0])

    def close(self) -> None:
        with self.lock:
            self.db.close()
