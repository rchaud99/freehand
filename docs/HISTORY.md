# Project history

A chronological journal of Freehand, from the first plan to this repository. It is compiled from the
preregistration addenda ([preregistration.md](preregistration.md)), the benchmark ladder
([provenance/benchmark_ladder.md](provenance/benchmark_ladder.md)), the run manifests and spend ledger (imported
into `results/`), both historical copies' reports ([provenance/](provenance/README.md)), the 2026-09-27 briefing
and the project plan, and this repository's git log.

## Glossary of provenance names

The project lived in two folders before this repository; older documents and a few code comments name them.

| Name | What it is |
|---|---|
| **Copy B**, "the working copy" (`freehand_b`) | The original research folder, 2026-09-27/28. Every paid pilot ran here. |
| **Copy A**, "the Codex copy" or "publication copy" (`freehand_publish`) | A parallel copy made on 2026-09-28 (with an AI coding agent) for publication work: the corrected scorer, the claim boundaries, the offline control studies. No paid calls. |
| **Addendum N** | A dated amendment of the [preregistration](preregistration.md), written before the run it describes. |
| **L2–L7** | Levels of the difficulty ladder (L3 shear, L6 camera vs plotter, ...; [perturbations.md](perturbations.md)). |
| **K1** | The preregistered basic-task gate: a model that cannot do the unchanged task is descriptive only. |
| **Freehand A / B** | The camera track (learn an uncalibrated, moving camera) / the plotter track (learn a changed plotter). |

This repository replaced both copies on 2026-09-28/29 ([provenance/MIGRATION.md](provenance/MIGRATION.md)). The verbatim
records (the preregistration and [provenance/](provenance/README.md)) were written with AI coding assistants and call
the project's author "the user".

## Conventions

- **Times.** Copy B's times are US Eastern (EDT). Copy A reported UTC.
- **Spend.** From the merged ledger (`results/ledger.sqlite`, one row per paid call, tagged by run). All model calls
  went through OpenRouter, except Gemini's direct-Google calls (billed by Google, counted in the tags).
- **Evidence level.** One episode per cell throughout. Every result below is a pilot lead; see
  [findings.md](findings.md) for the claim boundaries.

## Phase 0: the plan (2026-09-20)

- **Question.** Can multimodal agents restore accurate control when their view or controls change? The plan was a
  physical study: a webcam, an XY pen robot, four models. Acquire a mapping, meet an unknown change, choose probes,
  recover, complete the drawing (project plan v0.2).
- **Design.** Three research questions: acquisition (accuracy vs self-chosen calibration marks), recovery and reuse
  (camera moved, controller scaled, both), transfer to action (complete three unfinished squares).
- **What carried forward.** The square-completion task, "one missing side" squares, camera-vs-controller changes,
  and a claim boundary: measure behaviour, not inferred internal models. The hardware project's landing scatter
  (`estimate_scatter.py`) became the simulator's landing model (`sim/plotter.py`).

## Phase 1: simulator and preregistration (2026-09-27, morning)

- **Question.** In simulation, does a model notice that the plotter silently changed, and recover?
- **Design.** Simulated page, plotter and camera; hand-drawn squares with one side missing; one stroke per turn in
  page mm; closure within 2 mm of both free ends; permanent ink. Two families: B (rectified view with a mm grid,
  plotter changes) and A (raw camera view, camera moves). Code references: oracle, naive, ideal estimator.
  Preregistered **before any paid call**, with kill rule K1 (a model that can't do the unchanged task is
  descriptive only).
- **Spend.** $0.

## Phase 2: first pilot, no memory (2026-09-27, 14:06–14:36)

- **Models.** Opus 5.5, Sonnet 5, Gemini 3.8 Flash. Single-turn requests: every turn a fresh photo and state.
- **Result.** Only Opus closed squares (4/4 before the change). After a 10 mm shift it needed 9 strokes to recover:
  it had no way to carry the fix forward. Flash and Sonnet closed 0/4 pre-change squares first try; Sonnet's strokes
  landed 190–250 mm from targets that Opus read correctly on the same image.
