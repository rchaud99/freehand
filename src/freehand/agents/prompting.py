"""Assembling what the model receives: the system prompt, the per-turn state block and the request messages.

Everything is composed from the versioned text in `freehand/prompts/v1`; the composition rules are the historical
ones, so the same arm and turn produce byte-identical requests (and so the same request-cache keys).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from freehand import prompts, seeding
from freehand.agents.arms import MEMORY_WORDS, NOTEPAD_KEEP_WORDS, REASONING_CHARS
from freehand.llm.messages import Message
from freehand.sim.geometry import REGION, TOL_MM
from freehand.sim.render import png_bytes

MEASURE_SD_MM = 0.15  # noise of the landed ends reported to the stateless-numeric arm (and of the estimators)
SMALL_VIEW_SCALE = 0.5  # earlier photos in the memory arm are downscaled by this


@dataclass(frozen=True)
class SystemPromptSpec:
    view: str  # "rect" (calibrated gridded view) | "raw" (Freehand A camera)
    memory: bool
    disclosure: str = "silent"
    k_prev: int = 2
    output_mode: str = "page_mm"  # page_mm | crop_px
    tol: float = TOL_MM
    cap_strokes: int = 12
    extra: str = ""  # perturbation line (L7) + arm blocks, already joined
    version: str = prompts.DEFAULT_VERSION


def _fmt_tol(tol: float | None) -> str:
    return f"{tol or TOL_MM:g}"


def build_system(spec: SystemPromptSpec) -> tuple[str, list[str]]:
    """(system prompt, ids of the components used, in order)."""
    v = spec.version
    if spec.disclosure == "scaffolded" and not spec.memory:
        raise ValueError("scaffolded disclosure needs the memory notepad")
    if spec.output_mode not in ("page_mm", "crop_px") or (spec.output_mode == "crop_px" and spec.view != "rect"):
        raise ValueError(f"output_mode {spec.output_mode} not supported for view {spec.view}")
    ids: list[str] = []

    def t(pid: str, **vals) -> str:
        ids.append(f"{v}/{pid}")
        return prompts.render(f"{v}/{pid}", **vals) if vals else prompts.text(f"{v}/{pid}")

    plotter = t("system/plotter")
    if spec.view == "rect":
        vtext = (
            t("system/view_rect")
            + " "
            + (t("system/crop_px") if spec.output_mode == "crop_px" else t("system/units_mm"))
        )
    else:
        vtext = t("system/view_raw")
    task = t("system/task", tol=_fmt_tol(spec.tol), cap_strokes=spec.cap_strokes)
    ctx = t("system/context_memory", k_prev=spec.k_prev) if spec.memory else ""
    disclosure = t(f"disclosure/{spec.disclosure}") if spec.disclosure != "silent" else ""
    fmt_id = (
        "system/format_"
        + ("memory" if spec.memory else "stateless")
        + ("_crop_px" if spec.output_mode == "crop_px" else "")
    )
    fmt = t(fmt_id, memory_words=MEMORY_WORDS) if spec.memory else t(fmt_id)
    respond = t("system/respond") + "\n" + fmt
    region = t("system/region_rect" if spec.view == "rect" else "system/region_raw")
    parts = [plotter, vtext, task, spec.extra, ctx, disclosure, respond, region]
    return "\n\n".join(p for p in parts if p), ids


# ---------------------------------------------------------------- the state block
def fmt_stroke(pts) -> str:
    return " -> ".join(f"({x:.1f},{y:.1f})" for x, y in pts)


def measured_ends(ink, seed: int, stroke_no: int) -> np.ndarray:
    """The ink's two ends as the harness reports them: true landing + measurement noise (MEASURE_SD per axis),
    seeded by (page, stroke) so reruns and paired episodes match."""
    noise = seeding.rng(seed, "measure.landed", stroke_no).normal(0, MEASURE_SD_MM, (2, 2))
    return np.array([ink[0], ink[-1]], float) + noise


def history_entry(sq_idx: int, cmd, landed=None, version: str = prompts.DEFAULT_VERSION) -> str:
    s = prompts.phrase("history_entry", version, idx=sq_idx, command=fmt_stroke(cmd))
    if landed is not None:
        s += prompts.phrase("history_landed", version, landed=fmt_stroke(landed))
    return s


def state_block(
    view: str,
    turn: int,
    sq_idx: int,
    n_squares: int,
    used: int,
    cap_strokes: int,
    history: list[str],
    show_history: bool,
    last_result: str | None,
    landed: bool = False,
    version: str = prompts.DEFAULT_VERSION,
) -> tuple[str, str]:
    """(full state block, compact version without the stroke history for the memory transcript)."""
    x_lo, y_lo, x_hi, y_hi = REGION
    ph = prompts.phrases(version)
    s = (ph["state_raw_prefix"] if view == "raw" else "") + prompts.phrase(
        "state_head",
        version,
        turn=turn,
        x_lo=f"{x_lo:.0f}",
        x_hi=f"{x_hi:.0f}",
        y_lo=f"{y_lo:.0f}",
        y_hi=f"{y_hi:.0f}",
        idx=sq_idx,
        n_squares=n_squares,
        used=used,
        cap_strokes=cap_strokes,
    )
    if last_result:
        s += " " + last_result
    full = s
    if show_history:
        if history:
            full += " " + (ph["history_label_landed"] if landed else ph["history_label"]) + "; ".join(history)
        else:
            full += ph["no_history"]
    return full, s


def numeric_feedback_text(feedback: dict, version: str = prompts.DEFAULT_VERSION) -> str:
    return prompts.phrase("numeric_feedback", version, json=json.dumps(feedback, separators=(",", ":")))


def trim_words(s, n: int = NOTEPAD_KEEP_WORDS, version: str = prompts.DEFAULT_VERSION) -> str:
    w = str(s or "").split()
    return " ".join(w[:n]) + (prompts.phrase("notepad_truncated", version) if len(w) > n else "")


def crop_parts(
    sq_idx: int, crop_img: np.ndarray, origin, side: float, name: str, version: str = prompts.DEFAULT_VERSION
) -> list[dict]:
    ch, cw = crop_img.shape[:2]
    cap = prompts.phrase(
        "crop_caption",
        version,
        idx=sq_idx,
        x0=f"{origin[0]:.0f}",
        x1=f"{origin[0] + side:.0f}",
        y0=f"{origin[1]:.0f}",
        y1=f"{origin[1] + side:.0f}",
        w=cw,
        h=ch,
    )
    return [{"text": cap}, {"png": png_bytes(crop_img), "detail": "high", "name": name}]


# ---------------------------------------------------------------- requests
@dataclass
class Conversation:
    """The memory arm's running state: earlier (user, assistant) turns, small earlier photos, the notepad."""

    k_prev: int
    version: str = prompts.DEFAULT_VERSION
    turns: list[tuple[str, str]] = field(default_factory=list)
    small_views: list[tuple[bytes, str]] = field(default_factory=list)
    notepad: str = ""

    def previous_views(self) -> list[tuple[bytes, str]]:
        return self.small_views[-self.k_prev :] if self.k_prev > 0 else []

    def request(self, turn: int, png: bytes, img_name: str, extra_parts: list[dict], state: str) -> list[Message]:
        msgs: list[Message] = []
        for u, a in self.turns:
            msgs += [{"role": "user", "parts": [{"text": u}]}, {"role": "assistant", "parts": [{"text": a}]}]
        if msgs:
            msgs[-1]["parts"][-1]["cache"] = True  # prompt-cache everything before this turn
        ph = prompts.phrases(self.version)
        cur: list[dict[str, Any]] = [
            {
                "text": prompts.phrase("memory_prefix", self.version, notepad=self.notepad)
                if self.notepad
                else ph["memory_empty"]
            }
        ]
        for spng, sname in self.previous_views():
            cur += [
                {"text": prompts.phrase("earlier_photo", self.version, name=sname)},
                {"png": spng, "detail": "low", "name": sname},
            ]
        cur += [
            {"text": prompts.phrase("current_photo", self.version, turn=turn)},
            {"png": png, "detail": "high", "name": img_name},
        ]
        cur += extra_parts + [{"text": state}]
        msgs.append({"role": "user", "parts": cur})
        return msgs

    def record(
        self,
        turn: int,
        state_compact: str,
        reply_text: str | None,
        thoughts: str | None,
        view: np.ndarray | None,
        memory_out: str,
    ) -> None:
        ph = prompts.phrases(self.version)
        th = (thoughts or "").strip()
        summary = ""
        if th:
            summary = (
                prompts.phrase("reasoning_summary", self.version, text=th[:REASONING_CHARS])
                + (ph["reasoning_ellipsis"] if len(th) > REASONING_CHARS else "")
                + "\n\n"
            )
        a_text = summary + (reply_text or ph["empty_reply"])
        self.turns.append((prompts.phrase("past_user", self.version, turn=turn, state=state_compact), a_text))
        if view is not None:
            small = cv2.resize(view, None, fx=SMALL_VIEW_SCALE, fy=SMALL_VIEW_SCALE, interpolation=cv2.INTER_AREA)
            self.small_views.append((png_bytes(small), f"turn {turn}"))
        if memory_out:
            self.notepad = memory_out


def stateless_request(png: bytes, img_name: str, extra_parts: list[dict], state: str) -> list[Message]:
    return [
        {"role": "user", "parts": [{"png": png, "detail": "high", "name": img_name}] + extra_parts + [{"text": state}]}
    ]
