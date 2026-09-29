<!--
Provenance (updated 2026-09-29): the working copy's BENCHMARK_LADDER.md, final version (2026-09-28 23:45 EDT, with the
"Informed + objective and stateless arms: complete" and "Told a rule exists + objective, across models" sections),
verbatim below. The Codex copy's version is identical up to the informed/stateless section and carried this notice:
"Historical research document. See KEY_FINDINGS.md and PUBLICATION_REPORT.md for corrected claim boundaries and
verified new work. Predictions below are not new model results." That notice still applies: current claim
boundaries are in docs/findings.md.
First-try numbers below use the OLD scorer (an interrupted square whose first stroke missed was dropped). The
corrected scorer adds one observed miss to 12 cells, none of them a hit (docs/MIGRATION.md, "Rescoring"). Charts and
reports named below live in results/media/working_copy_reports/ (not in git); docs/figures/ has the regenerated ones.
-->

# Non-saturating benchmark design (agreed direction, 2026-09-27)

Goal: realistic perturbations plus a continuous score against an optimum, so there is headroom above Opus 5.5 for 1–2 years.

## Metric
- **Normalised regret:** (agent cost − ideal-estimator cost) / (naive cost − ideal cost), where cost is strokes plus wasted-ink length.
- **Also report:** final mapping error in mm (the implied map vs the true map) and ink spent on probing.

## Levels

| Level | Perturbation | Real-world analogue | Notes |
|---|---|---|---|
| 1 | Constant shift | Bumped mount | Solved by every frontier model with memory |
| 2 | Rotation or uniform scale | Rotated mount; wrong steps-per-mm | Opus ≈ optimal (hard pilot) |
| 3 | Anisotropic scale + shear | Gantry out of square; one stretched belt | 6-parameter affine |
| 4 | Backlash | Error depends on the direction of travel | Not a single map |
| 5 | Slow **linear** drift + occasional skipped steps | Heat; a loose belt | Never exponential |
| 6 | Attribution: camera vs plotter vs both | Old marks move in the image iff the camera moved | Causal reasoning |
| 7 | Scarce evidence | 1 mm tolerance, few targets, wasted ink penalised | Rewards small probe marks (active experimentation) |

## Next
Opus-only pilot of levels 3–7 (~$3–5), to find where Opus has clear regret. Those levels become the benchmark core.

## Ink metrics (user priority, 2026-09-27)
Report these for EVERY episode, next to strokes:
- **Total ink (mm of line drawn).** Headline efficiency number: "how much ink did it take to finish the page?"
- **Wasted ink (mm).** Ink that isn't part of a closing stroke: misses, probes, corrections.
- **Wasted-ink ratio:** wasted ÷ total.
- **Normalised against references:** agent ink vs the ideal estimator (floor) and vs the naive agent (ceiling).

Why these matter:
- Continuous and hard to saturate: even a perfect adapter can use less ink.
- Rewards small probe marks and careful experimentation.
- Intuitive for a post ("Opus wasted 38 mm of ink; Sol wasted 1.2 m").

To compute: the sum of stroke lengths from the logged landed ink (already in the turns/strokes logs). Backfill for all existing runs.

## Task families (added 2026-09-27)
- **T1: complete the square** (core, built). Endpoint precision on short local strokes.
- **T2: connect numbered dots** (next, after the ladder pilot). A path through 6–10 waypoints spread across the page. Stresses the page-wide map, long strokes, and drift and backlash accumulating along the path. Graded by the distance from the path to each waypoint (tolerance), plus ink.
- **T3: copy a shape to a target** (later, for the website). Draw the reference triangle or circle in the marked box at the marked size. Stresses scale, skew and orientation. The adaptation counterpart of whiteboard-bench.
- **Diagnostic: hit targets** (dot the ring centres). The cheapest pointing test.
- **Skipped:** hatch-fill (hard to grade) and text writing (hard to grade).

