"""The model registry (configs/models.toml) and adapter construction.

`resolve("opus")` returns the registered spec; `resolve("vendor/some-model")` also works for any OpenRouter slug that
is not registered: it gets the registry [defaults], prices from the OpenRouter models API (conservative placeholders
if unreachable) and a warning. Per-experiment overrides (reasoning, max_tokens, provider, output_mode) are applied
with `spec.with_overrides(...)`.
"""

from __future__ import annotations

import tomllib
import warnings
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from freehand import paths
from freehand.llm.adapter import Adapter
from freehand.llm.fake import FakeAdapter, Policy

APIS = ("openrouter", "google-genai", "fake")
OUTPUT_MODES = ("page_mm", "crop_px", "auto")
OUTPUT_MODE_ALIASES = {"mm": "page_mm"}
OVERRIDABLE = ("reasoning", "max_tokens", "provider", "output_mode", "settings", "price_in", "price_out")


class UnregisteredModelWarning(UserWarning):
    pass


def normalize_output_mode(mode: str) -> str:
    mode = OUTPUT_MODE_ALIASES.get(mode, mode)
    if mode not in OUTPUT_MODES:
        raise ValueError(f"output_mode must be one of {OUTPUT_MODES} (got {mode!r})")
    return mode


@dataclass(frozen=True)
class ModelSpec:
    id: str
    slug: str
    display: str = ""
    api: str = "openrouter"
    provider: str | None = None
    reasoning: dict = field(default_factory=dict)
    max_tokens: int = 8000
    price_in: float = 0.0
    price_out: float = 0.0
    output_mode: str = "page_mm"
    settings: dict = field(default_factory=dict)
    added: str = ""
    notes: str = ""
    registered: bool = True
    price_source: str = "registry"

    def __post_init__(self):
        if self.api not in APIS:
            raise ValueError(f"model {self.id}: api must be one of {APIS}")
        object.__setattr__(self, "output_mode", normalize_output_mode(self.output_mode))
        if self.max_tokens <= 0:
            raise ValueError(f"model {self.id}: max_tokens must be > 0")
        if self.price_in < 0 or self.price_out < 0:
            raise ValueError(f"model {self.id}: prices must be >= 0")

    @property
    def agent_name(self) -> str:
        """The name episodes are filed under (the slug after the vendor, as in the historical runs)."""
        return self.slug.split("/")[-1]

    @property
    def prices(self) -> tuple[float, float]:
        return (self.price_in, self.price_out)

    def with_overrides(self, **overrides: Any) -> ModelSpec:
        bad = set(overrides) - set(OVERRIDABLE)
        if bad:
            raise ValueError(f"cannot override {sorted(bad)} for model {self.id}; overridable: {OVERRIDABLE}")
        return replace(self, **overrides) if overrides else self

    def adapter_settings(self) -> dict:
        """The settings dict the adapter uses (part of every request's cache key)."""
        if self.api == "openrouter":
            return {
                "reasoning": self.reasoning,
                "max_tokens": self.max_tokens,
                "pin_provider": self.provider,
                "prompt_caching": True,
            }
        if self.api == "google-genai":
            return {
                "thinking_level": self.settings.get("thinking_level", "high"),
                "media_resolution": self.settings.get("media_resolution", "ultra_high"),
                "max_tokens": self.max_tokens,
            }
        return {"max_tokens": self.max_tokens}

    def to_manifest(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "api": self.api,
            "provider": self.provider or "auto",
            "reasoning": self.reasoning,
            "max_tokens": self.max_tokens,
            "settings": self.adapter_settings(),
            "prices_usd_per_mtok": {"input": self.price_in, "output": self.price_out, "source": self.price_source},
            "output_mode": self.output_mode,
            "registered": self.registered,
        }


