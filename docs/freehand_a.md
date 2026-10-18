# Freehand A: learning an unknown camera

**Can a model work out where its camera is, from its own strokes, and work it out again when the camera moves?**

A pen plotter draws on a large sheet of paper. The model sees the sheet only through a camera mounted above it at an
unknown position and angle, and commands strokes in page millimetres. To close a square on the first stroke it has to
know the map from page millimetres to photo pixels (a homography, 8 degrees of freedom). Nothing tells it that map:
there is no grid and no paper edge in view, so the only page positions it can ever know are those of its own ink.
After square 4 the camera moves, and nobody says so.

Code: `src/freehand/camera3d/`. Run: `freehand camera3d run`, table: `freehand camera3d report <run>`, video:
`freehand camera3d video <run> --seed <seed>`.

## Data

Everything lives under `results/camera3d/` (git-ignored, like all results):

```
results/camera3d/<run_id>/
  run.json                 plan (models with their exact settings, pages, arms, caps), environment (git commit,
                           dirty flag, Python, numpy/OpenCV), the preregistration text and its sha256, and each
                           episode's summary as it finishes, with the run's spend
  code_snapshot.tar.gz     src/freehand + configs/models.toml exactly as run (the working copy may be uncommitted)
  <agent>/s<page>/         a transfer episode;  <agent>/s<page>_fresh/  a fresh one
    episode.json           spec, both camera poses (K, R, t, H), the squares, every turn: the stroke as commanded
                           and as executed, the ink ends, closure, the stated camera and its error, the note, the
                           reasoning text (where the provider returns it), per-call usage and cost, the raw
                           assistant message, the sha256 of the photo the agent saw
    conversation.json      the whole conversation as sent (images as sha256)
    photos/NNN.png         every photo; they are deterministic, so the sha256 in episode.json can be re-checked
results/camera3d/studies/<name>/   `freehand camera3d study` over any set of runs:
  episodes.csv, strokes.csv, transfer.csv, claims.md, summary.json
```

Every paid call is also in `results/ledger.sqlite` (tag `camera3d`, with the run id).

## Design

- **Camera.** A physical pinhole camera (`camera3d/pose.py`): field of view 38–50°, optical axis tilted 18–38° from
  vertical towards a random azimuth, rolled up to ±30°, at the distance that gives 4.6–6.0 px/mm where the axis meets
  the page. The page-to-photo map is H = K [r1 r2 t]. The pose is drawn from the seed; a second pose, for the move,
  must shift the view by at least 25 mm (mean over the frame).
- **Page.** 8 hand-drawn open squares (16–26 mm) in a 96 × 116 mm work area, visited far apart. The rendered sheet
  extends past the camera's view in every direction, so no paper edge or corner is ever visible.
- **Episode.** One conversation. The model acts only through a `draw` tool: `start`, `end` (page mm), `note`, and
  `camera_estimate`. After each stroke it gets a tool result, the new photo (the current square outlined in green), a
  line saying whether the stroke closed the square, and the log of every commanded stroke. Up to 4 strokes per square;
  the camera moves after square 4. The last 3 photos stay in the conversation (older ones become a placeholder), which
  bounds the cost. The system prompt says the camera "may be bumped or moved at any time; if it moves, nobody will
  tell you". Prompts: `src/freehand/prompts/v1/camera3d/`.
- **Belief.** `camera_estimate` is the page point the model believes appears at each corner of the photo. Four point
  pairs fix a homography H_belief, so this is the model's whole belief about the camera, reported every turn (the
  tool description asks for an honest guess even when unsure; it is not scored).
- **Belief error** (`camera3d/belief.py`). The *aim error*: for a 7 × 7 grid of points over the work area, project each
  point into the photo with the true camera, then back to the page with the believed one; the mean distance in mm. It
  is how far off the pen would go if the model aimed at what it sees using its belief. 0 for the true camera.
  **Matched** means an aim error of at most 3 mm from some stroke on and for the rest of that camera pose (the
  closure tolerance is 2 mm per end). "Matched at stroke k" counts strokes within the pose (cold start: from the
  beginning; after the move: from the first stroke after it).
- **References**, on the same pages: the *oracle* (knows the camera) and the *estimator*, an ideal learner that
  re-measures its own marks in the current photo every turn (1 px noise) and fits the camera from its commanded ends
  (similarity from 1 stroke, affine from 2, homography from 3+), starting from a generic prior. After a camera move
  its old marks are still on the page, so it re-fits the new camera before its next stroke.
