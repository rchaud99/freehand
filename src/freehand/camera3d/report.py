"""Freehand A run reports: the summary table, the belief-error chart, and the showcase video (title cards, the
2 x 2 grid of models, the chart and table as the end card)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from freehand.camera3d import video
from freehand.camera3d.belief import MATCH_MM

MODEL_ORDER = ("claude-opus-5.5", "gpt-6-astra", "gpt-6-sol", "gemini-3.8-flash")
COLORS = {  # chart colours (hex)
    "claude-opus-5.5": "#E07B53",
    "gpt-6-astra": "#2FBF8F",
    "gpt-6-sol": "#A78BFA",
    "gemini-3.8-flash": "#F2C14E",
    "estimator": "#9AA0A6",
}


def episodes(run_dir: Path) -> dict[tuple[str, int], dict]:
    out = {}
    for f in sorted(Path(run_dir).glob("*/s*/episode.json")):
        rec = json.loads(f.read_text())
        out[(rec["agent"], rec["spec"]["seed"])] = rec
    return out


def table(run_dir: Path) -> list[dict]:
    rows = []
    for (agent, seed), rec in episodes(run_dir).items():
        s = rec["summary"]
        rows.append(
            {
                "agent": agent,
                "seed": seed,
                "status": s["status"],
                "strokes": s["strokes"],
                "closed": s["squares_closed"],
                "first_try_before": s["first_try_before_move"],
                "first_try_after": s["first_try_after_move"],
                "match_cold": s["match_turn_cold"],
                "match_after_move": s["match_turn_after_move"],
                "best_error_mm": min((e for e in s["aim_error_mm"] if e is not None), default=None),
                "final_error_mm": s["aim_error_mm"][-1] if s["aim_error_mm"] else None,
                "cost_usd": s["cost"],
            }
        )
    order = {a: i for i, a in enumerate((*MODEL_ORDER, "estimator", "oracle"))}
    return sorted(rows, key=lambda r: (r["seed"], order.get(r["agent"], 99), r["agent"]))


def table_markdown(rows: list[dict]) -> str:
    head = (
        "| seed | agent | strokes | closed | first-try (sq 1-4 / 5-8) | camera matched at stroke (cold / after "
        "move) | final belief error | cost | status |"
    )
    lines = [head, "|" + "---|" * 9]
    for r in rows:

        def m(v):
            return "never" if v is None else str(v)

        fe = "-" if r["final_error_mm"] is None else f"{r['final_error_mm']:.1f} mm"
        lines.append(
            f"| {r['seed']} | {video.DISPLAY.get(r['agent'], r['agent'])} | {r['strokes']} | {r['closed']}/8 | "
            f"{r['first_try_before']} / {r['first_try_after']} | {m(r['match_cold'])} / {m(r['match_after_move'])} | "
            f"{fe} | ${r['cost_usd']:.2f} | {r['status']} |"
        )
    return "\n".join(lines)


def error_chart(run_dir: Path, seed: int, out: Path, size=(1920, 1080), dark: bool = True) -> Path:
    """Belief error per stroke, cold start (left) and after the camera move (right), one line per agent."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    eps = episodes(run_dir)
    fg, bgc, grid = ("#EDEDED", "#111418", "#2A2F36") if dark else ("#1a1a1a", "white", "#dddddd")
    fig, axes = plt.subplots(1, 2, figsize=(size[0] / 100, size[1] / 100 * 0.62), dpi=100, sharey=True)
    fig.patch.set_facecolor(bgc)
    for ax, phase, title in (
        (axes[0], 1, "Cold start: strokes from the beginning"),
        (axes[1], 2, "After the camera moves: strokes since the move"),
    ):
        ax.set_facecolor(bgc)
        for agent in (*MODEL_ORDER, "estimator"):
            rec = eps.get((agent, seed))
            if rec is None:
                continue
            ys = [t["aim_error_mm"] for t in rec["turns"] if t.get("stroke") and t["pose"] == phase]
            ys = [60.0 if y is None else min(y, 60.0) for y in ys]
            if not ys:
                continue
            xs = np.arange(1, len(ys) + 1)
            ref = agent == "estimator"
            ax.plot(
                xs,
                ys,
                color=COLORS[agent],
                lw=1.8 if ref else 2.6,
                ls="--" if ref else "-",
                marker="o",
                ms=0 if ref else 4,
                label=video.DISPLAY[agent],
            )
        ax.axhline(MATCH_MM, color="#6CC05A", lw=1.2)
        ax.text(
            0.99,
            MATCH_MM * 1.12,
            f"match: within {MATCH_MM:g} mm",
            color="#6CC05A",
            ha="right",
            va="bottom",
            transform=ax.get_yaxis_transform(),
            fontsize=12,
        )
        ax.set_yscale("log")
        ax.set_ylim(0.3, 70)
        ax.set_yticks([0.5, 1, 3, 10, 30])
        ax.set_yticklabels(["0.5", "1", "3", "10", "30"])
        ax.set_title(title, color=fg, fontsize=16, loc="left", pad=12)
        ax.set_xlabel("stroke", color=fg, fontsize=13)
        ax.tick_params(colors=fg, labelsize=12)
        ax.grid(True, color=grid, lw=0.8)
        for sp in ax.spines.values():
            sp.set_color(grid)
    axes[0].set_ylabel("belief error (mm, log scale)", color=fg, fontsize=13)
    leg = axes[1].legend(frameon=False, fontsize=13, loc="upper right")
    for t in leg.get_texts():
        t.set_color(fg)
    fig.tight_layout()
    fig.savefig(out, facecolor=bgc)
    plt.close(fig)
    return out


