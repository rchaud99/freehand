"""Freehand A (camera3d): camera geometry, the belief metric, the world, the tool-calling loop (with a scripted
fake chat, no network) and the video frame renderer."""

from __future__ import annotations

import json

import numpy as np
import pytest

from freehand.camera3d import belief, pose
from freehand.camera3d.agents import Estimator, Oracle, ToolModel, parse_draw
from freehand.camera3d.chat import KEEP_PHOTOS, Conversation
from freehand.camera3d.env import Spec, World
from freehand.camera3d.episode import run_episode
from freehand.camera3d.run import SEEDS

SEED = SEEDS[0]


def test_homography_matches_pinhole_projection():
    p = pose.sample_pose(SEED, 1, (60, 80, 156, 196))
    X = np.array([[70.0, 90.0], [150.0, 190.0], [100.0, 120.0]])
    Xc = (p.R @ np.c_[X, np.zeros(3)].T).T + p.t
    px = (p.K @ Xc.T).T
    np.testing.assert_allclose(px[:, :2] / px[:, 2:], pose.project(p.H, X), atol=1e-6)
    assert p.centre[2] < 0  # above the page
    assert 18 <= p.tilt_deg <= 38


def test_pose_from_homography_recovers_the_pose():
    p = pose.sample_pose(SEED, 2, (60, 80, 156, 196))
    q = pose.pose_from_homography(p.H * 3.7, p.K)
    assert q is not None
    np.testing.assert_allclose(q.R, p.R, atol=1e-9)
    np.testing.assert_allclose(q.centre, p.centre, atol=1e-6)


def test_belief_roundtrip_and_error():
    w = World(Spec(SEED))
    H = w.H
    Hb = belief.H_from_corners(belief.corners_from_H(H))
    assert belief.aim_error_mm(H, Hb) < 1e-6
    assert belief.aim_error_mm(H, w.poses[1].H) > 10  # the other pose is far off
    assert belief.H_from_corners([[0, 0], [0, 0], [1, 1], [2, 2]]) is None  # degenerate
    assert belief.aim_error_mm(H, None) == float("inf")


def test_turns_to_match():
    assert belief.turns_to_match([9, 5, 2, 1]) == 3
    assert belief.turns_to_match([2, 9, 2, 1]) == 3  # must stay matched
    assert belief.turns_to_match([9, 9]) is None


def test_world_is_deterministic_and_the_camera_moves():
    a, b = World(Spec(SEED)), World(Spec(SEED))
    assert [s.to_dict() for s in a.squares] == [s.to_dict() for s in b.squares]
    assert np.array_equal(a.photo(), b.photo())
    assert a.pose_no == 1
    while a.current <= a.spec.move_after:
        a.draw(*a.square.open_ends)
    assert a.pose_no == 2


def test_oracle_and_estimator_episodes(tmp_path):
    o = run_episode(Spec(SEED), Oracle(), tmp_path / "o", log=lambda *_: None)["summary"]
    e = run_episode(Spec(SEED), Estimator(), tmp_path / "e", log=lambda *_: None)["summary"]
    assert o["squares_closed"] == 8 and o["match_turn_cold"] == 1
    assert e["squares_closed"] == 8
    assert e["match_turn_cold"] is not None and e["match_turn_after_move"] == 1  # re-anchors on its own marks


def test_parse_draw():
    ok = json.dumps(
        {
            "start": [1, 2],
            "end": ["3", 4],
            "camera_estimate": {"top_left": [0, 0], "top_right": [1, 0], "bottom_right": [1, 1], "bottom_left": [0, 1]},
            "note": "n",
        }
    )
    s, e, b, _note, prob = parse_draw(ok)
    assert s == [1.0, 2.0] and e == [3.0, 4.0] and len(b) == 4 and prob is None
    assert parse_draw('{"start": [1], "end": [2, 3]}')[4] is not None
    assert parse_draw("not json")[4] is not None
    assert parse_draw(json.dumps({"start": [1, 2], "end": [3, 4]}))[2] is None  # missing belief is not fatal


class FakeChat:
    """Stands in for ToolChat: answers each turn with a `draw` call aimed through a slightly wrong camera, and
    checks the conversation it is sent."""

    class spec:
        agent_name = "fake"
        slug = "fake/fake"

        @staticmethod
        def to_manifest():
            return {"id": "fake"}

    def __init__(self, world_ref):
        self.world_ref = world_ref
        self.calls = 0

    def complete(self, conv, tools):
        self.calls += 1
        msgs = conv.request_messages(cache=True)
        n_img = sum(1 for m in msgs if m["role"] == "user" for p in m["content"] if p["type"] == "image_url")
        assert n_img <= KEEP_PHOTOS
        roles = [m["role"] for m in msgs]
        for i, m in enumerate(msgs):  # every tool call is answered before the next user message
            if m["role"] == "assistant" and m.get("tool_calls"):
                assert roles[i + 1] == "tool"
        if self.calls == 2:  # once, answer without a tool call: the agent must re-prompt
            return {"content": "thinking out loud"}, {}, 0.01, {}
        w = self.world_ref["w"]
        H = w.H @ np.array([[1.0, 0.004, 0], [0, 1.0, 0], [0, 0, 1.0]])
        ends = pose.project(np.linalg.inv(H), pose.project(w.H, w.square.open_ends))
        est = dict(
            zip(
                ("top_left", "top_right", "bottom_right", "bottom_left"), belief.corners_from_H(H).tolist(), strict=True
            )
        )
        args = {"start": ends[0].tolist(), "end": ends[1].tolist(), "camera_estimate": est, "note": "aiming"}
        call = {"id": f"c{self.calls}", "type": "function", "function": {"name": "draw", "arguments": json.dumps(args)}}
        return (
            {"content": "", "tool_calls": [call], "reasoning_details": [{"type": "x"}]},
            {"input_tokens": 1},
            0.01,
            {},
        )


