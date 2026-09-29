"""Local-repair and known-family references (from the 2026-09-28 control studies).

  LocalPatcher     the "offset patcher": exact targets, corrects each square by its last observed endpoint offset,
                   forgets between squares
  FamilyEstimator  known-family, numeric-endpoint reference: knows the rule family and the change time (explicitly
                   privileged), learns the family's parameters from its own marks. A privileged perception control,
                   NOT an optimal agent or a fair vision-only competitor to an LLM.
"""
from __future__ import annotations

import numpy as np

from freehand.agents.base import Agent, code_reply
from freehand.sim.geometry import LETTER_H, LETTER_W
from freehand.sim.plotter import densify

ARX_GAIN_CLIP = (0.4, 1.0)
MODE_THRESHOLDS_MM = (60, 155, 191)       # linspace(start, stop, num) of candidate mirror thresholds
WARP_STEP_MM = 2.0


class LocalPatcher(Agent):
    name = "local_patcher"

    def __init__(self):
        self.square = None
        self.offset = np.zeros((2, 2))
        self.last = None

    def observe(self, cmd, ink_ends):
        self.last = (np.array([cmd[0], cmd[-1]]), np.asarray(ink_ends))

    def act(self, obs):
        pv = obs["priv"]
        q = obs["square_id"] if "square_id" in obs else tuple(np.asarray(pv["open_ends"]).ravel())
        if q != self.square:
            self.offset = np.zeros((2, 2))
            self.last = None
            self.square = q
        if self.last is not None:
            cmd, ink = self.last
            self.offset = cmd - ink
        return code_reply(np.asarray(pv["open_ends"]) + self.offset, "Local endpoint-offset correction.")


class FamilyEstimator(Agent):
    name = "family_estimator"

    def __init__(self, family: str):
        if family not in ("arx", "mode", "warp"):
            raise ValueError(f"FamilyEstimator family must be arx | mode | warp, not {family!r}")
        self.family = family
        self.marks: list = []
        self.active = False

    def observe(self, cmd, ink_ends):
        if self.active:
            self.marks.append((np.asarray(cmd), np.asarray(ink_ends)))

    def act(self, obs):
        pv = obs["priv"]
        self.active = pv["scen_on"]  # known change time; explicitly privileged
        t = np.asarray(pv["open_ends"], float)
        if not self.active or not self.marks:
            return code_reply(t, "Known-family reference collecting evidence.")
        if self.family == "arx":
            features, outcomes = [], []
            for j, (cmd, ink) in enumerate(self.marks):
                features.append(cmd[-1] - ink[0])
                outcomes.append(ink[-1] - ink[0])
                if j:
                    prev = self.marks[j - 1][1][-1]
                    features.append(cmd[0] - prev)
                    outcomes.append(ink[0] - prev)
            x, y = np.array(features), np.array(outcomes)
            gain = np.clip(np.sum(x * y, axis=0) / np.maximum(np.sum(x * x, axis=0), 1e-8), *ARX_GAIN_CLIP)
            prev = self.marks[-1][1][-1]
            cmd = []
            for target in t:
                cmd.append(prev + (target - prev) / gain)
                prev = target
        elif self.family == "mode":
            # Search candidate transition thresholds; fit only observed evidence.
            candidates = np.linspace(*MODE_THRESHOLDS_MM)
            loss = np.zeros(len(candidates))
            for j, (u, y) in enumerate(self.marks):
                if not j:
                    continue
                direct = np.array([u[0], u[-1]])
                mirrored = direct.copy()
                mirrored[:, 0] = LETTER_W - mirrored[:, 0]
                use = self.marks[j - 1][0][0, 0] < candidates
                loss += np.where(use, np.sum((mirrored - y) ** 2), np.sum((direct - y) ** 2))
            winners = candidates[np.isclose(loss, loss.min())]
            threshold = float(np.median(winners))
            cmd = t.copy()
            if self.marks[-1][0][0, 0] < threshold:
                cmd[:, 0] = LETTER_W - cmd[:, 0]
        else:  # warp
            u = np.vstack([np.array([c[0], c[-1]]) for c, _ in self.marks])
            y = np.vstack([i for _, i in self.marks])
            angle = 2 * np.pi * u[:, 1] / LETTER_H
            A = np.c_[np.sin(angle), np.cos(angle)]
            coef = np.linalg.lstsq(A, y[:, 0] - u[:, 0], rcond=None)[0]
            cmd = densify(t, step=WARP_STEP_MM)
            angle = 2 * np.pi * cmd[:, 1] / LETTER_H
            cmd[:, 0] -= np.c_[np.sin(angle), np.cos(angle)] @ coef
        return code_reply(cmd, "Known-family fit from numeric observed endpoints.")
