"""`freehand report`: one row per episode, summary tables and charts for one or more runs.

Outputs (default: <last run>/report/):
  summary.json / summary.csv   one row per episode (models and references)
  report.md                    the first-try table per rule (later squares, observed rate with coverage), strokes,
                               ink, regret against the references, tokens, cost, status
  learning_curves.png          first-try hit per post-change square: rows = models, columns = rules, one line per arm,
                               the ideal estimator dashed
  first_try_bars.png           later-square first-try rate per model x arm, one panel per rule
Scores are the corrected first-try scores (docs/method.md, "Scoring"). Stopped / capped episodes stay in the table
with their status; only squares actually attempted count toward the observed rate.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from freehand.analysis.episodes import Episode, load_episodes
from freehand.episode.mentions import attribution
from freehand.metrics.regret import regret

REFERENCE_IDEALS = ("adaptive", "family_estimator")  # the ideal estimator: ladder fit, else the known-family fit
REFERENCE_NAIVE = "naive"


def _later(ep: Episode) -> tuple[int, int]:
    lt = ep.summary["scores"]["later_first_try"]
    return lt["hits"], lt["attempted"]


def episode_row(ep: Episode, refs: dict[tuple, dict[str, Episode]]) -> dict:
    s = ep.summary
    ft = s["scores"]["first_try"]
    h, n = _later(ep)
    r = refs.get(ep.page_key, {})
    ideal = next((r[k] for k in REFERENCE_IDEALS if k in r), None)
    naive = r.get(REFERENCE_NAIVE)
    ink_reg = stroke_reg = None
    if ideal is not None and naive is not None:
        ink_reg = regret(
            s["ink"]["ink_post_mm"], ideal.summary["ink"]["ink_post_mm"], naive.summary["ink"]["ink_post_mm"]
        )
        stroke_reg = regret(
            s["metrics"]["post_strokes_total"],
            ideal.summary["metrics"]["post_strokes_total"],
            naive.summary["metrics"]["post_strokes_total"],
        )
    label, at_turn, _ = attribution(ep.turns(), s["perturb_after"]) if ep.kind == "model" else ("", None, "")
    return {
        "run": ep.run.name,
        "agent": ep.agent,
        "kind": ep.kind,
        "model": s["labels"].get("model"),
        "suite": s["labels"].get("suite"),
        "perturbation": ep.perturbation,
        "arm": ep.arm,
        "seed": ep.seed,
        "split": s["labels"].get("split"),
        "output_mode": s.get("output_mode"),
        "status": s["status"],
        "stop": (s.get("stop") or {}).get("kind"),
        "squares_done": len(s["squares_result"]),
        "n_squares": s["n_squares"],
        "curve": ft["curve"],
        "first_try_hits": ft["hits"],
        "first_try_attempted": ft["attempted"],
        "first_try_planned": ft["planned"],
        "first_try_observed_rate": ft["observed_rate"],
        "first_try_coverage": ft["coverage"],
        "first_try_fixed_budget": ft["fixed_budget_attainment"],
        "later_first_try": f"{h}/{n}",
        "later_rate": round(h / n, 3) if n else None,
        "squares_to_3_in_a_row": s["scores"]["squares_to_3_in_a_row"],
        "total_strokes": len(s["strokes"]),
        "post_strokes": s["metrics"]["post_strokes_total"],
        "abandoned_post": sum(not q["closed"] for q in s["squares_result"] if q["square"] > s["perturb_after"]),
        "ink_total_mm": s["ink"]["ink_total_mm"],
        "ink_post_mm": s["ink"]["ink_post_mm"],
        "ink_wasted_ratio": s["ink"]["ink_wasted_ratio"],
        "ink_regret": ink_reg,
        "stroke_regret": stroke_reg,
        "tokens_in": s["ink"]["tokens_in"],
        "tokens_out": s["ink"]["tokens_out"],
        "tokens_reasoning": s["ink"]["tokens_reasoning"],
        "cost_usd": round(s["cost"]["usd_original"], 4),
        "attribution_keyword_screen": label,
        "attribution_turn": at_turn,
        "dir": str(ep.dir),
    }


def build_rows(run_dirs: list[Path]) -> list[dict]:
    eps = load_episodes(run_dirs)
    refs: dict[tuple, dict[str, Episode]] = defaultdict(dict)
    for ep in eps:
        if ep.kind == "reference" and ep.summary["complete"]:
            refs[ep.page_key].setdefault(ep.agent, ep)
    return [episode_row(ep, refs) for ep in eps]


def _fmt(v, digits=2):
    if v is None:
        return "-"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def markdown(rows: list[dict]) -> str:
    out = [
        "# Freehand report",
        "",
        "First-try = the square's FIRST stroke closed it. `later` = squares after the first post-change square "
        "(hits/attempted). `rate (cov)` = observed first-try rate over post-change squares attempted, with the "
        "share of planned squares attempted. Regret: 0 = ideal estimator, 1 = never adapting. `attribution` is an "
        "unvalidated keyword screen.",
        "",
    ]
    cols = [
        "agent",
        "arm",
        "seed",
        "status",
        "later_first_try",
        "first_try_observed_rate",
        "first_try_coverage",
        "squares_to_3_in_a_row",
        "total_strokes",
        "abandoned_post",
        "ink_post_mm",
        "ink_regret",
        "stroke_regret",
        "tokens_in",
        "cost_usd",
        "attribution_keyword_screen",
    ]
    heads = [
        "agent",
        "arm",
        "seed",
        "status",
        "later",
        "rate",
        "cov",
        "to 3",
        "strokes",
        "abandoned",
        "ink post mm",
        "ink regret",
        "stroke regret",
        "tokens in",
        "$",
        "attribution",
    ]
    by_pert: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_pert[f"{r['suite'] or 'legacy page'} / {r['perturbation']}"].append(r)
    for pert, rs in by_pert.items():
        out += [f"## {pert}", "", "| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
        rs = sorted(rs, key=lambda r: (r["kind"] != "reference", r["agent"], r["arm"], r["seed"]))
        for r in rs:
            out.append("| " + " | ".join(_fmt(r[c]) for c in cols) + " |")
        out.append("")
    total = sum(r["cost_usd"] for r in rows)
    out.append(f"{len(rows)} episodes; total cost ${total:.2f}.")
    return "\n".join(out) + "\n"


def write_report(run_dirs: list[Path], out: Path | None = None) -> Path:
    from freehand.analysis import charts

    rows = build_rows(run_dirs)
    out = out or (run_dirs[-1] / "report")
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(rows, indent=1))
    if rows:
        with open(out / "summary.csv", "w", newline="") as f:
            cols = [c for c in rows[0] if c != "curve"]
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    (out / "report.md").write_text(markdown(rows))
    if any(r["kind"] == "model" for r in rows):
        charts.learning_curves(rows, out / "learning_curves.png")
        charts.first_try_bars(rows, out / "first_try_bars.png")
    return out