def test_tool_model_episode_with_fake_chat(tmp_path, monkeypatch):
    ref: dict = {}
    import freehand.camera3d.episode as ep

    real_world = ep.World

    def world(spec):
        ref["w"] = real_world(spec)
        return ref["w"]

    monkeypatch.setattr(ep, "World", world)
    chat = FakeChat(ref)
    agent = ToolModel(chat, 8, 4)  # type: ignore[arg-type]
    rec = run_episode(Spec(SEED), agent, tmp_path / "m", log=lambda *_: None)
    s = rec["summary"]
    assert s["status"] == "complete" and s["squares_closed"] >= 6
    assert rec["turns"][1]["problems"] == ["no draw call"]
    assert all(t["aim_error_mm"] is not None and t["aim_error_mm"] < 3 for t in rec["turns"])
    conv = json.loads((tmp_path / "m" / "conversation.json").read_text())
    assert all("image_url" not in json.dumps(m) for m in conv)  # images logged as hashes
    assert (tmp_path / "m" / "photos" / "000.png").is_file()


def test_conversation_drops_old_photos():
    c = Conversation("sys")
    for i in range(KEEP_PHOTOS + 2):
        c.user(f"t{i}", b"\x89PNG fake")
    msgs = c.request_messages(cache=False)
    kept = [m for m in msgs if m["role"] == "user" and any(p["type"] == "image_url" for p in m["content"])]
    assert len(kept) == KEEP_PHOTOS and kept[-1]["content"][0]["text"] == f"t{KEEP_PHOTOS + 1}"


@pytest.mark.slow
def test_video_frame_renders(tmp_path):
    from freehand.camera3d import video

    run_episode(Spec(SEED), Estimator(), tmp_path / "estimator" / f"s{SEED}", log=lambda *_: None)
    ep = video.load_episode(tmp_path / "estimator" / f"s{SEED}")
    img = video.model_panel(ep, 3, (960, 540))
    assert img.shape == (540, 960, 3)


def test_prompts_are_pinned():
    """The text the first Freehand A runs sent (system prompt, first message, tool schema, state text)."""
    import hashlib

    from freehand.camera3d import prompt

    w = World(Spec(3004))
    snap = {
        "system": prompt.system_prompt(8, 4),
        "first": prompt.first_message(),
        "tool": prompt.DRAW_TOOL,
        "state0": prompt.state_text(w, None),
    }
    snap["state1"] = prompt.state_text(w, w.draw([100, 100], [110, 100]))
    digest = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
    assert digest == "af4d87b406daa40f98381737381bcc29d8d26d09ff321930a638aac2e587fefc"


def test_fresh_world_starts_at_the_moved_camera_on_the_later_squares():
    t, f = World(Spec(SEED)), World(Spec(SEED, fresh=True))
    assert f.pose_no == 2 and np.allclose(f.H, t.poses[1].H)
    assert len(f.squares) == 4 and f.squares[0].idx == 1
    assert [s.open_ends for s in f.squares] == [s.open_ends for s in t.squares[4:]]
    with pytest.raises(ValueError):
        World(Spec(SEED, fresh=True, move_after=0))


def test_fresh_estimator_has_no_marks_to_transfer(tmp_path):
    t = run_episode(Spec(SEED), Estimator(), tmp_path / "t", log=lambda *_: None)["summary"]
    f = run_episode(Spec(SEED, fresh=True), Estimator(), tmp_path / "f", log=lambda *_: None)["summary"]
    assert t["match_turn_after_move"] == 1  # re-anchors on its old marks at once
    assert f["match_turn_after_move"] is None or f["match_turn_after_move"] > 1  # must learn from scratch


def test_implied_camera_of_perfect_strokes_is_the_true_camera():
    w = World(Spec(SEED))
    strokes = [{"cmd": q.open_ends} for q in w.squares[:3]]
    H = belief.implied_camera(w.poses[0], strokes, [q.open_ends for q in w.squares[:3]])
    assert H is not None and belief.aim_error_mm(w.poses[0].H, H) < 1e-6
    shifted = [{"cmd": (np.asarray(q.open_ends) + [2.0, 0.0]).tolist()} for q in w.squares[:3]]
    Hs = belief.implied_camera(w.poses[0], shifted, [q.open_ends for q in w.squares[:3]])
    assert abs(belief.aim_error_mm(w.poses[0].H, Hs) - 2.0) < 1e-6  # aiming 2 mm right everywhere = 2 mm off
    assert belief.implied_camera(w.poses[0], strokes[:1], [w.squares[0].open_ends]) is None


def test_study_tables_and_claims(tmp_path):
    from freehand.camera3d import study

    run = tmp_path / "run"
    for arm in ("transfer", "fresh"):
        spec = Spec(SEED, fresh=arm == "fresh")
        run_episode(
            spec, Estimator(), run / "estimator" / (f"s{SEED}" + ("_fresh" if spec.fresh else "")), log=lambda *_: None
        )
    out = study.build([run], "t", new_pages=[SEED], out_root=tmp_path / "studies")
    for f in ("episodes.csv", "strokes.csv", "transfer.csv", "claims.md", "summary.json"):
        assert (out / f).is_file()
    s = json.loads((out / "summary.json").read_text())
    assert len(s["episodes"]) == 2 and len(s["transfer"]) == 1 and len(s["claims"]) == 3
    assert s["transfer"][0]["transfer_match_stroke"] == 1  # the estimator re-anchors on its old marks
