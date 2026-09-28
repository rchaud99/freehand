"""The model registry: every entry parses; settings match the historical cache-key shape; any slug works."""
import pytest

from freehand.llm.registry import UnregisteredModelWarning, load_registry, parse_registry

EXPECTED = {"opus", "sonnet", "astra", "sol", "gpt55", "terra", "gpt54mini", "gpt54nano", "luna", "gpt5nano",
            "flash", "flash-genai", "kimi", "fake"}


def test_registry_has_every_historical_model():
    reg = load_registry()
    assert set(reg.ids()) >= EXPECTED
    assert not any("pro" in m.slug for m in reg.models.values() if "gemini" in m.slug)   # Flash is the top Gemini


def test_settings_have_the_historical_shape():
    reg = load_registry()
    # the exact settings dict the historical OpenRouter adapter hashed into every request key
    assert reg.resolve("opus").adapter_settings() == {"reasoning": {"max_tokens": 4000}, "max_tokens": 8000,
                                                      "pin_provider": "anthropic", "prompt_caching": True}
    assert reg.resolve("openai/gpt-6-astra").adapter_settings()["pin_provider"] == "openai"
    assert reg.resolve("kimi").adapter_settings()["pin_provider"] is None           # automatic routing
    assert reg.resolve("flash-genai").adapter_settings() == {"thinking_level": "high",
                                                             "media_resolution": "ultra_high", "max_tokens": 16000}
    for m in reg.models.values():
        if m.api == "openrouter":
            assert m.reasoning, f"{m.id}: reasoning must be forced on"
        assert m.price_in >= 0 and m.price_out >= 0


def test_unregistered_slug_gets_defaults_and_a_warning():
    reg = load_registry()
    with pytest.warns(UnregisteredModelWarning, match="not in configs/models.toml"):
        spec = reg.resolve("somevendor/new-model-9", lookup_price=False)
    assert spec.slug == "somevendor/new-model-9" and not spec.registered
    assert spec.reasoning == {"effort": "high"} and spec.provider is None and spec.output_mode == "page_mm"
    assert spec.price_source == "placeholder" and spec.price_in > 0
    assert spec.agent_name == "new-model-9"


def test_unknown_non_slug_is_an_error():
    with pytest.raises(KeyError, match="unknown model"):
        load_registry().resolve("gpt-9000")


def test_overrides_and_validation():
    reg = load_registry()
    o = reg.resolve("opus").with_overrides(reasoning={"effort": "medium"})
    assert o.adapter_settings()["reasoning"] == {"effort": "medium"}
    with pytest.raises(ValueError, match="cannot override"):
        reg.resolve("opus").with_overrides(slug="x/y")
    with pytest.raises(ValueError, match="unknown field"):
        parse_registry({"models": {"x": {"slug": "a/b", "colour": "red"}}})
    with pytest.raises(ValueError, match="output_mode"):
        parse_registry({"models": {"x": {"slug": "a/b", "output_mode": "pixels"}}})
