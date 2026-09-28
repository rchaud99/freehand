# Archive

Documents carried over verbatim for provenance. They describe the two historical copies and are not maintained;
their script names, commands and paths refer to the old layouts (docs/MIGRATION.md maps them).

- `codex/`: the Codex publication-development copy (`freehand_publish`): its README, PUBLICATION_PLAN,
  PUBLICATION_REPORT, CONTINUATION_REPORT, MODEL_STUDY, OVERNIGHT and KEY_FINDINGS ("evidence and claim
  boundaries").
- `working_copy/`: the working copy's (`freehand_b`) KEY_FINDINGS ("key surprising findings").
  docs/findings.md merges the two; docs/MIGRATION.md lists every disagreement.
- `quote_bank/`: the curated highlights of the historical quote bank. The full 3,273-row CSV
  (`reports/quote_bank/all_quotes.csv`) stays in the old copies; `freehand quote-bank` regenerates a superset from the
  imported runs (docs/MIGRATION.md).

The Codex copy's review/evidence bundles (`release/*.zip`), its `publication/` folder (including four full source
snapshots under `publication/*/source/`) and the historical charts and videos under `reports/` are not copied: the
publication episodes are indexed by `freehand import-legacy` and remain in place.