## T2 design: look frequency (links to the Look project)
- The agent draws **k strokes per look** (k = 1, 3, 5, all). Optionally the **agent chooses** k each turn (adaptive looking).
- **Trade-off curve:** tokens/cost spent looking vs ink wasted, per model × perturbation.
- **Predictions:**
  - with no perturbation, more looks are wasted, replicating Look's finding for static mazes;
  - with drift or backlash, looks pay; quantify "a look is worth X mm of ink";
  - the best models look more often after noticing a change.
- **Narrative across projects:** "In a static world a look is worth nothing (Look); when the tool can silently change, it's worth X mm of ink (Freehand)."
- Note that Look's own perception-vs-solving control is still parked (a separate project's to-do list).

## Ladder pilot, round 1 (2026-09-27): STOPPED, OpenRouter credits exhausted

**Run folder:** `runs/ladder_20260927_211005` (`ladder_results.json` in that folder). Tag `ladder`, spend $2.35. The
run stopped because the OpenRouter account reached $45.41 used of $50 in credits, and requests
returned HTTP 402.

**What was implemented.** `levels.py` defines L3–L7, each with one knob and an ideal-estimator code
reference (`LAdaptive`), plus an oracle and a naive agent, an oracle reachability check that picks the
seed, and adaptive escalation. A provider error now scores as `error`, never as `break`. Knobs:

| Level | Knob values |
|---|---|
| L3 | (sx, sy, shear °): (1.06, 0.95, 3) → (1.12, 0.90, 7) → (1.20, 0.84, 12) |
| L4 | backlash: 3 → 6 → 10 mm (play model; the pen parks at the plotter home each turn) |
| L5 | (drift mm/stroke, skip probability; skips are 2 mm): (0.7, 0.15) → (1.2, 0.25) → (2.0, 0.35) |
| L6 | (camera shift mm, camera rotation °, plotter offset mm): (5, 2, 6) → (8, 4, 9) → (12, 6, 12) |
| L7 | rotation 13°, tolerance 1.0 → 0.85 → 0.75 mm, plus the L7 prompt line (`levels.PROMPT_L7`) |

A code-only dry run over all levels and knobs confirmed three things. Seed 10 is reachable for every
cell except L7 at 0.75 mm (seed 11). The naive agent breaks. The ideal estimator solves every cell:
4–9 strokes after the change, except L7 at 0.85 mm, where it abandons 2 squares.

**Valid round-1 cells.** Seed 10, step 1, reasoning forced on (Opus `max_tokens` 4000, Astra effort
`high`); 0 turns without reasoning.

| Cell | Opus 5.5: strokes after · abandoned · ink regret · noticed turn · tokens (in / out / reasoning) | GPT-6 Astra: same |
|---|---|---|
| L3 (1.06, 0.95, 3°) | 8 · 0 · −0.04 · 2 · 58k / 2k / 3k | 9 · 0 · 0.01 · 3 (episode stopped by a 402 near the end) |
| L4 (3 mm) | 7 · 0 · 0.21 · 3 · 49k / 2k / 2k | 7 · 0 · 0.22 · 3 · 39k / 1k / 1k |
| L5 (0.7, 0.15) | 16 · 1 · 0.53 · 4 · 133k / 4k / 9k | 7 · 0 · 0.15 · 5 · 39k / 1k / 1k |

L6 and L7 are **invalid**: every episode ended within a few turns on HTTP 402.

**How they fail.** On L5 (drift), Opus blames its own reading instead of the plotter: "even 149.5 did not
close, so the free ends are likely at x of 151 or more". On L4 (backlash) both models model the error
as a constant 1–2 mm offset ("landed low-left by about 1-2 mm"), which works at 3 mm of backlash.

**Status.** L3 and L4 are solved at step 1 by both models. L5 is the first level where Opus shows real
regret (0.53). No level has broken both models yet. Finishing the ladder needs about $10–15 of
OpenRouter credit.

