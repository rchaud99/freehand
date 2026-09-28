# Migration: from the two historical copies to this repository (2026-09-28)

This repository replaces two diverged working folders:

- **A, the Codex copy** (`~/Documents/Codex/2026-09-27/anal/outputs/freehand_publish`). The better-engineered
  base: 24 offline tests, the corrected first-try scorer, replay audit, the discriminating rules, numeric baselines,
  the model-study runner, a dependency lock, bundled grid renderer and calibration asset, the budget-race fix, and
  rejection of non-finite commands.
- **B, the working copy** (`~/Desktop/strokes_research/freehand_b`). The newer experiments: the informed and
  stateless arms, informed_models, resume, the landed-ends history, crop views under a stale rectification, kimi,
  the reasoning adapters, the balance check, and the newest docs.

Both were only read: nothing in either was modified, moved or deleted. Where A and B overlapped, every file was
diffed and the union of behaviours kept (below). Work continues here.

## Where everything went

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
| `informed_report.py` (B) | `analysis/report.py` + `analysis/charts.py` (learning-curve grid and first-try bars for any runs and arms) |
| `model_study.py` (A) | `configs/experiments/model_study.yaml` (`episode_cap_mode: reservation`, `order: shuffle`, `on_error: stop`); plan-only = `--dry-run` |
| `publication_experiments.py`, `baseline_study.py` (A) | `configs/experiments/{controls,baseline_study}.yaml` (headless reference blocks) |
| `preflight_plan.py` (A) | `freehand suite verify <suite> --oracle` |
| `verify_baseline_decisions.py` (A) | superseded by `tests/test_legacy_parity.py` (the library/Broyden decisions are among the 150 cases) |
| `replay_audit.py` (A) | `replay.py` + `freehand replay` (also regenerates and checks the images) |
| `build_review_bundle.py` (A) | not ported (release bundles are a publishing decision) |
| `probe.py` (perception probe) | not ported (single questions, not episodes); its run is imported |
| `estimate_scatter.py`, `scatter_estimate.json` | not ported: the estimate needs the hardware project's runs; its result is the landing model in `sim/plotter.py` |
| B `reports/quote_bank` (no generator) | `analysis/quote_bank.py` + `freehand quote-bank`; curated highlights in `docs/archive/quote_bank/` |
| B `reports/*` charts, `three_model_comparison/` | not copied (generated media); `freehand report` on the imported runs regenerates the charts |
| A `publication/*/source/` (4 code copies), `release/*.zip` | not copied; the publication episodes are imported |
| `KEY_FINDINGS.md` (A and B, contradictory) | `docs/findings.md` (merged conservatively); originals in `docs/archive/` |
| `PREREGISTRATION.md` (A: addenda 1–9; B: 1–12) | `docs/preregistration.md` (the union, verbatim, with provenance) |
| `INTELLIGENCE_PERTURBATIONS.md` | `docs/perturbations.md`, part 2 |
| `BENCHMARK_LADDER.md` (B newer) | `docs/benchmark_ladder.md` |
| `ROADMAP.md` (B) | `docs/roadmap.md` |
| `RELATED_WORK.md` (A) | `docs/related_work.md` |
| A `README`, `PUBLICATION_*`, `CONTINUATION_REPORT`, `MODEL_STUDY`, `OVERNIGHT` | `docs/archive/codex/` |
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
  - The historical hardcoded `~/Desktop/...` key files and the `FREEHAND_*_ENV_FILE` overrides are gone.
  - The key is read lazily, so cache hits need none.
- **Gemini's default route is OpenRouter.** The `flash` entry points at `google/gemini-3.8-flash`. The historical
  direct Gemini API is kept as `flash-genai`; the historical configs use it, so their cached requests replay.
- **IPv4 forcing.** It is applied only when a live OpenRouter call is made, and can be disabled
  (`FREEHAND_FORCE_IPV4=0`).
- **Images.** They are not stored by default (`--save-images`); each turn logs the sha256 of every image sent,
  and `replay --render` regenerates and checks them.

## Verification

- **Tests.** 109 pass (`pytest`), 24 of them A's tests ported one-to-one:
  - `test_ported_model_workflow`: 6;
  - `test_ported_numeric_baselines`: 5;
  - `test_ported_publication`: 13;
  - also seeding and golden hashes, suite verification and tamper detection, registry and unregistered slugs, the
    llm layer, the results writer and schemas, a fake-model `freehand run` end to end (tree, validate, report,
    replay with images, ls), the stateless / crop_px / resume / crash-resume paths, the budget cap, the episode
    cap, the legacy import on a verbatim fixture, and prompt snapshots.
  - `ruff check`: clean.
