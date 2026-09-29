# Findings and claim boundaries

Current as of 2026-09-29, after informed_models. This page merges the project's two earlier findings documents
conservatively (the 2026-09-27 "key surprising findings" and the 2026-09-28 "evidence and claim boundaries", both in
[provenance/](provenance/README.md)) and updates them with every later result and the corrected scorer. Where the
two disagreed, it states only what both support. The chronology is in [HISTORY.md](HISTORY.md).

**Evidence level.** These are pilots: **one episode per cell, on one page (seed 10)**, seven models in all. No model
has run the frozen benchmark suites (`core-v1`, `discriminating-v1`, `camera-v1`) yet; they exist to replicate these
leads over held-out seeds. The pilots support *leads*, not model rankings or saturation claims.

## Claim boundaries

1. The historical pilots show recovery and explicit hypotheses after tool changes. They do not establish broad
   model rankings or saturation.
2. Final completion can conceal repeated local repairs. Report first-stroke transfer, total strokes, completion and
   ink together.
3. A correct-looking model written in a note is not evidence that the model is *used*. A roughly correct inverse
   can be applied and still miss because the estimates are imprecise. Keep model selection, estimation precision
   and command execution apart.
4. The attribution classifier (a keyword screen) is unvalidated and overbroad: "landed" or "compensate" does not
   identify a causal belief about the plotter. Camera-vs-plotter attribution needs behavioural probes or adjudicated
   annotations.
5. The reference agents with family knowledge (`adaptive`, `family_estimator`) have privileged perception and
   structural knowledge. They are useful controls, not proven optima.
6. Replay verifies the logs' deterministic consistency (in this repo: every imported historical episode, including
   informed_models, and every observation image re-rendered from them reproduce exactly). It does not verify the
   scientific validity of every historical claim.

## What the pilots show

All first-try figures are hits / squares reached, on the squares after the first post-change square (squares
6–20 of the 20-square learning-curve page, seed 10). They are recomputed with the corrected scorer;
[provenance/MIGRATION.md](provenance/MIGRATION.md#rescoring-with-the-corrected-scorer) lists every number that
changed. `capped` = the episode cost cap was reached (inconclusive); `stopped` = cut by a budget or provider limit.
The rules: a 13° rotation (`rot13`), an anisotropic scale + shear (`shear`, step 2 of ladder level L3), and a camera
bump under a stale rectification with the plotter unchanged (`camera`, ladder level L6, camera-only).

**Rescoring.** The corrected scorer counts a square whose first stroke missed even when the episode stopped before
the square's result was written. It changes 3 numbers in the objective / informed / stateless pilots (Opus rotation
objective 0/9 → 0/10, Opus camera objective 1/2 → 1/3, Opus shear stateless-image 1/14 → 1/15) and 9 in
informed_models, each by one added miss; no hit changes and no headline cell moves.

### 1. Models write explicit models of a silent change

Opus 5.5 and GPT-6 Astra were never told anything could change. After their strokes landed wrong, they wrote down
quantitative models of the fault, for example:

- Opus on the 13° rotation: "landed x' = 1.03x − 0.23y + 32.3" (sin 13° ≈ 0.225);
- Opus on the 0.73 scale: fitted 0.70–0.73;
- Astra: "actual = 0.75·command + (28.5, 35.0)".

Quotes: [quote_bank/HIGHLIGHTS.md](quote_bank/HIGHLIGHTS.md). Boundary 3 applies: a written model
is a hypothesis about the model's reasoning, not proof it used it.

### 2. Completion hides local patching

Without being told a rule exists, Opus mostly missed the first stroke on each new square after the rotation and the
shear, saw the gap, and corrected locally; the squares still closed. On the camera bump it did carry the fix
forward (12/15). objective_pilot, episode cap $3:

