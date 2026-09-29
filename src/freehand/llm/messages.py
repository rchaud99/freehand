"""Provider-neutral messages and the request-cache key.

Messages:
    [{"role": "user" | "assistant",
      "parts": [{"text": str, "cache": bool} | {"png": bytes, "detail": "high" | "low", "name": str}]}]

`"cache": True` marks a prompt-caching breakpoint (Anthropic cache_control, sent through OpenRouter). Image `name`s are
for logs only and never part of the request or the key.

The cache key is sha256 of the canonical JSON of {provider, route, model, settings, system, messages-with-images-as-
sha256}. It is byte-for-byte the historical key, so requests made by the pilots replay from the merged cache for free.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

Message = dict[str, Any]


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def neutral(messages: list[Message], keep_names: bool = True) -> list[Message]:
    """Messages with images replaced by their sha256 (for the cache key and the logs)."""
    out = []
    for m in messages:
        parts = []
        for p in m["parts"]:
            if "png" in p:
                q = {"image_sha256": sha256_hex(p["png"]), "detail": p.get("detail", "high")}
                if keep_names:
                    q["name"] = p.get("name")
                parts.append(q)
            else:
                parts.append({"text": p["text"], "cache": bool(p.get("cache"))})
        out.append({"role": m["role"], "parts": parts})
    return out


def request_key(provider: str, route: str, model: str, settings: dict, system: str, messages: list[Message]) -> str:
    return canonical_hash(
        {
            "provider": provider,
            "route": route,
            "model": model,
            "settings": settings,
            "system": system,
            "messages": neutral(messages, keep_names=False),
        }
    )


def text_chars(system: str, messages: list[Message]) -> int:
    return len(system) + sum(len(p.get("text", "")) for m in messages for p in m["parts"])


def image_parts(messages: list[Message]):
    return [p for m in messages for p in m["parts"] if "png" in p]