- **Spend.** $1.67 (`pilot`).
- **Corrections.**
  - **Memory-less pilots were meaningless.** Without memory every turn starts from scratch, so "does it learn the
    change" cannot even be asked. Addendum 2 redesigned the study around memory. This first
    design's code no longer exists in either copy; its runs are imported and replay, but cannot be re-run.
  - The mention regex was amended (a bare "scale" matched Opus's "4 px/mm scale").

## Phase 3: memory pilot (2026-09-27, 15:02–15:12)

- **Design (Addendum 2).** A running conversation, a ~150-word notepad echoed back each turn, and the previous 2
  photos downscaled (K = 2). Silent disclosure. Seed 7, 8 squares, change after square 4.
- **Result.** Opus matched the ideal estimator: the 10 mm shift took 3 strokes (estimator 3); after a camera move it
  needed 1 stroke with its old marks visible vs 6 from a fresh start. It monitored itself unprompted: "If the stroke
  is offset, correct next turn." Sonnet and Flash still failed K1.
- **Spend.** $2.32 (`pilot2`).
- **Lesson.** The first resume: Opus `cam_transfer` hit its episode cap at the camera move and was resumed from the
  request cache (23 turns replayed at $0). Cache replay worked here because the episode's requests were unique; see
  Phase 11.

## Phase 4: Sonnet, Flash, the perception probe and crop_px (2026-09-27, 15:21–17:45)

- **Question.** Why do Sonnet and Flash fail the basic task?
- **Runs.**
  - Sonnet on the pilot2 episodes ($3.87, `sonnet_pilot`): failed every pre-change square. Reasoning effort
    `medium` gave **0 reasoning tokens**; forcing `reasoning.max_tokens=4000` fixed that (Addendum 4). It still
    sent pixels as millimetres.
  - Flash on pilot2 ($2.17, `flash_pilot`).
  - Perception / units probe ($0.99, `probe`): 12 single-square pages × 4 answer modes × 3 models. Median end
    error, page mm vs magnified-crop pixels: Opus 0.27 vs 0.15 mm; Flash 1.9 vs 0.28 mm; **Sonnet 334 vs 0.49 mm**.
  - Sonnet in the new `crop_px` mode on no change: 8/8 first try ($0.07, `probe_episode`).
- **Correction.** **Sonnet's "perception failure" was units.** It read the page but converted badly. The fix is an
  interface choice, not a model limit: `crop_px` (a 12 px/mm crop with its own grid, answered in crop pixels,
  converted in code). Answer mode became a per-model setting, with the K1 gate for unknown models.
- **Lesson.** Reasoning must be forced on and logged per turn; provider "effort" settings can silently give none.

## Phase 5: GPT-6 Astra and the OpenAI capability ladder (2026-09-27, 17:45–19:42)

- **Astra** on pilot2 ($1.94): nearly identical to Opus on the shift and the camera move; it learned an uncalibrated
  view in 13 turns vs Opus's 29. Its reasoning is adaptive (0 reasoning tokens on 5 of 9 turns at `medium`).
- **OpenAI ladder** ($5.16): GPT-6 Astra, GPT-5.5 and GPT-6 Sol pass the basic task; GPT-5.6 Terra only with
  crop_px; GPT-5.4 mini and nano fail both (the threshold). Adaptive stop after two failures.
- **Spend to here:** $18.19 (Addendum 5).

## Phase 6: hard pilots (2026-09-27, 19:51–21:10)

- **Design.** Scale ×0.73 and rotation 13° about the page centre, seed 10 (seed 7 left a target unreachable).
  Opus, Sol (page mm), Sonnet and Flash (crop_px). Then again with reasoning forced on for every model.
- **Result (ink regret, scale / rotation; 0 = ideal estimator, 1 = never adapting).** Astra 0.03 / −0.03 · Opus
  0.07 / 0.15 · Flash 0.51 / 0.39 · Sol 0.97 / 0.61 · Sonnet 1.08 / 0.98. Opus wrote "landed x' = 1.03x − 0.23y +
  32.3" (sin 13° ≈ 0.225).
- **Spend.** $7.85 (`hard_pilot`) + $10.52 (`hard_pilot_reasoning`).
- **Lesson.** Ink metrics (total, wasted, regret) became standard; `reasoning_tokens` and `zero_reasoning` are logged
  per turn.

## Phase 7: difficulty ladder L3–L7 (2026-09-27, 21:10–21:44)

- **Design.** Five levels, three knob steps each: L3 shear, L4 backlash, L5 drift with skips, L6 camera / plotter /
  both with a stale rectification, L7 rotation with a 1 mm tolerance. Opus and Astra, adaptive escalation.
- **Result.** Astra never broke (regret ≤ 0.26). Opus broke only at L7 (it fitted "rotation about 12.4°" but could
  not hit 1 mm). When only the camera moved, the notes of both describe pen offsets (the keyword screen said
  "plotter" in 12 of 14 model cells; the screen is unvalidated, [findings.md](findings.md) section 6).
- **Spend.** $18.30 (`ladder`; first stopped by exhausted credit, HTTP 402, then resumed). Total $54.86.
- **Also.** A three-model comparison page with videos (`reports/three_model_comparison/`, now in
  `results/media/`).

## Phase 8: the "hacking" finding and the learning-curve metric (2026-09-27, evening)

- **Finding.** After a change, Opus and Astra mostly did not carry a global model to the next square: they missed
  first on each new square, saw the gap, and fixed it. Squares still closed, so completion and ink looked saturated.
  Opus hit about 8/42 later squares first try across the ladder, Astra about 12/39 (never recomputed with the
  corrected scorer; [roadmap.md](roadmap.md), known gaps).
- **Correction to the metric.** The primary measure became the **first-try learning curve** on squares after the
  first post-change square, with squares visited in far-apart order so a local patch does not transfer.

## Phase 9: objective pilot (2026-09-27, 22:08–22:33)

- **Design (Addendum 8).** 20 squares, far-apart order, change after square 4, seed 10. Rotation 13°, L3 shear step
  2, L6 camera-only step 1. Opus and Astra, silent vs **objective** ("you are benchmarked on the TOTAL NUMBER OF
  STROKES ... VERY, VERY IMPORTANT"). The code estimator was fixed first (fit window, similarity fit, camera bump as a
  similarity); it now hits 13–15 of 15.
- **Result.** Telling models to minimise strokes did not stop patching. Opus got worse on rotation (2/9 silent, 0/10
  objective, both capped) and wrote "try the plain target first; if the stroke lands off, invert the measured
  offset". Astra improved on shear (4/10 → 10/13).
- **Spend.** $24.47 (`objective_pilot`). **Total at the end of 2026-09-27: $79.33.** The OpenRouter balance ($14.08)
  then blocked the next run.
- **Design correction: objective vs informed prompts.** The objective prompt says strokes count; it does not say the
  tool can change. Addendum 9 (written the same night) adds the **informed** block: "The plotter/tool can be
  perturbed at any time and in any way, but always following a consistent pattern or rule ... deduce it". This
  separates "can't deduce the rule" from "doesn't realise it should try".
- **Docs written that night.** KEY_FINDINGS (four "surprising findings"), INTELLIGENCE_PERTURBATIONS (28 candidate
  rules in tiers, including a coloured-pen carousel), the briefing, website and outreach notes.

## Phase 10: the publication copy, copy A (2026-09-28, 12:17–~16:30 UTC)

A separate copy (`freehand_publish`) made for publication work. A planned overnight continuation never ran; the
work was done the next day. **No paid calls.**

- **Corrections.**
  - **The old scorer dropped interrupted misses.** It read only per-square results, so a square whose first stroke
    missed disappeared when the episode stopped before that square's result was written. The corrected scorer counts
    it; coverage and fixed-budget attainment are reported separately. At the time one historical episode changed (1/3
    → 1/4); with all later data, 12 cells change, none by a hit (provenance/MIGRATION.md, "Rescoring").
  - Claim boundaries (findings.md): no rankings or saturation; a written model is not evidence of use; the keyword
    attribution screen is unvalidated; the family estimators are privileged controls, not optima; "knowing ≠ using"
    withdrawn.
- **Code controls: rules that defeat patching.** Three new rules: persistent **command memory** (the plotter smooths
  over past commands), a **latent mirror mode** (a hidden switch flips an axis) and a smooth cross-axis warp.
  - 240 code-agent episodes on 16 seeds, then 896 on 32 new seeds with stronger baselines (offset patcher, a damped
    Broyden secant, an adaptive library learner).
  - Command memory: 4.13 strokes/target for the patcher, 5.31 for the secant, 1.29 for the library learner. Latent
    mode: 3.12 / 3.00 / 1.36. **A correction changes the state (command memory) or flips (mirror mode), so local
    repair keeps failing.** The warp is a weaker diagnostic; on affine the persistent fitter is not better.
  - These are within-generator code results, not model evidence.
- **Engineering.** 24 tests, replay audit (716 then +1,121 episodes exact), rejection of non-finite commands, a
  budget-race fix, a plan-only 48-cell model study (cap $0), a hash-pinned lock file, RELATED_WORK.

## Phase 11: informed and stateless arms (2026-09-28, 17:07–19:08 EDT)

- **Design.** Addendum 9: the informed + objective arm for Opus and Astra on the objective-pilot page. Addendum 10:
  **stateless** arms (no conversation, no notepad; one fresh request per turn) with the full stroke log, either
  commands only (`stateless_image`) or commands plus the landed ends as measured numbers (`stateless_numeric`).
  Prediction: numeric beats all model arms.
- **Deviation.** Both runs ran concurrently and hit the **API key's own $100 lifetime limit** (not the account
  balance that `/credits` reports): HTTP 403/402, episodes `stopped` (Addendum 11).