## Ladder resumed after the credit top-up (2026-09-27): results

**Run and cost.** Run folder: `runs/ladder_20260927_211005`, with `ladder_results.json` (round 1),
`ladder_results_resumed.json` and `ladder_summary.json` (all valid cells, corrected verdicts). The resume
spent **$15.94** (tag `ladder`: $18.30 in total, against a cap of $2.37 + $20). Total Freehand API spend
is $54.86. One episode per cell, seed 10, memory on, silent disclosure; reasoning forced on (Opus
`max_tokens` 4000, Astra effort `high`), with 0 turns without reasoning.

**Verdicts.** A model breaks if it abandons 2 or more squares after the change, or its ink regret
exceeds 0.6. It solves if it abandons at most 1 and its regret is below 0.3. Provider errors score as
"error". An episode stopped by the $2 per-episode cap without breaking scores as "capped", meaning
inconclusive.

**Ink regret after the change, Opus / Astra** (abandoned squares in brackets if any):

| Level | Step 1 | Step 2 | Step 3 |
|---|---|---|---|
| L3 shear (sx, sy, shear) | (1.06, .95, 3°): −0.04 / 0.05 | (1.12, .90, 7°): −0.07 / 0.04 | (1.20, .84, 12°): 0.05 / −0.00 |
| L4 backlash | 3 mm: 0.21 / 0.22 | 6 mm: 0.37 (1) / 0.06 | 10 mm: 0.09 / 0.18 |
| L5 drift (mm/stroke, skip p) | (0.7, .15): 0.53 (1) / 0.15 | (1.2, .25): 0.12 / 0.07 | (2.0, .35): 0.56 (1) / 0.26 |
| L6 camera + plotter ("both") | (5 mm, 2°, 6 mm): 0.50 (1) / 0.09 | (8, 4°, 9): 0.09 / 0.09 | (12, 6°, 12): 0.07 / 0.11 |
| L6 camera only / plotter only (step 1) | 0.15 / 0.12 and 0.00 / 0.00 | | |
| L7 scarce ink + rotation 13° | tolerance 1.0 mm: **0.42 (2), BREAK** / −0.24 (capped at $2; it had also abandoned a square before the change) | not run | not run |

**Break points.**
- Opus breaks only at L7 step 1 (1 mm tolerance). It is "partial" at L4 step 2, L5 steps 1 and 3,
  and L6-both step 1.
- Astra breaks nowhere. Its L7 run was stopped by the cost cap, so that cell is inconclusive.
- No level broke both models, so the escalation ran every level to step 3 (L7 stopped after step 1).
- The step-3 knobs are still inside both models' range for L3, L4 and L6. The sim needs stronger
  knobs, or combinations of perturbations, to find a second break point.

**How they fail.**
- **L6 attribution (the clearest failure).** When only the camera moved, both models blame the
  plotter, never their own old marks having moved. Opus: "landed about (54.5,118.3)->(56.3,157),
  roughly (-2,-2) off"; Astra: "Two attempts landed visibly above/left". Opus in L6-both at step 3:
  "The photo layout shifts between turns", yet it still models only pen offsets. Only Astra at L6-both
  step 3 fits a rotation: "Current commands appear rotated relative to photo". Attribution by the regex
  is "plotter" in 12 of 14 model cells; the correct answer was "camera" or "both" in 10 of them.
- **L5 drift.** Opus notices the growth ("offset ... seems to grow per stroke"), then gives up on it:
  "I can't pin down which line is which, so my growing-drift model is unreliable".
