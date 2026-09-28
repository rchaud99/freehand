"""The layout of turn records (episode.jsonl lines) and of the episode summary (summary.json).

docs/results_format.md documents every field; results/schemas/*.json are the machine-checkable JSON Schemas.
"""
from __future__ import annotations

from typing import Any

from freehand import __version__
from freehand.agents.base import Agent
from freehand.episode.config import EpisodeConfig
from freehand.llm.messages import sha256_hex
from freehand.metrics import episode_metrics, ink_metrics
from freehand.scoring import first_try_summary, later_first_try, squares_to_run

TURN_SCHEMA = "freehand.turn/1"
SUMMARY_SCHEMA = "freehand.episode_summary/1"
REPLY_FIELDS = ("text", "thoughts", "usage", "cost", "cost_original", "cached", "route", "model_version",
                "latency_s", "cache_key", "replayed")


def turn_record(*, turn: int, square: int, attempt: int, change_active: bool, view_H, state: str,
                images: list[dict], n_history_turns: int, prev_images: list[str], notepad_in: str, reply: dict,
                is_model: bool, action: dict, crop: dict | None, command_crop_px, mentions: dict) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "turn": turn, "square": square, "attempt": attempt, "change_active": change_active, "view_H": view_H,
        "prompt": {"state": state, "images": images, "n_history_turns": n_history_turns,
                   "prev_images": prev_images, "notepad_in": notepad_in},
        "reply": {k: reply.get(k) for k in REPLY_FIELDS if k in reply},
        "action": action, "crop": crop, "command_crop_px": command_crop_px,
        "command": None, "clamps": [], "stroke": None, "mentions": mentions,
    }
    if is_model:
        rt = (reply.get("usage") or {}).get("reasoning_tokens")
        rec["reasoning_tokens"] = rt
        rec["zero_reasoning"] = not rt
    return rec


def add_stroke(rec: dict, srec: dict, ink_len_mm: float) -> None:
    rec["command"] = srec["cmd"]
    rec["clamps"] = srec["clamps"]
    rec["stroke"] = {"n": srec["stroke"], "ends": srec["ink_ends"], "ink_len_mm": ink_len_mm,
                     "closed": srec["closed"], "end_err_mm": srec["end_err_mm"],
                     "straight_dev_mm": srec["straight_dev_mm"], "post": srec["post"],
                     "compensation_frac": srec["compensation_frac"]}


def agent_block(agent: Agent) -> dict[str, Any]:
    adapter = getattr(agent, "adapter", None) or getattr(getattr(agent, "live", None), "adapter", None)
    out = {"name": agent.name, "kind": "model" if agent.is_model else "reference"}
    if adapter is not None:
        out.update({"model": adapter.model, "provider": adapter.provider, "route": adapter.route,
                    "settings": adapter.settings})
    return out


def summary(*, cfg: EpisodeConfig, agent: Agent, world, system: str, prompt_ids: list[str], memory: bool,
            sq_results: list[dict], strokes: list[dict], turns: int, status: str, stop: dict | None, cost: float,
            cost_original: float, started: str, ended: str, seconds: float,
            turn_records: list[dict]) -> dict[str, Any]:
    p = cfg.perturbation
    ep = {"perturb_after": cfg.perturb_after, "n_squares": cfg.n_squares, "squares_result": sq_results,
          "strokes": strokes, "perturb_stroke": world.perturb_stroke}
    ft = first_try_summary(ep)
    later = later_first_try(ep)
    out: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "freehand_version": __version__,
        "labels": dict(cfg.labels),
        "agent": agent_block(agent),
        "seed": cfg.seed,
        "perturbation": p.describe(),
        "family": p.family,
        "arm": {**cfg.arm.to_dict(), "memory_effective": memory},
        "output_mode": cfg.output_mode if agent.is_model else None,
        "setup": {"n_squares": cfg.n_squares, "perturb_after": cfg.perturb_after,
                  "perturb_stroke": world.perturb_stroke, "cap_strokes": cfg.cap_strokes,
                  "cap_turns": cfg.cap_turns, "tol_mm": cfg.tol, "view": world.view_kind,
                  "cost_cap": cfg.cost_cap, "rendered": cfg.render,
                  "square_ids": [s.idx for s in cfg.squares],
                  "system_prompt": system, "system_prompt_sha256": sha256_hex(system.encode()),
                  "prompt_components": prompt_ids},
        "status": status,
        "stop": stop,
        "complete": status == "complete" and len(sq_results) == cfg.n_squares,
        "turns": turns,
        "squares_result": sq_results,
        "strokes": strokes,
        "n_squares": cfg.n_squares,
        "perturb_after": cfg.perturb_after,
        "perturb_stroke": world.perturb_stroke,
        "scores": {"first_try": ft, "later_first_try": later,
                   "squares_to_3_in_a_row": squares_to_run(ft["curve"])},
        "cost": {"usd": round(cost, 6), "usd_original": round(cost_original, 6)},
        "timing": {"started": started, "ended": ended, "seconds": round(seconds, 2)},
    }
    out["metrics"] = episode_metrics(out, turn_records)
    out["ink"] = ink_metrics(turn_records, cfg.perturb_after, cost_original)
    return out
