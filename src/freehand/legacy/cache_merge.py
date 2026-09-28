"""Merging historical request caches and spend ledgers into the shared ones (copy; the source is opened read-only).

Idempotent: cache rows are keyed on the request hash (INSERT OR IGNORE) and imported spend rows are unique on
(ts, key, tag, cost), so re-running a merge (for example after a run in the old copy finished) only adds new rows.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from freehand.llm.cache import COLUMNS, RequestCache
from freehand.llm.ledger import Ledger

CHUNK = 500


def merge(src: Path, cache: RequestCache, ledger: Ledger, label: str) -> dict:
    conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=60)
    try:
        before_cache = cache.count()
        cur = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM cache")
        n_src = 0
        while rows := cur.fetchmany(CHUNK):
            n_src += len(rows)
            with cache.lock:
                cache.db.executemany(f"INSERT OR IGNORE INTO cache VALUES ({','.join('?' * len(COLUMNS))})", rows)
                cache.db.commit()
        added_cache = cache.count() - before_cache
        spend_rows = conn.execute("SELECT ts, key, model, cost, tag FROM spend").fetchall()
    finally:
        conn.close()
    with ledger.lock:
        before = ledger.db.execute("SELECT COUNT(*) FROM spend").fetchone()[0]
        ledger.db.executemany("INSERT OR IGNORE INTO spend VALUES (?,?,?,?,?,?,?,?)",
                              [(ts, key, model, cost, tag, None, None, label)
                               for ts, key, model, cost, tag in spend_rows])
        ledger.db.commit()
        added_spend = ledger.db.execute("SELECT COUNT(*) FROM spend").fetchone()[0] - before
    return {"source": label, "cache_rows_in_source": n_src, "cache_rows_added": added_cache,
            "spend_rows_in_source": len(spend_rows), "spend_rows_added": added_spend}
