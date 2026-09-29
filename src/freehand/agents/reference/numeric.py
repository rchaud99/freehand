"""Code baselines behind an explicit numeric-observation boundary (from the 2026-09-28 control studies).

Controllers receive only: the target endpoints, their executed commands with the measured ink endpoints, and the
public command bounds. They never receive the rule family, change timing, hidden state, seed or correctness labels.
Numeric perception is still privileged relative to image-only agents; use the same numeric feedback in model
ablations (the `study_image_numeric` arm).

  LocalBroyden     within-target 4-D secant Jacobian, damped inversion, bounded steps; forgets at each new target
  AdaptiveLibrary  detects a departure from identity, then selects among a disclosed library (identity,
                   translation, affine, endpoint ARX, latent mirror threshold, sinusoidal x(y) warp) by noise-scaled
                   squared error plus a parameter penalty. An engineered library baseline, not general discovery.
"""
from __future__ import annotations

import copy

import numpy as np

from freehand.agents.base import Agent, code_reply
from freehand.sim.geometry import LETTER_H, LETTER_W, REGION
from freehand.sim.plotter import densify

BROYDEN_MIN_MOVE_SQ = 0.25       # skip secant updates after near-zero moves
BROYDEN_DAMPING = 0.04
BROYDEN_MAX_STEP_MM = 50.0
LIBRARY_CHANGE_MM = 4.0          # a mark further than this from its command signals a change
LIBRARY_NOISE_SD = 0.5           # residual scale in the model-selection score
ARX_GAINS = (0.35, 1.15, 321)
MODE_THRESHOLDS_MM = (60, 155, 191)


def numeric_observation(target, strokes, region=REGION) -> dict:
    return {"target": np.round(target, 3).tolist(), "region": list(region),
            "history": [{"command": s["cmd"], "landed": np.round(s["ink_ends"], 3).tolist()} for s in strokes]}


class NumericAgent(Agent):
    """Wraps a numeric controller: builds the public observation and nothing else."""

    def __init__(self, controller):
        self.controller = controller
        self.name = controller.name

    def act(self, obs):
        pv = obs["priv"]
        public = numeric_observation(pv["open_ends"], pv["strokes"])
        cmd, note = self.controller.act(copy.deepcopy(public))
        return code_reply(cmd, note)


class LocalBroyden:
    """Within-target damped Broyden secant correction. Not a claim that local optimisation is solved optimally."""
    name = "local_broyden"

    def __init__(self):
        self.target = None
        self.start = 0
        self.previous_count = 0
        self.J = np.eye(4)

    def act(self, obs):
        t = np.asarray(obs["target"], float)
        history = obs["history"]
        if self.target != obs["target"]:
            self.target = obs["target"]
            self.start = len(history)
            self.previous_count = len(history)
            self.J = np.eye(4)
        local = history[self.start:]
        if not local:
            return t, "Local secant: initial target command."
        if len(local) >= 2 and len(history) != self.previous_count:
            prev, last = local[-2:]
            u0 = np.array([prev["command"][0], prev["command"][-1]]).ravel()
            u1 = np.array([last["command"][0], last["command"][-1]]).ravel()
            y0, y1 = np.asarray(prev["landed"]).ravel(), np.asarray(last["landed"]).ravel()
            du, dy = u1 - u0, y1 - y0
            if du @ du > BROYDEN_MIN_MOVE_SQ:
                self.J += np.outer(dy - self.J @ du, du) / (du @ du)
        self.previous_count = len(history)
        last = local[-1]
        u = np.array([last["command"][0], last["command"][-1]]).ravel()
        error = t.ravel() - np.asarray(last["landed"]).ravel()
        left, singular, right = np.linalg.svd(self.J)
        # Damped pseudoinverse suppresses explosions after noisy near-zero moves.
        step = right.T @ ((singular / (singular ** 2 + BROYDEN_DAMPING)) * (left.T @ error))
        norm = np.linalg.norm(step.reshape(2, 2), axis=1).max()
        if norm > BROYDEN_MAX_STEP_MM:
            step *= BROYDEN_MAX_STEP_MM / norm
        cmd = (u + step).reshape(2, 2)
        lo, bottom, hi, top = obs["region"]
        cmd = np.clip(cmd, [lo, bottom], [hi, top])
        return cmd, "Within-target damped Broyden correction."


def _ends(mark):
    return np.array([mark["command"][0], mark["command"][-1]], float), np.asarray(mark["landed"], float)


def _features(points):
    angle = 2 * np.pi * np.asarray(points)[:, 1] / LETTER_H
    return np.c_[np.sin(angle), np.cos(angle)]


