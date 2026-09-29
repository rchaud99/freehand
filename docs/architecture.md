# Architecture

The bar: an outside researcher clones the repo, reads one README, and runs any OpenRouter model on a frozen suite
with one command. The same suite and seed give identical data, the results land in a documented tree, and every
historical result stays comparable. This page explains how the pieces meet that bar and where the design departs
from the original plan for the package, with the reason.

## Data flow

```
configs/experiments/X.yaml ──► experiments.config ──► cells (model|reference × rule × arm × seed)
                                     │                        │
configs/suites/S.yaml ──► suites (page, schedule, rules; data_hash verified before any run)
                                     │                        ▼
configs/models.toml ──► llm.registry ──► adapter ─► cache ─► budget/ledger ─► OpenRouter
                                                              ▲
                          episode.loop:  World (sim + rule) ─► agents.prompting (arm, prompts/v1) ─► agent.act
                                                              │
                          results.writer ──► results/<exp>/<run_id>/{manifest.json, episodes/..., report/}
                                         └─► results/index.jsonl (append-only)
```

## Packages

| Package | Responsibility | Key decisions |
|---|---|---|
| `seeding` | Named random substreams | See [Seeds](#seeds). |
| `sim` | Page generation, plotter landing model, closure, rendering, camera | Numerically identical to the historical `sim.py`: every expression kept in the same order, because float results depend on it. The grid renderer and calibration asset are bundled, so there is no import of the hardware project. |
| `perturbations` | One class per rule, typed frozen `Params`, registry | Two historical code paths are kept as types (`rotation` vs `L2_rotation`), because their reference estimators differ (see perturbations.md). |
| `suites` | YAML suite files, generation, hashing, feasibility scan, episode setup | See [Frozen data](#frozen-data). |
| `prompts` | The versioned model-facing text | Every model-facing string is a file under `prompts/v1/` (a leaf module: the perturbations and agents both read it). |
| `agents` | Arms, prompt assembly, LLM agent, reference agents | An arm is data (memory × history × disclosure × prompt blocks × feedback × output mode), not a subclass. |
| `llm` | Request cache, spend ledger, budgets, OpenRouter + historical Gemini adapters, registry, secrets | Cache and ledger are separate files: the cache is shareable and reusable, the ledger is accounting. Request keys are byte-identical to the historical ones. |
| `episode` | `World` (simulation state + the change), the loop, turn/summary records | The historical 250-line `run_episode` split into World (render/land/activate), prompting (requests), records (layout) and a small loop. The parity test pins the behaviour. |
| `scoring`, `metrics` | First-try curve/summary, episode metrics, ink, regret | `scoring.py` is the corrected scorer of the 2026-09-28 review. |
| `experiments` | Config → cells → the generic runner | One runner replaces ten scripts. Blocks are cartesian products, so irregular historical designs (per-job caps, subsets) are several blocks. |
| `results` | Run tree, manifest, index, JSON Schemas, provenance, the data export (`export.py`) | Nothing about a run lives in git; the manifest records the git commit and a source hash instead. |
| `replay` | Re-simulate logs; regenerate observations | Images are off by default because replay regenerates them and checks each sha256. |
| `analysis` | Reports, charts, study figures (`figures.py`: grid, bars, all-arms, table; corrected or legacy scorer), quote bank, rescoring | Works identically on new and imported runs. |
| `legacy` | Import historical runs, match suites, merge caches/ledgers | Never moves or copies originals; symlinks and hashes them. |

## Seeds

Every random draw is `seeding.rng(seed, "<stream>", *keys)` = `numpy.random.default_rng([seed, *tag])`, a
`SeedSequence`-seeded PCG64 generator.

- **Named streams.** `page.layout`, `page.paper`, `plotter.map`, `landing` (+ stroke), `camera.pose` (+ pose),
  `study.configuration`, and so on. Drawing from one stream never shifts another. Adding a rule, a model or an arm
  cannot change a page.
- **Legacy tags.** The streams that existed before this repo keep the integer tags the old code used
  (`[seed, 1]` page, `[seed, 99]` plotter change, `[seed, 1000 + stroke]` landing noise, ...). The historical data
  therefore regenerates exactly with no separate legacy generator.
- **New streams.** A new stream's tag is a hash of its name, placed above 2³¹, so it can never collide with a
  legacy tag.

*Deviation from the plan:* the plan was to keep a separate `legacy` generator path if exact regeneration
proved impossible. It proved possible, so there is one generator, and the legacy suites use it with the historical
parameters. `tests/test_suites.py` pins historical pages down to the pilot2 turn-1 PNG bytes.

## Frozen data

A suite file freezes the generator version, the page spec, the change schedule (fixed square, or `study-v1`: a
per-seed change square and rule parameters), the named rules with typed parameters, and explicit `dev` and `test`
seed lists.

- **`data_hash`.** sha256 over "seed:seed_hash" lines. A seed hash is sha256 of the canonical JSON of that seed's
  page (every square, its hand-drawn ink and its open corners), schedule and realised rules (directions, signs,
  thresholds, camera homographies), with floats rounded to 1e-6. `freehand suite verify` and the tests recompute
  it; the runner refuses to run a suite whose hash no longer verifies.
- **What is portable.** The *data* hash is the cross-platform guarantee. Rendered images are byte-identical under
  the pinned numpy/OpenCV builds (pyproject pins them exactly; `requirements.lock` pins the rest), and the tests
  pin image hashes under that lock only.
- **Seed selection.** Seeds come from `freehand suite scan`, a *feasibility* filter (the page can be placed, and
  the oracle reaches every target without clamping under every rule), applied in increasing order and recorded in
  the file. No agent's performance is used. In core-v1 every scanned seed passed.
- **Held out.** The test seeds are held out by convention only: they are in a public file. A truly private test
  split would need seeds kept outside the repo ([roadmap.md](roadmap.md#open-design-questions)).

## Results and provenance

See [results_format.md](results_format.md).

- Every run gets `results/<experiment>/<run_id>/`, where run_id = UTC timestamp + short config hash.
- The manifest records the git commit + dirty flag, a sha256 over the package source, prompts, schemas and
  configs, package versions, platform, the config, the suites with verified hashes, the resolved models (slug,
  route, reasoning, prices and where the prices came from), the arms, the budget (cap, balance/key-limit notes,
  spend before/after/this run), and **every planned cell with its final status**.
- `results/index.jsonl` is append-only and file-locked; `freehand ls` shows the latest line per run.
- The results root is `$FREEHAND_RESULTS`, else `<repo>/results`. *Deviation:* the plan said `./results/`
  (cwd-relative). The repo root is used so a run's location doesn't depend on the directory it was started from.

## Budgets and the request cache

- The tag cap, `--max-usd`, the balance/key-limit check and the episode cap are described in the README.
- Spend is written to the ledger **before** the reservation is released and before the cache row, so a
  concurrent worker always sees either the reservation or the spend. A crash in between over-counts, never
  under-counts.
- **The episode cap counts each call's original cost**, including cache hits. The historical loop counted only
  new spend, so an episode's `capped` status depended on what happened to be cached. Two pilot episodes exceeded
  their nominal caps for that reason ([provenance/MIGRATION.md](provenance/MIGRATION.md)). With this rule, a
  replay from the cache or a resume stops exactly where the original did.
- The cache key hashes provider, route, model, the settings dict, the system prompt and every message (images by
  their sha256). Because the key, the prompts and the images are byte-identical to the historical ones, every
  historical request replays for free once `import-legacy --merge-cache` has run. `freehand run objective_pilot
  --max-usd 0` re-runs that study from the cache at $0, but reproduces an episode only as far as its requests were
  unique: episodes that sent identical requests concurrently each got their own reply, and the cache keeps one. The
  logged episodes and `freehand replay` are the record ([reproducing.md](reproducing.md)).

## Agents

- **LLM agents.** An `LLMAgent` wraps an adapter. The arm decides the request:
  - *memory*: the running conversation, the last K photos downscaled, and the notepad;
  - *stateless*: one fresh request per turn;
  - optionally, the landed ends as numbers, or `NUMERIC_FEEDBACK_JSON`.
  The output mode (`page_mm` or `crop_px`) is per model, from the registry, and can be overridden. `auto` runs
  the historical K1 gate once per run.
- **Reference agents.** `make_reference(name, rule)` pairs a name with the rule's implementation:
  - `oracle`, `naive` and `adaptive` for plotter-map changes, for the camera, and for ladder levels (the last
    via `LAdaptive(level)`);
  - `local_patcher`, `local_broyden`, `adaptive_library` and `family_estimator`.
  Names are stable across rules, as in the historical runs.
- **Resume.** `ResumeAgent` replays logged replies, then hands over to the live model. The runner checks that the
  replayed strokes match the log.

## Where the design departs from the planned shape

- **`data/` → `suites/`.** The data *is* the suite; one name keeps it unambiguous.
- **`metrics/` holds only ink and regret.** Episode metrics are there too, but `scoring.py` stays at the top level
  because every report depends on it.
- **Configs.** Suites and experiments are YAML (as suggested). The model registry is TOML (as suggested). Prompts
  are `.txt` files, plus one `turn.toml` for the short per-turn phrases whose trailing spaces matter.
- **No `scripts/`.** Everything is a CLI subcommand. The one exception is `tests/parity/record_legacy.py`, which
  records the parity fixture from the original code (provenance) and is not needed to run anything.
- **Two adapters, not one.** Gemini runs through OpenRouter by default (`flash`). The historical direct-Gemini
  adapter is kept as `flash-genai`, because every historical Flash request was made that way and only that route
  replays them from the cache.
- **Ladder escalation and the OpenAI ladder's stop rule.** These were adaptive, sequential designs; they are not
  in the generic runner. Their configs list the cells that actually ran
  ([provenance/MIGRATION.md](provenance/MIGRATION.md)).
- **Perception probe.** `probe.py` asked single questions rather than running episodes. It is not ported; its
  results stay in the imported legacy run.