| Later first-try (squares 6–20) | rot13 | shear (L3 step 2) | camera bumped (L6) |
|---|---|---|---|
| code estimator (`adaptive`) | 14/15 | 13/15 | 15/15 |
| Opus, silent | 2/9 (capped) | 0/15 | 12/15 |
| Opus, told to minimise strokes | 0/10 (capped) | 0/15 | 1/3 (stopped) |
| Astra, silent | 14/15 | 4/10 (capped) | 13/14 (stopped) |
| Astra, told to minimise strokes | 13/15 | 10/13 (capped) | 8/9 (stopped) |

So the primary metric is the first-try learning curve, not completion.

### 3. Being told a consistent rule exists changed Opus's behaviour

With the informed + objective prompt (quoted in the README), the same page and the same settings (Addendum 9;
informed_pilot, episode cap $4; the cut cells finished by the Addendum 12 resumes):

| Later first-try | rot13 | shear | camera bumped |
|---|---|---|---|
| Opus, informed + objective | 11/15 | 8/15 | 13/15 |
| Astra, informed + objective | 14/15 | 13/15 | 11/15 |

- Opus rose from 2/9 to 11/15 on rotation (at about a third of the cost) and from 0/15 to 8/15 on shear. On
  rotation it fitted the change once, then aimed each new square through the fitted map.
- Astra was already near the estimator; the prompt helped it on shear.
- These are single episodes. Whether Opus's silent-arm behaviour was a *choice* (a framing effect) or a
  *capability* limit is not established by them; the `one_shot` mode in the [roadmap](roadmap.md) is the proposed
  test. The 2026-09-27 write-up called this "knowing ≠ using"; the 2026-09-28 review withdrew that phrasing
  (boundary 3).

### 4. Landed ends as numbers (stateless): helps on rotation, not (for Opus) on shear

Stateless (no conversation, no notes; the same informed + objective prompt), with each stroke's landed ends given as
measured numbers, or with only the log of commands (stateless_pilot, episode cap $2):

| Later first-try | rot13 | shear |
|---|---|---|
| Opus, stateless + numbers | 11/15 | 2/15 |
| Astra, stateless + numbers | 15/15 | 11/13 (capped) |
| Opus, stateless, image only | 0/9 (capped) | 1/15 (capped) |
| Astra, stateless, image only | 4/10 (capped) | 2/6 (capped) |

- On rotation, the numbers let both models re-derive the rule from the log every turn, without notes. Opus
  matched its informed-arm score (11/15) at a fraction of the context. With only the command log, where the model
  must read its own marks from the photo, both did far worse in the squares they reached.
- On shear, Opus stayed poor even with the numbers (2/15, versus 8/15 with memory and the informed prompt). So
  "the remaining gap is perception of one's own marks" holds for rotation only.
- n = 1 per cell; several cells capped. The shear cells come from the Addendum 12 resumes.

### 5. The informed arm across seven models (informed_models)

The same page, the same informed + objective prompt, memory on, reasoning forced on (Addenda 12–13). Later
first-try hits / squares reached, corrected scorer; C = capped at the $8 episode cap¹, S = stopped by the $95 cap on
the whole run.
Figures: [figures/learning_curves_grid.png](figures/learning_curves_grid.png),
[figures/first_try_bars.png](figures/first_try_bars.png); table: [figures/informed_summary.csv](figures/informed_summary.csv).

| Model (answer mode) | Rotation 13° | Shear (L3 step 2) | Camera moved (L6) | Spend (3 episodes) |
|---|---|---|---|---|
| Code estimator (reference) | 14/15 | 13/15 | 15/15 | $0 |
| GPT-6 Astra (page mm) | 14/15 | 13/15 | 11/15 | $7.50 |
| Claude Opus 5.5 (page mm) | 11/15 | 8/15 | 13/15 | $4.38 |
| GPT-6 Sol (page mm) | 11/15 | 0/12 C | 0/12 C | $17.97 |
| Gemini 3.8 Flash (crop px) | 6/15 | 5/15 | 0/15 | $14.96 |
| Claude Sonnet 5 (crop px) | 0/13 C | 0/15 | 0/14 C | $23.76 |
| GPT-5.5 (page mm) | 0/2 C | 0/3 C | 0/4 C | $29.26 |
| Kimi K3, open weights (page mm) | 0/3 S | 0/2 S | 0/1 S | $13.56 |

