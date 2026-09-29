# Method

What an episode is, what the agent sees and is told, how the tool changes, and how an episode is scored. The
dated design decisions and predictions are in [preregistration.md](preregistration.md). This page describes the
code as it stands.

## The task

- **Page.** A simulated US-letter sheet (215.9 × 279.4 mm) with hand-drawn squares. Each square is one wobbly
  three-sided stroke (corners misplaced by ~0.6 mm, 0.35 mm smooth wobble), so one side is open. Its two free ends
  are the targets. The suite fixes the count, size range, gap, area and order:
  - core pages: 20 squares, 16–28 mm, visited **far apart** (each square as far as possible from the previous one),
    so no square is a neighbour of the last;
  - pilot pages: 8 squares, 20–40 mm.
- **Turn.** The agent sees the page and returns a JSON action `{"action": "draw", "strokes": [[[x1,y1],[x2,y2]]],
  "note": ..., "memory": ...}`. Only the first stroke is drawn. Commands are clamped into the reachable region (the
  sheet minus a 5 mm inset, drawn as a dashed red rectangle).
- **Landing.** Ink = M(command) + a per-stroke offset (SD 0.30 mm per axis) + a smooth wobble (SD 0.40 mm),
  estimated from the real rig. M is the identity until the change, then the rule.
- **Closure.** A stroke closes the square if both ends of its ink land within 2 mm of the two free ends (either
  order) and the ink is roughly straight (chord deviation ≤ 2 mm). A perfectly aimed stroke closes 99.7% of the
  time.
- **Limits.** At most 12 strokes and 14 turns per square; a square still open is abandoned. Ink is permanent: every
  miss and every probe mark stays on the page and in the photos.
- **The change.** It happens silently after square P (4 on the core pages; per seed in 2–5 on the discriminating
  pages). Nothing in the prompt says it happened.

## What the agent sees

- **Calibrated view** (plotter track). A rectified photo at 4 px/mm with a blue 10 mm grid labelled every 50 mm,
  the reachable region, and the current square outlined in green and numbered. The outline's margin is jittered so
  it does not give the corners away. The photo is simulated: grey paper, a light gradient, texture, faint ghost
  marks, sensor noise, ink blur.
- **Crop** (`crop_px` output mode). A 12 px/mm crop around the current square with its own 5/10 mm grid. The model
  answers in crop pixels and code converts them to page mm. This exists because some models localise far better in
  pixels (Sonnet 5: 334 mm error in page mm, 0.5 mm with crop pixels; Addendum 5).
- **Raw camera** (camera track, "Freehand A"). A 960 × 960 frame through an unknown homography: rotated ±25°, 5.4–6.6
  px/mm, with perspective. There is no grid and the paper edges are out of view. Commands are still in page mm.
- **State block.** Ends every user message: the turn, the region, the current square, strokes used, whether the
  last square closed, and the log of every commanded stroke. In the stateless-numeric arm the log also gives where
  each stroke's ink landed, as measured numbers (true ends + 0.15 mm noise, seeded).

## Arms

An arm is data (`agents/arms.py`). The same arm is applied to every model.

