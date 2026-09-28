"""Ported from the Codex copy's tests/test_numeric_baselines.py (5 tests)."""
import numpy as np

from freehand.agents.reference.numeric import AdaptiveLibrary, LocalBroyden, NumericAgent

REGION = [5, 5, 210.9, 274.4]


def test_no_hidden_fields_cross_boundary():
    class Sentinel:
        name = "sentinel"

        def act(self, obs):
            self.seen = obs
            assert set(obs) == {"target", "history", "region"}
            assert set(obs["history"][0]) == {"command", "landed"}
            return obs["target"], "ok"

    control = Sentinel()
    stroke = {"cmd": [[1, 2], [3, 4]], "ink_ends": [[1.01, 2], [3, 4]], "closed": False, "square": 3, "post": True}
    NumericAgent(control).act({"priv": {"open_ends": [[1, 2], [3, 4]], "strokes": [stroke], "seed": 999,
                                        "scen_on": True, "scenario": object(), "perturb_stroke": 1}})
    assert "seed" not in str(control.seen)


def test_identity_never_needs_change_flag():
    a = AdaptiveLibrary()
    history = []
    for n in range(6):
        target = [[50 + n, 80], [70 + n, 80]]
        cmd, _ = a.act({"target": target, "history": history, "region": REGION})
        np.testing.assert_allclose(cmd, target)
        history.append({"command": target, "landed": target})
    assert a.change is None


def test_unknown_translation_detected_and_inverted():
    a = AdaptiveLibrary()
    obs = {"target": [[60, 90], [80, 90]], "history": [{"command": [[50, 80], [70, 80]], "landed": [[55, 76], [75, 76]]}],
           "region": REGION}
    cmd, _ = a.act(obs)
    assert a.change == 0
    np.testing.assert_allclose(np.asarray(cmd) + [5, -4], obs["target"], atol=1e-6)


def test_broyden_learns_reflection_within_square():
    a = LocalBroyden()
    target = [[60, 90], [80, 90]]
    history = []
    for _ in range(8):
        cmd, _ = a.act({"target": target, "history": history, "region": REGION})
        y = np.asarray(cmd).copy()
        y[:, 0] = 215.9 - y[:, 0]
        history.append({"command": np.asarray(cmd).tolist(), "landed": y.tolist()})
    assert np.max(np.abs(y - np.asarray(target))) < .1


def test_broyden_forgets_previous_square():
    a = LocalBroyden()
    a.act({"target": [[60, 90], [80, 90]], "history": [], "region": REGION})
    target = [[90, 120], [110, 120]]
    cmd, _ = a.act({"target": target, "history": [{"command": [[60, 90], [80, 90]], "landed": [[70, 90], [90, 90]]}],
                    "region": REGION})
    np.testing.assert_allclose(cmd, target)