Episode spend is each episode's original cost, which includes pre-change calls shared through the cache with the same
model's other episodes; the ledger total for informed_models is $94.54 (Sol $17.97, Sonnet $23.68, Flash $14.69,
GPT-5.5 $24.30, Kimi $13.91). Opus and Astra ran in informed_pilot ($11.50 with the resumes).

¹ GPT-5.5's shear and camera episodes log $10.65 and $10.50 against the $8 cap. The cap at the time counted each
episode's *new* spend ($8.15 and $8.05); the logged cost also counts the pre-change calls that were shared through
the request cache with GPT-5.5's other episodes (the three rules send identical requests before the change). This
repository's cap counts the logged cost, so a reproduction would stop earlier ([roadmap.md](roadmap.md), open
question 6).

What the logs show, per model (quotes are verbatim from the notes or memory; the full bank is in
[quote_bank/](quote_bank/)):

- **Astra and Opus fit a global map and carry it forward** on all three rules. Opus's memory on rotation: "rotate
  the target CCW 13.5° about the centre", applied from square 6 on. Opus's shear fit ("x'=1.17x+0.134y-37.6") is
  near-correct, but it layers local patches on top (8/15).
- **Sol gets rotation only.** Its final memory on rotation: "Working command-to-ink mapping: ink x≈0.974x−0.225y+34;
  ink y≈0.225x+0.974y−21" (cos/sin 13° = 0.974/0.225), after abandoning squares 5–7. On shear and camera it patches
  square by square ("appears to land roughly (80,158)→(83,170), drifting right as it descends") and hits the cap.
