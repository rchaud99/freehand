# Results format

Machine-checkable JSON Schemas: `src/freehand/results/schemas/{manifest,summary,turn,index_entry}.schema.json`
(draft 2020-12). `freehand validate <run_dir>` validates a run against them; `tests/test_results.py` and
`tests/test_cli_e2e.py` validate every file the runner writes. Schema ids carry a version
(`freehand.run_manifest/1`, `freehand.episode_summary/1`, `freehand.turn/1`); a change that breaks readers gets a
new version.

## Tree

```
$FREEHAND_RESULTS (default <repo>/results)
├── index.jsonl
├── ledger.sqlite
├── cache/llm_cache.sqlite
├── <experiment>/<run_id>/
│   ├── manifest.json
│   ├── config.yaml
│   ├── run.log
│   ├── episodes/<agent>/<perturbation>__<arm>/s<seed>/{episode.jsonl, summary.json, images/, page.json}
│   └── report/{summary.json, summary.csv, report.md, learning_curves.png, first_try_bars.png}
├── legacy/<copy>/<runs|publication>/<run>/{manifest.json, original -> ..., episodes/...}
├── reports/quote_bank/all_quotes.csv           # the full quote bank (docs/quote_bank/README.md)
├── release/freehand_figure_runs_v1.tar.gz      # `freehand export-data`: the data bundle (docs/reproducing.md)
└── media/                                      # historical videos and charts from the earlier copies (not published)
```

- `run_id`: `YYYYMMDDTHHMMSSZ-<6 hex of sha256(config text)>`. The same config keeps the same suffix.
- `<agent>`: the reference name (`oracle`, `adaptive`, ...) or the model slug after the vendor
  (`claude-opus-5.5`), as in the historical runs.
- `<arm>`: `code` for reference agents. The output-mode gate's check episodes use the rule name `check` (imported
  legacy checks too; their run manifest lists them under `output_mode_checks`).
- `images/`: only with `--save-images`. It holds `tNNN.png` (the photo), `tNNN_crop.png` (crop_px mode),
  `final.png` and, for the camera track, `final_raw.png`.
- `page.json`: only on imported legacy episodes whose page no suite regenerates (the dry runs, extra seeds).

## index.jsonl

One JSON object per line, never rewritten; the latest line of a run is its current state.

| Field | Meaning |
|---|---|
| `ts` | UTC time of the event |
| `event` | `started`, `finished` or `imported` |
| `run_id`, `experiment`, `kind` | kind: `experiment`, `episode` (ad-hoc `freehand episode`) or `legacy` |
| `path` | the run directory, relative to the results root |
| `status` | the run status at that event |
| `cells`, `counts` | number of cells; count per cell status |
| `spend_usd` | spend recorded under this run id (finished events) |
| `suites`, `models`, `git_commit`, `git_dirty` | for filtering |
| `fake_models` | the run used the offline fake model: its `spend_usd` is simulated accounting, not a charge |
| `duplicate_of`, `original_path` | legacy imports only |

## manifest.json

