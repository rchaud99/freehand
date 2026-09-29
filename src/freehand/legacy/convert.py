"""Converting one historical episode (episode.json + turns.jsonl) to the new format (summary.json + episode.jsonl).

Nothing is recomputed that the log already states: commands, landed ends, closures, replies and costs are copied.
What IS recomputed with the current code: the first-try scores (the corrected scorer), the metrics and the ink
totals; the historical values are kept under `legacy.original_metrics` / `legacy.original_metrics_ink`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from freehand import __version__
from freehand.episode.records import REPLY_FIELDS, SUMMARY_SCHEMA
from freehand.llm.messages import sha256_hex
from freehand.metrics import episode_metrics, ink_metrics
from freehand.perturbations import from_legacy_episode
from freehand.scoring import first_try_summary, later_first_try, squares_to_run
from freehand.sim.plotter import poly_len

REFERENCE_AGENTS = {
    "oracle",
    "naive",
    "adaptive",
    "local_patcher",
    "local_broyden",
    "adaptive_library",
    "family_estimator",
}
LEGACY_CAP_TURNS = 14


def stop_of(stopped: str | None) -> tuple[str, dict | None]:
    """(status, stop) from a historical `stopped` string."""
    if not stopped:
        return "complete", None
    if "cost cap" in stopped:
        return "capped", {"kind": "episode_cost_cap", "message": stopped}
    if "BudgetExceeded" in stopped or "reservation cap" in stopped:
        return "stopped", {"kind": "budget", "message": stopped}
    if any(k in stopped for k in ("openrouter", "HTTP", "TransientError", "APIError", "gemini", "Timeout")):
        return "stopped", {"kind": "provider", "message": stopped}
    return "error", {"kind": "exception", "message": stopped}


def arm_of(ep: dict, folder: str) -> str:
    """The arm label of a historical episode (the objective-pilot folder names carry it; older runs encode it in
    flags)."""
    if ep["agent"] in REFERENCE_AGENTS:
        return "code"
    parts = folder.split("__")
    if len(parts) == 4 and parts[3].startswith("s") and parts[2] not in ("code",):
        return parts[2]
    arm = ep.get("disclosure", "silent")
    if not ep.get("memory", True):
        arm += "_nomem"
    if not ep.get("show_history", True):
        arm += "_nohist"
    if ep.get("feedback_mode", "image") != "image":
        arm = "study_" + ep["feedback_mode"] + ("" if arm == "silent" else "_" + arm)
    if ep.get("output_mode", "mm") == "crop_px":
        arm += "_crop_px"
    return arm


def _images(t: dict, ep_dir: Path, hash_images: bool) -> list[dict]:
    out = []
    names = [t.get("image")] + ([t["crop"]["image"]] if t.get("crop") else [])
    for name in names:
        if not name:
            continue
        f = ep_dir / name
        if not f.exists():  # headless runs name an image they never wrote
            continue
        sha = sha256_hex(f.read_bytes()) if hash_images else None
        out.append({"name": name, "sha256": sha, "detail": "high"})
    return out


def convert_turn(t: dict, ep_dir: Path, hash_images: bool, is_model: bool) -> dict[str, Any]:
    d = t.get("drawn")
    rec: dict[str, Any] = {
        "turn": t["turn"],
        "square": t["square"],
        "attempt": t["attempt"],
        "change_active": bool(t.get("change_active", False)),
        "view_H": t.get("view_H"),
        "prompt": {
            "state": t.get("state", ""),
            "images": _images(t, ep_dir, hash_images),
            "n_history_turns": t.get("n_history_turns", 0),
            "prev_images": t.get("prev_images", []),
            "notepad_in": t.get("notepad_in", ""),
        },
        "reply": {k: t["reply"].get(k) for k in REPLY_FIELDS if k in (t.get("reply") or {})},
        "action": t.get("action") or {},
        "crop": t.get("crop"),
        "command_crop_px": t.get("cmd_crop_px"),
        "command": d["cmd"] if d else None,
        "clamps": (d or {}).get("clamps", []),
        "stroke": None,
        "mentions": {
            "note": bool(t.get("mention_note")),
            "memory": bool(t.get("mention_memory")),
            "reasoning": bool(t.get("mention_reasoning")),
        },
    }
    if d:
        rec["stroke"] = {
            "n": d["stroke"],
            "ends": d["ink_ends"],
            "ink_len_mm": poly_len(t["ink"]) if t.get("ink") else 0.0,
            "closed": d["closed"],
            "end_err_mm": d.get("end_err_mm"),
            "straight_dev_mm": d.get("straight_dev_mm", 0.0),
            "post": d.get("post", False),
            "compensation_frac": d.get("compensation_frac"),
        }
    if is_model:
        rec["reasoning_tokens"] = t.get("reasoning_tokens")
        rec["zero_reasoning"] = bool(t.get("zero_reasoning", not t.get("reasoning_tokens")))
    return rec


def convert_episode(
    ep_dir: Path, source: str, run_name: str, suite_match: dict | None, hash_images: bool = True
) -> tuple[dict, list[dict], list[dict] | None]:
    """(summary, turn records, page or None). `page` is returned when no suite reproduces the logged squares."""
    ep_raw = (ep_dir / "episode.json").read_bytes()
    ep = json.loads(ep_raw)
    turns_path = ep_dir / "turns.jsonl"
    turns_raw = turns_path.read_bytes() if turns_path.exists() else b""
    legacy_turns = [json.loads(x) for x in turns_raw.decode().splitlines() if x.strip()]
    is_model = ep["agent"] not in REFERENCE_AGENTS
    recs = [convert_turn(t, ep_dir, hash_images, is_model) for t in legacy_turns]
    pert = from_legacy_episode(ep)
    desc = pert.describe()
    desc["legacy_cond"] = ep.get("pert")
    if ep.get("map_after") and "map_after" not in desc:
        desc["map_after"] = ep["map_after"]
    status, stop = stop_of(ep.get("stopped"))
    out_mode = ep.get("output_mode", "mm")
    base = {
        "perturb_after": ep["perturb_after"],
        "n_squares": ep["n_squares"],
        "squares_result": ep.get("squares_result", []),
        "strokes": ep.get("strokes", []),
        "perturb_stroke": ep.get("perturb_stroke"),
    }
    ft = first_try_summary(base)
    labels = {
        "legacy": True,
        "source": source,
        "run": run_name,
        "original_episode": ep_dir.name,
        "suite": None,
        "seed_hash": None,
        "perturbation": ep.get("pert"),
        "arm": arm_of(ep, ep_dir.name),
    }
    if suite_match:
        labels.update(suite_match)
    summary: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "freehand_version": __version__,
        "labels": labels,
        "agent": {
            "name": ep["agent"],
            "kind": "model" if is_model else "reference",
            **(
                {"route": legacy_turns[0]["reply"].get("route"), "settings": legacy_turns[0]["reply"].get("settings")}
                if is_model and legacy_turns
                else {}
            ),
        },
        "seed": ep["seed"],
        "perturbation": desc,
        "family": "camera" if ep.get("family") == "A" else "plotter",
        "arm": {
            "name": labels["arm"],
            "memory": bool(ep.get("memory", False)),
            "k_prev": ep.get("k_prev", 2),
            "show_history": ep.get("show_history", True),
            "history_landed": ep.get("history_landed", False),
            "disclosure": ep.get("disclosure", "silent"),
            "blocks": [],
            "feedback": ep.get("feedback_mode", "image"),
            "output_mode": None,
            "prompt_version": "legacy",
            "extra_prompt": ep.get("extra_prompt", ""),
            "memory_effective": bool(ep.get("memory", False)),
        },
        "output_mode": ("page_mm" if out_mode == "mm" else out_mode) if is_model else None,
        "setup": {
            "n_squares": ep["n_squares"],
            "perturb_after": ep["perturb_after"],
            "perturb_stroke": ep.get("perturb_stroke"),
            "cap_strokes": ep.get("cap_strokes", 12),
            "cap_turns": LEGACY_CAP_TURNS,
            "tol_mm": ep.get("tol_mm", 2.0),
            "view": ep.get("view", "rect"),
            "cost_cap": None,
            "rendered": ep.get("rendered", True),
            "square_ids": [s["idx"] for s in ep["squares"]],
            "system_prompt": ep.get("system_prompt", ""),
            "system_prompt_sha256": sha256_hex(ep.get("system_prompt", "").encode()),
            "prompt_components": [],
        },
        "status": status,
        "stop": stop,
        "complete": bool(ep.get("complete")),
        "turns": ep.get("turns", len(recs)),
        "squares_result": base["squares_result"],
        "strokes": base["strokes"],
        "n_squares": ep["n_squares"],
        "perturb_after": ep["perturb_after"],
        "perturb_stroke": ep.get("perturb_stroke"),
        "scores": {
            "first_try": ft,
            "later_first_try": later_first_try(base),
            "squares_to_3_in_a_row": squares_to_run(ft["curve"]),
        },
        "cost": {"usd": round(ep.get("cost", 0.0), 6), "usd_original": round(ep.get("cost_original", 0.0), 6)},
        "timing": {"started": None, "ended": None, "seconds": None},
        "legacy": {
            "source": source,
            "run": run_name,
            "original_dir": str(ep_dir),
            "episode_json_sha256": hashlib.sha256(ep_raw).hexdigest(),
            "turns_jsonl_sha256": hashlib.sha256(turns_raw).hexdigest(),
            "stopped": ep.get("stopped"),
            "original_metrics": ep.get("metrics"),
            "original_metrics_ink": ep.get("metrics_ink"),
            "scenario": ep.get("scenario"),
            "scoring_version": ep.get("scoring_version", 1),
        },
    }
    summary["metrics"] = episode_metrics(summary, recs)
    summary["ink"] = ink_metrics(legacy_turns, ep["perturb_after"], ep.get("cost_original", 0.0))
    page = None if suite_match else ep["squares"]
    return summary, recs, page