def _table_card(rows: list[dict], seed: int, chart_png: Path, size=(1920, 1080)) -> np.ndarray:
    W, H = size
    img = np.full((H, W, 3), video.BG, np.uint8)
    chart = video._read(str(chart_png))
    chart = cv2.resize(chart, (W, int(chart.shape[0] * W / chart.shape[1])), interpolation=cv2.INTER_AREA)
    img[70 : 70 + chart.shape[0], :] = chart[: H - 70]
    video.text(img, "How long until each model's camera matches the real one?", (60, 50), 30, video.WHITE, "demi")
    y = 70 + chart.shape[0] + 40
    cols = [
        (60, "agent"),
        (520, "first-try closes (before / after move)"),
        (1000, "matched at stroke (cold / after)"),
        (1440, "strokes"),
        (1580, "cost"),
    ]
    for x, h in cols:
        video.text(img, h, (x, y), 17, video.MUTED, "demi")
    for r in rows:
        if r["seed"] != seed or r["agent"] == "oracle":
            continue
        y += 36

        def m(v):
            return "never" if v is None else str(v)

        vals = [
            video.DISPLAY.get(r["agent"], r["agent"]),
            f"{r['first_try_before']}/4  ·  {r['first_try_after']}/4",
            f"{m(r['match_cold'])}  ·  {m(r['match_after_move'])}",
            str(r["strokes"]),
            "-" if r["agent"] == "estimator" else f"${r['cost_usd']:.2f}",
        ]
        for (x, _), v in zip(cols, vals, strict=True):
            video.text(img, v, (x, y), 20, video.WHITE)
    video.text(
        img,
        f"Pilot: one episode per model on this page (seed {seed}). Belief error = how far the pen would land if the "
        "model aimed using the camera it reports.",
        (60, H - 34),
        16,
        video.MUTED,
    )
    return img


def hook(run_dir: Path, seed: int, out: Path, agents=("claude-opus-5.5", "gpt-6-astra"), thumb: Path | None = None):
    """A ~5 s cold open: two agents side by side from one stroke before the camera move to three after it, under a
    big headline; optionally saves the frame after the move (both beliefs settled) as a thumbnail."""
    eps = [video.load_episode(Path(run_dir) / a / f"s{seed}") for a in agents]
    moves = [g for g, (_, m) in enumerate(video._timeline(eps[0], max(e.n for e in eps))) if m]
    g = moves[0] if moves else 4
    state: dict = {}

    def grab(gg, f, canvas):
        if gg == g + 1 and f == int(video.FPS * video.STEP_S) - 1:
            state["thumb"] = canvas.copy()

    video.grid_video(
        eps,
        out,
        "Blue: where the AI says the page is. White: where it really is.",
        "Orange: where its strokes imply it is. We move the camera without telling it: "
        "watch who works out where it went.",
        steps=(g - 1, g + 2),
        title_px=44,
        top=110,
        hold_end_s=1.0,
        on_frame=grab,
        hero=True,
    )
    if thumb is not None and "thumb" in state:
        cv2.imwrite(str(thumb), state["thumb"])
    return out


def concat(parts: list[Path], out: Path) -> Path:
    """Join same-format MP4s without re-encoding."""
    import subprocess

    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )
    lst.unlink()
    return out