class AdaptiveLibrary:
    """The candidate-library learner (see module docstring). No true-family or change-time input."""
    name = "adaptive_library"

    def __init__(self):
        self.change = None
        self.selected = "identity"
        self.trace = []

    def _fit(self, marks):
        u = np.vstack([_ends(m)[0] for m in marks])
        y = np.vstack([_ends(m)[1] for m in marks])
        predictions = []

        def add(name, pred, params, complexity):
            # Same 4 residual dimensions per observation for every candidate.
            score = float(np.square(y - pred).sum() / LIBRARY_NOISE_SD ** 2 + complexity * np.log(max(y.size, 2)))
            predictions.append((score, name, params))

        add("identity", u, None, 0)
        shift = (y - u).mean(axis=0)
        add("translation", u + shift, shift, 2)
        matrix = np.c_[u, np.ones(len(u))]
        if len(marks) >= 3 and np.linalg.matrix_rank(matrix) == 3 and np.linalg.cond(matrix) < 1e5:
            affine = np.linalg.lstsq(matrix, y, rcond=None)[0]
            if abs(np.linalg.det(affine[:2])) > .1:
                add("affine", matrix @ affine, affine, 6)
        # Search gains through full commanded vertex sequences, so an early curved probe cannot permanently exclude
        # a stateful candidate.
        gains = np.linspace(*ARX_GAINS)
        best_gain = []
        for axis in range(2):
            losses = np.zeros(len(gains))
            for i, m in enumerate(marks):
                c = np.asarray(m["command"], float)
                ink = np.asarray(m["landed"], float)
                if i:
                    prev = np.asarray(marks[i - 1]["landed"])[-1, axis]
                    first = prev + gains * (c[0, axis] - prev)
                    losses += (first - ink[0, axis]) ** 2
                current = np.full(len(gains), ink[0, axis])
                for vertex in c[1:]:
                    current += gains * (vertex[axis] - current)
                losses += (current - ink[-1, axis]) ** 2
            best_gain.append(gains[np.argmin(losses)])
        gain = np.array(best_gain)
        pred = []
        for i, m in enumerate(marks):
            c, ink = np.asarray(m["command"], float), np.asarray(m["landed"], float)
            first = ink[0] if i == 0 else np.asarray(marks[i - 1]["landed"])[-1] + gain * (
                c[0] - np.asarray(marks[i - 1]["landed"])[-1])
            current = ink[0].copy()
            for vertex in c[1:]:
                current += gain * (vertex - current)
            pred.extend([first, current])
        add("arx", np.array(pred), gain, 4)
        coef = np.linalg.lstsq(_features(u), y[:, 0] - u[:, 0], rcond=None)[0]
        warped = u.copy()
        warped[:, 0] += _features(u) @ coef
        add("warp", warped, coef, 2)
        if len(marks) >= 2:
            candidates = np.linspace(*MODE_THRESHOLDS_MM)
            loss = []
            for threshold in candidates:
                pred = []
                for i, m in enumerate(marks):
                    c, ink = _ends(m)
                    # First mode is fitted (the detector starts after its trigger).
                    mirrored = (marks[i - 1]["command"][0][0] < threshold) if i else (
                        np.square(c - ink).sum() > np.square(np.c_[LETTER_W - c[:, 0], c[:, 1]] - ink).sum())
                    if mirrored:
                        c[:, 0] = LETTER_W - c[:, 0]
                    pred.extend(c)
                loss.append(np.square(y - np.array(pred)).sum())
            loss = np.array(loss)
            best = np.where(np.isclose(loss, loss.min()))[0]
            threshold = float(np.median(candidates[best]))
            predictions.append((float(loss.min() / LIBRARY_NOISE_SD ** 2 + 2 * np.log(max(y.size, 2))), "mode",
                                threshold))
        return min(predictions, key=lambda p: p[0])

    def act(self, obs):
        t = np.asarray(obs["target"], float)
        hist = obs["history"]
        if self.change is None:
            for i, m in enumerate(hist):
                u, y = _ends(m)
                if np.linalg.norm(y - u, axis=1).max() > LIBRARY_CHANGE_MM:
                    self.change = i
                    break
        if self.change is None:
            return t, "Library baseline: no change detected."
        marks = hist[self.change:]
        score, kind, p = self._fit(marks)
        self.selected = kind
        self.trace.append({"after_stroke": len(hist), "selected": kind, "score": score, "detected_at": self.change + 1})
        if kind == "identity":
            cmd = t
        elif kind == "translation":
            cmd = t - p
        elif kind == "affine":
            cmd = (t - p[2]) @ np.linalg.inv(p[:2])
        elif kind == "arx":
            prev = np.asarray(hist[-1]["landed"])[-1]
            cmd = []
            for point in t:
                cmd.append(prev + (point - prev) / p)
                prev = point
        elif kind == "warp":
            # Fixed polyline resolution, also available to other agents.
            cmd = densify(t, step=2)
            cmd[:, 0] -= _features(cmd) @ p
        elif kind == "mode":
            cmd = t.copy()
            if hist[-1]["command"][0][0] < p:
                cmd[:, 0] = LETTER_W - cmd[:, 0]
        else:
            raise AssertionError(kind)
        return cmd, f"Library baseline selected {kind}; detected change after stroke {self.change + 1}."
