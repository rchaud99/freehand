"""Ported from the historical tests/test_model_workflow.py (6 tests), onto the generic runner and llm layer."""

import json
from unittest.mock import patch

import pytest

from freehand.agents.arms import Arm
from freehand.agents.llm_agent import LLMAgent
from freehand.agents.reference import make_reference
from freehand.episode import EpisodeConfig, MemorySink, run_episode
from freehand.experiments import Runner, RunOptions, parse_experiment
from freehand.llm import Budget, BudgetExceeded, EpisodeBudget, FakeAdapter, Ledger, RequestCache
from freehand.perturbations import build
from freehand.sim import make_page


def _plan_config(seeds, families, feedback, disclosures):
    arms = {
        f"{fb}_{d}": {"preset": "study_image" if fb == "image" else "study_image_numeric", "disclosure": d}
        for fb in feedback
        for d in disclosures
    }
    return {
        "name": "plan",
        "budget": {"tag": "t", "cap_usd": 0.0},
        "order": "shuffle",
        "shuffle_seed": 281026,
        "models": ["fake"],
        "arms": arms,
        "blocks": [{"suite": "legacy-model-study-v0", "seeds": seeds, "perturbations": families, "arms": list(arms)}],
    }


def test_plan_preserves_every_arm_and_is_reproducible():
    d = _plan_config([4001, 4002], ["identity", "arx"], ["image", "image_numeric"], ["silent", "alerted"])
    a = Runner(parse_experiment(d)).ordered_cells()
    b = Runner(parse_experiment(d)).ordered_cells()
    assert len(a) == 16
    assert [c.id for c in a] == [c.id for c in b]
    assert len({c.id for c in a}) == 16


def test_plan_only_never_opens_store_or_credentials():
    exp = parse_experiment(_plan_config([4001], ["identity"], ["image_numeric"], ["silent"]))
    with (
        patch("freehand.experiments.runner.RequestCache", side_effect=AssertionError("store must stay unopened")),
        patch("freehand.experiments.runner.Ledger", side_effect=AssertionError("ledger must stay unopened")),
        patch("freehand.llm.secrets.get_key", side_effect=AssertionError("no credentials")),
    ):
        plan = Runner(exp, RunOptions(dry_run=True)).run()
    assert plan["cells"] == 1 and plan["model_cells"] == 1


def _store(tmp_path, cap=1.0):
    ledger = Ledger(tmp_path / "ledger.sqlite")
    return RequestCache(tmp_path / "cache.sqlite"), ledger, Budget(ledger, cap, "test")


def test_spend_recorded_before_reservation_released(tmp_path):
    cache, _ledger, budget = _store(tmp_path)
    adapter = FakeAdapter(cache, budget, lambda *_: "{}", max_tokens=10)
    observed = []
    original = budget.record

    def recording(*args, **kwargs):
        observed.append(budget.reserved)
        return original(*args, **kwargs)

    with patch.object(budget, "record", side_effect=recording):
        adapter.respond("test", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert observed[0] > 0
    assert budget.reserved == pytest.approx(0)
    spent = budget.spent()
    reply = adapter.respond("test", [{"role": "user", "parts": [{"text": "hi"}]}])
    assert reply.cached and reply.cost == 0
    assert budget.spent() == spent


def test_exception_releases_reservation(tmp_path):
    cache, _ledger, budget = _store(tmp_path)
    adapter = FakeAdapter(cache, budget, lambda *_: "{}", max_tokens=10)
    with (
        patch.object(adapter, "_call", side_effect=RuntimeError("offline synthetic failure")),
        pytest.raises(RuntimeError),
    ):
        adapter.respond("test", [])
    assert budget.reserved == pytest.approx(0)


def test_episode_budget_enforced_before_call(tmp_path):
    _cache, _ledger, budget = _store(tmp_path)
    episode = EpisodeBudget(budget, 0.01)
    with pytest.raises(BudgetExceeded):
        episode.reserve(0.02)
    assert budget.reserved == 0


def test_feedback_does_not_disclose_family_or_change(tmp_path):
    captured = []

    def policy(system, messages):
        txt = " ".join(p.get("text", "") for p in messages[-1]["parts"])
        feedback = json.loads(txt.split("NUMERIC_FEEDBACK_JSON: ")[-1])
        assert set(feedback) == {"target", "history", "region"}
        captured.append(feedback)
        return json.dumps({"strokes": [feedback["target"]]})

    cache, _ledger, budget = _store(tmp_path)
    agent = LLMAgent(FakeAdapter(cache, budget, policy, max_tokens=1000))
    cfg = EpisodeConfig(
        seed=2001,
        squares=make_page(2001, 2),
        perturbation=build("none", {"type": "none"}, 2001),
        perturb_after=1,
        arm=Arm("n", feedback="image_numeric"),
    )
    ep = run_episode(agent, cfg, MemorySink())
    assert ep["complete"], ep["stop"]
    assert captured and captured[0]["history"] == []
    assert make_reference("oracle", cfg.perturbation) is not None
