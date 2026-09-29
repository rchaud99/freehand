"""One episode: close the squares one at a time, one stroke per turn, under a silent change after square P.

    for each square:                          (at most cap_strokes strokes / cap_turns turns)
        render what the agent sees -> build the request (arm) -> agent.act -> parse the stroke
        -> clamp -> land it (through the rule once the change is on) -> closure check -> log the turn
    after square P: the change switches on

The loop is deliberately small: rendering and landing live in `World`, prompt assembly in `agents.prompting`, the
record layout in `episode.records`, IO in the sink. Behaviour (request contents, stroke numbering, seeds, closure,
stop rules) is the historical `run_episode`'s, which the parity tests pin.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any, Protocol

import numpy as np

from freehand.agents import prompting, prompts
from freehand.agents.base import Agent
from freehand.agents.reference.numeric import numeric_observation
from freehand.episode import records
from freehand.episode.actions import clamp, crop_px_to_mm, first_stroke, parse_json
from freehand.episode.config import EpisodeConfig
from freehand.episode.mentions import mention_regex
from freehand.episode.world import World
from freehand.llm.errors import BudgetExceeded, MissingKeyError, ProviderError
from freehand.llm.messages import sha256_hex
from freehand.sim import closure, png_bytes, poly_len

INK_LOG_DECIMALS = 3


class EpisodeCostCapReached(RuntimeError):
    """The episode's own cost cap was reached (status `capped`: inconclusive, not a failure)."""


class Sink(Protocol):
    save_images: bool

    def image(self, name: str, img: np.ndarray) -> None: ...
    def turn(self, rec: dict) -> None: ...
    def finish(self, summary: dict) -> None: ...


class MemorySink:
    """Keeps everything in memory (tests, parity checks, dry runs)."""

    def __init__(self, save_images: bool = False):
        self.save_images = save_images
        self.images: dict[str, np.ndarray] = {}
        self.turns: list[dict] = []
        self.summary: dict | None = None

    def image(self, name, img):
        self.images[name] = img

    def turn(self, rec):
        self.turns.append(rec)

    def finish(self, summary):
        self.summary = summary


