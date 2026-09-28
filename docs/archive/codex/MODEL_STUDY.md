# Matched model-evaluation workflow

`model_study.py` now provides a plan-only path and a tested execution path through the existing adapters. The default command reads no credentials and makes no model requests:

```sh
python model_study.py --out publication/my_model_plan
```

The saved default plan has 48 cells: two model IDs, four page seeds, three conditions (identity, command memory, latent mode), and image versus image-plus-numeric feedback. The twelve unique seed/condition configurations passed oracle reachability checks without clamping. These seeds were not discarded or adjusted based on oracle results.

A default plan is a design, not a promise that 48 cells fit any particular dollar allowance. Before execution, set a total and per-episode allowance and verify current provider rates/access. The adapter's token-based reservations are estimates; they cannot guarantee an external provider's bill. The runner is sequential, uses an isolated spend ledger, and records all not-run/stopped cells. A transaction-order bug was fixed so reservations remain held until the returned cost is recorded.

## Offline end-to-end verification

```sh
python model_study.py --out publication/my_smoke --fake --seeds 4001 \
  --families identity --feedback image_numeric --cap 1 --episode-cap .5 --max-tokens 1000
```

This runs the rendering, conversation, numeric feedback, response parser, request cache, budget logic, logging, and scorer with a canned policy. Its ledger contains **simulated accounting units, not paid API charges**. It is not evidence about a language model. The recorded smoke test completed all 12 targets.

## Authorized paid execution

The runner requires `--execute` and a positive `--cap`. Set `OPENROUTER_API_KEY` or `FREEHAND_OPENROUTER_ENV_FILE` explicitly for the configured OpenRouter adapters; do not copy keys into source or output artifacts. The inherited Gemini adapter is optional and additionally requires `google-genai` plus `GEMINI_API_KEY` or `FREEHAND_GEMINI_ENV_FILE`. No Gemini dependency is needed for offline controls or the current default plan.

Example command structure (choose the cap, models and subset deliberately):

```sh
python model_study.py --out publication/my_paid_run --execute --cap 25 \
  --episode-cap 2 --models openai/gpt-6-astra --seeds 4001 \
  --families identity arx mode --feedback image image_numeric
```

This example is not an executed study or a recommendation to spend automatically. Source, model IDs, reasoning settings, prompt, rates used for estimates, cell order, feedback condition, and spend are recorded. Model availability, provider billing, and reasoning-setting equivalence across providers remain unverified by the fake test.

## Interpretation requirements

- Numeric feedback includes the current target and observed command/ink endpoints only. It does not include rule identity, change timing, seed or hidden state. It does provide extra information and increases context length; the comparison is an information ablation, not a perfectly token-matched perception experiment.
- The candidate-library code reference is an engineered hypothesis class. Models in the current default plan are not shown this library. Comparing their scores does not establish an equal-prior capability ranking.
- Within a run, identical request contents can hit the cache. Shared prefixes across paired conditions may reuse responses; this is not independent stochastic replication. Page seeds are the current replication unit.
- Status `complete` means execution reached the end, not that every square closed. Inspect `closed_post`, first-try attainment, coverage, stroke totals, and ink together.
- Budget- or provider-stopped cells stay visible. Do not compute an apparently successful leaderboard by dropping them. Fixed-budget attainment and observed accuracy answer different questions.
- Commands may use multiple vertices; straightness is evaluated on the landed ink. This avoids giving the curved-inverse code oracle an action type the model prompt appears to prohibit.

The local fake-run ledger reports $0.060617 of simulated accounting. This is not an actual provider charge.
