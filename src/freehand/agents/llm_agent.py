"""The LLM agent and its resume wrapper.

The agent itself is thin: the arm (agents/arms.py) decides what goes into the request, the episode loop assembles it,
and the adapter (llm/) sends it through the cache and the budget.
"""

from __future__ import annotations

from freehand.agents.base import Agent, Reply
from freehand.llm.adapter import Adapter


class LLMAgent(Agent):
    is_model = True

    def __init__(self, adapter: Adapter, name: str | None = None):
        self.adapter = adapter
        self.name = name or adapter.model.split("/")[-1]

    def act(self, obs: dict) -> Reply:
        r = self.adapter.respond(obs["system"], obs["messages"])
        return {
            "text": r.text,
            "thoughts": r.thoughts,
            "usage": r.usage,
            "cost": r.cost,
            "cost_original": r.cost_original,
            "cached": r.cached,
            "route": r.route,
            "settings": r.settings,
            "latency_s": r.latency_s,
            "model_version": r.model_version,
            "cache_key": r.key,
        }


class ResumeAgent(Agent):
    """Resumes a cut-short episode: returns the replies logged for it, in order and at no cost, then hands over to
    the live agent. The simulation is deterministic given the replies, so the page state at the hand-over is the
    logged one. (Replaying from the request cache is not enough: episodes with identical early requests that ran
    concurrently each made their own call, and the cache keeps only one reply per request.)"""

    is_model = True

    def __init__(self, live: Agent | None, logged_replies: list[Reply], name: str | None = None, on_request=None):
        self.live = live
        self.name = name or (live.name if live is not None else "replay")
        self.logged = list(logged_replies)
        self.replayed = 0
        self.on_request = on_request  # optional callback(system, messages): prompt-parity checks

    def act(self, obs: dict) -> Reply:
        if self.on_request is not None:
            self.on_request(obs["system"], obs["messages"])
        if self.replayed < len(self.logged):
            r = dict(self.logged[self.replayed], cost=0.0, cached=True, replayed=True)
            self.replayed += 1
            return r
        if self.live is None:
            raise RuntimeError("replay exhausted: no live agent to hand over to")
        return self.live.act(obs)
