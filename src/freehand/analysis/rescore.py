"""Old vs corrected first-try scores of runs (used for docs/provenance/MIGRATION.md).

Old: the objective-pilot scorer read only the per-square results, so a square whose first stroke had MISSED was
dropped when the episode stopped before that square's result was written (it became "not reached").
New: freehand.scoring counts it as an observed miss. Only stopped/capped episodes can differ.
"""

from __future__ import annotations

from pathlib import Path

from freehand.analysis.episodes import load_episodes
from freehand.scoring import first_try_curve, legacy_squares_result_curve


def _hits(curve, skip_first: bool) -> tuple[int, int]:
    v = [x for x in (curve[1:] if skip_first else curve) if x is not None]
    return sum(v), len(v)


def rescore_runs(run_dirs: list[Path]) -> dict:
    rows = []
    for ep in load_episodes(run_dirs):
        s = ep.summary
        old, new = legacy_squares_result_curve(s), first_try_curve(s)
        oh, on = _hits(old, True)
        nh, nn = _hits(new, True)
        ah, an = _hits(old, False)
        bh, bn = _hits(new, False)
        rows.append(
            {
                "run": s.get("labels", {}).get("run") or ep.run.name,
                "agent": ep.agent,
                "perturbation": ep.perturbation,
                "arm": ep.arm,
                "seed": ep.seed,
                "status": s["status"],
                "squares_done": len(s["squares_result"]),
                "later_old": f"{oh}/{on}",
                "later_new": f"{nh}/{nn}",
                "post_old": f"{ah}/{an}",
                "post_new": f"{bh}/{bn}",
                "changed": old != new,
                "old_curve": old,
                "new_curve": new,
            }
        )
    lines = [
        "| run | agent | rule | arm | status | squares done | later first-try: old | new | all post-change: "
        "old | new | changed |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        flag = "**CHANGED**" if r["changed"] else ""
        lines.append(
            f"| {r['run']} | {r['agent']} | {r['perturbation']} | {r['arm']} | {r['status']} | "
            f"{r['squares_done']} | {r['later_old']} | {r['later_new']} | {r['post_old']} | "
            f"{r['post_new']} | {flag} |"
        )
    return {
        "rows": rows,
        "markdown": "\n".join(lines),
        "changed": sum(r["changed"] for r in rows),
        "episodes": len(rows),
    }
