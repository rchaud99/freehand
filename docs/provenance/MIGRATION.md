# Migration: from the two historical copies to this repository (2026-09-28; consolidated 2026-09-29)

A provenance record: how the code, results and documents of the two earlier copies became this repository, and how
that was verified. Counts are as of the consolidation (2026-09-29). Names: see the glossary in
[../HISTORY.md](../HISTORY.md#glossary-of-provenance-names).

This repository replaces two diverged working folders:

- **A, an earlier parallel copy** (the "Codex copy", `freehand_publish`). The better-engineered
  base: 24 offline tests, the corrected first-try scorer, replay audit, the discriminating rules, numeric baselines,
  the model-study runner, a dependency lock, bundled grid renderer and calibration asset, the budget-race fix, and
  rejection of non-finite commands.
- **B, the original working copy** (`freehand_b`). The newer experiments: the informed and
  stateless arms, informed_models, resume, the landed-ends history, crop views under a stale rectification, kimi,
  the reasoning adapters, the balance check, and the newest docs.

Both were only read: nothing in either was modified, moved or deleted. Where A and B overlapped, every file was
diffed and the union of behaviours kept (below). Work continues here.

## Consolidation pass (2026-09-29)

After informed_models finished in the working copy (B), this pass made the repository the single place for the
code, every result and the project's context. Both old folders were only read; nothing in them was modified, moved
or deleted.

- **Imported** `informed_models_20260928_174709` (24 episodes, plus Kimi K3's K1 check) and its 823 new cached
  requests and 827 spend rows; **refreshed** informed_pilot and stateless_pilot (`--force`; their content was
  already the final, resumed data).
- **Verified** by replay: informed_models, informed_pilot and stateless_pilot, 54 episodes / 3,770 strokes, every
  endpoint exact, 0 closure mismatches, and 4,646 re-rendered images (photos and crop_px crops, including the
  post-change L6 crops) byte-identical. Full replay of all imported runs: below ("Verification").
- **Ported** B's final behaviour, with tests:
  - crop_px under a camera move: already equivalent (`sim/render.crop_view(..., W)` via `World.crop`); now tested in
    `tests/test_crop_camera.py` (ink appears in the crop where the moved camera shows it, not on the true page);
  - resume by log replay: already equivalent (`agents/llm_agent.ResumeAgent`); now tested against a poisoned
    request cache (`test_resume_uses_the_logged_replies_not_the_request_cache`);
  - the K1 check replays an interrupted check's log, and a cut-short check leaves the cell `stopped` (resumable)
    instead of `error` (which resume skipped): `test_cut_short_output_mode_check_stops_the_cell_and_resume_replays_it`;
  - the informed_models cap $80 -> $95 (Addendum 12 amendment).
  - Re-recording the parity fixture from both copies' **current** source gives the same 150 cases (0 differences),
    so no other behaviour changed in B after the fixture was recorded (18:26).
- **Fixed** `import-legacy --force`: it made a re-imported run a duplicate of itself (an empty manifest).
- **Added** `freehand figures` (B's `informed_report.py` and all-arms chart on this package's rows) and regenerated
  the figures into `docs/figures/`. Parity with B's `reports/informed_models/summary.csv` under the legacy scorer:
  all 21 rows byte-identical; all 42 rows of B's `rows.json` match on 15 fields. Discrepancies: the order of the three
  tied 0-rate models (Sonnet, GPT-5.5, Kimi; B took it from Python set iteration) and the code references'
  attribution label ("none" in B, blank here). Under the corrected scorer 9 informed_models cells gain one miss.
- **Quote bank**: `--fields` and deterministic `.gz` output; regenerated over every working-copy model run
  (`docs/quote_bank/`), and the highlights extended with informed_models (every quote checked against the logs).
- **Docs**: `docs/HISTORY.md` (new), `docs/findings.md` (informed_models, camera and probe claims checked against the
  logs), `docs/preregistration.md` (Addenda 12 amendment and 13), `docs/benchmark_ladder.md` (final), `docs/roadmap.md`
  (status table), the README ("Results so far", links, the archive note). The Codex copy's four publication study
  reports and two figures went to `docs/archive/codex/publication/`; B's three-model comparison text to
  `docs/archive/working_copy/three_model_comparison/`. (The release cleanup later moved `docs/archive/`,
  `docs/benchmark_ladder.md` and this file to `docs/provenance/`; the table below gives the current homes.)
- **Media** (43 MB of historical videos and charts) copied to `results/media/` (outside git).
- **Tests**: 116 passed at the time; `ruff check` clean.

## Where everything went

Current homes, after the 2026-09-29 docs reorganisation.

| Old file (copy) | New home |
|---|---|
| `sim.py` (A = B + bundled grid; B: `warp_rect`, `crop_view(W)`) | `sim/` (`geometry`, `page`, `plotter`, `render`, `camera`), both copies' features |
| `render_grid.py`, `assets/page_calib.json` (A) | `sim/render.py` (`grid_view`), `sim/assets/page_calib.json` |
| `episode.py`: prompts | `agents/prompts/v1/*.txt` + `turn.toml`, assembled by `agents/prompting.py` |
| `episode.py`: code agents | `agents/reference/{plotter_map,camera}.py` |
| `episode.py`: `run_episode` (A: render flag, numeric feedback, change at P = 0, finite commands; B: `history_landed`, `measured_ends`, crop under warp) | `episode/{world,loop,records,actions,mentions}.py`, all features of both |
| `episode.py`: `ResumeAgent` (B), `LLMAgent` | `agents/llm_agent.py` |
| `episode.py`: `metrics`, `replay`, `recompute_mentions` | `metrics/episode.py`, `replay.py`; mention screens in `episode/mentions.py` |
| `levels.py`: scenarios L2–L7, KNOBS | `perturbations/calibration.py` (typed params; `LADDER_KNOBS`, `ladder_params`) |
| `levels.py`: LOracle / LNaive / LAdaptive | `agents/reference/levels.py` |
| `levels.py`: attribution, cell metrics, verdict, ladder runner | `episode/mentions.attribution`, `analysis/report.py`; escalation not ported (below) |
| `perturbations.py` (A) | `perturbations/discriminating.py`; `LocalPatcher`, `FamilyEstimator` → `agents/reference/local.py` |
| `numeric_baselines.py` (A) | `agents/reference/numeric.py` |
| `scoring.py` (A) | `scoring.py` (+ `later_first_try`, `squares_to_run`, and the old curve for rescoring only) |
| `inkmetrics.py` | `metrics/ink.py`, `metrics/regret.py` |
| `llm.py` (A: race fix, env-file overrides; B: kimi price, `or 'auto'` route, `openrouter_balance`) | `llm/{adapter,cache,ledger,openrouter,genai,fake,registry,secrets,messages}.py`; prices and reasoning params in `configs/models.toml` |
| model settings copy-pasted in `run.py`, `levels.py`, `probe.py`, `objective_pilot.py`, `hard_pilot*.py`, `ladder.py` | `configs/models.toml` + per-experiment overrides |
| `run.py` (dry / pilot2 / full / viz / cost) | `experiments/runner.py`; `configs/experiments/pilot2.yaml`; `dry` → `freehand run smoke --fake-models` + the tests; `full` → `configs/experiments/*` with `--model`; `viz` → `freehand replay --render --images`; `cost` → `report` (tokens, cost) + the ledger |
| `analyze.py` | `analysis/report.py` (the paired-excess table was specific to the first design; not ported) |
| `viz.py` (videos, final/compare PNGs) | not ported; `freehand replay --render --images DIR` regenerates every frame (known gap: MP4 assembly) |
| `sonnet_pilot.py`, `flash_pilot.py`, `astra_pilot.py` | `configs/experiments/{sonnet,flash,astra}_pilot.yaml` |
| `ladder.py` (OpenAI capability ladder) | `configs/experiments/openai_ladder.yaml` (the cells that ran) |
| `hard_pilot.py`, `hard_pilot_reasoning.py` | `configs/experiments/hard_pilot*.yaml` (the `--check` single-turn probe: `freehand episode --max-squares 1`) |
| `levels.py --run / --dry` | `configs/experiments/ladder.yaml` (the rungs that ran); `--dry` → `freehand run ladder --fake-models` |
| `objective_pilot.py` (`--run`, `--resume`, `--report`, `--dry-stateless`, `--check`) | `configs/experiments/{objective,informed,stateless}_pilot.yaml`, `informed_models.yaml`; `freehand run --resume`; `freehand report`; `tests/test_cli_e2e.py`; `freehand suite scan` |
| `informed_report.py` (B) | `analysis/figures.py` + `freehand figures` (grid, bars, table; `--scorer legacy` reproduces B's table); `analysis/report.py` for generic reports |
| `model_study.py` (A) | `configs/experiments/model_study.yaml` (`episode_cap_mode: reservation`, `order: shuffle`, `on_error: stop`); plan-only = `--dry-run` |
| `publication_experiments.py`, `baseline_study.py` (A) | `configs/experiments/{controls,baseline_study}.yaml` (headless reference blocks) |
| `preflight_plan.py` (A) | `freehand suite verify <suite> --oracle` |
| `verify_baseline_decisions.py` (A) | superseded by `tests/test_legacy_parity.py` (the library/Broyden decisions are among the 150 cases) |
| `replay_audit.py` (A) | `replay.py` + `freehand replay` (also regenerates and checks the images) |
| `build_review_bundle.py` (A) | not ported (release bundles are a publishing decision) |
| `probe.py` (perception probe) | not ported (single questions, not episodes); its run is imported |
| `estimate_scatter.py`, `scatter_estimate.json` | not ported: the estimate needs the hardware project's runs; its result is the landing model in `sim/plotter.py` |
| B `reports/quote_bank` (no generator) | `analysis/quote_bank.py` + `freehand quote-bank`; data and highlights in `docs/quote_bank/` (the 2026-09-27 highlights also verbatim in `docs/provenance/quote_bank_2026-09-27.md`) |
| B `reports/*` charts, `three_model_comparison/` | copied to `results/media/working_copy_reports/` (not in git); `freehand figures` regenerates the study charts into `docs/figures/` |
| A `publication/*/source/` (4 code copies), `release/*.zip` | not copied; the publication episodes are imported. The study `REPORT.md`s and two figures: `docs/provenance/codex/publication/` |
| `KEY_FINDINGS.md` (A and B, contradictory) | `docs/findings.md` (merged conservatively); originals in `docs/provenance/` |
| `PREREGISTRATION.md` (A: addenda 1–9; B: 1–12) | `docs/preregistration.md` (the union, verbatim, with provenance) |
| `INTELLIGENCE_PERTURBATIONS.md` | `docs/design/perturbation_ideas.md` |
| `BENCHMARK_LADDER.md` (B newer) | `docs/provenance/benchmark_ladder.md` |
| `ROADMAP.md` (B) | `docs/provenance/roadmap_2026-09-28.md` (the maintained plan: `docs/roadmap.md`) |
| `RELATED_WORK.md` (A) | `docs/related_work.md` |
| A `README`, `PUBLICATION_REPORT`, `MODEL_STUDY` | `docs/provenance/codex/` (its session logs `PUBLICATION_PLAN`, `CONTINUATION_REPORT` and `OVERNIGHT` were dropped in the release cleanup) |
| `requirements*.txt`, `requirements.lock` (A) | `pyproject.toml` + a regenerated `requirements.lock` (adds PyYAML, jsonschema, pytest, ruff) |
| `cache.sqlite` (A ⊂ B) | merged into `results/cache/llm_cache.sqlite`; spend into `results/ledger.sqlite` |
| `runs/`, `publication/*/episodes` | `results/legacy/` via `freehand import-legacy` |

## Behaviour

### Preserved exactly (tested)

- **Pages, rules, ink, closure, rendering.** The simulator is bit-identical to both copies.
  - Historical pages, rule parameters, change points and camera homographies regenerate from the legacy suites.
  - Rendered images are byte-identical, down to the pilot2 turn-1 PNG.
- **Every request.**
  - The system prompts, state blocks, notepad and history handling, and image bytes are identical.
  - So are the request-cache keys, for every arm (memory, stateless, numeric landed ends, crop_px, disclosures,
    objective and informed blocks, numeric feedback, L7's line, K = 0, history off).
  - Test: `tests/test_legacy_parity.py`, below.
- **Reference agents.** All of them reproduce the historical commands.
- **Budget accounting.** A's fix is kept: spend is recorded before the reservation is released.

### Changed on purpose

- **First-try scoring.** A's corrected scorer is used everywhere. A square interrupted after a failed first stroke
  counts as a miss; it no longer disappears. Rescoring table below.
- **Episode cap.** It counts each call's original cost, including cache hits (it used to count only new spend).
  - The old rule made `capped` depend on what was cached. Pilot2's Opus `cam_transfer` episode ran to $1.07
    against a $0.80 cap because 23 of its 29 calls were cache hits left from an earlier attempt. The two Astra shear
    objective-pilot episodes likewise ran 1–2 strokes past their caps.
  - Under the new rule a replay from the cache or a resume stops exactly where it should.
- **Budget stops.** A budget refusal stops the episode *and* marks every cell not yet started `not_run_budget`
  (A's model-study rule, now everywhere). B's pilots let later cells start and fail one by one.
- **Change at square 0.** A change scheduled at P = 0 is active from the first stroke for every rule. This was
  A's fix for scenarios; the plotter-map path never used P = 0.
- **K1 output-mode gate.** A check episode that was cut short decides nothing and raises. This is B's late change;
  before it, a cut-short check defaulted to crop_px.
- **Conflicting repeats of a cell across runs raise an error** in reports (A's rule). Identical repeats, such as
  the deterministic references, are merged.
- **Keys.**
  - The OpenRouter key comes only from `OPENROUTER_API_KEY` or `<repo>/.env`.
  - The historical hardcoded key-file paths and the `FREEHAND_*_ENV_FILE` overrides are gone.
  - The key is read lazily, so cache hits need none.
- **Gemini's default route is OpenRouter.** The `flash` entry points at `google/gemini-3.8-flash`. The historical
  direct Gemini API is kept as `flash-genai`; the historical configs use it, so their cached requests replay.
- **IPv4 forcing.** The historical workaround (a process-wide urllib3 setting) is opt-in:
  `FREEHAND_FORCE_IPV4=1` (it was on by default until the 2026-09-29 release cleanup).
- **Images.** They are not stored by default (`--save-images`); each turn logs the sha256 of every image sent,
  and `replay --render` regenerates and checks them.

## Verification

- **Tests.** 116 passed at the consolidation (`pytest`; 109 at the first migration, +7 in the consolidation), 24 of
  them A's tests ported one-to-one:
  - `test_ported_model_workflow`: 6 (renamed `test_model_study_workflow` in the release cleanup);
  - `test_ported_numeric_baselines`: 5 (now `test_numeric_baselines`);
  - `test_ported_publication`: 13 (now `test_scoring_and_stateful_rules`);
  - also seeding and golden hashes, suite verification and tamper detection, registry and unregistered slugs, the
    llm layer, the results writer and schemas, a fake-model `freehand run` end to end (tree, validate, report,
    replay with images, ls), the stateless / crop_px / resume / crash-resume paths, the budget cap, the episode
    cap, the legacy import on a verbatim fixture, and prompt snapshots;
  - added in the consolidation: crop_px under a camera move (3), resume against a poisoned cache and the K1 check
    replay (2), `freehand figures` and the quote-bank fields / gzip (2); the legacy-import test also covers
    `--force`.
  - `ruff check`: clean.
- **Prompt and behaviour parity.** `tests/test_legacy_parity.py` compares against a fixture recorded by running
  the original code of both copies.
  - Scope: 150 cases, 4,919 turns and 1,805 full-request keys (system prompt + every message + image bytes).
  - Result: 0 differences.
  - 28 representative cases run by default; `FREEHAND_FULL_PARITY=1` runs all 150.
- **Replay audit of every imported historical episode**, under the new code (re-run 2026-09-29):
  - 35 runs, 1,901 episodes / 52,024 strokes from A's runs, B's runs (including informed_pilot, stateless_pilot,
    informed_models and Kimi's K1 check) and A's publication studies;
  - every endpoint exact (max error 0.0 mm), 0 closure mismatches, 0 errors.
  - The 23 A runs that duplicate B's are linked, not replayed twice.
- **Image audit.** Re-rendering what the models saw in every historical model run gives 6,791 images (photos,
  crops, raw camera frames, stale-rectified views) across 195 episodes, plus 2,998 for informed_models (2026-09-29).
  Every one is byte-identical to the original PNG.
- **Reproduction from the merged cache at $0** (`freehand run <config> --max-usd 0`):
  - `pilot2`: 20 cells, 19 identical to history. The Opus `cam_transfer` cell is now capped at 23 strokes (see
    the episode-cap change).
  - `objective_pilot`: 21 cells, 19 identical; the 2 Astra shear cells are capped 1–2 strokes earlier (same
    reason).
  - `informed_models` (partial, while B was still running it): Sol rot13 reproduced completely. Sonnet's three
    crop_px episodes matched B's logs stroke for stroke up to the end of the cache snapshot (71–133 strokes).
    Sol's shear and camera episodes diverged at strokes 4–5. Before the change the three rules send *identical*
    requests; B ran them concurrently, each got its own reply, and the cache keeps one reply per request. So a
    cache replay reproduces an episode only as far as its requests are unique, the limitation B's `ResumeAgent`
    docstring records. The logged episodes (imported), not cache replays, are the historical record.
  - This confirms the historical configs carry the exact model settings: every request that could hit did.
- **Suites.** Every legacy suite regenerates its historical pages exactly: checked against 13 historical episodes
  of every design, and structurally by the importer's suite matching.
  - Every historical episode whose seed, page shape and rule parameters a legacy suite covers matched it.
  - 138 imported episodes carry a `page.json` instead: the dry runs, the extra L7 seeds of the ladder checks, and
    the first ladder dry run's older L5 knobs (0.3 mm/stroke, not a frozen rung).

## Rescoring with the corrected scorer

Model episodes of B's objective_pilot, informed_pilot and stateless_pilot (the final data, after the Addendum 12
resumes); all 9 reference episodes are unchanged. "Later" = squares 6–20 (hits / squares reached); "post" =
squares 5–20. **Bold** = changed by rescoring.

| Run | Model | Rule | Arm | Status | Later: old → new | Post: old → new |
|---|---|---|---|---|---|---|
| objective_pilot | Opus 5.5 | rot13 | silent | capped | 2/9 → 2/9 | 2/10 → 2/10 |
| objective_pilot | Opus 5.5 | rot13 | objective | capped | **0/9 → 0/10** | **0/10 → 0/11** |
| objective_pilot | Opus 5.5 | shear | silent | complete | 0/15 → 0/15 | 0/16 → 0/16 |
| objective_pilot | Opus 5.5 | shear | objective | complete | 0/15 → 0/15 | 0/16 → 0/16 |
| objective_pilot | Opus 5.5 | camera | silent | complete | 12/15 → 12/15 | 12/16 → 12/16 |
| objective_pilot | Opus 5.5 | camera | objective | stopped | **1/2 → 1/3** | **1/3 → 1/4** |
| objective_pilot | Astra | rot13 | silent | complete | 14/15 → 14/15 | 14/16 → 14/16 |
| objective_pilot | Astra | rot13 | objective | complete | 13/15 → 13/15 | 13/16 → 13/16 |
| objective_pilot | Astra | shear | silent | capped | 4/10 → 4/10 | 4/11 → 4/11 |
| objective_pilot | Astra | shear | objective | capped | 10/13 → 10/13 | 10/14 → 10/14 |
| objective_pilot | Astra | camera | silent | stopped | 13/14 → 13/14 | 13/15 → 13/15 |
| objective_pilot | Astra | camera | objective | stopped | 8/9 → 8/9 | 8/10 → 8/10 |
| informed_pilot | Opus 5.5 | rot13 | informed_objective | complete | 11/15 → 11/15 | 11/16 → 11/16 |
| informed_pilot | Opus 5.5 | shear | informed_objective | complete | 8/15 → 8/15 | 8/16 → 8/16 |
| informed_pilot | Opus 5.5 | camera | informed_objective | complete | 13/15 → 13/15 | 13/16 → 13/16 |
| informed_pilot | Astra | rot13 | informed_objective | complete | 14/15 → 14/15 | 14/16 → 14/16 |
| informed_pilot | Astra | shear | informed_objective | complete | 13/15 → 13/15 | 13/16 → 13/16 |
| informed_pilot | Astra | camera | informed_objective | complete | 11/15 → 11/15 | 12/16 → 12/16 |
| stateless_pilot | Opus 5.5 | rot13 | stateless_image | capped | 0/9 → 0/9 | 0/10 → 0/10 |
| stateless_pilot | Opus 5.5 | rot13 | stateless_numeric | complete | 11/15 → 11/15 | 11/16 → 11/16 |
| stateless_pilot | Opus 5.5 | shear | stateless_image | capped | **1/14 → 1/15** | **1/15 → 1/16** |
| stateless_pilot | Opus 5.5 | shear | stateless_numeric | complete | 2/15 → 2/15 | 2/16 → 2/16 |
| stateless_pilot | Astra | rot13 | stateless_image | capped | 4/10 → 4/10 | 4/11 → 4/11 |
| stateless_pilot | Astra | rot13 | stateless_numeric | complete | 15/15 → 15/15 | 15/16 → 15/16 |
| stateless_pilot | Astra | shear | stateless_image | capped | 2/6 → 2/6 | 2/7 → 2/7 |
| stateless_pilot | Astra | shear | stateless_numeric | capped | 11/13 → 11/13 | 11/14 → 11/14 |

informed_models (imported 2026-09-29; the other 6 of its 15 model episodes are unchanged):

| Run | Model | Rule | Status | Later: old → new | Post: old → new |
|---|---|---|---|---|---|
| informed_models | GPT-6 Sol | shear | capped | **0/11 → 0/12** | **0/12 → 0/13** |
| informed_models | GPT-6 Sol | camera | capped | **0/11 → 0/12** | **0/12 → 0/13** |
| informed_models | Sonnet 5 | rot13 | capped | **0/12 → 0/13** | **0/13 → 0/14** |
| informed_models | Sonnet 5 | camera | capped | **0/13 → 0/14** | **0/14 → 0/15** |
| informed_models | GPT-5.5 | rot13 | capped | **0/1 → 0/2** | **0/2 → 0/3** |
| informed_models | GPT-5.5 | shear | capped | **0/2 → 0/3** | **0/3 → 0/4** |
| informed_models | GPT-5.5 | camera | capped | **0/3 → 0/4** | **0/4 → 0/5** |
| informed_models | Kimi K3 | rot13 | stopped | **0/2 → 0/3** | **0/3 → 0/4** |
| informed_models | Kimi K3 | shear | stopped | **0/1 → 0/2** | **0/2 → 0/3** |

**Flagged:**

- Three numbers change in the three pilots, and nine in informed_models: all toward one more miss, no hit changes,
  and none is a headline cell.
- The resumes (not rescoring) moved several informed/stateless cells after the Addendum 11 / BENCHMARK_LADDER
  tables were written:
  - Opus shear informed: 6/13 (stopped) → 8/15 (complete);
  - Opus camera informed: 9/10 → 13/15;
  - Astra camera informed: 6/10 → 11/15;
  - Astra rot13 stateless numeric: 14/14 → 15/15;
  - Astra rot13 stateless image: 3/5 → 4/10 (capped);
  - Opus rot13 stateless image: 0/3 → 0/9 (capped);
  - the stateless shear cells, previously "no data", now exist.
- `docs/findings.md` uses the final numbers. `docs/provenance/benchmark_ladder.md` is verbatim history and still shows the old
  ones.

## Legacy import

`freehand import-legacy --source working=<working copy> --source codex=<parallel copy> --merge-cache` indexed every
historical run into
`results/legacy/`:

- 35 converted runs (1,901 episodes, including informed_models and its K1 check, imported 2026-09-29);
- 23 of A's runs recorded as duplicates of B's (identical content, linked via `duplicate_of`);
- A's `_objective_checks` differs from B's (re-run with newer code), so both are kept;
- each run has an `original` symlink;
- the PNGs are hashed, not copied (the converted logs take 187 MB).

The request caches were merged: B's 3,588 cached requests at the time, which contain all 2,268 of A's. The spend
rows were merged into the ledger with `source = legacy:<copy>`. Both merges are idempotent.

**informed_models** (B, Addendum 12) was running during the first migration and was imported on 2026-09-29 with
the command below (+823 cached requests, +827 spend rows). informed_pilot and stateless_pilot were refreshed with
`--only ... --force`; their content hashes already matched the final, resumed data.

```sh
freehand import-legacy --source working=<working copy> --only 'informed_models_*' --merge-cache
```

K1 output-mode checks (`runs/<run>/checks/`) are imported too, under the perturbation label `check`, and listed in
the manifest's `output_mode_checks` (reports and figures skip them).

## Quote bank

The historical `all_quotes.csv` (3,273 rows, 91 episodes) had no generator. `freehand quote-bank` implements a
documented rule: the union of both mention screens plus hypothesis/measurement words. It stores text
whitespace-collapsed and cut at 1,500 characters, as the historical bank did.

On the same runs it recovers 3,207 of the 3,273 historical rows (98.0%), with identical text, and adds 742 more
(3,949 rows). It is a superset to curate from, not a reproduction. The 66 historical rows it misses match none of
its keywords.

## Late changes (re-read at the end)

B's `objective_pilot.py`, `PREREGISTRATION.md` and `informed_report.py` were re-read after the rest of the migration.

- **`objective_pilot.py`** changed at 18:48 (during the migration). Ported:
  - the K1 gate refuses to decide on a cut-short check;
  - resume recovers episodes whose process died mid-episode (drops a truncated last log line) and runs
    never-started episodes in priority order.
  - Regression test: `test_resume_recovers_an_episode_whose_process_died`.
- **`PREREGISTRATION.md`** (last modified 17:33) and **`informed_report.py`** (17:36): unchanged since the snapshot
  this migration started from (re-read at 19:39 EDT). `docs/preregistration.md` is identical to B's file below its
  provenance header; Addendum 12 is the latest. `informed_report.py`'s charts and table are generalised in
  `analysis/report.py` / `analysis/charts.py`.
- **B's `cache.sqlite`** was re-merged at the end (+161 requests from informed_models so far); re-run the import
  command above once informed_models finishes (done 2026-09-29: +823 more).

**Changes in B after the first migration** (re-read 2026-09-29; every B file modified after 18:30 EDT):

| File (last modified, EDT) | Change | Here |
|---|---|---|
| `objective_pilot.py` (22:01) | the K1 check replays an interrupted check's log (`ResumeAgent`); informed_models cap $95 | ported: `experiments/runner._k1_gate`, `OutputModeCheckStopped` (a cut check is now `stopped`, resumable); `configs/experiments/informed_models.yaml` |
| `informed_report.py` (23:44) | final grid / bars / table layout | `analysis/figures.py`, `freehand figures` (parity above) |
| `PREREGISTRATION.md` (23:45) | Addendum 12 amendment ($95), Addendum 13 | `docs/preregistration.md`, verbatim |
| `BENCHMARK_LADDER.md` (23:45) | informed/stateless "complete"; informed_models section | `docs/provenance/benchmark_ladder.md`, verbatim |
| `cache.sqlite` (23:43) | informed_models calls | merged (+823 requests, +827 spend rows) |
| `sim.py` (17:30), `llm.py` (17:31), `episode.py` (17:32), `ROADMAP.md` (17:40) | before the parity fixture (18:26) | already ported; the re-recorded fixture is identical |

B's `KEY_FINDINGS.md`, `INTELLIGENCE_PERTURBATIONS.md` and `reports/quote_bank/*` were last changed on 2026-09-27
and are unchanged since the first migration.

## Open questions at the consolidation

The consolidation listed where the two copies (or the logs) disagreed, and the design questions still open.

- **Claims.** Every disagreement about a claim ("knowing ≠ using", "every model blames the plotter", "no probe
  marks", "recovers about as fast as an ideal estimator", "the benchmark looks saturated", "memory is essential",
  which models "get it") is resolved conservatively in [../findings.md](../findings.md): it states only what the
  logs support, with the evidence level.
- **Design questions** (the main score, public test seeds, core-v1's composition, the K1 gate size, the Gemini
  route, the episode-cap rule, resume order, adaptive designs, the model-study plan) are in
  [../roadmap.md](../roadmap.md#open-design-questions).

## Known gaps

- **No live run of this repository yet.** The smoke command without a key stopped cleanly with `MissingKeyError`
  at $0; the same episode with `--fake-models` wrote the full tree.
- **Not ported:** `viz.py` video/compare assembly (frames regenerate with `replay --render --images`; the historical
  videos are in `results/media/`); the perception probe; `analyze.py`'s paired-excess table (first design only); the
  ladder / OpenAI-ladder adaptive stop rules; `build_review_bundle.py`; `estimate_scatter.py` (needs the hardware
  runs).
- **Not implemented:** `one_shot` mode, the coloured-pen carousel, the Freehand A model study, and the other
  roadmap items ([../roadmap.md](../roadmap.md)).
- **Figures:** the order of tied 0-rate models in the grid and bars can differ from B's (set order there).
- **Quote bank:** the keyword rule misses some relevant texts (e.g. GPT-5.5's "Previous apparent perturbations were
  likely mostly misread/clutter" has none of its keywords), and reasoning summaries are cut at 1,500 characters.
  Curated quotes in HIGHLIGHTS.md were checked against the full logs.
- **`requirements.lock`** was regenerated offline; strict `--require-hashes` installs on other platforms may need a
  regeneration with network access. Only macOS arm64 / CPython 3.12 was tested.
- **Image determinism** is guaranteed only under the pinned numpy/OpenCV builds. The data hashes are the portable
  guarantee.