def showcase(run_dir: Path, seed: int, out: Path, agents=MODEL_ORDER, with_hook: bool = True) -> Path:
    """The full video: a 5 s cold open (two agents at the camera move), one title card, the 2 x 2 grid on one seed,
    then the chart and table."""
    run_dir, out = Path(run_dir), Path(out)
    eps = [video.load_episode(run_dir / a / f"s{seed}") for a in agents if (run_dir / a / f"s{seed}").is_dir()]
    W = video
    intro = [
        (
            video.card(
                [
                    ("Freehand A: can a model work out where its camera is?", 44, W.WHITE, "demi"),
                    ("", 14, W.WHITE, "regular"),
                    (
                        "A pen plotter draws on paper. The model sees it only through a camera at an unknown angle,",
                        26,
                        (215, 215, 215),
                        "regular",
                    ),
                    (
                        "commands strokes in millimetres, and closes 8 squares. After square 4 the camera moves.",
                        26,
                        (215, 215, 215),
                        "regular",
                    ),
                    (
                        "Every turn it also reports where it thinks the photo's corners are on the page: "
                        "its camera model.",
                        26,
                        (215, 215, 215),
                        "regular",
                    ),
                    ("", 14, W.WHITE, "regular"),
                    (
                        "White: the real camera and page.   Blue: the camera the model states.",
                        28,
                        W.BLUE,
                        "demi",
                    ),
                    (
                        "Orange: the camera its strokes imply (the one under which its recent strokes were perfect).",
                        24,
                        W.ORANGE,
                        "demi",
                    ),
                ]
            ),
            6.0,
        )
    ]
    rows = table(run_dir)
    chart = error_chart(run_dir, seed, out.with_name(out.stem + "_chart.png"))
    end = _table_card(rows, seed, chart)
    main = out.with_name(out.stem + "_main.mp4")
    video.grid_video(
        eps,
        main,
        "Freehand A: learning an unknown camera",
        "White: real camera and page. Blue: the camera the model states. Orange: the camera its strokes imply.",
        intro=intro,
        outro=[(end, 10.0)],
    )
    parts = [main]
    if with_hook:
        thumb = out.with_name(out.stem + "_thumbnail.png")
        h = hook(run_dir, seed, out.with_name(out.stem + "_hook.mp4"), thumb=thumb)
        parts = [h, main]
    concat(parts, out)
    for p_ in parts:
        p_.unlink()
    return out


def _pose_b_segment(rec: dict) -> dict:
    """The stretch of an episode spent at the moved camera (pose 2): all of a fresh episode, the post-move part of a
    transfer episode. Squares are those after the move in both cases."""
    turns = [t for t in rec["turns"] if t.get("stroke") and t["pose"] == 2]
    errs = [t["aim_error_mm"] if t["aim_error_mm"] is not None else float("inf") for t in turns]
    m = 0 if rec["spec"].get("fresh") else rec["spec"]["move_after"]
    outcomes = {int(k) - m: v for k, v in rec["outcomes"].items() if int(k) > m}
    from freehand.camera3d.belief import turns_to_match

    return {
        "first_error_mm": None if not errs or errs[0] == float("inf") else errs[0],
        "match_stroke": turns_to_match(errs) if errs else None,
        "first_try": sum(1 for v in outcomes.values() if v == "first"),
        "closed": sum(1 for v in outcomes.values() if v in ("first", "closed")),
        "done": len(outcomes),
        "strokes": len(turns),
        "complete": rec["status"] == "complete"
        and len(outcomes) == rec["spec"]["n_squares"] - rec["spec"]["move_after"],
    }


def transfer_vs_fresh(transfer_run: Path, fresh_run: Path) -> list[dict]:
    """Per agent and page: the moved camera learned with the agent's own earlier marks (transfer) vs from scratch
    (fresh), on the same pose and the same squares."""
    t_eps, f_eps = episodes(transfer_run), episodes(fresh_run)
    rows = []
    for (agent, seed), frec in sorted(f_eps.items()):
        trec = t_eps.get((agent, seed))
        if trec is None:
            continue
        rows.append({"agent": agent, "seed": seed, "transfer": _pose_b_segment(trec), "fresh": _pose_b_segment(frec)})
    return rows


def transfer_markdown(rows: list[dict]) -> str:
    def f(v, unit=""):
        return "never" if v is None else (f"{v:.1f}{unit}" if isinstance(v, float) else f"{v}{unit}")

    lines = [
        "| agent | page | belief error at first stroke (transfer / fresh) | matched at stroke (transfer / fresh) | "
        "first-try closes (transfer / fresh) | strokes for 4 squares (transfer / fresh) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        t, fr = r["transfer"], r["fresh"]
        flag = "" if t["complete"] and fr["complete"] else " *"
        lines.append(
            f"| {video.DISPLAY.get(r['agent'], r['agent'])}{flag} | {r['seed']} | {f(t['first_error_mm'], ' mm')} / "
            f"{f(fr['first_error_mm'], ' mm')} | {f(t['match_stroke'])} / {f(fr['match_stroke'])} | "
            f"{t['first_try']}/{t['done']} / {fr['first_try']}/{fr['done']} | {t['strokes']} / {fr['strokes']} |"
        )
    return "\n".join(lines) + "\n\n\\* an episode in the pair did not finish all four squares (capped or stopped)."