- **L4 backlash.** Both treat it as a constant offset plus shortening ("Strokes landed about 2mm left
  ... and were compressed in y"). Neither discovers that it depends on direction. Per-square
  re-correction is enough, so they still solve it.
- **L7.** Opus fits the rotation exactly ("rotation about 12.4°") but cannot hit the 1 mm tolerance
  reliably: it abandons 2 squares after the change, uses 694k input and 47k reasoning tokens, and hits
  the $2 cap.

## FINDING: models "hack" the game by patching each square locally (2026-09-27)
- **What they do:** after a silent change, the frontier models (Opus 5.5, GPT-6 Astra) mostly do NOT carry a global model of the change to the next square. On each new square they miss first, see the gap next to the target, and correct locally on the second stroke. Squares still close, so "squares closed" and total ink regret look near-optimal and the benchmark looks saturated.
- **Evidence:** first-try hit rate on the squares AFTER the first post-change square, i.e. once the model already has evidence, from the ladder and the reasoning-forced hard pilot (seed 10, one episode per cell).
  - Opus hits first try on about 8/42 later squares across the ladder; Astra about 12/39. The code estimator carries its fitted map and hits nearly all.
  - Pattern on L3 shear, L4 backlash, L5 drift and L6 camera / camera+plotter: typically 2 strokes on every later square (miss, then fix).
  - Exceptions:
    - plotter-only offset (L6plot): 3/3 for both;
    - Astra on 13° rotation: 3/3;
    - Opus on 0.73 scale: 2/3 (0/3 on rotation, even though it wrote a correct rotation model in its notes).
- **Why it matters:** the model's written theory can be right or wrong (camera moves blamed on the plotter in 12/14 runs) with no effect on the score, because local trial and correction works on every square. The metric must reward carrying the model forward.
- **Metric fix:** score the **first-try hit rate on squares after the first post-change square** (the first square necessarily costs a miss, since nothing signals the change). Add blind targets (page coordinates given in text, in empty space) and far-apart target ordering, so local patches don't transfer and wrong attribution costs points.

## Objective-told learning-curve pilot (2026-09-27)

**Setup.** Tag `objective_pilot`, spend $24.47 of the $25 cap (total Freehand spend $79.33). Run folder:
`runs/objective_pilot_20260927_220713` (`objective_summary.json`). Chart:
`reports/objective_pilot/learning_curves.png`. One episode per cell: seed 10, 20 squares in
far-apart order, a silent change after square 4, memory on, reasoning forced on. Prompts and settings
are in Addendum 8 of `PREREGISTRATION.md`.

**First-try hits on the squares after the first post-change square**, counting only squares reached
(caps cut some episodes short). Also: squares until 3 first-try hits in a row; total strokes; cost.

| Model | Perturbation | Silent | Objective told |
|---|---|---|---|
| Code estimator | rot13 / shear / camera | 14/15 · 5; 13/15 · 6; 15/15 · 3 | (same) |
| Opus 5.5 | rot13 | 2/9 · never · 64 · $3.01 (episode cap) | 0/9 · never · 76 · $3.04 (episode cap) |
| Opus 5.5 | shear | 0/15 · never · 43 · $1.27 | 0/15 · never · 52 · $1.63 |
| Opus 5.5 | camera moved | 12/15 · 6 · 25 · $0.67 | 1/2 · — · stopped at square 7 by the pilot cap (inconclusive) |
| GPT-6 Astra | rot13 | 14/15 · 5 · 26 · $2.23 | 13/15 · 5 · 27 · $2.70 |
| GPT-6 Astra | shear | 4/10 · 10 · 33 · $3.28 (episode cap) | **10/13 · 6** · 31 · $3.39 (episode cap) |
| GPT-6 Astra | camera moved | 13/14 · 5 · 25 · $2.09 | 8/9 · 5 · 21 · $1.86 (pilot cap) |

**Findings.**
- **Astra carries a global model forward.** On rotation and camera moves it matches the code
  estimator: 3 in a row by square 5. Telling it the objective helped only on shear, where it fitted a
  full affine map by square 7 ("#8–10 each closed in one compensated stroke. Reliable mapping: actual
  X≈1.121*x+0.1412*y−33.06 …"). Silent, it got there only by square 11.
- **Opus is the one that "hacks" by patching, and the objective makes it worse.**
  - Silent on rotation, it writes a correct global model ("landed = R(+13.8deg)*cmd + t") but still
    hits only 2/9 later squares first try.
  - Told the objective, it switches to explicit local patching: "Approach: try the plain target
    first; if the stroke lands off, invert the measured offset". It then misreads the change as
    noise: "noisy distortion that varied per stroke".
  - On shear, in both arms: "on each square check where the first stroke lands and correct by the
    observed per-endpoint offset". Its later-square first-try rate is 0/15 in both arms.
- **Attribution.** All 12 model episodes blame the plotter, including the 4 camera-only episodes.
- **Verdict.** The objective arm does not beat silent overall: it helps Astra on shear only and hurts
  Opus. One episode per cell, and the caps cut several episodes short, so these are leads rather than
  estimates.

## Disclosure arm to add: "informed + objective" (user request, 2026-09-27)
Not yet run. The existing arms are:
- **silent:** never told about changes;
- **alerted:** "camera or plotter may change at any time" (built, never run);
- **scaffolded:** an explicit log-and-fit procedure;
- **objective:** "minimise strokes, VERY important", with no warning about changes.

New arm, **informed + objective**. Proposed exact text:

"IMPORTANT: The plotter/tool can be perturbed at any time and in any way, but always following a consistent pattern or rule. Be intelligent: observe where your strokes actually land, form hypotheses about the rule, test them efficiently, and deduce it. YOUR OBJECTIVE — THIS IS VERY, VERY IMPORTANT: minimise the total number of strokes; you are benchmarked on it."

Run it against silent on the same seed and pages. It separates "can't deduce the rule" from "doesn't bother / doesn't realise it should".

**Status: run 2026-09-28; results below** (section "Informed + objective and stateless arms").
Housekeeping on the same day: the rejected tool-perturbation direction left unfinished hooks in `episode.py`,
`levels.py` and `viz.py`. They covered plotter JSON responses, a `scenario.execute` path, pen tracking and "no ink"
handling. `tools.py` was never created. The hooks were removed. The objective pilot's code references replay
identically, and `run.py dry` passes.

## Informed + objective and stateless arms (2026-09-28): complete

**Runs, cost and charts.**
- **Runs:** `runs/informed_pilot_20260928_170744` (tag `informed_pilot`, $11.50) and
  `runs/stateless_pilot_20260928_171227` (tag `stateless_pilot`, $14.14). Designs: PREREGISTRATION.md Addenda 9–10;
  the same page and settings as the objective pilot; one episode per cell.
- **Truncation, then resume.** Both runs were first cut short by the OpenRouter key's $100 lifetime limit.
  - The cut episodes were then resumed in place by replaying their logged replies (`episode.ResumeAgent`). A
    request-cache replay would have diverged: see Addendum 12.
  - Every cell below is complete or capped.
- **Charts:** `reports/objective_pilot/learning_curves_3arm.png` and `learning_curves_all_arms.png` (all five
  arms).

**First-try hits on squares 6–20** · squares to 3 in a row · total strokes · cost (C = capped at the episode cap;
"—" = never 3 in a row):

| Cell | Silent | Objective | Informed + objective | Stateless, image | Stateless, numeric |
|---|---|---|---|---|---|
| Code estimator rot13 / shear / camera | 14/15 · 5; 13/15 · 6; 15/15 · 3 | | | | |
| Opus rot13 | 2/9 · — · 64 · $3.01 C | 0/9 · — · 76 · $3.04 C | **11/15 · 4 · 32 · $0.96** | 0/9 · — · 45 · $2.02 C | **11/15 · 7 · 26 · $0.84** |
| Opus shear | 0/15 · — · 43 · $1.27 | 0/15 · — · 52 · $1.63 | **8/15 · 8 · 51 · $2.16** | 1/14 · — · 66 · $2.03 C | 2/15 · — · 52 · $1.80 |
| Opus camera | 12/15 · 6 · 25 · $0.67 | 1/2 (pilot cap) | **13/15 · 7 · 34 · $1.25** | not run | not run |
| Astra rot13 | 14/15 · 5 · 26 · $2.23 | 13/15 · 5 · 27 · $2.70 | 14/15 · 5 · 24 · $2.20 | 4/10 · 6 · 22 · $2.11 C | **15/15 · 4 · 21 · $1.45** |
| Astra shear | 4/10 · 10 · 33 · $3.28 C | 10/13 · 6 · 31 · $3.39 C | **13/15 · 6 · 25 · $2.51** | 2/6 · — · 25 · $2.06 C | 11/13 · 6 · 22 · $2.02 C |
| Astra camera | 13/14 · 5 · 25 · $2.09 | 8/9 · 5 · 21 · $1.86 | 11/15 · 6 · 28 · $2.79 | not run | not run |

**Findings.**
- **Being told that a deducible rule exists stops Opus patching.** It is the main effect, and it is Opus-specific.
  - Rotation: 2/9 silent (capped) → 11/15 informed, at a third of the cost.
  - Shear: 0/15 → 8/15.
  - Camera: 12/15 → 13/15.
  - It fits the change once, then aims each new square through the fitted map: "rotate the target CCW 13.5° about
    the centre: q=c+Rinv(t-c)", then, on square 6, "applying the same CCW 13.5° pre-rotation".
  - On shear it fits a near-correct global affine ("x'=1.17x+0.134y-37.6, y'=0.906y+12.8"). It then layers local
    per-region patches on top and loses 9+ strokes on one square.
- **Astra was already near the estimator.** Informed ties silent on rotation and camera. On shear it matches the
  objective arm and beats silent (13/15, not capped).
- **Stateless: the numeric landed-ink log replaces notes for rotation. Reading one's own marks from the photo
  without notes does not work.**
  - Numeric: Opus 11/15 on rotation (71k input tokens vs 343k with memory); Astra 15/15 on rotation and 11/13 on
    shear.
  - Opus cannot re-fit a shear from the numbers each turn (2/15).
  - Command log only: 0/9 and 1/14 for Opus, 4/10 and 2/6 for Astra, and three of those four hit the $2 cap.
- **No deliberate probe marks by any model. Every model episode blames the plotter, including all camera-only
  episodes.**

## Told a rule exists + objective, across models (2026-09-28)

**Run, budget and charts.**
- **Run:** `runs/informed_models_20260928_174709` (tag `informed_models`). Design: PREREGISTRATION.md Addendum 12:
  the same page and the same informed block, memory on, reasoning forced on for every model.
- **Budget:** hard cap $80, raised to $95 on the user's approval; $8 per episode. Spend: **$94.54**.
  - Per model: GPT-6 Sol $17.97, Sonnet 5 $23.68, Gemini 3.8 Flash $14.69 (billed by Google), GPT-5.5 $24.30,
    Kimi K3 $13.91.
  - The OpenRouter balance was $25.83 afterwards.
- **Opus and Astra rows:** from `runs/informed_pilot_20260928_170744`.
- **Charts:** `reports/informed_models/learning_curves_grid.png` and `first_try_bars.png`. Table:
  `reports/informed_models/summary.csv`.

**First-try hits on squares 6–20** · squares to 3 in a row · total strokes · cost per episode (C = capped at $8;
S = stopped by the $95 tag cap):

| Model (answer mode) | Rotation 13° | Shear (L3 step 2) | Camera moved (L6) |
|---|---|---|---|
| Code estimator | 14/15 · 5 · 23 | 13/15 · 6 · 24 | 15/15 · 3 · 21 |
| GPT-6 Astra (mm) | 14/15 · 5 · 24 · $2.20 | 13/15 · 6 · 25 · $2.51 | 11/15 · 6 · 28 · $2.79 |
| Opus 5.5 (mm) | 11/15 · 4 · 32 · $0.96 | 8/15 · 8 · 51 · $2.16 | 13/15 · 7 · 34 · $1.25 |
| GPT-6 Sol (mm) | 11/15 · 7 · 55 · $1.86 | 0/11 · — · 130 · $8.04 C | 0/11 · — · 135 · $8.06 C |
| Gemini 3.8 Flash (crop px) | 6/15 · — · 61 · $3.46 | 5/15 · 15 · 64 · $4.24 | 0/15 · — · 118 · $7.26 |
| GPT-5.5 (mm) | 0/1 · — · 38 · $8.11 C | 0/2 · — · 56 · $10.65 C | 0/3 · — · 57 · $10.51 C |
| Sonnet 5 (crop px) | 0/12 · — · 145 · $8.01 C | 0/15 · — · 175 · $7.74 | 0/13 · — · 155 · $8.01 C |
| Kimi K3, open weights (mm) | 0/2 · — · 88 · $4.85 S | 0/1 · — · 65 · $4.21 S | 0/1 · — · 64 · $4.50 S |

Episode costs include pre-change calls shared through the request cache with the same model's other episodes, so
GPT-5.5 shows more than $8. The $8 cap applies to new spend in each episode.

**Who "gets it" when told there is a pattern.**
- **Get it (fit a global map and carry it forward): Astra, Opus.** Sol gets it on rotation only.
  - Sol, rotation: "Working command-to-ink mapping: actual x≈0.974x−0.225y+34, actual y≈0.225x+0.974y−21", but only
    after abandoning squares 5–7.
  - Sol on shear and camera patches square by square and hits the cap: "Commands around y204 land at y≈198 and
    about 14–16 mm to the right".
- **Fit the rule, execute it unevenly: Gemini 3.8 Flash.** It solves the shear exactly ("Applying solved affine
  model (inverted: cmd_x = 0.8929*tgt_x - 0.1336*tgt_y + 30.71 …)"), but only from square 15; it has 4 hits in a
  row from square 17.
  It is 0/15 on camera-moved.
- **Fit the rule, can't execute it: Sonnet 5.** 0 first-try hits in all three conditions, with 4/4 before the
  change. On rotation it writes the exact map ("FIT: actual = R(13.13deg)*cmd + T, T=(35.51,-20.83) … forward-checks
  well"), then keeps aiming at raw crop coordinates and abandons most squares.
- **Deny the change: GPT-5.5.** It believes the strokes are unperturbed and blames its own target reading: "recent
  visible strokes seem to land near commands despite earlier offset doubts". It hits the $8 cap by square 6–8 in
  every condition (high reasoning, $5/$30 per M tokens).
- **Cannot do the basic task: Kimi K3.** It closed 0/4 pre-change squares on the first stroke, using 44–48
  strokes for the 4 squares. Its misreading of where the free ends are ("endpoints ≈(60,185) and (60,211)"; the
  true ends are at x≈50) is a perception or units failure.
  - Its 4-square no-change mode check scored exactly 2/4, so it ran in page mm. Its pre-change squares in the real
    episodes show the check was lucky.
  - By the K1 gate its cells are descriptive only. It also ran out of the $95 tag cap by squares 6–7.
- **Attribution.** Every episode of every model blames the plotter.

**Verdict (one episode per cell).** Telling the model that a consistent rule exists is a real capability probe.
Only GPT-6 Astra and Opus 5.5 turn it into first-try hits across all three perturbations. The others fit but
can't aim (Sonnet), fit only the easy rotation (Sol), are only partly reliable (Flash), deny the change (GPT-5.5),
or fail the basic task (Kimi). The informed arm spreads models widely: 0% to 93% first-try on later squares. That
makes it a good benchmark core. Next: more seeds for the top three, and crop_px for Kimi.
