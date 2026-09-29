# Reproducing the results

**The record is the logged episodes.** Every model episode behind the figures and [findings.md](findings.md) is kept
as its turn log (`episode.jsonl`: the prompt's state text and image hashes, the model's reply, the command, where
the ink landed, the closure verdict) and its summary (`summary.json`). `freehand replay` re-simulates every logged
stroke from those logs and checks that the ink lands exactly where it was logged; `--render` also regenerates every
image the model saw and checks it against the logged sha256. Nothing here calls a model or costs money.

## 1. Get the data bundle

The four runs behind the figures (objective_pilot, informed_pilot, stateless_pilot, informed_models: 75 episodes)
are published as one release asset, `freehand_figure_runs_v1.tar.gz` (4.3 MB). It holds, per run, the manifest and
each episode's `episode.jsonl` and `summary.json`; no images, cache or ledger.

```sh
# From the repository root, after the install in the README (source .venv/bin/activate).
DATA_URL="TODO-RELEASE-URL"   # TODO(release): the release-asset URL of freehand_figure_runs_v1.tar.gz
curl -L -o freehand_figure_runs_v1.tar.gz "$DATA_URL"
shasum -a 256 freehand_figure_runs_v1.tar.gz
# 6708610c408426990fe004f0d9037aac12310e3817434c450c50375bb3681ac5
mkdir -p data && tar -xzf freehand_figure_runs_v1.tar.gz -C data
(cd data/freehand_figure_runs_v1 && shasum -a 256 -c SHA256SUMS --quiet)
```

`data/` is gitignored. The bundle's own README lists its runs.

## 2. Regenerate the figures

```sh
freehand figures data/freehand_figure_runs_v1/runs/* --out figures
cmp figures/informed_summary.csv docs/figures/informed_summary.csv && echo "table identical"
for f in docs/figures/*.png; do cmp "$f" "figures/$(basename "$f")" && echo "same $(basename "$f")"; done
```

This writes the learning-curve grid, the first-try bars, the all-arms curves and `informed_summary.csv`. With the
pinned environment (CPython 3.12, the exact numpy and OpenCV in `pyproject.toml`, the matplotlib in
`requirements.lock`) the PNGs are byte-identical to [figures/](figures/); on another platform or matplotlib they
may differ in pixels, while the table is identical. `--scorer legacy` gives the historical scorer's table
(`informed_summary_legacy_scorer.csv`); `freehand rescore data/freehand_figure_runs_v1/runs/*` prints old vs
corrected scores per episode.

## 3. Replay and validate

```sh
for r in data/freehand_figure_runs_v1/runs/*; do freehand replay "$r"; freehand validate "$r"; done
freehand replay data/freehand_figure_runs_v1/runs/informed_pilot_20260928_170744 --render   # ~1 min
```

Expected: every episode exact (`"exact_episodes"` equals `"episodes"`, max endpoint error 0.0 mm, 0 closure
mismatches, no errors), 0 schema errors, and with `--render` 0 image mismatches (899 images for informed_pilot).
The pages are regenerated from the frozen suites in `configs/suites/` (their data hashes are checked first), so this
needs a clone of the repository, not just the bundle.

## Why not re-run the studies?

Every historical study is also a config (`configs/experiments/<study>.yaml`), and `freehand run <study> --max-usd 0`
re-runs it from the request cache at no cost. That is **not** an exact reproduction, and the cache is not published:

- Before the change, the three rules of a study send identical requests. Where those episodes ran concurrently, each
  got its own reply, but the cache keeps one reply per request, so a cache replay diverges from the logged episode
  at the first shared request (Sol's shear and camera episodes of informed_models diverge at strokes 4–5).
- The episode cost cap now counts each call's logged cost, so two historical episodes stop one or two strokes
  earlier when re-run ([roadmap.md](roadmap.md), open question 6).

So the logged episodes plus `freehand replay` are the record; cache re-runs are a debugging aid.

## Rebuilding the bundle (maintainers)

The bundle is built from the imported historical runs, which need the two original copies of the project:

```sh
freehand import-legacy --source working=<copy B> --source codex=<copy A> --merge-cache
freehand export-data                 # -> results/release/freehand_figure_runs_v1.tar.gz
```

`export-data` replaces local paths in the provenance fields with neutral labels, refuses to write anything that
still looks like a local path, and writes a byte-reproducible archive: rebuilding it gives the sha256 above.