| Field | Meaning |
|---|---|
| `schema` | `freehand.run_manifest/1` |
| `run_id`, `experiment`, `kind` | as above |
| `status` | `running`, `complete` (every cell `complete` or `capped`), `partial`, `stopped` (interrupted), `failed`, `imported` |
| `created_utc`, `started_utc`, `ended_utc` | |
| `provenance.git` | `commit`, `dirty` (uncommitted tracked changes), `branch` |
| `provenance.source_sha256` | sha256 over (path, content) of `src/freehand/**` code, prompts, schemas, `configs/**` and `pyproject.toml` |
| `provenance.packages`, `provenance.platform` | Python, numpy, OpenCV, ... versions; OS and machine |
| `config`, `config_sha256` | the parsed experiment config (also saved verbatim as `config.yaml`) |
| `description`, `preregistration` | from the config |
| `suites.<id>` | `data_hash` (recomputed at start), `verified` (matches the frozen hash), `version`, `seeds` used, `legacy` |
| `models.<id>` | `slug`, `api`, `provider` (`auto` = OpenRouter routing), `reasoning`, `max_tokens`, `settings` (the exact dict in every request key), `prices_usd_per_mtok` (+ `source`), `output_mode`, `registered` |
| `arms.<name>` | `memory`, `k_prev`, `show_history`, `history_landed`, `disclosure`, `blocks`, `feedback`, `output_mode`, `prompt_version` |
| `budget` | `tag`, `cap_usd`, `cap_this_invocation`, `max_usd_flag`, `episode_cap_usd`, `episode_cap_mode`, `spent_before`, `spent_after`, `spent_this_run`, `balance` (usable USD + detail), `notes` |
| `options` | `save_images`, `workers`, `fake_models`, `order`, `on_error` |
| `output_modes.<model>` | `auto` models only: `mode`, `basis` (the K1 gate result), `cost`, `episode` |
| `cells[]` | see below |
| `counts` | cells per status |
| `resumes[]` | one entry per `--resume`: time, cells re-run, spend before/after |
| `legacy` | imported runs only: `source`, `container`, `original_path`, `content_sha256`, `episodes`, `duplicate_of`, `files` |

**Cell** fields: `id` (`suite:agent:rule:arm:s<seed>`), `kind` (`model`/`reference`), `agent`, `model`, `suite`,
`perturbation`, `arm`, `seed`, `block`, `episode_cap_usd`, `max_squares`, `status`, and once run `started_utc`,
`ended_utc`, `episode_dir`, `output_mode`, `turns`, `squares_done`, `cost_usd` (new spend), `cost_original_usd`,
`first_try` {hits, attempted, planned}, and `stop` {kind, message}.

**Cell status**:

- `planned`, `running`.
- `complete`.
- `capped`: the episode cost cap was reached; inconclusive, not a failure.
- `stopped`: a budget refusal or a provider failure.
- `error`: a bug.
- `not_run_budget`: never started because the tag budget was exhausted.
- `not_run_after_error`: never started, with `on_error: stop`.
- `not_run_stopped`: never started because of Ctrl-C.
- `skipped`.

## episode.jsonl (one line per turn)

| Field | Meaning |
|---|---|
| `turn`, `square`, `attempt` | turn number (1..), square index, attempt on this square (1..) |
| `change_active` | the change is in effect this turn (plotter rule on / camera moved) |
| `view_H` | page mm → image px of the current view (camera track, stale rectification), else null |
| `prompt.state` | the exact state block that ends the user message (turn, region, square, strokes used, the last result, the stroke log, numeric feedback) |
| `prompt.images[]` | `{name, sha256, detail}` of every image sent this turn (photo; crop in crop_px mode). The sha256 is of the PNG bytes the model received; `replay --render` recomputes it |
| `prompt.n_history_turns`, `prompt.prev_images`, `prompt.notepad_in` | memory arm: earlier turns in the conversation, earlier photos attached, the notepad echoed |
| `reply.text` | the raw reply |
| `reply.thoughts` | the reasoning summary the provider returned |
| `reply.usage` | input / cached input / output / reasoning tokens (+ OpenRouter cost fields) |
| `reply.cost`, `reply.cost_original` | new spend now (0 on a cache hit) and the cost when the response was first made |
| `reply.cached`, `reply.replayed` | a cache hit / a logged reply replayed by `--resume` |
| `reply.route`, `reply.model_version`, `reply.latency_s`, `reply.cache_key` | |
| `action` | the parsed JSON action (`note`, `memory`, `strokes`), or `{"action": "error", "note": "unparseable: ..."}` |
| `crop`, `command_crop_px` | crop_px mode: the crop's page origin and size; the command in crop pixels |
| `command`, `clamps` | the executed command in page mm (after clamping to the reachable region) and each clamp |
| `stroke` | `null` if nothing was drawn, else `n` (stroke number), `ends` (the landed ink ends, mm), `ink_len_mm`, `closed`, `end_err_mm`, `straight_dev_mm`, `post` (after the change), `compensation_frac` (plotter-map rules) |
| `mentions` | `note` / `memory` / `reasoning` matched the (unvalidated) change-mention keyword screen |
| `reasoning_tokens`, `zero_reasoning` | models only |

