"""Report charts (matplotlib, headless). One visual system: the historical palette, gray dashed code estimator."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#6b6a66", "#e6e5e0", "#fcfcfb"
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#7a5cd6", "#3fb6c9", "#a3702b"]
C_CODE = "#8a8983"
KNOWN_ARM_COLOURS = {"silent": PALETTE[0], "objective": PALETTE[1], "informed_objective": PALETTE[2],
                     "stateless_image": PALETTE[3], "stateless_numeric": PALETTE[4]}
RUNNING_MEAN = 3


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _arm_colours(arms: list[str]) -> dict[str, str]:
    out, free = {}, [c for c in PALETTE if c not in KNOWN_ARM_COLOURS.values()]
    for a in arms:
        if a in KNOWN_ARM_COLOURS:
            out[a] = KNOWN_ARM_COLOURS[a]
        else:
            out[a] = free.pop(0) if free else MUTED
    return out


def _mean_curve(rows: list[dict]) -> np.ndarray:
    """Mean first-try (0/1) per post-change square over seeds; NaN where no seed reached the square."""
    if not rows:
        return np.array([])
    n = max(len(r["curve"]) for r in rows)
    vals = np.full((len(rows), n), np.nan)
    for i, r in enumerate(rows):
        vals[i, :len(r["curve"])] = [np.nan if v is None else v for v in r["curve"]]
    count = np.sum(np.isfinite(vals), axis=0)
    return np.divide(np.nansum(vals, axis=0), count, out=np.full(n, np.nan), where=count > 0)


def _running(y: np.ndarray) -> np.ndarray:
    windows = [y[max(0, k - RUNNING_MEAN + 1):k + 1] for k in range(len(y))]
    m = np.array([np.nanmean(w) if np.isfinite(w).any() else np.nan for w in windows])
    m[~np.isfinite(y)] = np.nan
    return m


def _ideal(rows: list[dict], pert: str) -> list[dict]:
    """The ideal-estimator reference rows of a rule: `adaptive`, else the known-family estimator."""
    for name in ("adaptive", "family_estimator"):
        sel = [r for r in rows if r["kind"] == "reference" and r["agent"] == name and r["perturbation"] == pert]
        if sel:
            return sel
    return []


def _model_order(rows: list[dict]) -> list[str]:
    tot: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["kind"] == "model":
            h, n = (int(x) for x in r["later_first_try"].split("/"))
            tot[r["agent"]][0] += h
            tot[r["agent"]][1] += n
    return sorted(tot, key=lambda a: -(tot[a][0] / tot[a][1]) if tot[a][1] else 1)


def learning_curves(rows: list[dict], out_png: Path) -> None:
    plt = _plt()
    models = _model_order(rows)
    perts = list(dict.fromkeys(r["perturbation"] for r in rows if r["kind"] == "model"))
    arms = list(dict.fromkeys(r["arm"] for r in rows if r["kind"] == "model"))
    colours = _arm_colours(arms)
    fig, axes = plt.subplots(len(models), len(perts), figsize=(4.3 * len(perts), 2.2 * len(models) + 1.0),
                             sharex=True, sharey=True, squeeze=False)
    for i, m in enumerate(models):
        for j, p in enumerate(perts):
            ax = axes[i, j]
            ref = _ideal(rows, p)
            first = next((r for r in rows if r["perturbation"] == p), None)
            start = (first["n_squares"] - len(first["curve"]) + 1) if first else 1
            if ref:
                y = _mean_curve(ref)
                ax.plot(np.arange(start, start + len(y)), _running(y), color=C_CODE, lw=1.6, ls="--",
                        label="ideal estimator (code)")
            for a in arms:
                sel = [r for r in rows if r["agent"] == m and r["perturbation"] == p and r["arm"] == a]
                if not sel:
                    continue
                y = _mean_curve(sel)
                xs = np.arange(start, start + len(y))
                ax.plot(xs, _running(y), color=colours[a], lw=2.0, label=a)
                ax.scatter(xs, y, s=12, color=colours[a], alpha=0.6, zorder=3)
            if i == 0:
                ax.set_title(p, fontsize=10, color=INK)
            if j == 0:
                ax.set_ylabel(m, fontsize=9, color=INK)
            ax.set_ylim(-0.1, 1.1)
            ax.set_yticks([0, 0.5, 1])
            ax.grid(axis="y", color=GRID, lw=0.8)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("square (after the change)", fontsize=9)
    h, lab = [], []
    for ax in axes.flat:
        for hh, ll in zip(*ax.get_legend_handles_labels(), strict=True):
            if ll not in lab:
                h.append(hh)
                lab.append(ll)
    fig.suptitle("First-try hit per post-change square (dots: mean over seeds; line: 3-square running mean)",
                 fontsize=10.5, y=1.0)
    fig.legend(h, lab, loc="upper center", ncol=min(len(h), 4), frameon=False, fontsize=9,
               bbox_to_anchor=(0.5, 0.985 - 0.02))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_png, dpi=140, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def first_try_bars(rows: list[dict], out_png: Path) -> None:
    plt = _plt()
    perts = list(dict.fromkeys(r["perturbation"] for r in rows if r["kind"] == "model"))
    groups = list(dict.fromkeys((r["agent"], r["arm"]) for r in rows if r["kind"] == "model"))
    fig, axes = plt.subplots(1, len(perts), figsize=(4.5 * len(perts), 0.45 * len(groups) + 1.6), sharey=True,
                             squeeze=False)
    yy = np.arange(len(groups))[::-1]
    for ax, p in zip(axes[0], perts, strict=True):
        for y, (agent, arm) in zip(yy, groups, strict=True):
            sel = [r for r in rows if r["agent"] == agent and r["arm"] == arm and r["perturbation"] == p]
            if not sel:
                ax.text(0.01, y, "not run", va="center", fontsize=8, color=MUTED)
                continue
            h = sum(int(r["later_first_try"].split("/")[0]) for r in sel)
            n = sum(int(r["later_first_try"].split("/")[1]) for r in sel)
            v = h / n if n else 0.0
            ax.barh(y, v, height=0.62, color=KNOWN_ARM_COLOURS.get(arm, PALETTE[0]))
            status = ",".join(sorted({r["status"] for r in sel if r["status"] != "complete"}))
            ax.text(v + 0.02, y, f"{h}/{n}" + (f" ({status})" if status else ""), va="center", fontsize=8, color=INK)
        ref = _ideal(rows, p)
        if ref:
            h = sum(int(r["later_first_try"].split("/")[0]) for r in ref)
            n = sum(int(r["later_first_try"].split("/")[1]) for r in ref)
            if n:
                ax.axvline(h / n, color=C_CODE, ls="--", lw=1.4)
        ax.set_title(p, fontsize=10, color=INK)
        ax.set_xlim(0, 1.3)
        ax.set_xticks([0, 0.5, 1])
        ax.set_xlabel("first-try rate, later squares", fontsize=9)
        ax.grid(axis="x", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0][0].set_yticks(yy)
    axes[0][0].set_yticklabels([f"{a} · {arm}" for a, arm in groups], fontsize=8.5)
    fig.suptitle("First-try rate on later squares (label: hits/attempted; dashed: ideal estimator)", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
