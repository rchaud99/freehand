"""An offline model: a scripted policy through the same cache / budget / logging path as a real model.

Usage is invented from message lengths so the budget and logs are exercised. Its ledger entries are simulated
accounting units, not charges.
"""

from __future__ import annotations

from collections.abc import Callable

from freehand.llm.adapter import Adapter, Reply
from freehand.llm.messages import Message

Policy = Callable[[str, list[Message]], str]
FAKE_MODEL = "fake-llm"
FAKE_PRICES = (1.00, 5.00)
FAKE_REASONING_TOKENS = 200
FAKE_THOUGHTS = "fake reasoning: aiming at the open corners."


class FakeAdapter(Adapter):
    provider = "fake"

    def __init__(
        self,
        cache,
        budget,
        policy: Policy,
        max_tokens: int = 2000,
        salt: str = "",
        prices: tuple[float, float] = FAKE_PRICES,
    ):
        super().__init__(FAKE_MODEL, cache, budget, prices, max_tokens=max_tokens, salt=salt)
        self.policy = policy

    def _call(self, system: str, messages: list[Message]) -> Reply:
        out = self.policy(system, messages)
        n_in = (len(system) + sum(len(p.get("text", "")) for m in messages for p in m["parts"])) // 4 + sum(
            1300 if p.get("detail", "high") == "high" else 320 for m in messages for p in m["parts"] if "png" in p
        )
        usage = {
            "input_tokens": n_in,
            "cached_input_tokens": 0,
            "output_tokens": len(out) // 4,
            "reasoning_tokens": FAKE_REASONING_TOKENS,
        }
        cost = self.price(n_in, usage["output_tokens"] + FAKE_REASONING_TOKENS)
        return Reply(
            out, FAKE_THOUGHTS, usage, cost, cost, False, FAKE_MODEL, "fake", dict(self.settings), 0.0, {"text": out}
        )
