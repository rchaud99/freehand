"""crop_px under a camera move (L6): the magnified crop is cut from the same camera-warped image as the main photo.

The bug this guards against (fixed during informed_models, 2026-09-28): the crop was cut from
the TRUE page, so a crop_px model (Sonnet, Flash) saw the marks where they really are after the camera was bumped,
bypassing the L6 camera perturbation that the main photo showed.
"""
import numpy as np
import pytest

from freehand.agents.arms import PRESETS
from freehand.agents.base import Agent
from freehand.episode import EpisodeConfig, MemorySink, run_episode
from freehand.episode.world import World
from freehand.experiments.fake import fake_policy
from freehand.sim import render
from freehand.sim.geometry import CROP_PX_PER_MM
from freehand.suites import episode_setup, load_suite

SEED = 10


@pytest.fixture
def l6cam():
    return episode_setup(load_suite("legacy-objective-v0"), SEED, "L6cam")


def _ink_centroid_mm(seed, squares, sq, W, stroke):
    """Where the crop SHOWS a short stroke, in the page mm its grid claims (origin + px / 12)."""
    blank, org, _ = render.crop_view(seed, squares, [], sq, W)
    inked, org2, _ = render.crop_view(seed, squares, [stroke], sq, W)
    assert org == org2
    diff = np.abs(inked.astype(int) - blank.astype(int)).sum(axis=2) > 60
    ys, xs = np.nonzero(diff)
    assert len(xs) > 20, "the stroke is not visible in the crop"
    return np.array([org[0] + xs.mean() / CROP_PX_PER_MM, org[1] + ys.mean() / CROP_PX_PER_MM])


def test_crop_shows_ink_where_the_moved_camera_shows_it(l6cam):
    st = l6cam
    st.perturbation.start(1)
    W = np.asarray(st.perturbation.warp, float)
    assert W.shape == (2, 3)
    sq = st.squares[st.perturb_after]                          # the first post-change square
    c = np.mean(np.asarray(sq.open_ends, float), axis=0)
    stroke = np.linspace(c - [4.0, 0.0], c + [4.0, 0.0], 40)   # a short horizontal mark at the square's open side
    true_mid = stroke.mean(axis=0)
    shown_mid = W[:, :2] @ true_mid + W[:, 2]                  # where the stale-rectified photo displays it
    gap = np.linalg.norm(shown_mid - true_mid)
    assert gap > 1.5                                           # the camera bump is large enough to tell apart
    seen = _ink_centroid_mm(st.seed, st.squares, sq, W, stroke)
    assert np.linalg.norm(seen - shown_mid) < 0.3              # the crop agrees with the main photo ...
    assert np.linalg.norm(seen - true_mid) > gap - 0.3         # ... not with the true page (the old bypass)
    unwarped = _ink_centroid_mm(st.seed, st.squares, sq, None, stroke)
    assert np.linalg.norm(unwarped - true_mid) < 0.3           # sanity: without the bump the crop is the page


def test_world_crop_follows_the_change(l6cam):
    st = l6cam
    w = World(st.seed, st.squares, st.perturbation, st.perturb_after)
    sq = st.squares[0]
    before, org0, _ = w.crop(sq)
    plain, orgp, _ = render.crop_view(st.seed, st.squares, [], sq, None)
    assert org0 == orgp and np.array_equal(before, plain)       # before the change: the plain crop
    for q in st.squares[:st.perturb_after]:
        w.end_square(q.idx)
    assert w.warp is not None
    post = st.squares[st.perturb_after]
    after, org1, _ = w.crop(post)
    warped, orgw, _ = render.crop_view(st.seed, st.squares, [], post, w.warp)
    unwarped, _, _ = render.crop_view(st.seed, st.squares, [], post, None)
    assert org1 == orgw and np.array_equal(after, warped)
    assert not np.array_equal(after, unwarped)


class _CropPxAgent(Agent):
    """A model-like agent that answers in crop pixels (the offline fake policy) and records every request."""
    is_model = True
    name = "crop-px-probe"

    def __init__(self, squares, seed):
        self.policy = fake_policy(squares, seed)
        self.requests = []

    def act(self, obs):
        self.requests.append(obs["messages"])
        return {"text": self.policy(obs["system"], obs["messages"]), "thoughts": None, "usage": {}, "cost": 0.0,
                "cost_original": 0.0, "cached": False}


def test_crop_px_episode_places_post_change_crops_on_the_warped_square(l6cam):
    st = l6cam
    squares = st.squares[:st.perturb_after + 2]
    agent = _CropPxAgent(squares, st.seed)
    cfg = EpisodeConfig(seed=st.seed, squares=squares, perturbation=st.perturbation, perturb_after=st.perturb_after,
                        arm=PRESETS["informed_objective"], output_mode="crop_px", cap_strokes=3, cap_turns=3)
    sink = MemorySink()
    s = run_episode(agent, cfg, sink)
    assert s["status"] == "complete"
    W = st.perturbation.warp
    by_sq = {}
    for t in sink.turns:
        by_sq.setdefault(t["square"], t)
    for q in squares:
        t = by_sq[q.idx]
        post = q.idx > st.perturb_after
        _, expect, _ = render.crop_view(st.seed, squares, [], q, W if post else None)
        assert tuple(t["crop"]["origin_mm"]) == expect, (q.idx, post)
        assert t["change_active"] == post
    # the crop is sent to the model with its page-mm frame, and the commanded pixels are converted back to page mm
    t = next(t for t in sink.turns if t["square"] > st.perturb_after and t.get("stroke") and not t["clamps"])
    org = np.array(t["crop"]["origin_mm"])
    px = np.array(t["command_crop_px"], float)
    assert np.allclose(np.array(t["command"], float), org + px / CROP_PX_PER_MM, atol=1e-9)
