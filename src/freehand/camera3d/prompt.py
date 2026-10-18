"""What a model is told in Freehand A, and the one tool it acts through. The text lives in prompts/v1/camera3d/.

The model draws with a `draw` tool call. Every call also carries `camera_estimate`: which page point the model believes
appears at each corner of the photo. Four corners fix a homography, so the estimate is the model's full belief about
the camera, recorded every turn (it is not scored and does not affect the stroke).
"""

from __future__ import annotations

import string
import tomllib
from functools import lru_cache

from freehand import prompts
from freehand.camera3d.pose import FRAME
from freehand.sim.geometry import REGION, TOL_MM

VERSION = "v1/camera3d"
CORNERS = ("top_left", "top_right", "bottom_right", "bottom_left")
CORNER_PX = {"top_left": (0, 0), "top_right": (FRAME, 0), "bottom_right": (FRAME, FRAME), "bottom_left": (0, FRAME)}


@lru_cache(maxsize=1)
def _phrases() -> dict[str, str]:
    with open(prompts.PROMPTS_DIR / VERSION / "turn.toml", "rb") as f:
        return tomllib.load(f)


def phrase(key: str, **values) -> str:
    return string.Template(_phrases()[key]).substitute({k: str(v) for k, v in values.items()})


def _point(description: str) -> dict:
    return {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2, "description": description}


def draw_tool() -> dict:
    corner = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}
    return {
        "type": "function",
        "function": {
            "name": "draw",
            "description": prompts.text(f"{VERSION}/tool_draw"),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": _point(phrase("start")),
                    "end": _point(phrase("end")),
                    "camera_estimate": {
                        "type": "object",
                        "description": prompts.render(f"{VERSION}/tool_camera_estimate", frame=FRAME),
                        "properties": {c: corner for c in CORNERS},
                        "required": list(CORNERS),
                    },
                    "note": {"type": "string", "description": phrase("note")},
                },
                "required": ["start", "end", "camera_estimate", "note"],
            },
        },
    }


DRAW_TOOL = draw_tool()


def system_prompt(n_squares: int, cap_strokes: int) -> str:
    x_lo, y_lo, x_hi, y_hi = REGION
    return prompts.render(
        f"{VERSION}/system",
        frame=FRAME,
        x_lo=f"{x_lo:g}",
        x_hi=f"{x_hi:g}",
        y_lo=f"{y_lo:g}",
        y_hi=f"{y_hi:g}",
        n_squares=n_squares,
        tol=f"{TOL_MM:g}",
        cap_strokes=cap_strokes,
    )


def first_message() -> str:
    return prompts.text(f"{VERSION}/first_message")


def state_text(world, last) -> str:
    """The text that comes with each new photo: what just happened, where the episode stands, and the log of every
    commanded stroke (older photos are dropped from the conversation; this log is not)."""
    lines = []
    if last is not None:
        lines.append(phrase("stroke_closed" if last.closed else "stroke_open", stroke=last.stroke, square=last.square))
        if last.clamped:
            lines.append(phrase("clamped"))
    if world.done:
        lines.append(phrase("all_done"))
        return "\n".join(lines)
    sq = world.square
    lines.append(
        phrase("current", square=sq.idx, n=len(world.squares), attempt=world.attempts + 1, cap=world.spec.cap_strokes)
    )
    log = [
        phrase(
            "log_line",
            stroke=s.stroke,
            square=s.square,
            x1=f"{s.cmd[0][0]:.1f}",
            y1=f"{s.cmd[0][1]:.1f}",
            x2=f"{s.cmd[1][0]:.1f}",
            y2=f"{s.cmd[1][1]:.1f}",
            verdict="closed" if s.closed else "open",
        )
        for s in world.strokes
    ]
    lines.append(phrase("log_header") + "\n" + "\n".join(log))
    return "\n".join(lines)
