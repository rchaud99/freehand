"""The historical direct-Gemini route (google-genai SDK).

Every historical Gemini 3.8 Flash call went through this route, so it is kept for exact cache replays and for
reproducing those experiments. New runs use OpenRouter (`flash` in configs/models.toml). The SDK and GEMINI_API_KEY
are needed only for live calls: `pip install -e .[genai]`.
"""

from __future__ import annotations

import time

from freehand.llm import secrets
from freehand.llm.adapter import Adapter, Reply, retry
from freehand.llm.errors import ProviderError, TransientError
from freehand.llm.messages import Message

GEMINI_CACHED_FRACTION = 0.25  # cached input priced at 25% of input (an assumption, conservative)
TRANSIENT_CODES = (408, 429, 500, 502, 503, 504)
HTTP_TIMEOUT_MS = 300_000


class GeminiDirectAdapter(Adapter):
    provider = "google-genai"

    def __init__(
        self,
        model: str,
        cache,
        budget,
        prices,
        thinking_level: str = "medium",
        media_resolution: str = "ultra_high",
        max_tokens: int = 8000,
    ):
        super().__init__(
            model,
            cache,
            budget,
            prices,
            thinking_level=thinking_level,
            media_resolution=media_resolution,
            max_tokens=max_tokens,
        )
        self._client = None
        self._types = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError as e:
                raise ProviderError("the direct Gemini route needs `pip install -e .[genai]`") from e
            self._types = types
            self._client = genai.Client(
                api_key=secrets.get_key(secrets.GEMINI_KEY), http_options=types.HttpOptions(timeout=HTTP_TIMEOUT_MS)
            )
        return self._client, self._types

    def _part(self, p, types):
        if "png" in p:
            level = self.settings["media_resolution"] if p.get("detail", "high") == "high" else "low"
            return types.Part(
                inline_data=types.Blob(data=p["png"], mime_type="image/png"),
                media_resolution=types.PartMediaResolution(
                    level=types.PartMediaResolutionLevel(f"MEDIA_RESOLUTION_{level.upper()}")
                ),
            )
        return types.Part(text=p["text"])

    def _call(self, system: str, messages: list[Message]) -> Reply:
        client, types = self._ensure_client()
        from google.genai import errors

        contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model", parts=[self._part(p, types) for p in m["parts"]]
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self.settings["max_tokens"],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel(self.settings["thinking_level"].upper()), include_thoughts=True
            ),
        )

        def go():
            try:
                return client.models.generate_content(model=self.model, config=config, contents=contents)
            except errors.APIError as e:
                if e.code in TRANSIENT_CODES:
                    raise TransientError(str(e.code)) from None
                raise ProviderError(f"gemini: {e}") from None
            except Exception as e:
                if any(k in (str(e) + type(e).__name__).lower() for k in ("timeout", "timed out", "connect")):
                    raise TransientError(type(e).__name__) from None
                raise

        t0 = time.time()
        try:
            r = retry(go)
        except TransientError as e:
            raise ProviderError(f"gemini: retries exhausted ({e})") from None
        dt = time.time() - t0
        cand = r.candidates[0] if r.candidates else None
        ps = (cand.content.parts or []) if cand and cand.content else []
        out = "".join(p.text for p in ps if p.text and not p.thought)
        th = "".join(p.text for p in ps if p.text and p.thought) or None
        m = r.usage_metadata
        cached = m.cached_content_token_count or 0
        usage = {
            "input_tokens": m.prompt_token_count or 0,
            "cached_input_tokens": cached,
            "output_tokens": m.candidates_token_count or 0,
            "reasoning_tokens": m.thoughts_token_count or 0,
        }
        pin, pout = self.prices
        cost = (
            (usage["input_tokens"] - cached) * pin
            + cached * pin * GEMINI_CACHED_FRACTION
            + (usage["output_tokens"] + usage["reasoning_tokens"]) * pout
        ) / 1e6
        raw = r.model_dump(mode="json", exclude_none=True, exclude={"sdk_http_response", "parsed"})
        return Reply(
            out,
            th,
            usage,
            cost,
            cost,
            False,
            r.model_version or self.model,
            self.provider,
            dict(self.settings),
            round(dt, 2),
            raw,
        )
