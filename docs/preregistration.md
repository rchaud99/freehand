<!--
Provenance (updated 2026-09-29 by the consolidation; everything below this comment is verbatim).
Union of both copies' PREREGISTRATION.md, in order:
  - the preamble and Addenda 1-9: byte-identical in the Codex copy (freehand_publish, last changed 2026-09-27 23:21)
    and the working copy (freehand_b);
  - Addenda 10, 11, 12 (with its  ->  amendment) and 13: only in the working copy, whose file was last changed
    2026-09-28 23:45 EDT, after informed_models finished. This is that final file.
The Codex copy did not change this document; its own claim boundaries are in docs/findings.md.
File, script and folder names below are the historical ones (sim.py, episode.py, objective_pilot.py, runs/...);
docs/MIGRATION.md maps each to its new home. Numbers are as written at the time (old scorer); docs/findings.md has
the rescored ones, and docs/HISTORY.md the chronology.
-->

# Freehand B in simulation: does a model notice that the plotter changed?

Preregistration. Written 2026-09-27, **before any paid API call**. Supersedes the single-call
reading-noise and detection probes, which were dropped before any data was collected. Any change
made after data arrives will be reported as a change.

## Question

A model closes open squares on a page through a camera-and-plotter loop. Partway through, the
plotter silently changes where ink lands, by an offset, a rotation or a scale. The model is never
told. Does it notice from the photos and its own stroke history, and adapt? How many strokes does
the change cost, compared with the same model on the same page with no change, and compared with a
simple estimator that learns from the same evidence?

## Task (code: `sim.py`, `episode.py`)

- **Page.** A US-letter page rendered the way `loop.py` shows it: rectified at 4 px/mm, the same
  blue 10 mm grid (`camera.grid_view`, imported unchanged), and the dashed red reachable region
  (5 mm inset). It holds 10–15 hand-drawn squares, with sides of 20–40 mm and gaps of at least
  9 mm, at seeded random positions. Each square is one wobbly three-sided stroke, so one side is
  open. The simulated photo has grey paper, texture, faint ghost marks and sensor noise.
- **Loop.** Each turn the model gets the current page image, with the current square outlined in
  green and numbered. It also gets a `loop.py`-style state block: the turn, the allowed region, the
  current square, strokes used on it, and whether the previous square closed. The block also carries
  the commanded-stroke history as text; this is **history on**, the default for this study. The
  model replies with `loop.py` JSON. Only the first stroke of a reply is drawn. Squares are done in
  a fixed, seeded order.
- **Plotter.** Ink lands at M(command) + scatter, and it cannot be erased. Scatter comes from the
  real runs (`estimate_scatter.py`, `scatter_estimate.json`: 42 turns from 7 runs after the current
  calibration). Each stroke gets an offset with SD 0.30 mm per axis; the measured turn-to-turn SD
  was 0.29/0.32 mm. Each stroke also gets a smooth wobble with SD 0.40 mm per axis; the measured
  within-stroke residual was ≤0.69 mm, which is an upper bound. So each end lands within about
  0.5 mm per axis. The rig's constant bias of about (−0.47, −0.46) mm is left out, because a
  constant bias is part of the documented map.
- **Closure.** A stroke closes the square if both ends of its ink land within **T = 2.0 mm** of the
  square's two free ends, in either order, and the ink deviates from its own chord by no more than
  2.0 mm. With the scatter above, a perfectly aimed stroke closes 99.7% of the time (measured).
  Every perturbation below moves most squares by more than T.
- **Limits.** Each square allows at most **6 strokes** and 8 turns; turns with no valid stroke count
  toward the 8. A square not closed by then is **failed**, and the model moves on. Wrong strokes
  stay on the page.
- **Probe strokes.** There is no separate probe action. The prompt says that every stroke counts
  toward the 6-stroke limit "whatever it is for" and that its ink stays on the page. That is the
  full cost of probing, and the model is told it.
- **Perturbation.** Once square 6 is finished (closed or failed), the plotter map M silently
  changes to one of the following:
  - `offset5`: 5 mm offset;
  - `offset10`: 10 mm offset;
  - `rot3`: 3° rotation about the page centre;
  - `rot6`: 6° rotation about the page centre;
  - `scale95`: ×0.95 about the page centre;
  - `none`: no change (the baseline).

  The page seed fixes the offset direction and the rotation sign. Each perturbed episode is paired
  with the `none` episode on the same page and seed, for the same agent. Scatter is seeded by
  (page, stroke number), so paired episodes share scatter stroke for stroke.

## Agents

| Agent | What it is |
|---|---|
| `gemini-3.8-flash` | google-genai; thinking_level `medium`, media_resolution `ultra_high`, max output 8000 |
| `claude-sonnet-5` | OpenRouter `anthropic/claude-sonnet-5`, provider pinned to Anthropic, no fallbacks; reasoning effort `medium`, max_tokens 8000 |
| `claude-opus-5.5` | OpenRouter `anthropic/claude-opus-5.5`, same route and settings as Sonnet |
| `oracle` | Knows the true map and commands M⁻¹(free ends). This is the lower bound. |
| `naive` | Commands the free ends exactly and never adapts. Under a change it never recovers. |
| `adaptive` | Knows the exact free ends and gets its own ink ends measured with 0.15 mm noise. It trusts the documented map until one stroke misses by more than 2.5 mm. From then on it fits the map from marks made since that miss: an offset for 1–2 strokes, a similarity transform for 3 or more. This is the reference for what the evidence makes achievable. |

The code agents see the true free ends, so they have perfect perception. Temperature stays at the
provider default. Every call is logged with its route and reasoning settings, and cached on the full
request.

