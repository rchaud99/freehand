"""OpenRouter: chat completions with images, prompt caching, forced reasoning, provider pinning; account checks."""
from __future__ import annotations

import base64
import os
import socket
import time
from typing import Any

from freehand.llm import secrets
from freehand.llm.adapter import Adapter, Reply, retry
from freehand.llm.errors import ProviderError, TransientError
from freehand.llm.messages import Message

API = "https://openrouter.ai/api/v1"
CHAT_URL = f"{API}/chat/completions"
REQUEST_TIMEOUT_S = 600
ACCOUNT_TIMEOUT_S = 30
TRANSIENT_HTTP = (408, 429, 500, 502, 503, 504)
TRANSIENT_ERROR_CODES = (429, 502, 503)
FORCE_IPV4_ENV = "FREEHAND_FORCE_IPV4"
_ipv4_forced = False


def _force_ipv4_once() -> None:
    """openrouter.ai's IPv6 routes intermittently failed from the development network: use IPv4 unless
    FREEHAND_FORCE_IPV4=0. (A process-wide urllib3 setting; applied only when a live call is made.)"""
    global _ipv4_forced
    if _ipv4_forced or os.environ.get(FORCE_IPV4_ENV, "1") == "0":
        return
    import urllib3.util.connection
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
    _ipv4_forced = True


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {secrets.get_key(secrets.OPENROUTER_KEY)}", "Content-Type": "application/json"}


class OpenRouterAdapter(Adapter):
    provider = "openrouter"

    def __init__(self, model: str, cache, budget, prices, reasoning: dict, max_tokens: int,
                 pin_provider: str | None):
        # The settings dict is part of the request key; its shape is the historical one.
        super().__init__(model, cache, budget, prices, reasoning=reasoning, max_tokens=max_tokens,
                         pin_provider=pin_provider, prompt_caching=True)

    @property
    def route(self) -> str:
        return f"openrouter/{self.settings['pin_provider'] or 'auto'}"

    @staticmethod
    def _content(parts: list[dict]) -> list[dict]:
        out = []
        for p in parts:
            if "png" in p:
                out.append({"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.standard_b64encode(p["png"]).decode()}})
            else:
                c: dict[str, Any] = {"type": "text", "text": p["text"]}
                if p.get("cache"):
                    c["cache_control"] = {"type": "ephemeral"}
                out.append(c)
        return out

    def body(self, system: str, messages: list[Message]) -> dict:
        msgs = [{"role": "system", "content": [{"type": "text", "text": system,
                                                "cache_control": {"type": "ephemeral"}}]}]
        msgs += [{"role": m["role"], "content": self._content(m["parts"])} for m in messages]
        body = {"model": self.model, "max_tokens": self.settings["max_tokens"],
                "reasoning": self.settings["reasoning"], "usage": {"include": True}, "messages": msgs}
        if self.settings.get("pin_provider"):
            body["provider"] = {"order": [self.settings["pin_provider"]], "allow_fallbacks": False}
        return body

    def _call(self, system: str, messages: list[Message]) -> Reply:
        import requests
        _force_ipv4_once()
        body = self.body(system, messages)
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
                raise ProviderError(f"openrouter HTTP {r.status_code}: {str(err)[:300]}")
            return j

        t0 = time.time()
        try:
            j = retry(go)
        except TransientError as e:
            raise ProviderError(f"openrouter: retries exhausted ({e})") from None
        dt = time.time() - t0
        msg = j["choices"][0]["message"]
        u = j.get("usage", {}) or {}
        rt = ((u.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0
        pd = u.get("prompt_tokens_details") or {}
        usage = {"input_tokens": u.get("prompt_tokens", 0), "cached_input_tokens": pd.get("cached_tokens", 0) or 0,
                 "cache_write_tokens": pd.get("cache_write_tokens", 0) or 0,
                 "output_tokens": (u.get("completion_tokens", 0) or 0) - rt, "reasoning_tokens": rt,
                 "openrouter_cost": u.get("cost")}
        list_cost = self.price(usage["input_tokens"], usage["output_tokens"] + rt)
        usage["list_price_cost_uncached"] = round(list_cost, 6)
        cost = float(u["cost"]) if u.get("cost") is not None else list_cost
        return Reply(msg.get("content") or "", msg.get("reasoning") or None, usage, cost, cost, False,
                     j.get("model", self.model), f"openrouter/{j.get('provider', '?')}", dict(self.settings),
                     round(dt, 2), j)


# ---------------------------------------------------------------- account checks (free endpoints)
def balance() -> float:
    """Remaining OpenRouter account credit in USD (total credits - total usage)."""
    import requests
    _force_ipv4_once()
    r = requests.get(f"{API}/credits", timeout=ACCOUNT_TIMEOUT_S, headers=_auth_headers())
    r.raise_for_status()
    d = r.json()["data"]
    return round(float(d["total_credits"]) - float(d["total_usage"]), 2)


def key_info() -> dict:
    """The API key's own limit and usage (`limit_remaining` is None when the key has no limit). A key's lifetime
    limit is separate from the account balance: it cut the informed/stateless pilots short (PREREGISTRATION
    Addendum 11)."""
    import requests
    _force_ipv4_once()
    r = requests.get(f"{API}/key", timeout=ACCOUNT_TIMEOUT_S, headers=_auth_headers())
    r.raise_for_status()
    return r.json().get("data", {})


def spendable() -> tuple[float, str]:
    """(USD that can still be spent, explanation): min(account balance, key limit remaining)."""
    bal = balance()
    try:
        info = key_info()
    except Exception as e:  # the key endpoint is informational; the balance is authoritative
        return bal, f"balance ${bal:.2f} (key limit unknown: {type(e).__name__})"
    rem = info.get("limit_remaining")
    if rem is None:
        return bal, f"balance ${bal:.2f}; key has no limit"
    return min(bal, float(rem)), f"balance ${bal:.2f}; key limit remaining ${float(rem):.2f}"


def model_pricing(slug: str) -> tuple[float, float] | None:
    """(input, output) USD per million tokens from the public models API, or None if unknown/unreachable."""
    import requests
    try:
        r = requests.get(f"{API}/models", timeout=ACCOUNT_TIMEOUT_S)
        r.raise_for_status()
    except Exception:
        return None
    for m in r.json().get("data", []):
        if m.get("id") == slug:
            p = m.get("pricing", {})
            try:
                return float(p["prompt"]) * 1e6, float(p["completion"]) * 1e6
            except (KeyError, TypeError, ValueError):
                return None
    return None
