# Roadmap

Where the project stands, what comes next, and the design questions still open. The plan as it was written on
2026-09-28 is kept verbatim in [provenance/roadmap_2026-09-28.md](provenance/roadmap_2026-09-28.md).

## Status (2026-09-29)

| Piece | Status |
|---|---|
| Pilots in `retry` mode: silent, objective, informed + objective and stateless arms on one page (seed 10) | **Done.** One episode per cell; [findings.md](findings.md) |
| The informed arm across seven models (informed_models) | **Done** as a pilot: one page, one episode per cell, several cells capped or stopped |
| One repository: tested package, frozen suites, generic runner, results tree, legacy import with exact replay | **Done** ([provenance/MIGRATION.md](provenance/MIGRATION.md)) |
| A real model on the frozen v1 suites (`core-v1`, `discriminating-v1`, `camera-v1`) | **Not started.** No model has run them yet |
| `one_shot` mode and a continuous landing-error metric | **Not started.** All suites and data are `retry` mode |
| Freehand A (the camera track: learning an uncalibrated, moving camera) | **Pilots only.** The `camera-v1` suite and the `CamAdaptive` homography reference exist; no model study |
| Coloured-pen carousel ([design/perturbation_ideas.md](design/perturbation_ideas.md)) | **Designed, not built** |
| A live smoke run of this repository with a real model | **Not done** (every check so far is offline) |

## Next

1. **Replicate before comparing.** Run the informed arm on `core-v1`'s test seeds for the models that separated in
   the pilots (GPT-6 Astra, Claude Opus 5.5, GPT-6 Sol), with enough seeds for an interval, before any model
   comparison is published.
2. **`one_shot` mode.** One stroke per target and never revisit, so local patching is impossible. Validate it with
   the code agents first (free): the patcher should fail and the learner succeed. `retry` measures whether a model
   *chooses* to learn the rule; `one_shot` measures whether it *can*.
3. **The attribution test.** Whether models blame the plotter when only the camera moved is a hypothesis
   ([findings.md](findings.md), section 6). Test it behaviourally: blind text targets, or re-anchoring on old marks
   in `camera-v1`, not a keyword screen.
4. **Freehand A model study** on `camera-v1` (transfer vs fresh), with the full model lineup.
5. **Discriminating rules with models.** Command memory, latent mirror mode and the smooth warp separate a learner
   from a local patcher among the code agents ([findings.md](findings.md), section 8); no model has run them yet.

## Open design questions

Decisions the design still needs. None changes an existing result.

1. **Main score: `one_shot` or `retry`?** The 2026-09-28 plan makes `one_shot` the main v1 score; every suite and
   all data so far are `retry`, and `one_shot` is not implemented.
2. **Public test seeds.** The `test` seeds are in public suite files, so they are held out by convention only. A
   private split would need seeds kept outside the repository (and a way to score submissions on them).
3. **Command memory is not in `core-v1`.** On the far-apart page its inverse command leaves the reachable region
   for every seed, so it lives in `discriminating-v1`. The alternative is a page design that keeps it reachable.
4. **The K1 gate size.** The basic-task gate (a no-change check on 4 squares; the model answers in page mm if at
   least 2 close on the first stroke) passed Kimi K3 at exactly 2/4, after which it closed 0/4 pre-change squares
   first try in each real episode. A larger gate (more squares, or at least 3/4) would be stricter.
5. **Gemini route.** The historical Flash results used Google's API directly (`flash-genai`); new runs default to
   OpenRouter (`flash`). Tables that mix the two routes should say so, or not mix them.
6. **Episode-cap rule.** The cap now counts each call's original cost, including calls shared through the cache
   with a model's other episodes (so replays and resumes stop where the original did). The historical runs counted
   only new spend; two historical episodes therefore cap one or two strokes earlier when reproduced from the cache.
7. **Resume order.** A resume re-runs stopped cells first, then starts not-run cells in plan order. The historical
   pilots used one priority queue for both. It matters only when the budget runs out mid-resume.
8. **Adaptive designs.** The ladder's escalation and the OpenAI ladder's stop-after-two-failures rule are not in the
   generic runner; their configs list the cells that ran. Adding sequential designs to the runner is open.
9. **The 48-cell model study.** Its config is a plan (cap $0); its shuffled cell order differs from the earlier
   copy's. Adapt it to `one_shot` before running it.

## Known gaps

- The first pilots used a single-turn design whose code is gone: their runs replay, but cannot be re-run.
- Not ported: video assembly (`replay --render --images DIR` regenerates every frame), the single-question
  perception probe, and the first design's paired-excess table.
- The ladder totals quoted in the history (Opus about 8/42, Astra about 12/39 first-try on later squares) were
  never recomputed with the corrected scorer.
- The attribution keyword screen and the quote-bank keyword rule are unvalidated search aids.
- Golden image hashes were recorded on macOS arm64 under the pinned numpy and OpenCV; other platforms are checked
  by CI only.
