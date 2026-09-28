<!--
Provenance: the working copy's BENCHMARK_LADDER.md (the newer version, with the 2026-09-28 "Informed + objective and
stateless arms" section), verbatim below. The Codex copy's version is identical up to that section and carried this
notice: "Historical research document. See KEY_FINDINGS.md and PUBLICATION_REPORT.md for corrected claim boundaries
and verified new work. Predictions below are not new model results." That notice still applies: current claim
boundaries are in docs/findings.md. First-try numbers below use the old scorer; docs/MIGRATION.md lists the ones the
corrected scorer changes, and the informed-arm cells that the Addendum 12 resumes later completed.
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
- Note that Look's own perception-vs-solving control is still parked in ~/Desktop/how_much_is_a_look_worth/TODO.md.

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

## Informed + objective and stateless arms (2026-09-28)

**Runs, cost and chart.**
- **Runs:** `runs/informed_pilot_20260928_170744` (tag `informed_pilot`, $10.41) and
  `runs/stateless_pilot_20260928_171227` (tag `stateless_pilot`, $4.33).
- **Data:** each run folder has a `manifest.json`. The stateless folder also holds the all-arms summary.
- **Designs:** Addenda 9–10 of PREREGISTRATION.md: the same page and settings as the objective pilot, one episode
  per cell.
- **Charts:** `reports/objective_pilot/learning_curves_3arm.png` (silent, objective, informed) and
  `learning_curves_all_arms.png` (adds the stateless arms).
- **Truncation:** both runs were cut short by the **OpenRouter key's $100 lifetime limit** (HTTP 403/402), not by
  our caps. The account itself still had about $30. Those episodes are marked `stopped` and are inconclusive.
- **Stateless coverage:** the stateless shear cells stopped before the change, so they have no data. Stateless
  rotation has one complete episode (Opus, numeric) and two near-complete ones.

**First-try hits on later squares (squares 6–20 reached)** · squares to 3 in a row · total strokes · cost
(C = capped at the episode cap, S = stopped by the key limit, at the square given):

| Cell | Silent | Objective | Informed + objective | Stateless, image | Stateless, numeric |
|---|---|---|---|---|---|
| Code estimator rot13 / shear / camera | 14/15 · 5; 13/15 · 6; 15/15 · 3 | | | | |
| Opus rot13 | 2/9 · — · 64 · $3.01 C | 0/9 · — · 76 · $3.04 C | **11/15 · 4 · 32 · $0.96** | 0/3 · S at sq 8 | **11/15 · 7 · 26 · $0.84** |
| Opus shear | 0/15 · — · 43 · $1.27 | 0/15 · — · 52 · $1.63 | **6/13 · 8** · 49 · $1.96 S at sq 18 | no data | no data |
| Opus camera | 12/15 · 6 · 25 · $0.67 | 1/2 (pilot cap) | 9/10 · 7 · 28 · $1.02 S at sq 15 | not run | not run |
| Astra rot13 | 14/15 · 5 · 26 · $2.23 | 13/15 · 5 · 27 · $2.70 | 14/15 · 5 · 24 · $2.20 | 3/5 · 6 · S at sq 10 | **14/14 · 4** · 20 · $1.38 S at sq 19 |
| Astra shear | 4/10 · 10 · 33 · $3.28 C | 10/13 · 6 · 31 · $3.39 C | **13/15 · 6 · 25 · $2.51** | no data | no data |
| Astra camera | 13/14 · 5 · 25 · $2.09 | 8/9 · 5 · 21 · $1.86 | 6/10 · 6 · 23 · $2.13 S at sq 15 | not run | not run |

**Findings.**
- **Being told that a deducible rule exists stops Opus patching.** It is the main effect, and it is Opus-specific.
  - Rotation: 2/9 silent → 11/15 informed, at a third of the cost ($0.96 vs $3.01 capped).
  - Shear: 0/15 → 6/13.
  - It fits the change once, then aims each new square through the fitted map. On rotation: "strokes are rotated
    ~13.5° clockwise (on screen) about ~(108,143). To compensate, rotate the target CCW 13.5° about the centre:
    q=c+Rinv(t-c)". Then, on square 6: "applying the same CCW 13.5° pre-rotation … to join the top ends of sq6".
  - On shear it fits a near-correct global affine ("x'=1.17x+0.134y-37.6, y'=0.906y+12.8"; true ≈ 1.12x+0.138y,
    0.90y). It then layers local per-region patches on top ("left (x'<70) subtract ~2 … far right add ~+3") and
    spends 9+ strokes on one square (sq 15), blaming "drift" or "waviness".
- **Astra was already near the estimator.** Informed + objective ties silent on rotation (14/15). It helps on
  shear (13/15, 3 in a row by square 6, no cap), as the objective arm did.
- **No separate probe marks.** No model draws a test mark away from a target. The closest is Astra using a
  square's uncompensated first stroke as a probe: "direct horizontal probe will help identify rule".
- **Attribution.** Every model episode blames the plotter, including the camera-only episodes under the informed
  prompt.
- **Stateless, with the landed ink as numbers, needs no notes: the rule is re-derived from the log every turn.**
  - Opus: 11/15 at $0.84 (small context: 71k input tokens vs 343k with memory). Each note re-fits the change from
    scratch: "Recent strokes fit a consistent ~13° rotation plus an offset of about (34,-20.5) mm, so I
    pre-compensated".
  - Astra: 14/14.
  - With only the command log (it must read its own marks from the photo), both are worse before the cutoff:
    Opus 0/3, Astra 3/5. That is suggestive only.
- **Verdict (one episode per cell; several cut short).**
  - The "patching" failure is largely motivational/framing for Opus, not an inability to fit.
  - The remaining gap to the estimator is perception of its own marks: the numeric log closes it on rotation.
  - The stateless shear cells still need to be run.
- **To finish:** raise the key's limit. Then rerun `objective_pilot.py --run informed_pilot` and
  `--run stateless_pilot`: cached calls replay for free into a new folder, and the cut episodes resume from where
  they stopped.
