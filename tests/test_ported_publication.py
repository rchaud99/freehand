"""Ported from the Codex copy's tests/test_publication.py (13 tests): scoring, stateful rules, summaries."""
import json

import numpy as np
import pytest

from freehand.agents.base import Agent
from freehand.agents.reference import LOracle
from freehand.analysis.episodes import load_episodes
from freehand.episode import EpisodeConfig, MemorySink, run_episode
from freehand.episode.actions import first_stroke
from freehand.perturbations import CommandDynamics, CrossAxisWarp, LatentMirror, build
from freehand.perturbations.discriminating import CommandMemoryParams, LatentMirrorParams
from freehand.scoring import first_try_curve, first_try_summary
from freehand.sim import densify, make_page

FACTORIES = (CommandDynamics, LatentMirror, CrossAxisWarp)


class TestScoring:
    def test_interrupted_failed_first_stroke_is_observed(self):
        ep = {"perturb_after": 1, "n_squares": 4, "squares_result": [], "strokes": [{"square": 2, "closed": False}]}
        assert first_try_curve(ep) == [0, None, None]
        s = first_try_summary(ep)
        assert s["attempted"] == 1 and s["unobserved"] == 2 and s["fixed_budget_attainment"] == 0

    def test_retry_success_does_not_change_first_try(self):
        ep = {"perturb_after": 0, "n_squares": 1, "squares_result": [],
              "strokes": [{"square": 1, "closed": False}, {"square": 1, "closed": True}]}
        assert first_try_curve(ep) == [0]

    def test_missing_is_not_observed_failure(self):
        ep = {"perturb_after": 1, "n_squares": 3, "squares_result": [], "strokes": [{"square": 2, "closed": True}]}
        assert first_try_summary(ep)["observed_rate"] == 1
        assert first_try_summary(ep)["fixed_budget_attainment"] == .5

    def test_reject_nonfinite_commands(self):
        for n in [float("nan"), float("inf"), -float("inf")]:
            assert first_stroke({"strokes": [[[n, 1], [2, 3]]]}) is None


def _episode(agent, seed, n, P, pert, render=False):
    cfg = EpisodeConfig(seed=seed, squares=make_page(seed, n), perturbation=pert, perturb_after=P, render=render)
    return run_episode(agent, cfg, MemorySink())


class TestScenarios:
    def test_arx_oracle_inverse_and_no_query_mutation(self):
        sc = CommandDynamics(1)
        sc.start(4)
        target = np.array([[80., 110.], [100., 110.]])
        state = sc.state.copy()
        cmd = sc.oracle_cmd(target, 4)
        np.testing.assert_allclose(sc.expected(cmd, 4), target)
        np.testing.assert_equal(sc.state, state)
        sc.land(cmd, 1, 4)
        np.testing.assert_allclose(sc.state, target[-1])

    def test_mirror_transition_applies_to_next_stroke(self):
        sc = LatentMirror(1, LatentMirrorParams(threshold_mm=100))
        sc.start(1)
        cmd = np.array([[70., 110.], [90., 110.]])
        np.testing.assert_equal(sc.expected(cmd, 1), cmd)
        sc.land(cmd, 1, 1)
        assert sc.mirrored
        target = np.array([[80., 120.], [100., 120.]])
        np.testing.assert_allclose(sc.expected(sc.oracle_cmd(target, 2), 2), target)
        sc.land([[150, 120], [155, 120]], 1, 2)
        assert not sc.mirrored

    def test_warp_inverse_full_curve(self):
        sc = CrossAxisWarp(1)
        sc.start(1)
        target = np.array([[80., 70.], [80., 220.]])
        cmd = sc.oracle_cmd(target, 1)
        np.testing.assert_allclose(sc.expected(cmd, 1), densify(target, step=2), atol=1e-10)
        # Inverting only endpoints would leave curved ink.
        dense = sc.expected(densify(cmd), 1)
        assert abs(dense[:, 0] - 80).max() < .01

    def test_state_reset_and_replay_determinism(self):
        for cls in FACTORIES:
            a, b = cls(31), cls(31)
            a.start(1)
            b.start(1)
            for n in range(1, 4):
                cmd = [[70 + n, 90], [100, 110 + n]]
                np.testing.assert_equal(a.land(cmd, 31, n), b.land(cmd, 31, n))

    def test_identity_controls_complete(self):
        ep = _episode(LOracle(), 2001, 4, 1, build("none", {"type": "none"}, 2001))
        assert ep["complete"], ep["stop"]
        assert all(s["closed"] for s in ep["squares_result"])
        assert ep["metrics"]["post_first_try"]["planned"] == 3

    def test_change_at_start_is_active(self):
        sc = CommandDynamics(2001, CommandMemoryParams())
        ep = _episode(LOracle(), 2001, 2, 0, sc)
        assert ep["complete"], ep["stop"]
        assert sc.n0 == 1
        assert all(s["closed"] for s in ep["squares_result"])

    def test_model_headless_is_forbidden(self):
        class Model(Agent):
            is_model = True

        with pytest.raises(ValueError):
            _episode(Model(), 1, 2, 1, build("none", {"type": "none"}, 1))


class TestSummaries:
    @staticmethod
    def _write(root, run, seed, strokes):
        d = root / run / "episodes" / "agent" / "rot13__silent" / f"s{seed}"
        d.mkdir(parents=True)
        summ = {"agent": {"name": "agent", "kind": "model"}, "labels": {"perturbation": "rot13", "arm": "silent"},
                "perturbation": {"name": "rot13"}, "arm": {"name": "silent"}, "seed": seed, "n_squares": 20,
                "perturb_after": 4, "squares_result": [], "strokes": strokes, "status": "capped"}
        (d / "summary.json").write_text(json.dumps(summ))
        (d / "episode.jsonl").write_text("")

    def test_seed_replicates_survive_and_conflicts_fail(self, tmp_path):
        for seed in (10, 11):
            self._write(tmp_path, "run", seed, [])
        eps = load_episodes([tmp_path / "run"])
        assert [e.seed for e in eps] == [10, 11]
        assert first_try_summary(eps[0].summary, 6)["unobserved"] == 15
        self._write(tmp_path, "other", 10, [{"square": 5, "closed": False}])
        with pytest.raises(ValueError, match="conflicting"):
            load_episodes([tmp_path / "run", tmp_path / "other"])

    def test_rendering_does_not_change_commands_or_ink(self):
        pert = build("none", {"type": "none"}, 2001)
        a = _episode(LOracle(), 2001, 2, 1, pert, render=False)
        b = _episode(LOracle(), 2001, 2, 1, build("none", {"type": "none"}, 2001), render=True)
        assert a["strokes"] == b["strokes"]
