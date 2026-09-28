"""The spend ledger and hard budget caps.

Every paid call is recorded in `results/ledger.sqlite` (table `spend`) with a budget tag and the run id. A `Budget`
caps the spend recorded under one tag:

  * before a call, the worst case (all input uncached + max output at list price, +25%) is reserved; the call is
    refused (`BudgetExceeded`) if spend + in-flight reservations + worst case would pass the cap;
  * the reservation is released only AFTER the billed cost is in the ledger (releasing first let a concurrent worker
    see neither the reservation nor the spend: the race fixed in the Codex copy);
  * cache hits cost nothing and reserve nothing.

The caps are local, estimate-based guards, not provider-enforced billing limits; OpenRouter keys can also carry their
own lifetime limit (see `openrouter.key_info`).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from freehand.llm.errors import BudgetExceeded

SCHEMA = ("CREATE TABLE IF NOT EXISTS spend (ts REAL, key TEXT, model TEXT, cost REAL, tag TEXT, run_id TEXT, "
          "route TEXT, source TEXT)")
SQLITE_TIMEOUT_S = 60


class Ledger:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, timeout=SQLITE_TIMEOUT_S)
        self.db.execute(SCHEMA)
        self.db.execute("CREATE INDEX IF NOT EXISTS spend_tag ON spend (tag)")
        # imported historical rows are unique, so re-merging an old ledger is idempotent
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS spend_imported ON spend (ts, key, tag, cost) "
                        "WHERE source != 'live'")
        self.db.commit()

    def record(self, key: str, model: str, cost: float, tag: str, run_id: str | None = None,
               route: str | None = None, source: str = "live", ts: float | None = None) -> None:
        with self.lock:
            self.db.execute("INSERT INTO spend VALUES (?,?,?,?,?,?,?,?)",
                            (ts if ts is not None else time.time(), key, model, float(cost), tag, run_id, route,
                             source))
            self.db.commit()

    def spent(self, tag: str | None = None, model: str | None = None, run_id: str | None = None) -> float:
        q, a = "SELECT COALESCE(SUM(cost), 0) FROM spend WHERE 1=1", []
        for col, val in (("tag", tag), ("model", model), ("run_id", run_id)):
            if val is not None:
                q += f" AND {col}=?"
                a.append(val)
        with self.lock:
            return float(self.db.execute(q, a).fetchone()[0])

    def by_tag(self) -> list[tuple[str, int, float]]:
        with self.lock:
            return [(t, int(n), float(c)) for t, n, c in self.db.execute(
                "SELECT tag, COUNT(*), COALESCE(SUM(cost), 0) FROM spend GROUP BY tag ORDER BY tag")]

    def close(self) -> None:
        with self.lock:
            self.db.close()


class Budget:
    """Hard cap on the spend recorded under one tag (shared by every thread of a run)."""

    def __init__(self, ledger: Ledger, cap_usd: float, tag: str, run_id: str | None = None):
        if cap_usd < 0:
            raise ValueError("budget cap must be >= 0")
        self.ledger, self.cap, self.tag, self.run_id = ledger, float(cap_usd), tag, run_id
        self.lock = threading.Lock()
        self.reserved = 0.0

    def spent(self) -> float:
        return self.ledger.spent(tag=self.tag)

    def remaining(self) -> float:
        return self.cap - self.spent()

    def reserve(self, worst: float) -> None:
        with self.lock:
            s = self.spent()
            if s + self.reserved + worst > self.cap:
                raise BudgetExceeded(f"cap ${self.cap:.2f} [{self.tag}]: spent ${s:.4f} + in flight "
                                     f"${self.reserved:.4f} + this call up to ${worst:.4f}")
            self.reserved += worst

    def release(self, worst: float) -> None:
        with self.lock:
            self.reserved -= worst

    def record(self, key: str, model: str, cost: float, route: str | None = None) -> None:
        self.ledger.record(key, model, cost, self.tag, self.run_id, route)

    def status(self) -> dict:
        return {"tag": self.tag, "cap": self.cap, "spent": round(self.spent(), 6)}


class EpisodeBudget:
    """A per-episode reservation gate over a shared Budget (the 48-cell model study's sequential runner):
    refuses a call if this episode's recorded spend + in-flight + worst case would pass `cap`."""

    def __init__(self, overall: Budget, cap: float):
        self.overall, self.cap = overall, float(cap)
        self.start = overall.spent()
        self.tag = overall.tag
        self.run_id = overall.run_id
        self.ledger = overall.ledger
        self.inflight = 0.0

    def spent(self) -> float:
        return self.overall.spent()

    def reserve(self, amount: float) -> None:
        if self.overall.spent() - self.start + self.inflight + amount > self.cap:
            raise BudgetExceeded("per-episode reservation cap reached")
        self.overall.reserve(amount)
        self.inflight += amount

    def release(self, amount: float) -> None:
        self.inflight -= amount
        self.overall.release(amount)

    def record(self, key: str, model: str, cost: float, route: str | None = None) -> None:
        self.overall.record(key, model, cost, route)

    def status(self) -> dict:
        return {**self.overall.status(), "episode_cap": self.cap}
