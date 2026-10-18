"""Freehand A agents. Each turn an agent sees the photo (and, for code references, privileged truth) and returns a
Decision: one stroke plus its belief about the camera (the four page points at the photo's corners).

ToolModel   a model behind OpenRouter, acting through the `draw` tool (one ongoing conversation)
Oracle      knows the camera
Estimator   the ideal learner: re-measures its own marks in the current photo every turn (1 px noise) and fits the
            camera from commanded ends (similarity from 1 stroke, affine from 2, homography from 3+), starting from a
            generic prior; the floor a model is compared with
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from freehand.agents.reference.camera import fit_mm_to_px
from freehand.camera3d.belief import corners_from_H
from freehand.camera3d.chat import Conversation, ToolChat
from freehand.camera3d.env import WORK_AREA, World
from freehand.camera3d.pose import FRAME, project
from freehand.camera3d.prompt import CORNERS, DRAW_TOOL, first_message, phrase, state_text, system_prompt
from freehand.seeding import AGENT_SEEDS

MAX_REPROMPTS = 2
PIX_SD = 1.0
PRIOR_PX_PER_MM = 5.0


@dataclass
class Decision:
    start: list | None
    end: list | None
    belief: list | None  # 4 x [x, y] page mm, CORNERS order; None if missing or malformed
    note: str = ""
    reasoning: str | None = None
    cost: float = 0.0
    usage: list = field(default_factory=list)  # one entry per call this turn
    problems: list = field(default_factory=list)  # re-prompts and malformed arguments this turn
    raw: list = field(default_factory=list)  # the raw assistant messages of this turn


def _point(v) -> list | None:
    try:
        x, y = (float(a) for a in v)
    except (TypeError, ValueError):
        return None
    return [x, y] if np.isfinite([x, y]).all() else None


def parse_draw(arguments: str) -> tuple[list | None, list | None, list | None, str, str | None]:
    """(start, end, belief, note, problem) from a `draw` call's JSON arguments."""
    try:
        a = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
    except (ValueError, TypeError):
        return None, None, None, "", "arguments are not valid JSON"
    if not isinstance(a, dict):
        return None, None, None, "", "arguments are not an object"
    start, end = _point(a.get("start")), _point(a.get("end"))
    est = a.get("camera_estimate")
    belief = None
    if isinstance(est, dict):
        pts = [_point(est.get(c)) for c in CORNERS]
        belief = pts if all(p is not None for p in pts) else None
    note = str(a.get("note", ""))[:2000]
    if start is None or end is None:
        return None, None, belief, note, "start and end must each be [x, y] numbers in page mm"
    return start, end, belief, note, None


class ToolModel:
    name = "model"
    is_model = True

    def __init__(self, chat: ToolChat, n_squares: int, cap_strokes: int):
        self.chat = chat
        self.name = chat.spec.agent_name
        self.conv = Conversation(system_prompt(n_squares, cap_strokes))
        self.pending: list[str] = []  # tool-call ids of the last assistant message, the executed one first

    def act(self, world: World, png: bytes, last) -> Decision:
        if last is None:
            self.conv.user(first_message(), png)
        else:
            self.conv.tool(self.pending[0], phrase("tool_drawn", stroke=last.stroke))
            for cid in self.pending[1:]:
                self.conv.tool(cid, phrase("tool_ignored"))
            self.conv.user(state_text(world, last), png)
        self.pending = []
        d = Decision(None, None, None)
        for _ in range(1 + MAX_REPROMPTS):
            msg, usage, cost, _raw = self.chat.complete(self.conv, [DRAW_TOOL])
            self.conv.assistant(msg)
            d.cost += cost
            d.usage.append(usage)
            d.raw.append({k: msg.get(k) for k in ("content", "tool_calls")})
            d.reasoning = "\n".join(x for x in (d.reasoning, msg.get("reasoning")) if x) or None
            calls = [c for c in (msg.get("tool_calls") or []) if c.get("function", {}).get("name") == "draw"]
            others = [c for c in (msg.get("tool_calls") or []) if c not in calls]
            for c in others:
                self.conv.tool(c["id"], phrase("tool_unknown"))
            if not calls:
                d.problems.append("no draw call")
                self.conv.user(phrase("reprompt_no_call"))
                continue
            start, end, belief, note, problem = parse_draw(calls[0]["function"].get("arguments", "{}"))
            if problem:
                d.problems.append(problem)
                for c in calls:
                    self.conv.tool(c["id"], phrase("tool_not_drawn", problem=problem))
                self.conv.user(phrase("reprompt_bad_args"))
                continue
            d.start, d.end, d.belief, d.note = start, end, belief, note
            self.pending = [c["id"] for c in calls]
            break
        return d


class Oracle:
    name = "oracle"
    is_model = False

    def __init__(self):
        self.rng = np.random.default_rng(AGENT_SEEDS["camera_agents"])

    def act(self, world: World, png: bytes, last) -> Decision:
        H = world.H
        sq = world.square
        assert sq is not None
        px = project(H, sq.open_ends) + self.rng.normal(0, PIX_SD, (2, 2))
        cmd = project(np.linalg.inv(H), px)
        return Decision(cmd[0].tolist(), cmd[1].tolist(), corners_from_H(H).tolist(), "Aiming through the true camera.")


def prior_camera() -> np.ndarray:
    """A generic first guess: the work area's centre at the photo's centre, 5 px/mm, not rotated."""
    x0, y0, x1, y1 = WORK_AREA
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    s = PRIOR_PX_PER_MM
    return np.array([[s, 0, FRAME / 2 - s * c[0]], [0, s, FRAME / 2 - s * c[1]], [0, 0, 1.0]])


class Estimator:
    name = "estimator"
    is_model = False

    def __init__(self):
        self.rng = np.random.default_rng(AGENT_SEEDS["camera_agents"])

    def act(self, world: World, png: bytes, last) -> Decision:
        H = world.H  # used only to *measure* marks and targets in the current photo, with pixel noise
        mm, px = [], []
        for s in world.strokes:
            for c, e in zip(s.cmd, s.ink_ends, strict=True):
                mm.append(c)
                px.append(project(H, [e])[0] + self.rng.normal(0, PIX_SD, 2))
        Hh, kind = (prior_camera(), "prior") if not mm else fit_mm_to_px(mm, px)
        assert world.square is not None
        target_px = project(H, world.square.open_ends) + self.rng.normal(0, PIX_SD, (2, 2))
        cmd = project(np.linalg.inv(Hh), target_px)
        note = f"Camera fitted from {len(mm) // 2} own marks ({kind})."
        return Decision(cmd[0].tolist(), cmd[1].tolist(), corners_from_H(Hh).tolist(), note)


def reference(name: str) -> Any:
    return {"oracle": Oracle, "estimator": Estimator}[name]()