- **Flash fits, executes unevenly.** On shear it solves an affine inverse ("cmd_x = 0.8929*tgt_x - 0.1336*tgt_y +
  30.71, cmd_y = 1.1173*tgt_y - 16.42") but only late (4 in a row from square 17). On the camera move it concludes
  "constant tool offset dx = -50 px (-4.17 mm), dy = -44 px (-3.67 mm)" and gets 0/15.
- **Sonnet 5 gets 0 first-try hits in every condition**, despite 4/4 before the change in crop_px mode. Its memories
  describe a "severe unpredictable ink placement perturbation" and "persistent unresolved mystery pattern"; it
  abandons most post-change squares.
- **GPT-5.5 denies the change.** "Previous apparent perturbations were likely mostly misread/clutter; recent strokes
  look near commanded positions." It spends 17 turns on the four pre-change squares and is capped by squares 6–8.
- **Kimi K3 passed the basic-task gate at its threshold, then struggled with the basic task.** Its 4-square K1 check
  (the no-change gate that picks the answer mode) scored exactly 2/4, the threshold, so it answered in page mm. In
  each real episode it then closed 0/4 pre-change squares on the first stroke (44–49 turns before square 5), and the
  $95 run cap stopped it by squares 6–7. It concludes "Strokes land at commanded coords (no perturbation)" and
  "Mapping is identity". Its cells are descriptive only.

The informed arm spreads the seven models from 0% to 93% later first-try, which is why Addendum 13 proposed it as the
benchmark core. With one episode per cell this is a spread, not a ranking.

### 6. Camera vs plotter: a hypothesis, not a finding

- **What was checked.** The 11 camera-only (L6) model episodes of objective_pilot (4), informed_pilot (2) and
  informed_models (5), plus the ladder's 2: 13 in all. A keyword screen of their notes and memories finds **no
  note or memory that names the camera or the view**.
- **Reasoning summaries float it a few times, without acting on it.** GPT-5.5 (turn 57: "maybe perturbation
  isn’t about global translation but rather a camera overlay"); Astra, silent (turns 8 and 11: "I need to understand
  any camera shifts"); Kimi K3 (turns 5 and 20, before the change took effect: "Maybe the perturbation is a
  homography due to camera?"). Flash's memory calls the shift a "constant tool offset".
- **A caveat on the prompt.** The informed prompt says "The plotter/tool can be perturbed", which may prime a model
  to blame the plotter; 7 of the 11 episodes had it.
- **The screen's label is not a belief.** The attribution screen labels every one of these episodes "plotter",
  including GPT-5.5 and Kimi, which deny any change (boundary 4).
- So the supported statement is narrow: in these 13 episodes, no note or memory names the camera (a keyword
  screen). Whether models *blame the plotter* stays a hypothesis until a behavioural test (blind text targets, or
  re-anchoring on old marks in `camera-v1`).

### 7. After a plotter change, almost no deliberate probe marks

- **After the change, on the gridded view** (the objective, informed, stateless and informed_models runs), strokes
  that the notes call "probes" are aimed at the target square itself (measure-by-attempt), for example Opus,
  stateless: "this probe stroke joins the two free ends directly to see how it gets perturbed". The one exception
  found is Sonnet 5 on shear (informed_models, turn 11): "Diagnostic stroke: drawing an isolated vertical line at
  x=58mm (offset from the messy existing ink at x=50mm) to clearly observe how the plotter renders a simple vertical
  command".
- **Calibration probes do occur elsewhere.** On an uncalibrated raw camera view (a cold start, before any change),
  models spend their first stroke on a probe: Opus in pilot2 (`cam_transfer`: "a 20 mm horizontal probe near page
  center to calibrate"; `cam_fresh`: "a 10 mm horizontal calibration stroke at page center"), Astra in astra_pilot
  ("Initial probe commanded (108,110) to (108,130)") and Flash in flash_pilot ("Initial probe stroke").
- So the claim is limited to post-change strokes on the gridded view, and it rests on a keyword search of the
  notes, not an annotation of every stroke.

### 8. Offline controls: which rules separate learning from local repair

Code agents only (not model evidence), on 32 page seeds; the study reports are in
[provenance/codex/publication/](provenance/codex/publication/):

| Rule | Offset patcher, strokes/target | Local secant | Library learner | Library completion |
|---|---:|---:|---:|---:|
| identity | 1.03 | 1.03 | 1.02 | 100% |
| affine | 1.74 | 1.74 | 1.86 | 97.5% |
| command memory | 4.13 | 5.31 | 1.29 | 100% |
| latent mode | 3.12 | 3.00 | 1.36 | 100% |
| smooth warp | 2.09 | 2.09 | 1.45 | 99.2% |

Command memory and latent mode strongly separate a learner from local repair. The warp is a weaker diagnostic;
affine shows persistent fitting is not uniformly better. These are within-generator code results; they show
nothing yet about model difficulty.

### 9. The interface can masquerade as a capability limit

Sonnet 5's end-location error went from 334 mm (answering in page mm read off the grid) to 0.5 mm (answering in
pixels of a magnified crop) (Addendum 5). Answer mode is therefore a per-model setting (`output_mode`), and `auto`
runs the K1 perception gate. The converse also holds: a 4-square gate can pass a model by luck (Kimi K3, 2/4), so a
passed gate is not proof of basic competence.

### 10. Smaller models, earlier pilots

In the hard pilots Flash wrote an approximately right affine model and was too imprecise to use it, and Sonnet formed
no model (single episodes, keyword/quote based). informed_models (section 5) repeats the pattern with
the informed prompt: Flash fits late, Sonnet fits a rotation ("FIT: actual = R(13.13deg)*cmd + T" in its memory, turn 39)
but does not aim through it. Treat as anecdotes.

## What is not established

- Which models "get it" in general, model rankings, saturation, or that any model "can't" do the task. Section 5 is
  one page, one seed, one episode per cell; several cells are capped or stopped, and Kimi passed the basic-task gate
  only at its threshold.
- That failing to apply a written model reflects a gap between knowledge and use. It may be estimation imprecision
  (boundary 3).
- Any causal attribution from wording (boundary 4).
- That the reference estimators are optimal (boundary 5).
- Novelty over prior work on hidden-law discovery ([related_work.md](related_work.md)).