- **3D view in the video** (`camera3d/video.py`). A belief homography decomposes, with the camera's intrinsics, into a
  pose: "the page is there, relative to me". Drawing that believed page through the true camera gives a plane (blue)
  inside the camera's field of view; it lies on the real page (white outline) exactly when the belief is right. Where
  the belief is not a physically consistent camera, the decomposition takes the nearest rotation, so the plane is an
  approximation of the belief, while the error numbers are computed from the belief itself.

## Results (pilot, 2026-09-30)

Run `results/camera3d/20260930T202111Z-6181fa`: four models, two pages, one episode each, $13.58.

| seed | agent | strokes | closed | first-try (sq 1-4 / 5-8) | camera matched at stroke (cold / after move) | final belief error | cost | status |
|---|---|---|---|---|---|---|---|---|
| 3004 | Claude Opus 5.5 | 19 | 7/8 | 0 / 0 | never / never | 39.9 mm | $1.80 | complete |
| 3004 | GPT-6 Astra | 12 | 6/8 | 0 / 1 | 8 / 2 | 1.0 mm | $2.58 | capped |
| 3004 | GPT-6 Sol | 18 | 8/8 | 0 / 0 | never / never | 5.9 mm | $0.86 | complete |
| 3004 | Gemini 3.8 Flash | 27 | 3/8 | 0 / 1 | never / never | 8.6 mm | $1.49 | complete |
| 3004 | Code estimator (ideal learner) | 11 | 8/8 | 1 / 4 | 5 / 1 | 0.5 mm | $0.00 | complete |
| 3004 | Oracle | 8 | 8/8 | 4 / 4 | 1 / 1 | 0.0 mm | $0.00 | complete |
| 3017 | Claude Opus 5.5 | 16 | 8/8 | 1 / 1 | never / never | 20.5 mm | $1.25 | complete |
| 3017 | GPT-6 Astra | 14 | 8/8 | 1 / 3 | 8 / 1 | 0.8 mm | $2.70 | complete |
| 3017 | GPT-6 Sol | 16 | 8/8 | 2 / 0 | never / never | 6.5 mm | $0.96 | complete |
| 3017 | Gemini 3.8 Flash | 29 | 2/8 | 0 / 0 | never / never | 29.3 mm | $1.94 | complete |
| 3017 | Code estimator (ideal learner) | 12 | 8/8 | 2 / 4 | 7 / 1 | 0.4 mm | $0.00 | complete |
| 3017 | Oracle | 8 | 8/8 | 4 / 4 | 1 / 1 | 0.0 mm | $0.00 | complete |

