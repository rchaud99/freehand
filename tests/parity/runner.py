"""Runs one parity case through the new package (the same cases the fixture recorded from the legacy code)."""
from __future__ import annotations

from freehand import perturbations as PT
from freehand.agents.arms import Arm
from freehand.agents.llm_agent import LLMAgent
from freehand.agents.reference import make_reference
from freehand.episode import EpisodeConfig, MemorySink, run_episode
from freehand.llm import FakeAdapter
from freehand.sim import A_AREA, A_SIZES, far_apart_order, make_page

from .fake_policy import make_policy

MAP_CONDS = {
    "none": {"type": "none"}, "offset10": {"type": "offset", "params": {"mm": 10.0}},
    "offset5": {"type": "offset", "params": {"mm": 5.0}}, "rot13": {"type": "rotation", "params": {"degrees": 13.0}},
    "rot6": {"type": "rotation", "params": {"degrees": 6.0}}, "rot3": {"type": "rotation", "params": {"degrees": 3.0}},
    "scale73": {"type": "scale", "params": {"factor": 0.73}}, "scale95": {"type": "scale", "params": {"factor": 0.95}},
    "cam_transfer": {"type": "camera_move", "params": {"mode": "transfer"}},
    "cam_fresh": {"type": "camera_move", "params": {"mode": "fresh"}},
    "cam_static": {"type": "camera_move", "params": {"mode": "static"}},
}
X_TYPES = {"arx": "command_memory", "mode": "latent_mirror", "warp": "smooth_warp", "identity": "identity"}
BLOCKS = {"": (), "objective": ("objective",), "informed": ("informed_objective",), "model_study": ("model_study",)}


def spec_for(c: dict) -> tuple[str, dict]:
    if c.get("cond"):
        return c["cond"], MAP_CONDS[c["cond"]]
    s = c.get("scenario")
    if s:
        if s["level"] == "L2rot":
            return "rot13", {"type": "L2_rotation"}
        return f"{s['level']}{s['variant']}", {"type": PT.LADDER_TYPES[s["level"]],
                                               "params": PT.ladder_params(s["level"], s["step"], s["variant"]),
                                               "step": s["step"] + 1}
    return c["x"], {"type": X_TYPES[c["x"]]}


def squares_for(c: dict, pert):
    if c["page"] == "objective":
        return far_apart_order(make_page(c["seed"], 20, size_range=(16.0, 28.0), gap=7.0))
    if c["page"] == "publication":
        return far_apart_order(make_page(c["seed"], 12, area=(55, 80, 160, 205), size_range=(12, 19), gap=4))
    if pert.family == "camera":
        return make_page(c["seed"], c["n"], area=A_AREA, size_range=A_SIZES, gap=8.0)
    return make_page(c["seed"], c["n"])


def run_case(c: dict, cache, budget) -> tuple[dict, list[dict]]:
    name, spec = spec_for(c)
    pert = PT.build(name, spec, c["seed"])
    sqs = squares_for(c, pert)
    P = c["P"]
    if pert.family == "camera":
        sqs, P = pert.episode_squares(sqs, P)
    if c["agent"] == "fake":
        pol = make_policy({s.idx: s.open_ends for s in sqs}, c["seed"], crop=c["output_mode"] == "crop_px")
        agent = LLMAgent(FakeAdapter(cache, budget, pol, salt=c["id"]), name="fake-llm")
    else:
        agent = make_reference(c["agent"], pert)
    arm = Arm("case", memory=c["memory"], k_prev=c["k_prev"], show_history=c["show_history"],
              history_landed=c["history_landed"], disclosure=c["disclosure"], blocks=BLOCKS[c["block"]],
              feedback=c["feedback"])
    cfg = EpisodeConfig(seed=c["seed"], squares=sqs, perturbation=pert, perturb_after=P, arm=arm,
                        output_mode="page_mm" if c["output_mode"] == "mm" else c["output_mode"],
                        cost_cap=c["cost_cap"])
    sink = MemorySink()
    summary = run_episode(agent, cfg, sink)
    return summary, sink.turns