@dataclass(frozen=True)
class Registry:
    models: dict[str, ModelSpec]
    defaults: dict[str, Any]
    path: Path | None = None

    def ids(self) -> list[str]:
        return list(self.models)

    def by_slug(self, slug: str) -> ModelSpec | None:
        return next((m for m in self.models.values() if m.slug == slug), None)

    def resolve(self, name: str, lookup_price: bool = True) -> ModelSpec:
        if name in self.models:
            return self.models[name]
        m = self.by_slug(name)
        if m is not None:
            return m
        if "/" not in name:
            raise KeyError(
                f"unknown model {name!r}: not a registered id ({', '.join(self.models)}) and not an "
                "OpenRouter slug (vendor/model)"
            )
        return self.unregistered(name, lookup_price)

    def unregistered(self, slug: str, lookup_price: bool = True) -> ModelSpec:
        d = self.defaults
        prices, source = None, "placeholder"
        if lookup_price:
            from freehand.llm.openrouter import model_pricing

            prices = model_pricing(slug)
            source = "openrouter-models-api" if prices else "placeholder"
        pin, pout = prices or (float(d.get("price_in", 15.0)), float(d.get("price_out", 75.0)))
        warnings.warn(
            f"{slug} is not in configs/models.toml: using defaults (reasoning {d.get('reasoning')}, "
            f"max_tokens {d.get('max_tokens')}, automatic provider routing, output_mode "
            f"{d.get('output_mode')}) and prices ${pin:.2f}/${pout:.2f} per Mtok ({source}). "
            "Register it to pin these.",
            UnregisteredModelWarning,
            stacklevel=2,
        )
        return ModelSpec(
            id=slug.replace("/", "_"),
            slug=slug,
            display=slug,
            api=d.get("api", "openrouter"),
            provider=None,
            reasoning=dict(d.get("reasoning", {"effort": "high"})),
            max_tokens=int(d.get("max_tokens", 8000)),
            price_in=pin,
            price_out=pout,
            output_mode=d.get("output_mode", "page_mm"),
            registered=False,
            price_source=source,
            notes="unregistered",
        )


def parse_registry(data: dict, path: Path | None = None) -> Registry:
    defaults = dict(data.get("defaults", {}))
    models = {}
    for mid, m in (data.get("models") or {}).items():
        unknown = set(m) - {
            "slug",
            "display",
            "api",
            "provider",
            "reasoning",
            "max_tokens",
            "price_in",
            "price_out",
            "output_mode",
            "settings",
            "added",
            "notes",
        }
        if unknown:
            raise ValueError(f"models.toml [{mid}]: unknown field(s) {sorted(unknown)}")
        if "slug" not in m:
            raise ValueError(f"models.toml [{mid}]: missing slug")
        api = m.get("api", defaults.get("api", "openrouter"))
        if api != "fake" and not {"price_in", "price_out"} <= set(m):
            raise ValueError(
                f"models.toml [{mid}]: price_in and price_out ($ per million tokens) are required; "
                "budgets reserve and record spend at these prices"
            )
        models[mid] = ModelSpec(
            id=mid,
            slug=m["slug"],
            display=m.get("display", m["slug"]),
            api=api,
            provider=m.get("provider"),
            reasoning=dict(m.get("reasoning", defaults.get("reasoning", {})) if api == "openrouter" else {}),
            max_tokens=int(m.get("max_tokens", defaults.get("max_tokens", 8000))),
            price_in=float(m.get("price_in", 0.0)),
            price_out=float(m.get("price_out", 0.0)),
            output_mode=m.get("output_mode", defaults.get("output_mode", "page_mm")),
            settings=dict(m.get("settings", {})),
            added=m.get("added", ""),
            notes=m.get("notes", ""),
        )
    return Registry(models, defaults, path)


@lru_cache(maxsize=4)
def _load(path: str) -> Registry:
    with open(path, "rb") as f:
        return parse_registry(tomllib.load(f), Path(path))


def load_registry(path: str | Path | None = None) -> Registry:
    return _load(str(Path(path) if path else paths.models_file()))


def make_adapter(spec: ModelSpec, cache, budget, policy: Policy | None = None, salt: str = "") -> Adapter:
    """An adapter for `spec` (settings from the spec; the key is read lazily on the first live call)."""
    if spec.api == "openrouter":
        from freehand.llm.openrouter import OpenRouterAdapter

        return OpenRouterAdapter(
            spec.slug,
            cache,
            budget,
            spec.prices,
            reasoning=spec.reasoning,
            max_tokens=spec.max_tokens,
            pin_provider=spec.provider,
        )
    if spec.api == "google-genai":
        from freehand.llm.genai import GeminiDirectAdapter

        s = spec.adapter_settings()
        return GeminiDirectAdapter(
            spec.slug,
            cache,
            budget,
            spec.prices,
            thinking_level=s["thinking_level"],
            media_resolution=s["media_resolution"],
            max_tokens=spec.max_tokens,
        )
    if spec.api == "fake":
        if policy is None:
            raise ValueError("the fake model needs a policy")
        return FakeAdapter(cache, budget, policy, max_tokens=spec.max_tokens, salt=salt, prices=spec.prices)
    raise ValueError(spec.api)