- **Correction: the resume-cache divergence (Addendum 12).** A request-cache replay did not reproduce the cut
  episodes. Episodes with identical early requests (the same page before the change) ran concurrently, each got its
  own reply, and the cache keeps one reply per request, so a cached replay diverged at turn 1. **Resume became a log
  replay** (`ResumeAgent`): the episode's own logged replies are fed back at no cost, then the model continues live.
  All 10 cut episodes replayed their logged strokes exactly.
- **Result.** Informed: Opus 11/15 rotation, 8/15 shear, 13/15 camera; Astra 14/15, 13/15, 11/15. Opus rose from 2/9
  (silent) to 11/15 on rotation at a third of the cost. Stateless numeric: Opus 11/15 rotation but 2/15 shear;
  Astra 15/15 rotation, 11/13 shear (capped). Stateless image-only: poor and mostly capped. The prediction was not
  confirmed (numeric ties informed for Opus on rotation, loses on shear).
- **Spend.** $11.50 (`informed_pilot`) + $14.14 (`stateless_pilot`), including the Addendum 12 resumes.

## Phase 12: informed arm across models (2026-09-28, 17:47–23:44 EDT)

- **Design (Addendum 12).** The informed arm, same page, five more models: GPT-6 Sol, Sonnet 5 (crop_px), Gemini
  3.8 Flash (crop_px, direct Google API), GPT-5.5, Kimi K3 (newest open-weight vision model; answer mode by the K1
  gate). Cap $80, raised to **$95** mid-run (the Addendum 12 amendment); $8 per episode.
