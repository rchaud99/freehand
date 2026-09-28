"""What the legacy-parity test compares, extracted identically from a legacy log and from a new episode.

Per case: the system prompt, and per turn the state block, the request-cache key (it hashes the system prompt, every
message and every image's bytes), memory/notepad bookkeeping, the parsed action and the executed stroke; per episode
the square results, stroke log, stop reason and the historical metrics (except the first-try rate, which the new
scorer corrects on purpose).
"""
from __future__ import annotations

SKIP_METRICS = ("post_first_try_rate", "post_first_try")


def from_legacy(lg: dict) -> dict:
    turns = []
    for t in lg["turns"]:
        d = t["drawn"]
        turns.append({
            "turn": t["turn"], "square": t["square"], "attempt": t["attempt"], "state": t["state"],
            "cache_key": t["cache_key"], "prev_images": t["prev_images"], "notepad_in": t["notepad_in"],
            "n_history_turns": t["n_history_turns"], "change_active": t["change_active"], "view_H": t["view_H"],
            "mention": t["mention"], "action": t["action"], "cmd_crop_px": t["cmd_crop_px"],
            "crop": None if t["crop"] is None else [t["crop"]["origin_mm"], t["crop"]["side_mm"]],
            "stroke": None if d is None else [d["stroke"], d["cmd"], d["ink_ends"], d["closed"], d["end_err_mm"],
                                              d["straight_dev_mm"], d["post"], d["compensation_frac"], d["clamps"]]})
    stop = lg["stopped"].split(": ", 1)[1] if lg["stopped"] else None
    return {"system_prompt": lg["system_prompt"], "turns": turns, "squares_result": lg["squares_result"],
            "strokes": lg["strokes"], "perturb_stroke": lg["perturb_stroke"], "complete": lg["complete"],
            "stop": stop, "metrics": {k: v for k, v in lg["metrics"].items() if k not in SKIP_METRICS},
            "ink": lg["metrics_ink"], "cost_original": lg["cost_original"]}


def from_new(summary: dict, turns: list[dict]) -> dict:
    out = []
    for b in turns:
        st = b["stroke"]
        out.append({
            "turn": b["turn"], "square": b["square"], "attempt": b["attempt"], "state": b["prompt"]["state"],
            "cache_key": b["reply"].get("cache_key"), "prev_images": b["prompt"]["prev_images"],
            "notepad_in": b["prompt"]["notepad_in"], "n_history_turns": b["prompt"]["n_history_turns"],
            "change_active": b["change_active"], "view_H": b["view_H"],
            "mention": [b["mentions"]["note"], b["mentions"]["memory"], b["mentions"]["reasoning"]],
            "action": b["action"], "cmd_crop_px": b["command_crop_px"],
            "crop": None if b["crop"] is None else [b["crop"]["origin_mm"], b["crop"]["side_mm"]],
            "stroke": None if st is None else [st["n"], b["command"], st["ends"], st["closed"], st["end_err_mm"],
                                               st["straight_dev_mm"], st["post"], st["compensation_frac"],
                                               b["clamps"]]})
    stop = summary["stop"]["message"].split(": ", 1)[1] if summary["stop"] else None
    return {"system_prompt": summary["setup"]["system_prompt"], "turns": out,
            "squares_result": summary["squares_result"], "strokes": summary["strokes"],
            "perturb_stroke": summary["perturb_stroke"], "complete": summary["complete"], "stop": stop,
            "metrics": {k: v for k, v in summary["metrics"].items() if k not in SKIP_METRICS},
            "ink": summary["ink"], "cost_original": summary["cost"]["usd_original"]}
