# Extending Freehand

How to add a model, an arm, a perturbation (a hidden rule), a suite or an experiment. The rule of thumb: frozen
things (suite files with results, prompt texts of a released version) are never edited; add a new version instead.
Run `pytest`, `ruff check .` and `mypy` after any change; `tests/test_legacy_parity.py` fails if a change would alter
a historical request or stroke.

## A model

`configs/models.toml` is the registry; `freehand models` prints it.

```toml
[models.mymodel]
slug = "vendor/model-name"        # the OpenRouter slug
display = "My Model"
provider = "vendor"               # optional: pin one OpenRouter provider (no fallbacks)
reasoning = { effort = "high" }   # the OpenRouter `reasoning` object; reasoning is forced on for every model
max_tokens = 8000                 # output cap per call, reasoning included
price_in = 3.00                   # USD per million tokens; required (budgets reserve and record at these prices)
price_out = 15.00
output_mode = "auto"              # page_mm | crop_px | auto (decided per run by the K1 gate, below)
added = "2026-10-01"
notes = "why these settings"
```

- **Try before registering.** Any OpenRouter slug works unregistered (`freehand episode --model vendor/model ...`),
  with the `[defaults]` of the file, prices from OpenRouter's models API, and a warning. Register it to pin the
  settings a published result used.
- **Answer mode.** Some models read the gridded page well but convert badly to millimetres. `crop_px` shows a
  magnified crop and takes the answer in its pixels. `auto` runs the K1 gate once per run: a no-change episode on 4
  squares in page mm; `page_mm` if at least 2 close on the first stroke, else `crop_px`.
- **Experiments can override** reasoning, max_tokens, provider and output_mode per model (that is how the historical
  settings are reproduced): `models: [{id: mymodel, output_mode: crop_px}]`.
- **A new API** (not OpenRouter) is an `Adapter` subclass in `src/freehand/llm/` (see `openrouter.py`, `genai.py`),
  wired into `registry.make_adapter`. Keep the request-cache key stable: it is what makes old runs replay.

## An arm

An arm is what the agent is told and remembers: memory or stateless, how many earlier photos, the disclosure, the
prompt blocks, numeric feedback, the answer mode (`src/freehand/agents/arms.py`). Presets have names (`silent`,
`objective`, `informed_objective`, `stateless_numeric`, ...). An experiment can define a new one inline:

```yaml
arms:
  informed_no_history: {preset: informed_objective, k_prev: 0}
```

New model-facing text goes in a file under `src/freehand/prompts/v1/blocks/` (one trailing newline) and is
referenced by id in `blocks`. Changing an existing `v1` text changes historical requests; make `v2/` instead
(`tests/test_prompts.py` pins the `v1` texts).

## A perturbation

A perturbation is the hidden rule the plotter (or camera) follows after the change. The registry is
`src/freehand/perturbations/`; the implemented rules are listed in [perturbations.md](perturbations.md) and the
design space in [design/perturbation_ideas.md](design/perturbation_ideas.md).

1. Subclass `Perturbation` with a `type_name` and a frozen `Params` dataclass (validate in `__post_init__`), and
   implement:
   - `expected(pts, n)`: the noise-free landing of a dense commanded path for stroke `n`;
   - `oracle_cmd(target, n)`: the command whose ideal landing ends are the targets (must not change state);
   - `land(cmd, seed, n)` only if the rule has state (update it there, once per executed stroke);
   - `start(n0)` if its state resets when the rule switches on;
   - `describe()` extras for anything needed to rebuild it from a log.
2. Draw every random parameter from a new named stream in `seeding.STREAMS` (the tag is derived from the name), so
   adding the rule changes no existing page.
3. Register the class in `perturbations/__init__.py` (`_TYPES`, `TIERS`) and pick a reference estimator: set
   `reference_level` for `LAdaptive`, or add it to `FAMILY_OF_TYPE` for the family estimator.
4. Add unit tests: the oracle inverse, no state change on a query, determinism.
5. Use it in a **new** suite version (below).

## A suite

A suite (`configs/suites/<id>.yaml`) freezes the page generator, the change schedule, the named rules with their
parameters, the episode caps and explicit `dev` and `test` seed lists. Every random draw comes from a named
substream of the seed, and the file stores a `data_hash` of everything it generates.

```sh
cp configs/suites/core-v1.yaml configs/suites/mysuite-v1.yaml   # edit id, rules, page; empty the seed lists
freehand suite scan mysuite-v1 --start 2000 --count 15          # a feasibility filter only (oracle reachability)
# put the seeds it prints into dev/test, then:
freehand suite freeze mysuite-v1                                # writes data_hash
freehand suite verify mysuite-v1 --oracle
```

Once results exist, never edit the file: make `<id>-v2`. When freezing a suite for a benchmark, also add its episode
caps to `PINNED_EPISODE_CAPS` in `src/freehand/suites/generate.py` (the data hash does not cover them).

## An experiment

An experiment (`configs/experiments/<name>.yaml`) is models × arms × rules × suite seeds, plus a budget; the header
of `src/freehand/experiments/config.py` documents every key. `freehand run <name> --dry-run` prints the plan (cells,
settings, suite hashes) without reading a key or calling anything; `--fake-models` runs the whole pipeline offline.
