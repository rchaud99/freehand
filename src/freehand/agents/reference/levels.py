"""Reference agents of the ladder levels and the discriminating rules (historical `levels.py`).

  LOracle    knows the rule: aims through `perturbation.oracle_cmd` once the change is on
  LNaive     aims where the targets appear in the photo and never adapts
  LAdaptive  the "ideal estimator" for a level: perfect perception of where things appear in the photo, plus a fit
             of the level's model family from its own commanded vs observed marks after the first clear miss.
             Privileged (it knows the rule family); a strong control, not a proven optimum.
"""
from __future__ import annotations

import numpy as np

from freehand.agents.base import Agent, code_reply
from freehand.agents.prompting import MEASURE_SD_MM
from freehand.perturbations.calibration import canonical
from freehand.seeding import AGENT_SEEDS

CLEAR_MISS_MM = 2.5           # ~5x the per-axis end scatter
SPREAD_FOR_AFFINE_MM = 8.0    # L3: fit a full affine only once marks are spread in 2-D
L5_WINDOW = 4                 # L5: marks in the drift trend fit
L5_RESTART_MM = 1.5           # L5: residual that signals a skipped step
OFFSET_MARKS = 3              # other levels: mean offset of the last 3 marks


def _reply(cmd, note):
    return code_reply(np.asarray(cmd, float), note)


class LOracle(Agent):
    name = "oracle"

    def act(self, obs):
        pv = obs["priv"]
        if pv["scen_on"]:
            return _reply(pv["scenario"].oracle_cmd(pv["open_ends"], pv["next_stroke"]), "Oracle.")
        return _reply(pv["open_ends"], "Oracle.")


class LNaive(Agent):
    """Aims where the targets appear in the photo and never adapts."""
    name = "naive"

    def act(self, obs):
        pv = obs["priv"]
        t = np.asarray(pv["open_ends"], float)
        sc = pv["scenario"]
        if pv["scen_on"] and sc.warp is not None:
            t = np.c_[t, np.ones(2)] @ np.asarray(sc.warp).T
        return _reply(t, "Joining the free ends.")


def affine_fit(src, dst):
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    A = np.c_[src, np.ones(len(src))]
    M, *_ = np.linalg.lstsq(A, dst, rcond=None)
    return M.T                                                  # 2x3


