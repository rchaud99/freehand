"""Freehand A study tables: everything from a set of runs in flat, analysis-ready files, and the preregistered claims
scored mechanically.

    freehand camera3d study <run> [<run> ...] --name <name> [--new-pages 3008,3023,...]

writes results/camera3d/studies/<name>/:
    episodes.csv     one row per episode (agent, page, arm, status, cost, tokens, headline numbers)
    strokes.csv      one row per stroke (command, ink, closure, stated and stroke-implied camera errors, first-stroke
                     aim, note, the photo's sha256)
    transfer.csv     one row per agent and page: the moved camera with vs without the agent's own earlier ink
    claims.md        the preregistered claims (docs/freehand_a.md), each PASS or FAIL with the numbers behind it
    summary.json     all of the above in one file, plus the runs it came from
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from freehand import paths
from freehand.camera3d.belief import H_from_corners, aim_error_mm, implied_camera, implied_window
from freehand.camera3d.pose import Pose, project

MODELS = ("gpt-6-astra", "claude-opus-5.5", "gpt-6-sol", "gemini-3.8-flash")


def load_episodes(run_dirs: list[Path]) -> list[dict]:
    out = []
    for rd in run_dirs:
        rd = Path(rd)
        plan = json.loads((rd / "run.json").read_text()) if (rd / "run.json").is_file() else {}
        for f in sorted(rd.glob("*/s*/episode.json")):
            rec = json.loads(f.read_text())
            rec["_run"] = rd.name
            rec["_study"] = plan.get("study")
            rec["_arm"] = "fresh" if rec["spec"].get("fresh") else "transfer"
            rec["_dir"] = str(f.parent)
            out.append(rec)
    return out


def _first_stroke_aims(rec: dict):
    """For the first stroke at each square: (actual aim error, stated-camera aim error, gap between them), mm."""
    poses = [Pose.from_dict(p) for p in rec["poses"]]
    sq = {q["idx"]: q for q in rec["squares"]}
    rows = {}
    for t in rec["turns"]:
        s = t.get("stroke")
        if not s or s["attempt"] != 1:
            continue
        tgt = np.asarray(sq[s["square"]]["open_ends"], float)
        cmd = np.asarray(s["cmd"], float)
        if np.linalg.norm(cmd - tgt, axis=1).sum() > np.linalg.norm(cmd[::-1] - tgt, axis=1).sum():
            cmd = cmd[::-1]
        actual = float(np.linalg.norm(cmd - tgt, axis=1).mean())
        stated = gap = None
        Hb = H_from_corners(t["belief"]) if t.get("belief") else None
        if Hb is not None:
            aim = project(np.linalg.inv(Hb), project(poses[t["pose"] - 1].H, tgt))
            stated = float(np.linalg.norm(aim - tgt, axis=1).mean())
            gap = float(np.linalg.norm(aim - cmd, axis=1).mean())
        rows[t["turn"]] = (actual, stated, gap)
    return rows


def stroke_rows(rec: dict) -> list[dict]:
    poses = [Pose.from_dict(p) for p in rec["poses"]]
    sq = {q["idx"]: q for q in rec["squares"]}
    turns = [t for t in rec["turns"] if t.get("stroke")]
    firsts = _first_stroke_aims(rec)
    rows = []
    for i, t in enumerate(turns):
        s = t["stroke"]
        strokes, targets = implied_window(turns, sq, i)
        Hi = implied_camera(poses[t["pose"] - 1], strokes, targets)
        implied = None if Hi is None else aim_error_mm(poses[t["pose"] - 1].H, Hi)
        u = t.get("usage") or []
        f = firsts.get(t["turn"])
        rows.append(
            {
                "run": rec["_run"],
                "agent": rec["agent"],
                "page": rec["spec"]["seed"],
                "arm": rec["_arm"],
                "turn": t["turn"],
                "stroke": s["stroke"],
                "square": s["square"],
                "attempt": s["attempt"],
                "pose": t["pose"],
                "closed": s["closed"],
                "cmd_x1": s["cmd"][0][0],
                "cmd_y1": s["cmd"][0][1],
                "cmd_x2": s["cmd"][1][0],
                "cmd_y2": s["cmd"][1][1],
                "ink_x1": round(s["ink_ends"][0][0], 3),
                "ink_y1": round(s["ink_ends"][0][1], 3),
                "ink_x2": round(s["ink_ends"][1][0], 3),
                "ink_y2": round(s["ink_ends"][1][1], 3),
                "end_err1_mm": s["end_err_mm"][0],
                "end_err2_mm": s["end_err_mm"][1],
                "clamped": s["clamped"],
                "stated_camera_err_mm": t.get("aim_error_mm"),
                "implied_camera_err_mm": None if implied is None else round(implied, 3),
                "first_stroke_actual_aim_mm": None if f is None else round(f[0], 3),
                "first_stroke_stated_aim_mm": None if f is None or f[1] is None else round(f[1], 3),
                "first_stroke_stated_vs_actual_mm": None if f is None or f[2] is None else round(f[2], 3),
                "cost_usd": t.get("cost"),
                "input_tokens": sum(x.get("input_tokens", 0) or 0 for x in u),
                "output_tokens": sum(x.get("output_tokens", 0) or 0 for x in u),
                "reasoning_tokens": sum(x.get("reasoning_tokens", 0) or 0 for x in u),
                "reprompts": len(t.get("problems") or []),
                "photo_sha256": t.get("photo_sha256"),
                "note": t.get("note", ""),
            }
        )
    return rows


def _pose_b(rec: dict) -> dict:
    from freehand.camera3d.report import _pose_b_segment

    return _pose_b_segment(rec)


def episode_row(rec: dict) -> dict:
    s = rec["summary"]
    b = _pose_b(rec)
    return {
        "run": rec["_run"],
        "study": rec["_study"],
        "agent": rec["agent"],
        "page": rec["spec"]["seed"],
        "arm": rec["_arm"],
        "status": rec["status"],
        "strokes": s["strokes"],
        "squares_closed": s["squares_closed"],
        "first_try_before_move": s["first_try_before_move"],
        "first_try_after_move": s["first_try_after_move"],
        "abandoned": s["abandoned"],
        "matched_cold_at": s["match_turn_cold"],
        "matched_moved_at": b["match_stroke"],
        "moved_first_error_mm": b["first_error_mm"],
        "moved_strokes": b["strokes"],
        "moved_complete": b["complete"],
        "cost_usd": s["cost"],
        "dir": rec["_dir"],
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def score_claims(eps: list[dict], new_pages: list[int]) -> tuple[list[dict], str]:
    """The three preregistered claims of docs/freehand_a.md, on `new_pages` only."""
    by = {(e["agent"], e["spec"]["seed"], e["_arm"]): e for e in eps}

    def ep(agent, page, arm):
        return by.get((agent, page, arm))

    def matched_cold(agent, page):
        e = ep(agent, page, "transfer")
        return bool(e and e["summary"]["match_turn_cold"] is not None)

    res = []
    # 1. only Astra learns the camera from a cold start
    n = {a: sum(matched_cold(a, p) for p in new_pages) for a in ("gpt-6-astra", "claude-opus-5.5", "gpt-6-sol")}
    ok1 = n["gpt-6-astra"] >= 3 and n["claude-opus-5.5"] <= 1 and n["gpt-6-sol"] <= 1
    res.append({"claim": 1, "pass": ok1, "detail": {a: f"{k}/{len(new_pages)} pages matched" for a, k in n.items()}})
    # 2. Astra transfers
    per = {}
    for p in new_pages:
        t, f = ep("gpt-6-astra", p, "transfer"), ep("gpt-6-astra", p, "fresh")
        if t is None or f is None:
            per[p] = (False, "missing episode")
            continue
        bt, bf = _pose_b(t), _pose_b(f)
        a = bt["match_stroke"] is not None and bt["match_stroke"] <= 2
        b = bt["complete"] and bf["complete"] and bt["strokes"] < bf["strokes"]
        per[p] = (
            a and b,
            f"matched moved camera at {bt['match_stroke']}; strokes {bt['strokes']} vs fresh {bf['strokes']}"
            + ("" if bt["complete"] and bf["complete"] else " (incomplete)"),
        )
    ok2 = sum(v[0] for v in per.values()) >= 3
    res.append({"claim": 2, "pass": ok2, "detail": {p: ("yes: " if v[0] else "no: ") + v[1] for p, v in per.items()}})
    # 3. Opus says one thing and does another
    gaps = {}
    for a in ("claude-opus-5.5", "gpt-6-astra"):
        g = []
        for p in new_pages:
            e = ep(a, p, "transfer")
            if e:
                g += [x[2] for x in _first_stroke_aims(e).values() if x[2] is not None]
        gaps[a] = float(np.median(g)) if g else float("nan")
    ok3 = gaps["claude-opus-5.5"] >= 5 and gaps["claude-opus-5.5"] >= 2 * gaps["gpt-6-astra"]
    res.append(
        {
            "claim": 3,
            "pass": bool(ok3),
            "detail": {a: f"median stated-vs-actual gap {v:.1f} mm" for a, v in gaps.items()},
        }
    )
    names = {
        1: "Only Astra learns the camera from a cold start (Astra >= 3/4 pages; Opus, Sol <= 1/4)",
        2: "Astra transfers (matched within 2 strokes after the move AND fewer strokes than fresh, >= 3/4 pages)",
        3: "Opus says one thing and does another (median gap >= 5 mm and >= 2x Astra's)",
    }
    md = [
        f"# Preregistered claims, scored on pages {', '.join(map(str, new_pages))}\n",
        "Rules: docs/freehand_a.md, 'Replication plan'. Claims 1 and 3 use the transfer episodes (claim 3: the first",
        "stroke at every square, both camera poses); a capped, stopped or failed episode counts against the claim.\n",
    ]
    for r in res:
        md.append(f"## {r['claim']}. {names[r['claim']]}: **{'PASS' if r['pass'] else 'FAIL'}**\n")
        md += [f"- {k}: {v}" for k, v in r["detail"].items()]
        md.append("")
    return res, "\n".join(md)


def build(run_dirs: list[Path], name: str, new_pages: list[int] | None = None, out_root: Path | None = None) -> Path:
    out = (out_root or paths.results_root() / "camera3d" / "studies") / name
    out.mkdir(parents=True, exist_ok=True)
    eps = load_episodes(run_dirs)
    ep_rows = [episode_row(e) for e in eps]
    st_rows = [r for e in eps for r in stroke_rows(e)]
    _write_csv(out / "episodes.csv", ep_rows)
    _write_csv(out / "strokes.csv", st_rows)
    # transfer vs fresh, pairing each agent's transfer and fresh episode on the same page from any of the runs
    tr_rows = []
    by = {(e["agent"], e["spec"]["seed"], e["_arm"]): e for e in eps}
    for (agent, page, arm), e in sorted(by.items()):
        if arm != "fresh" or (agent, page, "transfer") not in by:
            continue
        t, f = _pose_b(by[(agent, page, "transfer")]), _pose_b(e)
        tr_rows.append(
            {
                "agent": agent,
                "page": page,
                **{f"transfer_{k}": v for k, v in t.items()},
                **{f"fresh_{k}": v for k, v in f.items()},
            }
        )
    _write_csv(out / "transfer.csv", tr_rows)
    summary = {"runs": [str(Path(r)) for r in run_dirs], "episodes": ep_rows, "transfer": tr_rows}
    if new_pages:
        claims, md = score_claims(eps, new_pages)
        (out / "claims.md").write_text(md)
        summary["claims"] = claims
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    return out