- **Prompt and behaviour parity.** `tests/test_legacy_parity.py` compares against a fixture recorded by running
  the original code of both copies.
  - Scope: 150 cases, 4,919 turns and 1,805 full-request keys (system prompt + every message + image bytes).
  - Result: 0 differences.
  - 28 representative cases run by default; `FREEHAND_FULL_PARITY=1` runs all 150.
- **Replay audit of every imported historical episode**, under the new code:
  - 1,876 episodes / 49,901 strokes from A's runs, B's runs (including informed_pilot and stateless_pilot) and A's
    publication studies;
  - every endpoint within 1e-6 mm, 0 closure mismatches.
  - The 23 A runs that duplicate B's are linked, not replayed twice. informed_models was still running.
- **Image audit.** Re-rendering what the models saw in every historical model run gives 6,791 images (photos,
  crops, raw camera frames, stale-rectified views) across 195 episodes. Every one is byte-identical to the original
  PNG.
- **Reproduction from the merged cache at $0** (`freehand run <config> --max-usd 0`):
  - `pilot2`: 20 cells, 19 identical to history. The Opus `cam_transfer` cell is now capped at 23 strokes (see
    the episode-cap change).
  - `objective_pilot`: 21 cells, 19 identical; the 2 Astra shear cells are capped 1–2 strokes earlier (same
    reason).
  - This confirms the historical configs reproduce the exact model settings (every cached request matched).
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

**Flagged:**

- Three numbers change, all toward more misses, and none is a headline cell.
- The resumes (not rescoring) moved several informed/stateless cells after the Addendum 11 / BENCHMARK_LADDER
  tables were written:
  - Opus shear informed: 6/13 (stopped) → 8/15 (complete);
  - Opus camera informed: 9/10 → 13/15;
  - Astra camera informed: 6/10 → 11/15;
  - Astra rot13 stateless numeric: 14/14 → 15/15;
  - Astra rot13 stateless image: 3/5 → 4/10 (capped);
  - Opus rot13 stateless image: 0/3 → 0/9 (capped);
  - the stateless shear cells, previously "no data", now exist.
- `docs/findings.md` uses the final numbers. `docs/benchmark_ladder.md` is verbatim history and still shows the old
  ones.

## Legacy import

`freehand import-legacy --source working=~/Desktop/strokes_research/freehand_b --source
codex=~/Documents/Codex/2026-09-27/anal/outputs/freehand_publish --merge-cache` indexed every historical run into
`results/legacy/`:

- 34 converted runs (1,876 episodes);
- 23 of A's runs recorded as duplicates of B's (identical content, linked via `duplicate_of`);
- A's `_objective_checks` differs from B's (re-run with newer code), so both are kept;
- each run has an `original` symlink;
- the PNGs are hashed, not copied (the converted logs take 187 MB).

The request caches were merged: B's 3,588 cached requests at the time, which contain all 2,268 of A's. The spend
rows were merged into the ledger with `source = legacy:<copy>`. Both merges are idempotent.

**informed_models** (B, Addendum 12) was running during the migration and was excluded. When it has finished,
import it and pick up its cached requests with:

```sh
freehand import-legacy --source working=~/Desktop/strokes_research/freehand_b --only 'informed_models_*' --merge-cache
```

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
- **`PREREGISTRATION.md`, `informed_report.py`**: see the final check at the bottom of this file.

## Needs a human decision

1. **Findings, "Knowing ≠ using".** B's KEY_FINDINGS #3 says Opus writes the correct model and doesn't apply it. A
   withdrew it: a roughly correct inverse can miss through imprecise estimates. B's later informed-arm result (Opus
   2/9 → 11/15 when told a rule exists) supports a framing reading. findings.md states neither conclusion.
2. **Findings, "every model blames the plotter when the camera moved" (12/12).** B asserts it; A says the keyword
   classifier is unvalidated and needs behavioural probes. findings.md lists it as a hypothesis.
3. **Findings, "recover about as fast as an ideal statistical estimator".** B uses the phrase; A says the estimators
   are privileged controls, not proven optima. findings.md keeps A's boundary.
4. **Findings, "made the benchmark look saturated".** B uses it; A says the pilots establish no rankings or
   saturation. findings.md keeps A's wording.
