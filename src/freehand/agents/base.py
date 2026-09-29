"""The agent interface.

`act(obs)` gets
    obs["system"], obs["messages"]   what a model would be sent (LLM agents use these)
    obs["priv"]                      privileged ground truth for reference agents only: open_ends, map, H, H_old,
                                     strokes, scenario, scen_on, next_stroke, perturb_stroke
and returns a reply dict: text (the JSON action), thoughts, usage, cost, cost_original, cached, route, settings,
latency_s, model_version (+ cache_key for models). Reference agents may also implement `observe(cmd, ink_ends)`,
called after every executed stroke with the TRUE ink ends (they add their own measurement noise).
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

Reply = dict[str, Any]


class Agent:
    name = "?"
    is_model = False

    def act(self, obs: dict) -> Reply:
        raise NotImplementedError


def code_reply(cmd, note: str, memory: str = "") -> Reply:
    """A reference agent's reply, in the same JSON action format a model uses (commands rounded to 0.01 mm)."""
    return {
        "text": json.dumps({"action": "draw", "strokes": [np.round(cmd, 2).tolist()], "note": note, "memory": memory}),
        "thoughts": None,
        "usage": {},
        "cost": 0.0,
        "cost_original": 0.0,
        "cached": False,
        "route": "code",
        "settings": {},
        "latency_s": 0.0,
        "model_version": "code",
    }