def similarity_fit(src, dst):
    """Least-squares similarity (rotation, uniform scale, shift) src -> dst as a 2x3 matrix; exact from 2 points."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    n = len(src)
    A = np.zeros((2 * n, 4))
    y = dst.reshape(-1)
    A[0::2] = np.c_[src[:, 0], -src[:, 1], np.ones(n), np.zeros(n)]
    A[1::2] = np.c_[src[:, 1], src[:, 0], np.zeros(n), np.ones(n)]
    a, b, tx, ty = np.linalg.lstsq(A, y, rcond=None)[0]
    return np.array([[a, -b, tx], [b, a, ty]])


def spread(pts) -> float:
    """Smallest singular value of the centred points (mm): ~0 when all marks lie along one line."""
    p = np.asarray(pts, float)
    return float(np.linalg.svd(p - p.mean(0), compute_uv=False)[-1]) if len(p) >= 3 else 0.0


def apply_affine(M, pts):
    return np.c_[np.asarray(pts, float), np.ones(len(pts))] @ np.asarray(M).T


def invert_affine(M):
    M3 = np.vstack([M, [0, 0, 1.0]])
    return np.linalg.inv(M3)[:2]


class LAdaptive(Agent):
    """The ideal estimator for a level (see module docstring)."""
    name = "adaptive"
    CHANGE_MM = 1.5          # ~3x the per-axis end scatter; small backlash moves ink by less than 2.5 mm

    def __init__(self, level: str):
        self.level = level
        self.marks: list = []    # (stroke_no, cmd_ends[2x2], ink_ends_measured[2x2])
        self.change_at = None
        self.window = None       # L5: first stroke of the current drift window
        self.errs: list = []     # per-mark miss vs the documented map (mm)
        self.window_fixed = None  # L6 camera: window fixed at the change point
        self.rng = np.random.default_rng(AGENT_SEEDS["level_adaptive"])

    def observe(self, cmd, ink_ends):
        n = len(self.marks) + 1
        c = np.array([cmd[0], cmd[-1]], float)
        i = np.asarray(ink_ends, float) + self.rng.normal(0, MEASURE_SD_MM, (2, 2))
        self.marks.append((n, c, i))
        self.errs.append(float(np.linalg.norm(i - c, axis=1).max()))
        # window start: the first clear miss if there is one, else the first > CHANGE_MM (small backlash); a lone
        # scatter outlier before the change must not pull unchanged marks into the fit
        big = [k for k, e in enumerate(self.errs) if e > CLEAR_MISS_MM]
        small = [k for k, e in enumerate(self.errs) if e > self.CHANGE_MM]
        start = big[0] if big else (small[0] if small else None)
        if start is not None and self.window_fixed is None and self.change_at != start + 1:
            self.change_at = start + 1
            self.window = start + 1

    def _post(self):
        return [m for m in self.marks if self.change_at is not None and m[0] >= self.change_at]

    def _plot_inverse(self, target, n, page_of=None):
        """cmd for target (page mm) under the fitted plotter model."""
        post = self._post()

        def page(m):
            return m[2] if page_of is None else page_of(m)

        if not post:
            return np.asarray(target, float)
        if self.level == "L5":
            win = [m for m in post if m[0] >= self.window][-L5_WINDOW:]
            offs = np.array([(page(m) - m[1]).mean(0) for m in win])
            ns = np.array([m[0] for m in win], float)
            if len(win) >= 2:
                A = np.c_[ns, np.ones(len(ns))]
                coef, *_ = np.linalg.lstsq(A, offs, rcond=None)
                pred = np.array([n, 1.0]) @ coef
            else:
                pred = offs[-1]
            return np.asarray(target, float) - pred
        if self.level in ("L3", "L7", "L2rot"):
            # a similarity is exact from one stroke and right for rotation/scale; a full affine (shear) only once the
            # marks are spread in two dimensions, so it is not extrapolated from marks along one line
            src = np.vstack([m[1] for m in post])
            dst = np.vstack([page(m) for m in post])
            M = affine_fit(src, dst) if (self.level == "L3" and len(post) >= 3 and spread(src) > SPREAD_FOR_AFFINE_MM) \
                else similarity_fit(src, dst)
            return apply_affine(invert_affine(M), target)
        off = np.mean([(page(m) - m[1]).mean(0) for m in post[-OFFSET_MARKS:]], axis=0)
        return np.asarray(target, float) - off

    def act(self, obs):
        pv = obs["priv"]
        n = pv["next_stroke"]
        sc = pv["scenario"]
        t = np.asarray(pv["open_ends"], float)
        page_of = None
        if self.level == "L6" and pv["scen_on"] and sc.warp is not None:
            # everything is seen through the moved camera: fit displayed = W(page) from pre-change marks (whose
            # page positions are their commands), then read targets and later marks back into page mm
            pre = [m for m in self.marks if m[0] < pv["perturb_stroke"]]

            def disp(pts):
                return apply_affine(sc.warp, pts) + self.rng.normal(0, MEASURE_SD_MM, (len(pts), 2))

            W = similarity_fit(np.vstack([m[1] for m in pre]), np.vstack([disp(m[2]) for m in pre]))
            Wi = invert_affine(W)
            t = apply_affine(Wi, disp(t))

            def page_of(m):
                return apply_affine(Wi, disp(m[2]))

            if self.window_fixed is None:                  # own old marks moved: the camera, not the plotter
                self.change_at = self.window_fixed = pv["perturb_stroke"]
        if self.level == "L5" and len(self._post()) >= 2:
            last = self._post()[-1]
            prev = self._post()[:-1][-3:]
            if len(prev) >= 2:
                ns = np.array([m[0] for m in prev], float)
                offs = np.array([(m[2] - m[1]).mean(0) for m in prev])
                coef, *_ = np.linalg.lstsq(np.c_[ns, np.ones(len(ns))], offs, rcond=None)
                if np.linalg.norm((last[2] - last[1]).mean(0) - np.array([last[0], 1.0]) @ coef) > L5_RESTART_MM:
                    self.window = last[0]                  # a skipped step: restart the trend
        cmd = self._plot_inverse(t, n, page_of)
        if self.level == "L4":
            cmd = canonical(cmd)
        return _reply(cmd, f"Ideal estimator ({self.level}).")