5. **Findings, "the patching failure is largely motivational/framing for Opus, not an inability to fit"** (B's
   BENCHMARK_LADDER verdict). With the final data, Opus stateless-numeric shear is 2/15 while informed shear is
   8/15, so fitting shear is not settled; A's boundary 3 also applies. Left open.
6. **Findings, numbers never recomputed.** B's KEY_FINDINGS ladder totals (Opus ~8/42, Astra ~12/39 first-try on
   later squares) were never recomputed and are not repeated in findings.md. Recompute with `freehand rescore` on
   the ladder run, or drop them.
7. **Findings, "memory is essential"** (B, supporting). The stateless-numeric results (Opus 11/15 on rotation
   without notes) qualify it; findings.md drops the general claim.
8. **OpenRouter key.** `<repo>/.env` was **not created**:
   - the file named in the brief (`~/Desktop/how_much_is_a_look_worth/.env`) has no `OPENROUTER_API_KEY` line
     (only Gemini and Anthropic keys);
   - copying the line from `~/Desktop/jev_npc/.env`, where B's code read it, was blocked by the permission system.
   - To enable paid runs, create `.env` yourself (see `.env.example`).
   - The real smoke run therefore did not happen (Known gaps).
9. **Private test seeds.** The core-v1 / discriminating-v1 / camera-v1 test seeds are in a public file, so they
   are held out only by convention. A truly private split needs the seeds kept outside the repo.
10. **Benchmark mode.** The roadmap makes `one_shot` (one stroke per target, fresh targets) the main v1 score; the
    frozen suites here are `retry` mode, the mode of all historical data. `one_shot` is not implemented.
11. **core-v1 composition.** Command memory could not go into core-v1: its inverse leaves the page on the far-apart
    layout for every seed. It is in discriminating-v1 (A's central page). Alternatively, redesign the page.
12. **Gemini route.** Future Flash results (via OpenRouter) and historical ones (direct API) are not guaranteed
    identical; provider-side settings differ (media resolution). Decide whether benchmark tables mix them.
13. **The first pilots** (`pilot_20260927_140928`, `pilot_20260927_142254`) used the pre-memory single-turn design;
    neither copy still has that code. They are imported and replay exactly but cannot be re-run.
14. **Adaptive study designs.** The ladder's escalation rule and the OpenAI ladder's stop-after-two-failures rule
    are not in the generic runner; their configs list the cells that ran. Port them as runner strategies if the
    ladder will be re-run.
15. **Episode-cap semantics** (the change above) makes two historical episodes capped earlier on reproduction.
    Confirm this is the rule you want going forward. The alternative is exact historical reproduction, which
    depends on cache state.
16. **The 48-cell model study** keeps A's cap of $0 (plan only). Set `budget.cap_usd` when you decide to run it.
    Its cell order differs from A's shuffle; the cell set is the same.
17. **License.** Not chosen (README says TODO).
18. **The old folders.** The roadmap says to freeze `freehand_b` as an archive. Nothing was deleted; archiving,
    deleting the 20+ GB of historical PNGs, or keeping them is your call. The imported runs depend on them only for
    images and videos (via the `original` symlinks).

## Known gaps

- **Real smoke run not done.** No OpenRouter key was available (decision 8). The exact command, `freehand episode
  --model flash --suite smoke-v1 --seed 1 --perturbation rot13 --tag repo_smoke --max-usd 1.50 --name repo_smoke`,
  was run. It stopped cleanly with `MissingKeyError` at $0 (`results/repo_smoke/20260928T231911Z-efcb40`). The same
  episode with `--fake-models` wrote the full tree (`results/repo_smoke/20260928T231911Z-13d9fb`).
- **Not ported:**
  - `viz.py` video/compare assembly (frames regenerate with `replay --render --images`);
  - the perception probe;
  - `analyze.py`'s paired-excess table (first design only);
  - the ladder / OpenAI-ladder adaptive stop rules;
  - `build_review_bundle.py`;
  - `estimate_scatter.py` (needs the hardware runs).
- **`one_shot` mode**, the coloured-pen carousel and the other roadmap/design items are not implemented.
- **`requirements.lock`** was regenerated offline from the local cache. Its hash lists cover the cached
  distributions; strict `--require-hashes` installs on other platforms may need a regeneration with network
  access. Only macOS arm64 / CPython 3.12 was tested.
- **Image determinism** is guaranteed only under the pinned numpy/OpenCV builds. The data hashes are the portable
  guarantee.
- **informed_models** must be imported after it finishes (command above).