## Metrics (per episode; `episode.metrics`)

- **M1 (primary).** Strokes from the change to the first square closed on its first stroke,
  counting that stroke. If no such square exists, M1 is censored at the number of post-change
  strokes + 1.
- **M2 (primary).** Total strokes spent on the squares after the change, with failed squares
  counting the strokes they used.
- Both are reported as the **excess over the paired `none` episode**: same agent, page and seed.
- **Secondary:**
  - failed squares after the change;
  - post-change first-try rate;
  - **pre-change first-try rate** (squares 1–6), which shows the agent could do the task before
    the change;
  - **mention of a change** in the note or the reasoning. This is a regex (`episode.MENTION`),
    reported as the turn of first mention after the change. Mentions before the change and in
    `none` episodes are false alarms. At least 20 flagged turns and 20 unflagged turns will be
    hand-checked before any mention claim is made;
  - **compensation fraction** for each post-change stroke: the fraction of the needed correction,
    M⁻¹(target) − target, that the command carried (1 = full compensation, 0 = none).

## Hypotheses (dated predictions, 2026-09-27)

- **H1, prerequisite.** Opus 5.5 closes at least 70% of pre-change squares on the first stroke.
  Sonnet 5 and Flash may fall below this, since both failed Look's perception probe.
- **H2, large changes get noticed.** Under `offset10` and `rot6`, Opus fails at most 1 post-change
  square on average, and its M1 excess is ≤ 6 strokes.
- **H3, small changes cost more than their size suggests.** Take the gap between a model's M2
  excess and the adaptive estimator's. That gap is larger under `offset5`, `rot3` and `scale95`
  than under `offset10` and `rot6`. A small miss is easy to blame on one's own aim.
- **H4, the evidence arrives before the action.** Pooled over perturbations, every model's M1
  excess exceeds the adaptive estimator's, paired by seed.
- **H5, models rarely name the change.** Flash and Sonnet name a change in their notes in fewer
  than half of the perturbed episodes. Mention false alarms in `none` episodes stay under 20% of
  episodes.

## Analysis

1. For each model and perturbation, report the mean paired excess (M1, M2) with a 95% bootstrap CI
   over episodes (10,000 resamples, seed 0; `analyze.py`).
2. Model vs adaptive: take the paired difference (model excess − adaptive excess) by seed and
   bootstrap its CI. The two-sided bootstrap p-value is 2 × min(P(diff ≤ 0), P(diff ≥ 0)). Holm
   correction runs across the 5 perturbations within each model.
3. For censored M1, report the count of censored episodes, plus a sensitivity analysis that drops
   them.
4. Report oracle and naive beside every row. The oracle excess is ≈0 by construction; the naive row
   shows the cost of never adapting.
5. Incomplete episodes (a budget stop or provider failure) are resumed from the cache. The
   simulation is deterministic given the responses, so a rerun replays the calls already made at no
   cost. Episodes that cannot be completed are reported, then excluded.

## Kill and stop rules

- **K1, perception gate.** If a model's pre-change first-try rate in its `none` episodes is below
  0.5, its perturbation results are descriptive only. Its excess would measure seeing, not
  noticing.
- **K2, ceiling.** If every model is within 1 stroke of the adaptive estimator's M2 excess at every
  perturbation, looks already carry what they need. Stop and write up; no hardware episodes.