- **Correction: the crop_px camera bypass (harness fix before this run).** The magnified crop used to be cut from
  the *true* page, so under L6 camera-only a crop_px model would have seen the unmoved page and bypassed the
  perturbation. The crop is now cut from the same camera-warped image as the main photo. No earlier crop_px episode
  used L6, so no earlier result changed. (Ported and tested here: `tests/test_crop_camera.py`.)
- **Result.** Astra and Opus turn the hint into first-try hits on all three rules; Sol on rotation only (11/15);
  Flash fits the rules but executes unevenly (6/15, 5/15, 0/15 camera); Sonnet 0 first-try hits everywhere; GPT-5.5
  denies the change and is capped by squares 6–8; Kimi K3 passed its K1 check at exactly 2/4 (the threshold), then
  closed 0/4 pre-change squares first try in each real episode, and was stopped by the run's cap by squares 6–7. In
  the camera-only condition no note or memory names the camera (a keyword screen; whether models blame the plotter
  is untested). Details: [findings.md](findings.md).
- **Spend.** $94.54 (`informed_models`): Sol $17.97, Sonnet $23.68, Flash $14.69, GPT-5.5 $24.30, Kimi $13.91.
- **Lesson: episode-cost accounting.** An episode's reported cost includes pre-change calls shared through the cache
  with the same model's other episodes, while the cap counted new spend; GPT-5.5 episodes show $10.50 and $10.65
  under an $8 cap. This repository's cap counts original cost (provenance/MIGRATION.md, "Changed on purpose").

