# Quote bank

Every note, memory entry and reasoning summary of the model episodes that talks about the change, with run,
episode, turn and square, so each quote can be traced to its log.

- **Generator:** `src/freehand/analysis/quote_bank.py` (`freehand quote-bank`). The rule is deterministic and
  documented in the module: the union of the two historical mention screens plus hypothesis and measurement words.
  Text is whitespace-collapsed and cut at 1,500 characters, as in the historical bank.
- **In git:** `quotes_notes_memory.csv.gz`: notes and memory entries (4,313 rows, 114 episodes) from every
  historical model run except the fake-model dry runs, including informed_models. An episode repeated in a later
  run (sonnet_pilot carries pilot2's Opus episodes) is listed once. Regenerated 2026-09-29.
- **Not in git (5 MB):** the full bank with reasoning summaries (7,327 rows), `results/reports/quote_bank/all_quotes.csv`.
- **Curated:** [HIGHLIGHTS.md](HIGHLIGHTS.md). Every quote there was checked verbatim against the episode logs
  (2026-09-29); quote anything new from its source row.

Regenerate (after `freehand import-legacy`):

```sh
RUNS=$(ls -d results/legacy/working/runs/* | grep -v dry)
freehand quote-bank $RUNS --out results/reports/quote_bank/all_quotes.csv
freehand quote-bank $RUNS --out docs/quote_bank/quotes_notes_memory.csv.gz --fields note,memory
```

(In zsh, use `RUNS=($(ls -d results/legacy/working/runs/* | grep -v dry))` and `"${RUNS[@]}"`.)

The historical `reports/quote_bank/all_quotes.csv` (3,273 rows, 91 episodes, built by an unrecorded procedure) is
kept outside git in `results/media/working_copy_reports/quote_bank/`; on the same runs this rule recovers 98% of its
rows ([../provenance/MIGRATION.md](../provenance/MIGRATION.md#quote-bank)).