The dense ink polyline is not stored; `replay` regenerates it exactly. `ink_len_mm` is measured on the polyline
rounded to 0.001 mm, as the historical ink metrics were.

## summary.json

| Field | Meaning |
|---|---|
| `schema`, `freehand_version` | |
| `labels` | `run_id`, `experiment`, `cell`, `suite`, `suite_data_hash`, `seed_hash`, `split` (dev/test), `perturbation`, `arm`, `model`, `budget_tag`, `max_squares`, `output_mode_basis`. Legacy: `legacy: true`, `source`, `run`, `original_episode` |
| `agent` | `name`, `kind`; models: `model` (slug), `provider`, `route`, `settings` |
| `seed`, `family` | family: `plotter` or `camera` |
| `perturbation` | the realised rule: `type`, `name`, `params`, plus the historical `level`, `variant`, `step`, `knob`, `tol`, `prompt_extra`, and rule extras (`map_after`, `camera_warp`, `plotter_offset`, `phase`, `H1`, `H2`) |
| `arm` | the arm as run (+ `memory_effective`: memory applies to models only) |
| `output_mode` | `page_mm` or `crop_px` (models), null for references |
| `setup` | `n_squares`, `perturb_after` (P), `perturb_stroke`, `cap_strokes`, `cap_turns`, `tol_mm`, `view`, `cost_cap`, `rendered`, `square_ids`, `system_prompt` (verbatim), `system_prompt_sha256`, `prompt_components` (ids of the prompt files used) |
| `status`, `stop` | `complete`, `capped`, `stopped` or `error`; stop `{kind: episode_cost_cap, budget, provider or exception, message}` |
| `complete` | finished every square with no stop |
| `turns`, `squares_result[]`, `strokes[]` | per square: `square`, `closed`, `strokes`, `turns`, `first_try`, `post`. Per stroke: `stroke`, `turn`, `square`, `attempt`, `cmd`, `ink_ends`, `closed`, `end_err_mm`, `straight_dev_mm`, `post`, `compensation_frac`, `clamps` |
| `scores.first_try` | over squares P+1..n: `curve` (1 hit / 0 miss / null not attempted), `planned`, `attempted`, `unobserved`, `hits`, `observed_rate` (hits/attempted), `coverage`, `fixed_budget_attainment` (hits/planned) |
| `scores.later_first_try` | the same over squares P+2..n (after the first post-change square): the transfer measure of the pilots |
| `scores.squares_to_3_in_a_row` | post-change squares until three first-try hits in a row |
| `metrics` | the historical metrics: pre/post first-try and closed rates, strokes to the first first-try closure, post strokes, failed squares, mention-screen turns, compensation by stroke |
| `ink` | `ink_total_mm`, `ink_wasted_mm`, `ink_wasted_ratio`, `ink_post_mm`, `ink_post_wasted_mm`, `tokens_in`, `tokens_cached_in`, `tokens_out`, `tokens_reasoning`, `cost` |
| `cost` | `usd` (new spend), `usd_original` |
| `timing` | `started`, `ended`, `seconds` (null on legacy imports) |
| `legacy` | imported episodes: `original_dir`, sha256 of the original `episode.json` / `turns.jsonl`, the original `stopped`, `original_metrics`, `original_metrics_ink`, `scenario`, `scoring_version` |

## Imported legacy runs

`freehand import-legacy` writes the same formats, with these differences:

- Every value that the log states is copied, not recomputed: commands, landed ends, closures, replies, costs and
  the system prompt. Scores, metrics and ink are recomputed with the current code; the originals are kept under
  `legacy`.
- `prompt_components` is empty: legacy prompts were not built from files. The system prompt text is verbatim.
- Turn image hashes are those of the original PNG files. Headless publication episodes have no images.
- If a legacy suite regenerates the page, rule and change point exactly, `labels.suite` and `labels.seed_hash`
  are set. Otherwise the squares are stored in `page.json`.
- The run's `original` symlink points at the untouched historical folder (images, videos, logs, summaries).