| Arm | Memory | Told |
|---|---|---|
| `silent` | running conversation, last 2 photos downscaled, ~150-word notepad echoed each turn, reasoning summaries of earlier turns | nothing about changes |
| `alerted` | memory | "The camera position or the plotter's behaviour may change at any time without warning." |
| `scaffolded` | memory | alerted + keep a log of commanded vs landed positions and estimate the map |
| `objective` | memory | "YOUR OBJECTIVE ... the TOTAL NUMBER OF STROKES ..." |
| `informed_objective` | memory | "The plotter/tool can be perturbed ... always following a consistent pattern or rule ... deduce it" + minimise strokes |
| `stateless_image` | none: every turn is one fresh request (system prompt, current photo, state block) | informed_objective |
| `stateless_numeric` | none, and the log includes the landed ends as numbers | informed_objective |
| `study_image`, `study_image_numeric` | memory; the numeric variant appends `NUMERIC_FEEDBACK_JSON` (target + every command's landed ends) | the model-study objective (polyline commands allowed; straightness judged on ink) |

The exact texts are in `src/freehand/prompts/v1/`. `tests/test_legacy_parity.py` pins them to what the
historical code sent.

## Rules

See [perturbations.md](perturbations.md). There are three tiers:

- **Calibration tier** (global maps that local patching can absorb): offset, rotation, scale, anisotropic
  scale + shear, backlash, drift with skipped steps, camera bump vs plotter shift (L6), and a 13° rotation with a
  1 mm tolerance and an ink-penalty line (L7).
- **Discriminating tier** (local patching fails): command memory (ARX low-pass with persistent state), latent
  mirror mode (where the previous stroke started decides whether the next is mirrored), and a smooth cross-axis
  warp.
- **Camera track**: an uncalibrated camera that moves.

## Reference agents

All see the true targets; the table says what else each gets.

| Name | Access | Behaviour |
|---|---|---|
| `oracle` | the true rule and state | aims through the true inverse (a floor; still subject to ink noise and the region) |
| `naive` | nothing | aims at the targets, never adapts (a ceiling on cost) |
| `adaptive` (ideal estimator) | its own marks, measured with 0.15 mm noise; the rule's model family | detects the change from misses, then fits the family: offset → similarity for plotter maps; similarity/affine, backlash direction trick, linear drift with restarts, camera re-anchoring for the ladder levels; a homography from its own marks on the camera track |
| `family_estimator` | numeric ends; the family **and the change time** | fits the discriminating rule's parameters |
| `local_patcher` | the last miss on this square | offset correction; forgets between squares (the "patching" strategy made explicit) |
| `local_broyden` | numeric observations only | within-target damped Broyden secant |
| `adaptive_library` | numeric observations only (no family, no change time) | detects a departure, then selects among identity / translation / affine / ARX / mirror threshold / warp by penalised fit |

These are privileged controls, not proven optima or vision-matched competitors to a model ([findings.md](findings.md)).

## Scoring

The **first-try curve** is the primary measure (`scoring.py`). For each post-change square it records 1 if the
square's first stroke closed it, 0 if it missed, and null if the square was never attempted.

- A square whose first stroke missed is a miss, even if the episode stopped before the square finished. The
  historical objective-pilot scorer dropped these;
  [provenance/MIGRATION.md](provenance/MIGRATION.md#rescoring-with-the-corrected-scorer) lists what that changed.
- **observed rate** = hits / attempted. **coverage** = attempted / planned. **fixed-budget attainment** = hits /
  planned; it is not an error rate.
- **later first-try** is the same over the squares after the first post-change square (squares 6–20 on the core
  pages): the first post-change square is where the change is discovered, so the later squares measure transfer.
- **squares to 3 in a row**: post-change squares until three consecutive first-try hits.

Secondary measures, reported alongside:

- strokes after the change, and abandoned squares;
- ink: total, wasted (not part of a closing stroke) and post-change;
- **regret** = (agent − ideal) / (naive − ideal), on post-change ink and strokes. The ideal is `adaptive`, or
  `family_estimator` on discriminating rules, on the same page;
- tokens and cost;
- the attribution keyword screen, which is unvalidated (a search aid, not evidence).

## Stop rules and statuses

- `capped`: the per-episode cost cap was reached, counting each call's original cost. Inconclusive, not a failure.
  Only squares reached are scored.
- `stopped`: a budget refusal or a provider failure. Resumable in place.
- `error`: a bug.
- Every planned cell stays in the manifest. A stop never silently drops a cell (see results_format.md).

## Replication unit and caveats

- **The replication unit is the page seed.** Identical requests hit the cache, so repeated runs of one cell are
  not independent samples.
- **Most historical evidence is one episode per cell.** The frozen suites exist to change that.
- **Numeric feedback is an information ablation,** not a token-matched perception experiment.
