"""Reference agents of the plotter-map conditions (the pilots' B family: none, offset*, rot*, scale*).

All have perfect perception of the targets.
  OracleAgent    knows the plotter map
  NaiveAgent     never adapts
  AdaptiveAgent  trusts the documented map until one stroke misses by > 2.5 mm, then fits the marks made since:
                 an offset until three strokes, then a similarity (from commanded vs measured ink ends)
"""
from __future__ import annotations

import numpy as np

from freehand.agents.base import Agent, code_reply
from freehand.agents.prompting import MEASURE_SD_MM
from freehand.seeding import AGENT_SEEDS

SIMILARITY_AFTER_ENDS = 6       # an offset until this many end pairs (three strokes), then a similarity


class NaiveAgent(Agent):
    name = "naive"

    def act(self, obs):
        return code_reply(obs["priv"]["open_ends"], "Joining the two free ends.")


class OracleAgent(Agent):
    name = "oracle"

    def act(self, obs):
        return code_reply(obs["priv"]["map"].inverse(obs["priv"]["open_ends"]), "Aiming through the true plotter map.")


class AdaptiveAgent(Agent):
    name = "adaptive"
    CHANGE_MM = 2.5

    def __init__(self):
        self.pairs, self.window_start, self.changed = [], 0, False
        self.rng = np.random.default_rng(AGENT_SEEDS["map_adaptive"])

    def _fit(self):
        P = self.pairs[self.window_start:]
        if not P:
            return lambda c: np.asarray(c, float), "identity"
        C = np.array([p[0] for p in P])
        Lm = np.array([p[1] for p in P])
        if len(P) < SIMILARITY_AFTER_ENDS:
            t = (Lm - C).mean(0)
            return (lambda c, t=t: np.asarray(c, float) + t), f"offset ({t[0]:+.1f},{t[1]:+.1f}) mm"
        A = np.zeros((2 * len(P), 4))
        y = Lm.reshape(-1)
        A[0::2] = np.c_[C[:, 0], -C[:, 1], np.ones(len(P)), np.zeros(len(P))]
        A[1::2] = np.c_[C[:, 1], C[:, 0], np.zeros(len(P)), np.ones(len(P))]
        a, b, tx, ty = np.linalg.lstsq(A, y, rcond=None)[0]
        M = np.array([[a, -b], [b, a]])
        t = np.array([tx, ty])
        return (lambda c, M=M, t=t: np.asarray(c, float) @ M.T + t), \
            f"similarity (scale {np.hypot(a, b):.3f}, rot {np.degrees(np.arctan2(b, a)):+.2f} deg)"

    def observe(self, cmd, ink_ends):
        cmd_ends = [cmd[0], cmd[-1]]
        meas = [np.asarray(e) + self.rng.normal(0, MEASURE_SD_MM, 2) for e in ink_ends]
        if not self.changed:
            err = max(np.linalg.norm(np.asarray(c) - m) for c, m in zip(cmd_ends, meas, strict=True))
            if err > self.CHANGE_MM:
                self.changed, self.window_start = True, len(self.pairs)
        self.pairs += [(np.asarray(c, float), m) for c, m in zip(cmd_ends, meas, strict=True)]

    def act(self, obs):
        fwd, desc = self._fit() if self.changed else (lambda c: np.asarray(c, float), "identity")
        tgt = np.asarray(obs["priv"]["open_ends"], float)
        c0 = fwd(np.zeros(2))
        J = np.array([fwd(np.array([1.0, 0])) - c0, fwd(np.array([0, 1.0])) - c0]).T
        cmd = np.linalg.solve(J, (tgt - c0).T).T
        note = "Joining the two free ends." if not self.changed else \
            f"Last marks landed off target; plotter map estimated as {desc}; compensating."
        return code_reply(cmd, note)