def classify_stop(e: BaseException) -> tuple[str, str]:
    """(status, stop kind) for an exception that ended an episode early."""
    if isinstance(e, EpisodeCostCapReached):
        return "capped", "episode_cost_cap"
    if isinstance(e, BudgetExceeded):
        return "stopped", "budget"
    if isinstance(e, (ProviderError, MissingKeyError)):
        return "stopped", "provider"
    return "error", "exception"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def run_episode(agent: Agent, cfg: EpisodeConfig, sink: Sink) -> dict[str, Any]:
    """Run one episode; everything goes to `sink`. Returns the summary (also passed to sink.finish)."""
    if not cfg.render and agent.is_model:
        raise ValueError("model episodes need rendered observations (render=True)")
    arm = cfg.arm
    memory = arm.memory and agent.is_model
    world = World(cfg.seed, cfg.squares, cfg.perturbation, cfg.perturb_after)
    if cfg.output_mode == "crop_px" and world.view_kind != "rect":
        raise ValueError("crop_px output mode needs the rectified view (not the camera track)")
    extra = "\n\n".join(x for x in (cfg.perturbation.prompt_extra, arm.block_text()) if x)
    system, prompt_ids = prompting.build_system(
        prompting.SystemPromptSpec(
            view=world.view_kind,
            memory=memory,
            disclosure=arm.disclosure,
            k_prev=arm.k_prev,
            output_mode=cfg.output_mode if agent.is_model else "page_mm",
            tol=cfg.tol,
            cap_strokes=cfg.cap_strokes,
            extra=extra,
            version=arm.prompt_version,
        )
    )
    convo = prompting.Conversation(arm.k_prev, arm.prompt_version)
    mention_rx = mention_regex(cfg.perturbation.family)
    history: list[str] = []
    strokes: list[dict] = []
    sq_results: list[dict] = []
    turn_log: list[dict] = []
    turn = 0
    spent = cost = cost_original = 0.0
    last_result: str | None = None
    stop: dict | None = None
    status = "complete"
    t_start, started = time.time(), _now()
    use_crop = cfg.output_mode == "crop_px" and cfg.render and agent.is_model
    try:
        for sq in cfg.squares:
            used = tries = 0
            closed = False
            while used < cfg.cap_strokes and tries < cfg.cap_turns:
                if cfg.cost_cap is not None and spent >= cfg.cost_cap:
                    raise EpisodeCostCapReached(f"episode cost cap ${cfg.cost_cap:.2f} reached")
                turn += 1
                tries += 1
                # ---- observe
                view = world.render(sq) if cfg.render else None
                png = png_bytes(view) if view is not None else b""
                img_name = f"t{turn:03d}.png"
                if view is not None and sink.save_images:
                    sink.image(img_name, view)
                state, state_compact = prompting.state_block(
                    world.view_kind,
                    turn,
                    sq.idx,
                    cfg.n_squares,
                    used,
                    cfg.cap_strokes,
                    history,
                    arm.show_history,
                    last_result,
                    arm.history_landed,
                    arm.prompt_version,
                )
                if arm.feedback == "image_numeric":
                    fb = prompting.numeric_feedback_text(numeric_observation(sq.open_ends, strokes), arm.prompt_version)
                    state += fb
                    state_compact += fb
                crop_info, crop_parts = None, []
                if use_crop:
                    cimg, corg, side = world.crop(sq)
                    cname = f"t{turn:03d}_crop.png"
                    if sink.save_images:
                        sink.image(cname, cimg)
                    crop_info = {"origin_mm": list(corg), "side_mm": side, "image": cname}
                    crop_parts = prompting.crop_parts(sq.idx, cimg, corg, side, cname, arm.prompt_version)
                if memory:
                    msgs = convo.request(turn, png, img_name, crop_parts, state)
                    prev_images = [n for _, n in convo.previous_views()]
                else:
                    msgs = prompting.stateless_request(png, img_name, crop_parts, state)
                    prev_images = []
                n_history_turns, notepad_in = len(convo.turns), convo.notepad
                obs = {
                    "system": system,
                    "messages": msgs,
                    "priv": {
                        "open_ends": sq.open_ends,
                        "map": world.current_map(),
                        "H": world.H,
                        "H_old": world.H_old,
                        "strokes": strokes,
                        "scenario": cfg.perturbation,
                        "scen_on": world.scen_on,
                        "next_stroke": world.stroke_no + 1,
                        "perturb_stroke": world.perturb_stroke,
                    },
                }
                # ---- act
                rep = agent.act(obs)
                # The episode cap counts what each call cost when it was made, so a replay from the cache or a
                # resume stops exactly where the original did (the historical loop counted only new spend).
                spent += rep.get("cost_original", rep.get("cost", 0)) or 0
                cost += rep.get("cost", 0) or 0
                cost_original += rep.get("cost_original", 0) or 0
                try:
                    action = parse_json(rep["text"])
                    cmd = first_stroke(action)
                except (ValueError, json.JSONDecodeError) as e:
                    action, cmd = {"action": "error", "note": f"unparseable: {e}"}, None
                cmd_crop_px = None
                if cmd is not None and crop_info is not None:
                    cmd_crop_px = cmd
                    cmd = crop_px_to_mm(cmd, crop_info["origin_mm"])
                note = str(action.get("note", ""))
                mem_out = prompting.trim_words(action.get("memory", ""), version=arm.prompt_version) if memory else ""
                mentions = {
                    "note": bool(mention_rx.search(note)),
                    "memory": bool(mention_rx.search(mem_out)),
                    "reasoning": bool(mention_rx.search(rep.get("thoughts") or "")),
                }
                if memory:
                    convo.record(turn, state_compact, rep["text"], rep.get("thoughts"), view, mem_out)
                images = [{"name": img_name, "sha256": sha256_hex(png), "detail": "high"}] if view is not None else []
                if crop_parts:
                    assert crop_info is not None
                    images.append(
                        {"name": crop_info["image"], "sha256": sha256_hex(crop_parts[1]["png"]), "detail": "high"}
                    )
                rec = records.turn_record(
                    turn=turn,
                    square=sq.idx,
                    attempt=used + 1,
                    change_active=world.change_active,
                    view_H=world.view_H_record(),
                    state=state,
                    images=images,
                    n_history_turns=n_history_turns,
                    prev_images=prev_images,
                    notepad_in=notepad_in,
                    reply=rep,
                    is_model=agent.is_model,
                    action=action,
                    crop=crop_info,
                    command_crop_px=cmd_crop_px,
                    mentions=mentions,
                )
                turn_log.append(rec)
                if cmd is None:
                    sink.turn(rec)
                    last_result = prompts.phrase("no_valid_stroke", arm.prompt_version)
                    continue
                # ---- land
                cmd, clamps = clamp(cmd)
                used += 1
                ink = world.land(cmd)
                ok, errs, dev = closure(ink, sq.open_ends, cfg.tol)
                if hasattr(agent, "observe"):
                    agent.observe(cmd, [ink[0], ink[-1]])
                srec = {
                    "stroke": world.stroke_no,
                    "turn": turn,
                    "square": sq.idx,
                    "attempt": used,
                    "cmd": cmd,
                    "ink_ends": [ink[0].tolist(), ink[-1].tolist()],
                    "closed": ok,
                    "end_err_mm": errs,
                    "straight_dev_mm": dev,
                    "post": world.perturb_stroke is not None,
                    "compensation_frac": world.compensation_frac(cmd, sq.open_ends),
                    "clamps": clamps,
                }
                strokes.append(srec)
                # ink length as the historical metrics measured it: on the polyline logged at 0.001 mm
                records.add_stroke(rec, srec, poly_len(np.round(ink, INK_LOG_DECIMALS)))
                history.append(
                    prompting.history_entry(
                        sq.idx,
                        cmd,
                        prompting.measured_ends(ink, cfg.seed, world.stroke_no) if arm.history_landed else None,
                        arm.prompt_version,
                    )
                )
                sink.turn(rec)
                last_result = None
                if ok:
                    closed = True
                    break
            sq_results.append(
                {
                    "square": sq.idx,
                    "closed": closed,
                    "strokes": used,
                    "turns": tries,
                    "first_try": closed and used == 1,
                    "post": sq.idx > cfg.perturb_after,
                }
            )
            last_result = prompts.phrase(
                "square_closed" if closed else "square_abandoned", arm.prompt_version, idx=sq.idx
            )
            world.end_square(sq.idx)
    except Exception as e:  # budget stop, cost cap, provider failure, or a bug (status "error")
        status, kind = classify_stop(e)
        stop = {"kind": kind, "message": f"{type(e).__name__}: {e}"}
    if cfg.render and sink.save_images:
        for name, img in world.final_views().items():
            sink.image(f"{name}.png", img)
    summary = records.summary(
        cfg=cfg,
        agent=agent,
        world=world,
        system=system,
        prompt_ids=prompt_ids,
        memory=memory,
        sq_results=sq_results,
        strokes=strokes,
        turns=turn,
        status=status,
        stop=stop,
        cost=cost,
        cost_original=cost_original,
        started=started,
        ended=_now(),
        seconds=time.time() - t_start,
        turn_records=turn_log,
    )
    sink.finish(summary)
    return summary