- **K3, floor.** If no model compensates, meaning a compensation fraction below 0.5 on every
  post-change stroke of every `offset10` episode, run the alerted condition ("the setup may have
  changed") before scaling up.
- **K4, budget.** The dollar cap is hard in code (`llm.Budget`): lifetime spend in `cache.sqlite`
  plus the worst case of the next call. The pilot cap is $2 total. The full study runs only with
  the user's approval and an explicit `--cap`.

## Planned counts

- **Full study:** 3 models × 6 conditions (`none` + 5 perturbations) × 5 pages (seeds 1001–1005),
  which is **90 model episodes**. Pages have 10–15 squares, with the change after square 6. The
  code baselines run on the same grid at no cost.
- **Optional, exploratory:** history off (`--no-history`) for Opus × {`none`, `offset10`} × 5
  seeds, only if the budget allows.
- **Pilot:** excluded from all analyses; it checks the harness and measures cost. It runs 1 episode
  per model on seed 7, with 8 squares, the change after square 4, and `offset10`. The paired
  `none` episodes run only if the $2 cap allows.

## Addendum after the pilot (2026-09-27; hypotheses and metrics unchanged)

The pilot is excluded from all analyses. It cost **$1.67** in all, against the $2 hard cap; the
figures for each run are in `runs/pilot_20260927_142254/cost_estimate.json`. Flash's episode was
made in `runs/pilot_20260927_140928` and copied into that folder.

- **Mention regex amended.** Before, it matched Opus's "4 px/mm scale" in its reasoning on turns
  1–4. A bare "scale" no longer counts; "is/was scaled", "scale factor" and "shrink" still do. The
  flags on pilot episodes were recomputed (`episode.recompute_mentions`). The regex also flags a
  model talking about its *own* misses before the change (Flash, Sonnet). Those count as false
  alarms, as registered.
- **K1 is likely to bind.**
  - **Flash and Sonnet:** closed 0/4 pre-change squares on the first stroke. Flash failed 2 of 4
    pre-change squares; Sonnet failed all 4, some with strokes 190–250 mm from the target on the
    same image Opus read correctly.
  - **Opus:** 4/4.
  - **Next step:** before their full grids, run one `none` episode each for Flash and Sonnet
    (~$1.2–1.4 each). If K1 holds, report them descriptively only.
- **Cost per turn at the registered settings.**
  - **Opus:** $0.015 (2.1k tokens in, 0.3k out).
  - **Sonnet:** $0.015 (2.6k in, 1.0k out).
  - **Flash:** $0.019. At `medium` thinking, its reasoning often hits ~7.7k tokens, near the
    8000-token output cap.
- **Estimated full study (5 seeds × 6 conditions).**

  | Model | Per perturbed cell | Full study | Basis |
  |---|---|---|---|
  | Opus | ~$1.9 | ~$10.5 | |
  | Sonnet | ~$6.9 | ~$41 | its failing behaviour, every square at the 6-stroke cap |
  | Flash | ~$6.4 | ~$38 | same as Sonnet |
  | **All** | | **~$90** | |

## Addendum 2: redesign before the memory pilot (2026-09-27, written before any call tagged `pilot2`)

The user asked for this redesign after the first pilot. Nothing below was chosen after seeing
memory-pilot data. The first pilot's $1.67 is spent under tag `pilot`. The new pilot has its own
hard cap of $3 under tag `pilot2` (`llm.Budget` counts spend per tag), plus per-episode cost caps.

### What changed

1. **Memory is the default for all model agents** (`episode.run_episode(memory=True)`).
   - Each episode is one running conversation. Earlier turns appear as the compact state text plus
     the model's full reply, prefixed with a reasoning summary of up to 400 characters when the API
     returns one.
   - Each turn shows the current photo at full resolution, plus the previous K = 2 photos at half
     size (`--k-prev`).
   - The JSON reply gains a `memory` notepad (about 150 words), echoed at the top of the next turn.
     The per-turn state still lists every commanded stroke.
   - Prompt caching: `cache_control` goes on the system prompt and on the last earlier assistant
     turn (OpenRouter to Anthropic); Gemini caches implicitly. All images sit in the newest user
     message, so the cached prefix is append-only.
   - Cost per turn is logged with cached-token counts (`cost_per_turn.csv`).
   - The old single-turn design stays as the **no-memory** arm (`--no-memory`), for comparison
     only.
2. **Limits and prompt fixes.**
   - The per-square cap rises from 6 to **12 strokes** (14 turns), so first successes are seen
     rather than censored.
   - For the rectified view the prompt now says: "the image is 4 px per mm (the whole page is 864 x
     1118 px) … Always give page millimeters read from the grid labels, never pixels." In the first
     pilot, Sonnet reasoned in pixels and sent (145, 225) as page mm.
   - Thinking was on for every model in the first pilot, but Claude's is adaptive: Sonnet produced
     0 reasoning tokens on 11 of 48 turns, and Opus on 1 of 21. The settings are unchanged
     (effort `medium`); reasoning tokens per turn are reported.
3. **Freehand A (camera change with transfer), a new family.** The plotter never changes. The model
   sees a **raw, uncalibrated 960×960 camera view**: no grid and no rectification. The pose is a
   random homography (rotation ±25°, 5.4–6.6 px/mm, perspective from corner jitter up to 9%, and a
   shift). The paper edges are always out of frame: the view back-projects strictly inside the sheet
   (`sim.make_camera`). Squares (18–30 mm) lie in a working area that every pose sees.
   - `cam_transfer`: pose H1 from the start (the uncalibrated start), moved to H2 once square P is
     finished. After the move, the model's own old marks, whose commanded coordinates it knows, are
     the only cue to the new mapping.
   - `cam_fresh`: the same model, the same later squares (renumbered 1…), pose H2 from the start,
     no old marks.
   - `cam_static`: H1 throughout; a code-baseline reference only.
   - **Transfer measure:** M1 and M2 for `cam_transfer` after the move, minus the same model's
     `cam_fresh` values on the same seed. Negative means transfer saves strokes.
   - **Mapping mention:** the first post-move turn whose note or memory matches `episode.MENTION_A`.
   - **Code baselines for A:** `CamOracle` knows the camera; `CamNaive` assumes H1 forever;
     `CamAdaptive` re-measures all its own marks in the current photo every turn and fits page mm →
     px (a similarity from 1 stroke, an affine from 2, a homography from 3 or more), with a generic
     prior before any mark.
   - **Dry-run result:** `CamAdaptive` wastes 0 strokes after a move with transfer (M1 = 1) and 4–8
     from a fresh start, as predicted.
   - **Prediction (H7, dated now):** with memory and silent disclosure, Opus's transfer saves strokes
     against fresh start (negative M1 excess). It saves fewer than the adaptive estimator does,
     because models re-probe rather than re-anchor on old marks.
4. **Disclosure factor** (`--disclosure`, default `silent`; the pilot uses silent only). The exact
   texts:
   - **silent:** no extra line. The notepad is described neutrally as "anything you want to remember
     for later turns (at most about 150 words)". Nothing says the camera or plotter might change,
     and nothing says what to log. This tests spontaneous monitoring.
   - **alerted:** adds "The camera position or the plotter's behaviour may change at any time
     without warning."
   - **scaffolded:** adds "The camera position or the plotter's behaviour may change at any time
     without warning. In memory, keep a log of each stroke's commanded page coordinates and where its
     ink actually appeared in the image. Use that log to estimate how commands map to the page, and
     update it if marks stop landing where expected." This needs the memory arm, and it is the upper
     bound on capability given the right procedure.

### Exact system prompt, memory arm, silent

For the B family (rectified view), the blocks are separated by blank lines:

> You are controlling a pen plotter through a camera. The plotter draws where you command, to within
> about 0.5 mm, lifting the pen between strokes. Black ink on the page is real: the squares were
> drawn by a person before you started; the rest is your own strokes. Ink cannot be erased.
>
> You see a photo of a sheet of US-letter paper (215.9 x 279.4 mm) that has been straightened so
> that pixels map to millimeters: the image is 4 px per mm (the whole page is 864 x 1118 px). A blue
> grid is drawn on the image every 10 mm with labels every 50 mm; the grid is an overlay for you,
> not on the paper. Coordinates are page millimeters: origin at the top-left corner of the sheet, x
> to the right, y downward. Always give page millimeters read from the grid labels, never pixels.
>
> Task: the page has several squares drawn by hand, each with one side missing. Close them one at a
> time, in the order given. The current square is outlined in green and labelled with its number
> (an overlay, not ink, and not tight to the square). Close it with one straight stroke that joins
> the two free ends of its open side. It counts as closed when the ink of one stroke lands within
> 2 mm of both free ends and is roughly straight; then you move to the next square.
>
> Send exactly ONE stroke per turn (only the first stroke is drawn); after each stroke you get a new
> photo. You have at most 12 strokes per square. Every stroke counts toward that limit, whatever it
> is for, and its ink stays on the page. A square still open after 12 strokes is abandoned.
>
> Each turn you see this conversation so far, the current photo, the previous 2 photos (smaller),
> and the memory you wrote in your last reply.
>
> *[alerted / scaffolded line, if any]*
>
> Respond with ONLY a JSON object, no prose before or after:
> {"action": "draw", "strokes": [[[x1,y1],[x2,y2]]], "note": "one short sentence on what you see and
> why this stroke", "memory": "anything you want to remember for later turns (at most about 150
> words)"}
>
> The pen can only reach part of the page: the allowed region is given each turn as x_min, y_min,
> x_max, y_max in page mm and drawn on the image as a dashed red rectangle. Points outside it are
> clamped to its edge.

For the A family (raw view), the second block becomes:

> You see a raw, uncalibrated photo (960 x 960 px) from a camera above part of a sheet of US-letter
> paper (215.9 x 279.4 mm). The photo is not straightened and has no grid: the page may appear
> rotated, scaled, tilted or in perspective, and the paper's edges are out of view. The camera sees
> roughly the middle of the sheet. You are not told how page millimeters map to pixels in this
> photo. Your commands are always in page millimeters: origin at the top-left corner of the sheet, x
> to the right, y downward. Never give pixels.

The last block also drops "and drawn on the image as a dashed red rectangle". "The camera sees
roughly the middle of the sheet" matches the adaptive agent's prior. In the no-memory arm, the
context line and the `memory` field are absent. `episode.build_system` generates all of these.

### Memory pilot plan (seed 7, 8 squares, change after square 4, silent, memory on)

| Episode | Model | Condition | Episode cost cap |
|---|---|---|---|
| (a) | Opus | B `offset10` | $0.60 |
| (b) | Opus | A `cam_transfer` | $0.80 |
| (b) | Opus | A `cam_fresh` | $0.60 |
| (c) | Sonnet | B `none`, with the fixes | $0.40 |
| (c) | Flash | B `none`, with the fixes | $0.40 |

- The hard cap is $3 in total.
- All code baselines run on the same seed.
- The pilot is excluded from the confirmatory analysis.

### Full study (planned, needs approval)

- **Design:** memory on, one disclosure level per block. The B family has 6 conditions × 5 seeds
  (10–15 squares, change after square 6); the A family has 2 conditions (`cam_transfer`,
  `cam_fresh`) × 5 seeds (8 squares, move after square 4). There are 3 models.
- **Order:** silent first. Alerted and scaffolded are separate blocks at about the same cost each.
- **Kill rule K1 applies per model:** if a model's pre-change first-try rate in B `none` stays
  below 0.5 even with the fixes, its episodes are descriptive only.

## Addendum 3: after the memory pilot (2026-09-27; nothing above changed)

The memory pilot spent **$2.32** under tag `pilot2`, within its $3 cap. Results are in
`runs/pilot2_20260927_150151/` (`summary.md`, `cost_estimate.json`, `cost_per_turn.csv`).

- **Resumed episode.** Opus `cam_transfer` hit its $0.80 episode cap exactly at the camera move. It
  was resumed from the request cache: the 23 earlier turns replayed identically at $0, and new spend
  was capped at $0.85.
- **Caching.** Claude prompt caching works; by turns 21–30, about 78% of input tokens are cached.
  Gemini's implicit cache never triggered (0 cached tokens), and Flash's reasoning grows to the
  8k-token cap on hard squares.
- **K1 binds for Sonnet 5 and Flash, even with memory and the prompt fixes.** Neither closed a
  pre-change square on the first stroke (0/3 and 0/4). Sonnet still sent pixel coordinates on
  turn 1, with 0 reasoning tokens, and misread free ends by 3–25 mm.
- **Recommendation for the full study:** Opus only for the confirmatory grid. Sonnet and Flash are
  descriptive only, or dropped.

## Addendum 4: Sonnet 5 on the Opus pilot2 episodes (2026-09-27)

Run folder: `runs/sonnet_pilot_20260927_152203`, budget tag `sonnet_pilot`. Spend: **$3.87** of the
$4 hard cap.

- **Thinking.** Effort `medium`, the setting Opus used, gave 0 reasoning tokens on the identical
  turn-1 request, even with `enabled: true`. Forcing a thinking budget (`reasoning.max_tokens=4000`)
  gave reasoning tokens on every turn (median 1.7k–4.9k). Sonnet's settings therefore differ from
  Opus's (effort `medium`); the setting is recorded in every logged turn.
- **Pixels for millimetres.** Even with thinking on, Sonnet's first command used pixel coordinates
  as millimetres.
- **Outcome.** No episode reached the change. Sonnet failed every pre-change square at the
  12-stroke cap, and all three episodes stopped at the hard cap. The K1 prerequisite fails for
  Sonnet 5.

## Addendum 5: Flash runs, perception probe, crop-pixel mode, Astra, OpenAI ladder (2026-09-27)

- **Flash** on the pilot2 setup (tag `flash_pilot`, $2.17). It ran offset10, cam_transfer and
  cam_fresh. Thinking was on for every turn (thinking level `medium`). offset10 hit a transient read
  timeout, now retried in `llm.py`, and was resumed from cache.
- **Perception / units probe** (`probe.py`, tag `probe`, $0.99): 12 single-square pages × 4 answer
  modes × 3 models. Median error in mm when answering in page mm vs in magnified-crop pixels:

  | Model | page mm | crop pixels |
  |---|---|---|
  | Opus | 0.27 | 0.15 |
  | Flash | 1.9 | 0.28 |
  | Sonnet | 334 | 0.49 |

  Sonnet reads the page but converts units badly, so its failure is a harness/units problem, not a
  perception one.
- **New option `--output-mode crop_px`** (B family only; the default stays `mm`, and no earlier
  condition changed). Each turn adds a 12 px/mm crop with its own labelled grid, and the stroke is
  given in crop pixels. Sonnet in this mode, on no change, seed 7: 8/8 squares first try, $0.07 (tag
  `probe_episode`).
- **GPT-6 Astra** (`openai/gpt-6-astra`, pinned to OpenAI, effort `medium`; tag `astra_pilot`,
  $1.94) on the pilot2 setup, default mode. Its reasoning is adaptive: 0 reasoning tokens on 5 of 9
  offset10 turns.
- **OpenAI ladder** (`ladder.py`, tag `openai_ladder`, $5.16), on the basic task:
  - GPT-6 Astra, GPT-5.5 and GPT-6 Sol pass.
  - GPT-5.6 Terra fails in page mm but passes in crop_px.
  - GPT-5.4-mini and GPT-5.4-nano fail in both modes, and the ladder stopped there.
- **Total Freehand API spend:** $18.19.

## Addendum 6: hard pilot, scale73 and rot13 (2026-09-27)

Tag `hard_pilot`, spend **$7.85** of the $8 cap. Run folder: `runs/hard_pilot_20260927_195044`.
(The earlier folder `runs/hard_pilot_20260927_1947*` is a code-baselines-only run and can be
deleted.)

- **Conditions.** Two new perturbations: `scale73` (×0.73 about the page centre) and `rot13` (13°
  about the page centre), switched on after square 4.
- **Seed.** Seed 7 was replaced by **seed 10**. On seed 7, one post-change scale73 target would need
  a command 11.8 mm outside the drawable region, so that square could never close. Seed 10 is the
  first seed from 7 upward on which every post-change target is reachable under both maps.
  Clamping: 1 of 509 strokes, which is negligible.
- **Agents.** Opus and GPT-6 Sol answered in page mm. Sonnet (thinking budget 4000) and Flash used
  `crop_px`. The adaptive code estimator sets the floor: 5 strokes to the first first-try closure
  after the change, 7 strokes after it.
- **Budget stop.** Sonnet's rot13 episode was stopped by the tag's hard cap.

## Addendum 7: hard pilot with reasoning forced on (2026-09-27)

Tag `hard_pilot_reasoning`, spend **$10.52** of the $15 cap. Seed 10; scale73 and rot13; memory on;
silent; K = 2.

**Exact reasoning settings.**

| Model | Reasoning setting | Answer mode |
|---|---|---|
| Opus 5.5 | `reasoning.max_tokens=4000` | page mm |
| Sonnet 5 | `reasoning.max_tokens=4000` | crop_px |
| GPT-6 Astra | `reasoning.effort="high"` (provider openai) | page mm |
| GPT-6 Sol | `reasoning.effort="high"` (provider openai) | page mm |
| Gemini 3.8 Flash | `thinking_level="high"`, `max_output_tokens=16000` | crop_px |

- All models except Sonnet use `max_tokens=8000`. Flash's limit was raised to 16000 because at
  `high` its reasoning nearly fills 8000 tokens.
- Every model produced reasoning tokens on its first call. Each turn now logs `reasoning_tokens` and a
  `zero_reasoning` flag.
- Despite the forced budget, Sonnet still had turns with 0 reasoning tokens: 8 on rot13 and 4 on
  scale73.
- GPT-6 Sol was also run with `--disclosure scaffolded`, on both conditions.

**Ink metrics** (BENCHMARK_LADDER.md) are backfilled into every `episode.json` as `metrics_ink`, and
are computed automatically from now on.

## Addendum 8: objective-told learning-curve pilot (2026-09-27, written before any call tagged `objective_pilot`)

Tag `objective_pilot`, hard cap $25, $3 per episode. Script: `objective_pilot.py`.

- **Page and ordering.** 20 squares (sides 16–28 mm, gaps 7 mm) on seed 10: the first seed where the
  oracle reaches every target under all three perturbations. Squares are ordered far apart, each
  as far as possible from the previous one (greedy). The change applies silently after square 4.
- **Perturbations.**
  - rot13: 13° about the page centre;
  - L3 shear at its step-2 knob: sx 1.12, sy 0.90, shear 7°;
  - L6 camera-only at its step-1 knob: a 5 mm shift and 2° rotation of the view, with a stale
    rectification.
- **Models.** Opus 5.5 (`reasoning.max_tokens=4000`) and GPT-6 Astra (`reasoning.effort=high`,
  provider openai). Memory on, K = 2, page-mm answers.
- **Arms.** `silent` is the current prompt. `objective` is the same prompt plus this block, verbatim.
  Nothing in it says that the camera or plotter may change:

  > YOUR OBJECTIVE — THIS IS VERY, VERY IMPORTANT: You are being benchmarked on the TOTAL NUMBER OF STROKES you use
  > to complete all squares. Every stroke counts against you, including misses and corrections. Minimising total
  > strokes is your single most important goal. Before each stroke, think carefully about how to make it land
  > correctly on the first try, using everything you have observed so far.
- **Metrics.**
  - **Primary: the learning curve.** First-try hit (0/1) for each square after the change, and the
    number of squares until 3 first-try hits in a row.
  - **Also:** first-try rate on squares 6–20, total strokes, ink regret against the code references
    on the same page, tokens, cost, and when the model noticed the change and what it blamed.
- **Code-estimator fix, made before this pilot.**
  - **Starting window.** The fitting window now starts at the first miss larger than 2.5 mm. One
    scatter outlier before the change used to trigger a false alarm, and unchanged marks leaked into
    the fit.
  - **Rotation and scale fit.** Rotation and scale use a similarity fit, which is exact from one
    stroke. Affine is used only once the marks spread out in two dimensions.
  - **Camera bump.** The camera bump is fitted as a similarity.
  - **Effect.** The reference now hits 13–15 of 15 later squares on the first try on this page. The
    earlier ladder's regrets used the older reference.

## Addendum 9: informed + objective arm (2026-09-27, written before any call tagged `informed_pilot`)

Tag `informed_pilot`, hard cap $20, $4 per episode. Script: `objective_pilot.py --run informed_pilot` (config in
`PILOTS`). The run refuses to start if the OpenRouter balance is below the cap still left under the tag.

- **Question.** Does being told that the tool follows a consistent, deducible rule (and that strokes are scored)
  make a model fit and carry a global map instead of patching each square locally? This separates "can't deduce
  the rule" from "doesn't realise it should try".
- **Design, identical to Addendum 8.**
  - Page: seed 10, 20 squares (sides 16–28 mm, gaps 7 mm), far-apart order, silent change after square 4.
  - Perturbations and knobs: rot13 (13° about the page centre); L3 shear at step 2 (sx 1.12, sy 0.90, shear 7°);
    L6 camera-only at step 1 (5 mm shift, 2° view rotation, stale rectification).
  - Models: Opus 5.5 (`anthropic/claude-opus-5.5`, `reasoning.max_tokens=4000`) and GPT-6 Astra
    (`openai/gpt-6-astra`, `reasoning.effort=high`, provider openai), `max_tokens=8000`. Memory on, K = 2,
    page-mm answers, history on. Reasoning tokens logged per turn as before.
  - 6 episodes: 2 models × 3 perturbations, one arm. The `silent` and `objective` episodes and the code references
    are reused from `runs/objective_pilot_20260927_220713` (same pages, same settings; the code references are
    re-run and reproduce identically).
- **Arm `informed_objective`.** The silent system prompt plus this block, verbatim, in the position the objective
  block used (after the task paragraph, before the context line):

  > IMPORTANT: The plotter/tool can be perturbed at any time and in any way, but always following a consistent
  > pattern or rule. Be intelligent: observe where your strokes actually land, form hypotheses about the rule, test
  > them efficiently, and deduce it. YOUR OBJECTIVE — THIS IS VERY, VERY IMPORTANT: minimise the total number of
  > strokes; you are benchmarked on it.
- **Metrics (as in Addendum 8).** First-try hit per post-change square (learning curve); first-try hits on
  squares 6–20; squares until 3 first-try hits in a row; total strokes; tokens; cost; attribution of the change
  (`levels.attribution`). An episode stopped by the $4 episode cap is scored **capped** (inconclusive), not as a
  failure; only squares reached are counted.
- **Qualitative.** Memory notes are read for deliberate probe strokes and for whether a fitted global model is
  used to aim the first stroke on a new square.
- **Status at writing.** Not run: the OpenRouter balance was $14.08, below the $20 threshold set for this run.

## Addendum 10: stateless arms (2026-09-28, written before any call tagged `stateless_pilot`)

Tag `stateless_pilot`, hard cap $15, $2 per episode. Script: `objective_pilot.py --run stateless_pilot`, with arms
`stateless_image` and `stateless_numeric` (config in `PILOTS` / `ARM_EPISODE`). The run refuses to start if the
OpenRouter balance is below the cap left under the tag.

- **Question.** Without notes or a running conversation, can a model rebuild the rule from the stroke log on every
  turn? And does giving it the landed ink as numbers (so it need not read its own marks from the photo) make it
  hit on the first try the way the code estimator does?
- **Arm.** `memory=False`: every turn is one fresh request. It holds the system prompt, the current page photo
  (full resolution, no earlier photos) and the state block, with no notepad and no earlier replies. The system prompt
  is the Addendum 9 prompt (informed + objective block, verbatim, in the same position). Because there is no memory,
  it drops the context line ("Each turn you see this conversation so far …") and the `memory` field of the reply
  format. It does not say that nothing is remembered: the state block is all the model has.
- **State block (exact format; `episode.state_block`).** Every commanded stroke so far, across all squares, in
  order. The square-result line ("Square #k is closed." / "… was not closed and is abandoned.") appears after the
  stroke count on the first turn of a new square.
  - **(a) `stateless_image`** (the command log only, as in every earlier arm):
    > Turn 7. Allowed region (page mm): x 5 to 211, y 5 to 274. Current square: #7 of 20 (outlined in green).
    > Strokes used on this square: 1 of 12. Strokes you have already drawn (page mm): sq1: (61.0,40.2) ->
    > (61.1,62.3); sq5: (140.3,201.0) -> (163.9,201.2)
  - **(b) `stateless_numeric`** (each entry also gives where the ink landed):
    > … Strokes you have already drawn (page mm; each is the command you sent, then where its ink actually landed,
    > measured from the photo to about 0.2 mm): sq1: (61.0,40.2) -> (61.1,62.3) landed (61.2,40.0) -> (60.9,62.5);
    > sq5: (140.3,201.0) -> (163.9,201.2) landed (139.1,195.2) -> (162.6,200.4)

    "Landed" is the true ink end plus Gaussian noise of SD 0.15 mm per axis (`episode.MEASURE_SD`, the adaptive
    estimator's measurement noise), seeded by (page, stroke) (`episode.measured_ends`). Values are rounded to 0.1 mm.
- **Design, otherwise identical to Addenda 8–9.**
  - Page: seed 10, 20 squares, far-apart order, change after square 4.
  - Reasoning forced on: Opus `reasoning.max_tokens=4000`; Astra effort `high`, provider openai; `max_tokens=8000`.
  - Page-mm answers.
  - Conditions: rot13 and L3 shear at step 2. L6 camera-only is dropped to save money. Numeric landed positions
    would also sidestep its camera question.
  - 2 models × 2 conditions × 2 variants = **8 episodes**.
- **Comparison.** Against the memory arms (silent, objective, informed_objective) and the code estimator, for the
  same models and conditions.
  - Metrics: first-try hits on squares 6–20; squares until 3 first-try hits in a row; total strokes; tokens; cost;
    attribution.
  - Episodes stopped by the $2 cap score **capped**; only squares reached are counted.
- **Prediction (dated now).** `stateless_numeric` gives the highest first-try rate of the model arms, because the fit
  is pure arithmetic on a list. `stateless_image` is no better than `informed_objective`.
- **Checks before any paid call.** `objective_pilot.py --dry-stateless` runs a fake model through both arms, no API.
  It asserts: one message per request, no notepad or earlier photos, the informed block in the system prompt, every
  earlier stroke in the log, and landed ends only in the numeric arm. `run.py dry` also passes.

## Addendum 11: what happened in the Addendum 9–10 runs (2026-09-28; nothing above changed)

- **Spend.**
  - `informed_pilot`: $10.41 of the $20 cap, in `runs/informed_pilot_20260928_170744`.
  - `stateless_pilot`: $4.33 of the $15 cap, in `runs/stateless_pilot_20260928_171227`.
  - Both runs ran concurrently. Each folder has a `manifest.json`.
- **Deviation: provider stop.**
  - The OpenRouter API key has its own $100 lifetime spending limit. `/api/v1/credits` reports the account
    balance, which is not this limit. The key limit was reached mid-run, and every later call returned HTTP 403 or
    402.
  - Episodes cut this way are `stopped` (inconclusive, as registered for provider failures). No episode reached
    its per-episode cap.
- **Informed arm.** Complete: Opus rot13, Astra rot13, Astra shear. Stopped: Opus shear at square 18, Opus camera
  at square 15, Astra camera at square 15.
- **Stateless arms.**
  - Complete: Opus rot13 numeric.
  - Stopped: Astra rot13 numeric at square 19, Astra rot13 image at square 10, Opus rot13 image at square 8.
  - All four shear episodes stopped at squares 1–4, before the change, so there is no stateless shear data.
- **Resuming.** The episodes can be resumed from the request cache at no cost for the calls already made, once the
  key's limit is raised.
- **Results.** In BENCHMARK_LADDER.md ("Informed + objective and stateless arms").
- **Prediction check (Addendum 10).** On rotation, `stateless_numeric` gave 11/15 first-try hits for Opus and
  14/14 for Astra. That ties `informed_objective` for Opus (11/15) and is at least as good for Astra (14/15). It is
  not above both, so the prediction is not confirmed on this evidence. `stateless_image` was worse than
  `informed_objective` in the squares it reached.

## Addendum 12: finishing the cut cells, and five more models on the informed arm (2026-09-28, written before any call tagged `informed_models` and before the resumes)

### Resumes (tags `informed_pilot`, `stateless_pilot`)

- **Correction to Addendum 11.** A request-cache replay does *not* reproduce the cut episodes. Episodes with
  identical early requests (the same page before the change) ran concurrently. Each made its own call, and the cache
  keeps one reply per request. So a cached replay of such an episode diverges at turn 1.
- **Resume = log replay.** The replies logged in `turns.jsonl` are fed back in order at no cost
  (`episode.ResumeAgent`), and the episode then continues live.
  - Checked with no API calls, on all 10 cut episodes: every replay reproduced the logged strokes exactly.
  - `--resume` asserts this for each episode.
- **Episode cap on a resumed episode:** the logged spend plus the new spend stays within the tag's per-episode
  cap ($4 informed, $2 stateless).
- **Order (priority).**
  1. The informed arm: Opus shear, Opus camera, Astra camera.
  2. Stateless rotation: Opus image, Astra image, Astra numeric.
  3. Stateless shear (4 episodes, all cut before the change), only if the budget allows after the new models.
- **The objective-pilot episodes cut by that pilot's cap are left as they are.** They are Opus camera (objective)
  and Astra camera (silent and objective).

### New models on `informed_objective` (tag `informed_models`)

- **Budget.** Hard cap $80, $8 per episode.
  - At the start the OpenRouter balance was $39.35, so the cap for an invocation is lowered to what the balance
    covers, minus $1 (`open_budget`, recorded in the manifest).
  - Models run in priority order, so later ones may be cut: GPT-6 Sol, Claude Sonnet 5, Gemini 3.8 Flash, GPT-5.5,
    Kimi K3.
  - Gemini runs once only (3.8 Flash is the top Gemini model; user's correction). Its calls go to Google directly and
    count toward the tag, but not the OpenRouter balance.
  - Episodes stopped by the $8 episode cap are **capped** (inconclusive), never failed. Episodes stopped by the tag
    cap or a provider error are **stopped**.
- **Design: identical to Addendum 9.**
  - The same page (seed 10, 20 squares, far-apart order, change after square 4).
  - The same informed + objective block in the same position; memory on; K = 2.
  - Conditions: rot13, L3 shear at step 2 (1.12, 0.90, 7°), L6 camera-only at step 1 (5 mm, 2°).
  - 5 models × 3 conditions = **15 episodes**.
- **Models and settings.** Reasoning is forced on everywhere, and reasoning tokens are logged per turn.

  | Model | Route | Reasoning | Max tokens | Answer mode |
  |---|---|---|---|---|
  | GPT-6 Sol `openai/gpt-6-sol` | OpenRouter, pinned openai | effort high | 8000 | page mm (hard pilot) |
  | Claude Sonnet 5 `anthropic/claude-sonnet-5` | OpenRouter, pinned anthropic | `reasoning.max_tokens=4000` | 8000 | **crop_px** (fails page mm: Addenda 4–5) |
  | Gemini 3.8 Flash `gemini-3.8-flash` | google-genai | thinking_level high, media_resolution ultra_high | 16000 | **crop_px** (1.9 mm error in page mm: Addendum 5) |
  | GPT-5.5 `openai/gpt-5.5` | OpenRouter, pinned openai | effort high | 8000 | page mm (passed the basic task in page mm: Addendum 5) |
  | Kimi K3 `moonshotai/kimi-k3` | OpenRouter, unpinned (route logged) | effort high | 8000 | decided by a check (below) |

- **Open-weight model choice.** From the OpenRouter models API on 2026-09-28: Kimi K3 is the newest flagship
  vision-capable model with published weights (`hugging_face_id` moonshotai/Kimi-K3, $3/$15 per M tokens,
  reasoning supported). The Qwen "max" models list no published weights.
- **Kimi's answer mode.** Kimi has no earlier data, so a no-change episode on the first 4 squares of the same
  page runs first: page mm, the informed prompt, memory on.
  - Page mm if it closes at least 2 of 4 on the first stroke (the K1 gate); otherwise crop_px.
  - The episode and the decision are recorded in `output_modes.json` and `checks/` in the run folder.
- **Harness fix, made before these runs: crop_px under L6.** The magnified crop used to be cut from the true
  page, so under L6 camera-only it would have shown the unmoved page and bypassed the perturbation.
  - The crop is now cut from the same stale-rectified image as the main photo (`sim.crop_view(..., W)`), around
    where the square appears, and its grid still claims page mm.
  - Checked: the L6 main photos are pixel-identical to the pilot's, and ink appears in the crop at the
    grid-claimed position.
  - No earlier crop_px episode used L6, so no earlier result changes.
- **Metrics and charts (as Addenda 8–9).**
  - Metrics: first-try hits on squares 6–20, squares until 3 first-try hits in a row, total strokes, tokens, cost,
    attribution.
  - Charts in `reports/informed_models/`:
    - a learning-curve grid (rows = models ordered by overall later-square first-try rate; columns = conditions;
      the code estimator dashed; the silent arm faint for Opus and Astra);
    - a bar chart of later-square first-try rate with the estimator reference and cost per episode.

**Amendment to Addendum 12 (2026-09-28, during the run).** On the user's approval, the `informed_models` hard cap is
raised from $80 to **$95** so Kimi K3 can finish. The $8 per-episode cap is unchanged. Episodes that would pass $95 stop
cleanly and are reported as partial.

## Addendum 13: outcome of the Addendum 12 runs (2026-09-28; nothing above changed)

- **Resumes (log replay).**
  - Informed arm: +$1.09, and all 6 cells are complete.
  - Stateless rotation: +$1.80.
  - Stateless shear: +$7.68. Three of the four stateless shear episodes hit the $2 cap and are capped; Opus
    numeric completed.
  - Every replay reproduced its logged strokes.
- **`informed_models`: $94.54 of the $95 cap** (after the amendment above), in `runs/informed_models_20260928_174709`.
  - The first invocation started under a $35.16 cap lowered to the balance. It was stopped when more credit was
    added, and the folder was finished with `--resume` (log replay of the interrupted Sonnet episodes). The
    manifest records the resume.
  - Two Sonnet episodes stopped on HTTP 429 and were resumed the same way.
  - Episodes capped at $8: Sol shear and camera, Sonnet rotation and camera, and all three GPT-5.5 episodes.
  - Kimi K3's three episodes stopped at the $95 tag cap, at squares 6–7: partial.
- **Kimi K3's output mode.** The no-change check gave 2/4 first-try closures, exactly the threshold, so it ran in
  page mm. In the real episodes it closed 0/4 pre-change squares on the first stroke. The K1 gate therefore binds:
  its cells are descriptive only.
- **Episode cost accounting.** An episode's reported cost is the sum of its calls' costs. That includes pre-change
  calls it shared, through the request cache, with the same model's earlier episode. The $8 cap applies to new
  spend, so GPT-5.5 shows $10.5–10.7.
- **Results.** In BENCHMARK_LADDER.md ("Told a rule exists + objective, across models").
