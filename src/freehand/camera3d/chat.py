"""Multi-turn tool-calling chat through OpenRouter, with the spend recorded in the shared ledger under a hard cap.

Unlike the plotter track's single-message turns, a Freehand A episode is one ongoing conversation: the model calls
`draw`, gets a tool result and a new photo, and calls again. Only the last KEEP_PHOTOS photos stay in the
conversation (older ones become a text placeholder), which bounds the cost; the state text logs every stroke.
Reasoning details are passed back with each assistant turn, as tool use with reasoning requires.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any

from freehand.llm.adapter import retry
from freehand.llm.errors import BudgetExceeded, ProviderError, TransientError
from freehand.llm.ledger import Budget
from freehand.llm.registry import ModelSpec

KEEP_PHOTOS = 3
IMAGE_TOKENS_EST = 1600
CHARS_PER_TOKEN_EST = 3
RESERVATION_MARGIN = 1.25


def image_part(png: bytes) -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64," + base64.standard_b64encode(png).decode()},
    }


class Conversation:
    """The message list of one episode, provider-neutral (OpenAI chat format, which OpenRouter translates)."""

    def __init__(self, system: str):
        self.system = system
        self.messages: list[dict[str, Any]] = []

    def user(self, text: str, png: bytes | None = None) -> None:
        content: list[dict] = [{"type": "text", "text": text}]
        if png is not None:
            content.append(image_part(png))
        self.messages.append({"role": "user", "content": content})

    def assistant(self, msg: dict) -> None:
        keep = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            keep["tool_calls"] = msg["tool_calls"]
        if msg.get("reasoning_details"):
            keep["reasoning_details"] = msg["reasoning_details"]
        self.messages.append(keep)

    def tool(self, call_id: str, text: str) -> None:
        self.messages.append({"role": "tool", "tool_call_id": call_id, "content": text})

    def request_messages(self, cache: bool) -> list[dict]:
        """The messages to send: photos beyond the last KEEP_PHOTOS replaced by a placeholder, and (for Anthropic)
        a prompt-cache breakpoint on the system prompt and the last user text."""
        n_img = sum(1 for m in self.messages if m["role"] == "user" for p in m["content"] if p["type"] == "image_url")
        drop = max(0, n_img - KEEP_PHOTOS)
        out: list[dict] = [{"role": "system", "content": [{"type": "text", "text": self.system}]}]
        for m in self.messages:
            if m["role"] != "user":
                out.append(m)
                continue
            content = []
            for p in m["content"]:
                if p["type"] == "image_url" and drop > 0:
                    drop -= 1
                    content.append({"type": "text", "text": "[older photo removed]"})
                else:
                    content.append(dict(p))
            out.append({"role": "user", "content": content})
        if cache:
            out[0]["content"][0]["cache_control"] = {"type": "ephemeral"}
            last = next(m for m in reversed(out) if m["role"] == "user")
            last["content"][0]["cache_control"] = {"type": "ephemeral"}
        return out

    def neutral(self) -> list[dict]:
        """The conversation with images as sha256 (for the log)."""
        out = []
        for m in self.messages:
            if m["role"] == "user":
                c = [
                    {
                        "image_sha256": hashlib.sha256(
                            base64.b64decode(p["image_url"]["url"].split(",", 1)[1])
                        ).hexdigest()
                    }
                    if p["type"] == "image_url"
                    else p
                    for p in m["content"]
                ]
                out.append({"role": "user", "content": c})
            else:
                out.append(m)
        return out


class ToolChat:
    """One model behind OpenRouter. `complete(conv, tools)` returns (message, usage, cost_usd, raw_response)."""

    def __init__(self, spec: ModelSpec, budget: Budget, run_id: str, episode_cap_usd: float):
        self.spec, self.budget, self.run_id = spec, budget, run_id
        self.episode_cap = float(episode_cap_usd)
        self.spent = 0.0  # this episode's recorded spend (the shared Budget holds the run's)

    @property
    def anthropic(self) -> bool:
        return self.spec.slug.startswith("anthropic/")

    def body(self, conv: Conversation, tools: list[dict]) -> dict:
        body: dict[str, Any] = {
            "model": self.spec.slug,
            "max_tokens": self.spec.max_tokens,
            "reasoning": self.spec.reasoning,
            "usage": {"include": True},
            "messages": conv.request_messages(cache=self.anthropic),
            "tools": tools,
            "tool_choice": "auto",
        }
        if not self.anthropic:
            body["parallel_tool_calls"] = False
        if self.spec.provider:
            body["provider"] = {"order": [self.spec.provider], "allow_fallbacks": False}
        return body

    def worst_case(self, body: dict) -> float:
        chars = sum(
            len(json.dumps({k: v for k, v in m.items() if k != "reasoning_details"}))
            for m in body["messages"]
            if "image_url" not in json.dumps(m)
        )
        n_img = sum(
            1 for m in body["messages"] if m["role"] == "user" for p in m["content"] if p.get("type") == "image_url"
        )
        in_tok = chars // CHARS_PER_TOKEN_EST + n_img * IMAGE_TOKENS_EST
        pin, pout = self.spec.prices
        return (in_tok * pin + self.spec.max_tokens * pout) / 1e6 * RESERVATION_MARGIN

    def post(self, body: dict) -> dict:
        import requests

        from freehand.llm.openrouter import (
            CHAT_URL,
            REQUEST_TIMEOUT_S,
            TRANSIENT_ERROR_CODES,
            TRANSIENT_HTTP,
            _auth_headers,
            _force_ipv4_once,
        )

        _force_ipv4_once()
        headers = _auth_headers()

        def go():
            try:
                r = requests.post(CHAT_URL, json=body, timeout=REQUEST_TIMEOUT_S, headers=headers)
            except requests.RequestException as e:
                raise TransientError(type(e).__name__) from None
            if r.status_code in TRANSIENT_HTTP:
                raise TransientError(f"HTTP {r.status_code}")
            try:
                j = r.json()
            except ValueError:
                raise ProviderError(f"openrouter HTTP {r.status_code}: non-JSON response") from None
            if r.status_code != 200 or "error" in j:
                err = j.get("error", {})
                if isinstance(err, dict) and err.get("code") in TRANSIENT_ERROR_CODES:
                    raise TransientError(str(err.get("code")))
                raise ProviderError(f"openrouter HTTP {r.status_code}: {str(err)[:400]}")
            return j

        try:
            return retry(go)
        except TransientError as e:
            raise ProviderError(f"openrouter: retries exhausted ({e})") from None

    def complete(self, conv: Conversation, tools: list[dict]) -> tuple[dict, dict, float, dict]:
        body = self.body(conv, tools)
        worst = self.worst_case(body)
        if self.spent + worst > self.episode_cap:
            raise BudgetExceeded(
                f"episode cap ${self.episode_cap:.2f}: spent ${self.spent:.4f} + this call up to ${worst:.4f}"
            )
        self.budget.reserve(worst)
        try:
            t0 = time.time()
            j = self.post(body)
            u = j.get("usage") or {}
            pin, pout = self.spec.prices
            cost = (
                float(u["cost"])
                if u.get("cost") is not None
                else ((u.get("prompt_tokens", 0) * pin + u.get("completion_tokens", 0) * pout) / 1e6)
            )
            key = hashlib.sha256(json.dumps(conv.neutral(), sort_keys=True).encode()).hexdigest()
            self.budget.record(key, self.spec.slug, cost, f"openrouter/{j.get('provider', '?')}")
            self.spent += cost
        finally:
            self.budget.release(worst)
        choices = j.get("choices") or [{}]
        msg = choices[0].get("message") or {}
        usage = {
            "input_tokens": u.get("prompt_tokens", 0),
            "cached_input_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
            "output_tokens": u.get("completion_tokens", 0),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0,
            "latency_s": round(time.time() - t0, 2),
            "provider": j.get("provider"),
            "finish_reason": choices[0].get("finish_reason"),
        }
        return msg, usage, cost, j
