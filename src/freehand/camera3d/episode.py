"""Run one Freehand A episode and write its record.

<out>/
  episode.json     spec, both camera poses, the squares, and one entry per turn: the stroke, what it hit, the
                   belief (4 corner points), its aim error against the camera the agent was looking at, the note,
                   reasoning, usage and cost
  photos/NNN.png   the photo the agent saw before stroke NNN+1 (000 = the first photo; the last one is after the end)
  conversation.json  (models) the whole conversation, images as sha256
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from freehand.camera3d.belief import H_from_corners, aim_error_mm, turns_to_match
from freehand.camera3d.env import Spec, World
from freehand.llm.errors import BudgetExceeded, ProviderError

MAX_TURNS_FACTOR = 1  # turns are bounded by squares x strokes per square; decisions without a stroke end the episode


def png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def run_episode(spec: Spec, agent, out: Path, log=print) -> dict:
    out = Path(out)
    (out / "photos").mkdir(parents=True, exist_ok=True)
    world = World(spec)
    turns: list[dict] = []
    status, error = "complete", None
    photo = world.photo()
    cv2.imwrite(str(out / "photos" / "000.png"), photo)
    last = None
    t0 = time.time()
    while not world.done:
        pose_no, H = world.pose_no, world.H
        png = png_bytes(photo)
        try:
            d = agent.act(world, png, last)
        except BudgetExceeded as e:
            status, error = "capped", str(e)
            break
        except ProviderError as e:
            status, error = "error", str(e)
            break
        if d.start is None:
            turns.append({"turn": len(turns) + 1, "stroke": None, "problems": d.problems, "cost": d.cost})
            status, error = "stopped", "; ".join(d.problems) or "no stroke"
            break
        Hb = H_from_corners(d.belief) if d.belief is not None else None
        err = aim_error_mm(H, Hb)
        res = world.draw(d.start, d.end)
        photo = world.photo()
        cv2.imwrite(str(out / "photos" / f"{res.stroke:03d}.png"), photo)
        turns.append(
            {
                "turn": len(turns) + 1,
                "stroke": asdict(res),
                "pose": pose_no,
                "belief": d.belief,
                "belief_valid": Hb is not None,
                "aim_error_mm": None if not np.isfinite(err) else round(err, 3),
                "photo_sha256": hashlib.sha256(png).hexdigest(),  # the image the agent saw for this stroke
                "note": d.note,
                "reasoning": d.reasoning,
                "problems": d.problems,
                "usage": d.usage,
                "cost": round(d.cost, 6),
                "raw": d.raw,
            }
        )
        last = res
        e_txt = "  -" if not np.isfinite(err) else f"{err:6.1f}"
        log(
            f"[{getattr(agent, 'name', '?')} s{spec.seed}] stroke {res.stroke:2d} sq {res.square} try {res.attempt} "
            f"{'CLOSED' if res.closed else 'open  '} belief err {e_txt} mm  ${sum(t.get('cost', 0) for t in turns):.3f}"
        )
    rec = {
        "agent": getattr(agent, "name", "?"),
        "is_model": getattr(agent, "is_model", False),
        "model": getattr(getattr(agent, "chat", None), "spec", None) and agent.chat.spec.to_manifest(),
        "spec": spec.to_dict(),
        "poses": [p.to_dict() for p in world.poses],
        "squares": [s.to_dict() for s in world.squares],
        "status": status,
        "error": error,
        "outcomes": {str(k): v for k, v in world.outcomes.items()},
        "turns": turns,
        "elapsed_s": round(time.time() - t0, 1),
    }
    rec["summary"] = summarize(rec)
    (out / "episode.json").write_text(json.dumps(rec, indent=1))
    if hasattr(agent, "conv"):
        (out / "conversation.json").write_text(json.dumps(agent.conv.neutral(), indent=1))
    return rec


def summarize(rec: dict) -> dict:
    """Headline numbers of one episode: first-stroke closes and belief matching, before and after the move."""
    spec = rec["spec"]
    m = spec["move_after"]
    strokes = [t for t in rec["turns"] if t.get("stroke")]
    errs = [t["aim_error_mm"] if t["aim_error_mm"] is not None else float("inf") for t in strokes]
    pre = [i for i, t in enumerate(strokes) if t["pose"] == 1]
    post = [i for i, t in enumerate(strokes) if t["pose"] == 2]
    outcomes = {int(k): v for k, v in rec["outcomes"].items()}

    def firsts(lo, hi):
        return sum(1 for k, v in outcomes.items() if lo <= k <= hi and v == "first")

    n = spec["n_squares"]
    if spec.get("fresh"):  # every square is at the moved camera; report them as the "after the move" segment
        n, m = n - m, 0
        return {
            "status": rec["status"],
            "strokes": len(strokes),
            "cost": round(sum(t.get("cost", 0) for t in rec["turns"]), 4),
            "squares_closed": sum(1 for v in outcomes.values() if v in ("first", "closed")),
            "first_try_before_move": None,
            "first_try_after_move": firsts(1, n),
            "abandoned": sum(1 for v in outcomes.values() if v == "abandoned"),
            "aim_error_mm": [None if not np.isfinite(e) else round(e, 2) for e in errs],
            "match_turn_cold": None,
            "match_turn_after_move": turns_to_match(errs) if errs else None,
            "first_error_after_move": None if not errs or not np.isfinite(errs[0]) else round(errs[0], 2),
        }
    return {
        "status": rec["status"],
        "strokes": len(strokes),
        "cost": round(sum(t.get("cost", 0) for t in rec["turns"]), 4),
        "squares_closed": sum(1 for v in outcomes.values() if v in ("first", "closed")),
        "first_try_before_move": firsts(1, m) if m else firsts(1, n),
        "first_try_after_move": firsts(m + 1, n) if m else None,
        "abandoned": sum(1 for v in outcomes.values() if v == "abandoned"),
        "aim_error_mm": [None if not np.isfinite(e) else round(e, 2) for e in errs],
        "match_turn_cold": turns_to_match([errs[i] for i in pre]) if pre else None,
        "match_turn_after_move": turns_to_match([errs[i] for i in post]) if post else None,
        "first_error_after_move": (None if not post or not np.isfinite(errs[post[0]]) else round(errs[post[0]], 2)),
    }
