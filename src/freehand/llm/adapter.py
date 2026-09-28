"""The common call path: request -> cache lookup -> budget reservation -> provider call -> ledger + cache."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from freehand.llm.cache import RequestCache
from freehand.llm.errors import TransientError
from freehand.llm.messages import Message, image_parts, neutral, request_key, text_chars

IMAGE_TOKENS_EST = {"high": 3000, "low": 600}   # generous per-image input estimates for the reservation
CHARS_PER_TOKEN_EST = 3                         # conservative (English runs ~4)
RESERVATION_MARGIN = 1.25
DEFAULT_MAX_TOKENS = 8000
RETRY_TRIES = 5
RETRY_BACKOFF_S = 4
RETRY_MAX_SLEEP_S = 60


class BudgetLike(Protocol):
    tag: str

    def reserve(self, worst: float) -> None: ...
    def release(self, worst: float) -> None: ...
    def record(self, key: str, model: str, cost: float, route: str | None = None) -> None: ...


@dataclass
class Reply:
    text: str
    thoughts: str | None
    usage: dict
    cost: float                     # dollars this call cost now (0 for a cache hit)
    cost_original: float            # dollars the response cost when it was first made
    cached: bool
    model_version: str
    route: str
    settings: dict
    latency_s: float
    raw: dict = field(default_factory=dict)
    key: str = ""


def retry(fn, tries: int = RETRY_TRIES, sleep=time.sleep):
    """Call fn, retrying TransientError with exponential backoff (4, 8, 16, 32 s ... capped at 60 s)."""
    for i in range(tries):
        try:
            return fn()
        except TransientError:
            if i == tries - 1:
                raise
            sleep(min(RETRY_MAX_SLEEP_S, RETRY_BACKOFF_S * 2 ** i))
    raise AssertionError("unreachable")


class Adapter:
    """Subclasses set `provider`, build `settings` (part of the cache key) and implement `_call`."""
    provider = "?"

    def __init__(self, model: str, cache: RequestCache, budget: BudgetLike, prices: tuple[float, float],
                 **settings: Any):
        self.model, self.cache, self.budget = model, cache, budget
        self.prices = (float(prices[0]), float(prices[1]))
        self.settings = dict(settings)

    @property
    def route(self) -> str:
        return self.provider

    def price(self, in_tok: float, out_tok: float) -> float:
        pin, pout = self.prices
        return (in_tok * pin + out_tok * pout) / 1e6

    def key(self, system: str, messages: list[Message]) -> str:
        return request_key(self.provider, self.route, self.model, self.settings, system, messages)

    def worst_case(self, system: str, messages: list[Message]) -> float:
        imgs = sum(IMAGE_TOKENS_EST[p.get("detail", "high")] for p in image_parts(messages))
        in_tok = text_chars(system, messages) // CHARS_PER_TOKEN_EST + imgs
        return self.price(in_tok, self.settings.get("max_tokens", DEFAULT_MAX_TOKENS)) * RESERVATION_MARGIN

    def respond(self, system: str, messages: list[Message]) -> Reply:
        key = self.key(system, messages)
        row = self.cache.get(key)
        if row:
            return Reply(row["text"], row["thoughts"], json.loads(row["usage"]), 0.0, row["cost"], True,
                         row["model_version"], row["route"], json.loads(row["settings"]), row["latency"],
                         json.loads(row["response"]), key)
        worst = self.worst_case(system, messages)
        self.budget.reserve(worst)
        try:
            rep = self._call(system, messages)
            # Record the spend BEFORE releasing the reservation (and before the cache row), so a concurrent worker
            # always sees either the reservation or the spend; a crash in between over-counts, never under-counts.
            self.budget.record(key, self.model, rep.cost, rep.route)
            self.cache.put(key, self.model, rep.route, rep.settings,
                           {"system_sha256": hashlib.sha256(system.encode()).hexdigest(),
                            "messages": neutral(messages, keep_names=False)},
                           rep.raw, rep.text, rep.thoughts, rep.usage, rep.cost, rep.model_version, rep.latency_s)
        finally:
            self.budget.release(worst)
        rep.key = key
        rep.cost_original = rep.cost
        return rep

    def _call(self, system: str, messages: list[Message]) -> Reply:
        raise NotImplementedError