- **GPT-6 Astra is the only model whose camera matched**, at stroke 8 on both pages from a cold start (the ideal
  estimator: strokes 5 and 7). After the move it re-matched on the first stroke (seed 3017; note: "The camera has
  moved; matching existing strokes restores the mapping") or the second (seed 3004), and closed 3 of 4 later squares
  first try on seed 3017. Its seed 3004 episode is capped (see Limits).
- **Claude Opus 5.5 closes squares without a camera model.** 15 of 16 squares closed, but its reported camera never
  came within 3 mm; after the move it stayed 20–40 mm off (on seed 3004 the same estimate for 9 strokes) while it
  closed squares by correcting its last miss against nearby ink ("referencing stroke 10 on square 4 just to its right").
- **GPT-6 Sol** closed every square; its belief plateaued at 6–7 mm and never matched.
- **Gemini 3.8 Flash** closed 5 of 16 squares and never matched.
- First-try closes after the move (squares 5–8): Astra 3/4 and 1/4, Opus 1/4 and 0/4, Sol 0/4 and 0/4, Flash 0/4 and
  1/4 (seeds 3017 and 3004); estimator 4/4 on both.

### Does it transfer? The moved camera, with vs without its own earlier ink

A second run (`results/camera3d/20260930T205532Z-90c393`, $6.58) started *fresh* at the moved camera: the same
pose, the same squares 5–8, but none of the agent's own ink on the page. Compared with the part of the first run
spent at that camera (after the move):

| agent | page | belief error at first stroke (transfer / fresh) | matched at stroke (transfer / fresh) | first-try closes (transfer / fresh) | strokes for 4 squares (transfer / fresh) |
|---|---|---|---|---|---|
| Claude Opus 5.5 | 3004 | 39.9 mm / 23.0 mm | never / never | 0/4 / 1/4 | 9 / 9 |
| Claude Opus 5.5 | 3017 | 20.5 mm / 15.5 mm | never / never | 1/4 / 1/4 | 7 / 8 |
| Code estimator (ideal learner) | 3004 | 0.4 mm / 21.1 mm | 1 / 6 | 4/4 / 1/4 | 4 / 9 |
| Code estimator (ideal learner) | 3017 | 0.5 mm / 14.1 mm | 1 / 5 | 4/4 / 2/4 | 4 / 8 |
| Gemini 3.8 Flash | 3004 | 8.6 mm / 38.6 mm | never / never | 1/4 / 0/4 | 13 / 16 |
| Gemini 3.8 Flash | 3017 | 29.3 mm / 11.9 mm | never / never | 0/4 / 0/4 | 15 / 16 |
| GPT-6 Astra * | 3004 | 13.1 mm / 7.4 mm | 2 / never | 1/2 / 0/4 | 4 / 9 |
| GPT-6 Astra | 3017 | 0.9 mm / 12.9 mm | 1 / never | 3/4 / 0/4 | 5 / 9 |
| GPT-6 Sol | 3004 | 6.6 mm / 25.6 mm | never / never | 0/4 / 0/4 | 8 / 12 |
| GPT-6 Sol | 3017 | 5.3 mm / 10.4 mm | never / never | 0/4 / 0/4 | 8 / 10 |
| Oracle | 3004 | 0.0 mm / 0.0 mm | 1 / 1 | 4/4 / 4/4 | 4 / 4 |
| Oracle | 3017 | 0.0 mm / 0.0 mm | 1 / 1 | 4/4 / 4/4 | 4 / 4 |

\* an episode in the pair did not finish all four squares (capped or stopped).

- **GPT-6 Astra transfers.** With its old ink it matched the new camera at stroke 1 (seed 3017; stroke 2 on seed
  3004), closed 3 of 4 squares first try and used 5 strokes. Fresh at the same camera it never matched in 4 squares,
  closed 0 first try and used 9. The ideal estimator shows the same pattern by construction (1 vs 5–6 strokes).
- **GPT-6 Sol transfers partly.** It never matched either way, but it started closer (6.6 and 5.3 mm vs 25.6 and
  10.4 mm) and used fewer strokes with its old ink (8 vs 12 and 8 vs 10).
- **Claude Opus 5.5 does not.** Its first belief at the moved camera was *worse* with the old ink (39.9 and 20.5 mm,
  a stale camera it had not updated) than fresh (23.0 and 15.5 mm), and it used about the same strokes (9/9, 7/8).
- **Gemini 3.8 Flash**: mixed and noisy (13 vs 16 and 15 vs 16 strokes).

### What it says vs what it does

The blue plane is the camera the model *states* (its `camera_estimate`). The orange plane is the camera its
*strokes* imply: an affine map from each target to the command sent for it, fitted over its last 5 strokes, turned
into the camera under which those commands would have been exact (`belief.implied_camera`). On the first stroke at
each new square (median over both pages, n = 15–16 per model):

| Model | Actual first stroke aimed off by | Its stated camera would aim off by | Stated vs actual |
|---|---|---|---|
| Claude Opus 5.5 | 3.3 mm | 15.1 mm | 18.8 mm apart |
| GPT-6 Astra | 1.5 mm | 2.5 mm | 0.5 mm apart |
| GPT-6 Sol | 4.6 mm | 6.3 mm | 5.0 mm apart |
| Gemini 3.8 Flash | 13.2 mm | 13.1 mm | 11.4 mm apart |

Opus aims competently off nearby ink but writes down a camera 15 mm off; Astra acts on the camera it states.

## Replication plan (preregistered 2026-09-30, before the run)

Written before any replication episode ran. The pilot pages (3004, 3017) chose the hypotheses, so they are reported
but do not count toward the pass rules below.

- **Pages:** the next four of `camera3d.run.SEEDS`: 3008, 3023, 3033, 3015 (fixed in advance; none dropped).
- **Models:** GPT-6 Astra, Claude Opus 5.5, GPT-6 Sol (registry settings as in the pilot). Gemini 3.8 Flash is not
  replicated (budget); its results stay pilot-only and are labelled so.
- **Arms per page:** `transfer` (8 squares, the camera moves after square 4) and `fresh` (the moved camera from the
  start, squares 5–8 only). Code estimator and oracle on every cell.
- **Budget:** hard cap $30 for the run; per episode $4 (transfer) and $2.50 (fresh). A capped, stopped or failed
  episode counts as *not matched* and as *no transfer* for the model concerned, and is reported.
- **Metrics:** as defined above (aim error; matched = ≤ 3 mm from some stroke on and for the rest of the pose).

Claims and pass rules, on the four new pages:

1. **Only Astra learns the camera from a cold start.** Pass if Astra's stated camera matches at the first pose on at
   least 3 of 4 pages, and Opus and Sol each match on at most 1 of 4.
2. **Astra transfers.** Pass if, on at least 3 of 4 pages, Astra (a) matches the moved camera within 2 strokes in
   `transfer` and (b) uses fewer strokes for squares 5–8 in `transfer` than in `fresh`.
3. **Opus says one thing and does another.** Pass if, pooled over the four pages, the median gap between where
   Opus's stated camera would aim and where its first stroke on each new square actually aimed is at least 5 mm,
   and at least twice Astra's.

Everything else (Sol's partial transfer, Opus's stale belief after the move, first-try closes) is descriptive.
A claim that fails is reported as failed and is not posted.

## Replication results (run `results/camera3d/20260930T212228Z-1f1729`, $27.54, 24/24 model episodes complete)

Scored by `freehand camera3d study` against the rules above; tables in `results/camera3d/studies/replication-1/`
(all runs together: `studies/all-2026-09-30/`).

##### Preregistered claims, scored on pages 3008, 3023, 3033, 3015

Rules: docs/freehand_a.md, 'Replication plan'. Claims 1 and 3 use the transfer episodes (claim 3: the first
stroke at every square, both camera poses); a capped, stopped or failed episode counts against the claim.

#### 1. Only Astra learns the camera from a cold start (Astra >= 3/4 pages; Opus, Sol <= 1/4): **PASS**

- gpt-6-astra: 3/4 pages matched
- claude-opus-5.5: 0/4 pages matched
- gpt-6-sol: 0/4 pages matched

#### 2. Astra transfers (matched within 2 strokes after the move AND fewer strokes than fresh, >= 3/4 pages): **FAIL**

- 3008: no: matched moved camera at 3; strokes 6 vs fresh 10
- 3023: no: matched moved camera at None; strokes 4 vs fresh 6
- 3033: yes: matched moved camera at 1; strokes 4 vs fresh 9
- 3015: yes: matched moved camera at 1; strokes 5 vs fresh 8

#### 3. Opus says one thing and does another (median gap >= 5 mm and >= 2x Astra's): **PASS**

- claude-opus-5.5: median stated-vs-actual gap 14.7 mm
- gpt-6-astra: median stated-vs-actual gap 0.6 mm


**Claim 2 failed as preregistered** (2 of 4 pages). It failed on the matching criterion, not on behaviour: on page
3023 Astra's stated camera settled at 3.6 mm after the move (the bar is 3 mm) while it closed all four squares on the
first stroke; on page 3008 it matched at stroke 3 instead of 2. Descriptive, not preregistered: with its own earlier
ink Astra closed 13 of 16 squares after the move on the first stroke, vs 3 of 16 started fresh at the same camera,
and used fewer strokes on all four pages; Opus 4/16 vs 4/16; Sol 3/16 vs 2/16; the estimator 15/16 vs 4/16. By the
preregistration's own rule, the transfer claim is not posted as a finding.

## Limits

- Pilot scale: two pages (seeds 3004 and 3017), one episode per model and page. A spread of behaviours, not a
  ranking.
- The reported belief and the strokes can disagree: a model can close a square by correcting its last miss locally
  while its reported camera stays wrong (Opus). Belief error measures the report; first-try closes measure the
  behaviour; both are shown.
- Reporting a camera estimate every turn is itself a prompt to model the camera. A run without the field (behaviour
  only) is the control this pilot does not have.
- The per-call spend reservation counts encrypted reasoning as input text, so it is conservative: GPT-6 Astra's seed
  3004 episode stopped at its $3.50 cap after 12 strokes (logged as `capped`, inconclusive), with $2.58 actually spent.
