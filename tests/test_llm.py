"""Request keys, the cache, the budget cap and the key loading rules."""
import pytest

from freehand.llm import Budget, BudgetExceeded, FakeAdapter, Ledger, RequestCache
from freehand.llm import secrets as S
from freehand.llm.messages import request_key

MSG = [{"role": "user", "parts": [{"png": b"\x89PNG fake", "detail": "high", "name": "t001.png"}, {"text": "hi"}]}]


def test_image_names_are_not_part_of_the_key():
    renamed = [{"role": "user", "parts": [{**MSG[0]["parts"][0], "name": "other.png"}, MSG[0]["parts"][1]]}]
    k = request_key("openrouter", "openrouter/anthropic", "m", {"a": 1}, "sys", MSG)
    assert k == request_key("openrouter", "openrouter/anthropic", "m", {"a": 1}, "sys", renamed)
    assert k != request_key("openrouter", "openrouter/anthropic", "m", {"a": 2}, "sys", MSG)


def test_budget_cap_refuses_before_calling(tmp_path):
    ledger = Ledger(tmp_path / "l.sqlite")
    budget = Budget(ledger, 0.001, "tiny")
    calls = []
    a = FakeAdapter(RequestCache(tmp_path / "c.sqlite"), budget, lambda *_: calls.append(1) or "{}")
    with pytest.raises(BudgetExceeded, match=r"cap \$0.00 \[tiny\]"):
        a.respond("system " * 200, MSG)
    assert calls == [] and ledger.spent(tag="tiny") == 0 and budget.reserved == 0


def test_ledger_by_tag_and_run(tmp_path):
    ledger = Ledger(tmp_path / "l.sqlite")
    ledger.record("k1", "m", 0.5, "a", run_id="r1")
    ledger.record("k2", "m", 0.25, "b", run_id="r1")
    assert ledger.spent(tag="a") == 0.5 and ledger.spent(run_id="r1") == 0.75
    assert ledger.by_tag() == [("a", 1, 0.5), ("b", 1, 0.25)]


def test_keys_come_only_from_env_or_repo_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "configs").mkdir()
    monkeypatch.setattr(S.paths, "repo_root", lambda: tmp_path)
    with pytest.raises(S.MissingKeyError) as e:
        S.get_key("OPENROUTER_API_KEY")
    assert "sk-" not in str(e.value)
    (tmp_path / ".env").write_text("OTHER=1\nOPENROUTER_API_KEY='sk-or-test'\n")
    assert S.get_key("OPENROUTER_API_KEY") == "sk-or-test"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    assert S.get_key("OPENROUTER_API_KEY") == "sk-or-env"


def test_cache_hit_needs_no_key(tmp_path, monkeypatch):
    """A cached request replays without any credentials (historical requests replay free)."""
    from freehand.llm.openrouter import OpenRouterAdapter
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(S, "get_key", lambda name: (_ for _ in ()).throw(AssertionError("key read")))
    cache = RequestCache(tmp_path / "c.sqlite")
    a = OpenRouterAdapter("x/y", cache, Budget(Ledger(tmp_path / "l.sqlite"), 1.0, "t"), (1.0, 1.0),
                          reasoning={"effort": "high"}, max_tokens=100, pin_provider=None)
    key = a.key("sys", MSG)
    cache.put(key, "x/y", "openrouter/auto", a.settings, {}, {}, "{}", None, {}, 0.01, "x/y", 1.0)
    r = a.respond("sys", MSG)
    assert r.cached and r.cost == 0 and r.cost_original == 0.01