## Phase 13: this repository (2026-09-28, 18:30–19:41 EDT)

- **Question.** Two diverged copies (A: better engineered; B: newer experiments). Merge into one clean, tested
  package without losing either's behaviour.
- **Design.** `pip install -e .`, CLI `freehand`; frozen seeded suites with data hashes; perturbation registry; one
  generic runner driven by YAML configs (every historical study is one); results tree with manifests, an append-only
  index and JSON Schemas; legacy import with converted logs and `original` symlinks; merged request cache and ledger.
- **Verification.** A parity fixture recorded from both copies' original code (150 cases, 4,919 turns, 1,805
  request keys: 0 differences); at the time, 1,876 historical episodes replayed exactly, 6,791 historical images
  regenerated byte for byte, and 109 tests passed (now 1,901 episodes, after the consolidation, and more tests).
- **Spend.** $0 real (a fake-model smoke run; no live run of this repository has been made yet).
- **Note on the git log.** The first six commits carry the same minute (18:30): the package was assembled and then
  committed in logical steps. informed_models was still running and was imported later.

## Phase 14: consolidation (2026-09-29)

- **What.** Imported informed_models (24 episodes + Kimi's K1 check) and refreshed informed_pilot and
  stateless_pilot; replayed them (54 episodes, 3,770 strokes, 4,646 images: all exact); ported copy B's final
  runner behaviour (K1 check replay, resumable cut checks, the $95 cap) with tests for the crop_px camera fix and
  log-replay resume; fixed an import bug (`--force` made a run a duplicate of itself); added `freehand figures`
  (copy B's charts, byte-identical table under the legacy scorer); regenerated the quote bank; wrote this history,
  the updated findings and the migration notes.
- **Spend.** $0.

## Phase 15: release cleanup (2026-09-29)

- **What.** Local paths and private names removed from the tracked files; `freehand export-data` builds the
  sanitised data bundle behind the figures (byte-reproducible; the figures regenerate from it byte for byte and every
  episode replays exactly); safer resume, Ctrl-C and budget handling, clear CLI errors, mypy and CI; the charts
  state their evidence level; the docs reorganised (provenance records under `docs/provenance/`) and several claims
  narrowed to what the logs support (Kimi K3's gate, probe marks, camera attribution).
- **Results.** Unchanged: the parity fixture, every replay and the figure data are identical; only chart titles and
  labels changed.
- **Spend.** $0.

## Lessons and corrections, in one place

| Correction | Where it came from | What changed |
|---|---|---|
| Memory-less pilots were meaningless | First pilot (Phase 2) | Memory arm: conversation + notepad + K = 2 photos (Addendum 2) |
| Sonnet's "perception failure" was units | Probe (Phase 4) | `crop_px` answer mode; K1 gate; per-model `output_mode` |
| Reasoning "effort" can give 0 reasoning tokens | Sonnet pilot | Reasoning forced on with budgets; logged per turn |
| Completion hides local patching | Ladder (Phase 8) | Primary metric = first-try learning curve; far-apart order |
| "Minimise strokes" is not "a rule exists" | Objective pilot (Phase 9) | Informed + objective arm (Addendum 9) |
| The old scorer dropped interrupted misses | Copy A (Phase 10) | Corrected scorer everywhere; 12 cells rescored |
| Code controls: command memory and mirror mode defeat patching | Copy A (Phase 10) | `discriminating-v1` suite; roadmap tiers |
| The key's lifetime limit is not the balance | Informed/stateless runs (Phase 11) | Balance and key-limit check before paid runs |
| Cache replay diverges for concurrent identical requests | Resumes (Phase 11) | Resume = log replay (`ResumeAgent`) |
| crop_px bypassed the L6 camera move | Before informed_models (Phase 12) | Crop cut from the camera-warped image |
| Episode cost cap depended on cache state | informed_models accounting | Cap counts original cost (this repo) |
| Retry mode mixes metacognition and capability | Roadmap (2026-09-28) | `one_shot` mode planned as the capability control (not built) |
| A 4-square K1 check can pass a model at its threshold | Kimi K3 (Phase 12) | Its cells are descriptive only; the gate size is an open question ([roadmap](roadmap.md)) |

## Spend by run

Real API spend from the merged ledger. The `dry` tag ($1.71, 392 rows, 2026-09-28) is simulated accounting from the
copy B's fake-model dry runs, and `fake:repo_smoke` ($0.17) from this repository's; neither was charged.

| Date (EDT) | Run (tag) | Models | Calls | Spend |
|---|---|---|---:|---:|
| 09-27 14:09 | `pilot` (first pilot, no memory) | Opus, Sonnet, Flash | 99 | $1.67 |
| 09-27 15:02 | `pilot2` (memory pilot) | Opus, Sonnet, Flash | 93 | $2.32 |
| 09-27 15:21 | `sonnet_pilot` | Sonnet 5 | 90 | $3.87 |
| 09-27 17:14 | `flash_pilot` | Gemini 3.8 Flash | 84 | $2.17 |
| 09-27 17:40 | `probe` (perception / units) | Opus, Sonnet, Flash | 144 | $0.99 |
| 09-27 17:44 | `probe_episode` (Sonnet crop_px) | Sonnet 5 | 8 | $0.07 |
| 09-27 17:45 | `astra_pilot` | GPT-6 Astra | 33 | $1.94 |
| 09-27 17:50 | `openai_ladder` | Astra, Sol, GPT-5.5, Terra, 5.4 mini/nano | 436 | $5.16 |
| 09-27 19:51 | `hard_pilot` | Opus, Sol, Sonnet, Flash | 282 | $7.85 |
| 09-27 20:24 | `hard_pilot_reasoning` | Opus, Astra, Sol, Sonnet, Flash | 265 | $10.52 |
| 09-27 21:10 | `ladder` (L3–L7) | Opus, Astra (+ one $0 GPT-5 nano call) | 339 | $18.30 |
| 09-27 22:08 | `objective_pilot` | Opus, Astra | 400 | $24.47 |
| | **Subtotal 2026-09-27** | | **2,273** | **$79.33** |
| 09-28 | Copy A: controls, baselines, plans | code agents only | 0 | $0.00 |
| 09-28 17:09 | `informed_pilot` (incl. resumes) | Opus, Astra | 183 | $11.50 |
| 09-28 17:13 | `stateless_pilot` (incl. resumes) | Opus, Astra | 268 | $14.14 |
| 09-28 17:48 | `informed_models` | Sol, Sonnet, Flash, GPT-5.5, Kimi K3 | 1,471 | $94.54 |
| | **Subtotal 2026-09-28** | | **1,922** | **$120.18** |
| 09-28/29 | This repository (fake-model smoke; consolidation) | none | 0 | $0.00 |
| | **Total** | | **4,195** | **$199.51** |

Per-model spend for the last four runs: `sqlite3 results/ledger.sqlite "SELECT tag, model, SUM(cost) FROM spend
GROUP BY tag, model"`. The OpenRouter balance after informed_models was about $26 (Addendum 13 records $25.83).
