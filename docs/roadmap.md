# Roadmap

## Status (2026-09-29)

The plan below is the working copy's ROADMAP.md (2026-09-28), kept verbatim. Where each step stands now:

| Step | Status |
|---|---|
| 1. informed_objective + stateless arms in `retry` mode | **Done.** informed_pilot, stateless_pilot (resumed to completion) and informed_models (5 more models); docs/findings.md |
| 2. Merge the codebases | **Done.** This repository (docs/MIGRATION.md). Both old folders are read-only archives. |
| 3. `one_shot` mode + continuous landing-error metric | **Not started.** The suites here are `retry` mode. Validate with the code agents first (free). |
| 4. v1 model study in `one_shot` mode (paid) | **Not started.** A's 48-cell `model_study` config exists as a plan (cap $0). Adapt to one_shot. |
| 5. Rig demos, video with the quote bank, red team, website, post | **Not started.** Quote bank: docs/quote_bank/. Historical videos: results/media/. |
| Freehand A (camera learning), below | **Pilots only.** `camera-v1` suite (transfer vs fresh) and the `CamAdaptive` homography reference exist; no model study. |
| Coloured-pen carousel (INTELLIGENCE_PERTURBATIONS, docs/perturbations.md part 2) | **Designed, not built.** |
| Real-model smoke run of this repo (`freehand episode --model flash ... --max-usd 1.50`) | **Pending:** no OpenRouter key in the repo; needs the owner's key and approval. |

Next decisions for the owner are in docs/MIGRATION.md, "Needs a human decision". The informed_models verdict
suggests the informed arm as the benchmark core, with more seeds for Astra, Opus and Sol and crop_px for Kimi before
any ranking (Addendum 13).

---

<!-- Provenance: the working copy's ROADMAP.md (2026-09-28, last changed 17:40 EDT), verbatim below. -->

# Freehand roadmap: how the pieces fit (2026-09-28)

## Three independent factors
- **Task mode:**
  - `retry` (current): up to 12 strokes per square; local patching is possible.
  - `one_shot` (NEW): one stroke per target, and the next target changes after every stroke. Patching is impossible.
- **Agent arm:**
  - memory: silent / objective / informed_objective;
  - stateless: image / numeric (a command log, plus landed coordinates in the numeric variant).
- **Perturbation:**
  - calibration tier: offset, rotation, scale, shear;
  - discriminating tier: command memory (smoothing), latent mirror mode, camera vs plotter with text targets, recurring contexts, coloured-pen carousel.

Nothing replaces anything. Each factor is a dimension of the same benchmark.

## Roles
- **`one_shot` = the MAIN benchmark score (v1).** Pure learning and transfer. Metrics:
  - continuous landing error (mm) by stroke index, which is the learning curve;
  - hit rate;
  - strokes and ink to competence vs the ideal estimator and the smart patcher;
  - cost.
  One-shot targets are far apart, which catches "carry the last error forward".
- **`retry` = the realistic recovery mode.** It keeps the "models hack the task by local patching" finding and all historical data.
- **Stateless-numeric + one-shot = the cleanest intelligence measure,** and the cheapest.

## Order
1. **Now:** the informed_objective run and the stateless arm, in `retry` mode on the objective-pilot pages. Same mode as the prior arms, so the comparison is clean.
2. **Merge the codebases:** Codex's `freehand_publish` copy becomes the source of truth. Port our newer files into it (objective_pilot.py with the informed and stateless arms, KEY_FINDINGS, INTELLIGENCE_PERTURBATIONS with the coloured pens, BENCHMARK_LADDER, quote bank). `git init`, and freeze the working copy as an archive.
3. **Build `one_shot` mode** plus the continuous-error metric. Validate with the code agents first (free): the patcher fails, the learner succeeds.
4. **v1 model study in `one_shot` mode** (paid):
   - Opus + Astra (+ Sol/Sonnet as the middle tier);
   - × {memory + informed_objective, stateless_numeric};
   - × {rotation, command memory, latent mode, and later coloured pens};
   - × 3 seeds.
   Codex's 48-cell plan is adapted to one_shot.
5. **Then:** rig demos, the video with the quote bank overlaid, a red-team pass, the website and a one-command "run any OpenRouter model", then the post.

## one_shot mode: target rules (decided 2026-09-28)
- **Never revisit in the scored phase.** Each target gets exactly ONE stroke, then it's done forever, closed or not. Revisiting would let the old miss act as a local reference, which is patching again.
- **30–40 fresh targets per episode.** Each is far from the previous target AND from all earlier ink or misses (a minimum-distance constraint), so no nearby cue exists. Option: generate targets on the fly in empty space, which avoids running out and never repeats.
- **Main score:** continuous landing error (mm) plus hit rate, by stroke index (the learning curve).
- **Optional, secondary and separately scored:** a final "revisit round" where missed squares come back. It measures using what was learned to fix old misses; it's easier because of local cues.

## Retry vs one-shot: metacognition vs capability (decided 2026-09-28)
- **retry mode, 50+ squares, objective told** = a METACOGNITION / strategy test: does the model realise that learning the rule beats patching, and choose to?
- **one_shot mode** = a CAPABILITY control: can it learn the rule when patching is impossible?
- **Interpretation:**
  - fails retry but succeeds one_shot → can but doesn't (a metacognition failure; the clean version of "knowing ≠ using");
  - fails both → a capability limit.
- **Why patching works on smooth changes:** any smooth distortion is locally ≈ a translation, so correcting by the observed miss leaves about 23% residual on the 13° rotation (0.27 on the 0.73 scale), and squares close in 2–3 strokes. It fails on command memory (the correction changes the state) and on mirror mode (the correction flips).
- Use **50+ squares** in retry mode so patching has longer to lose to rule-learning.

## Freehand A: learning the camera (NOT yet done systematically; added 2026-09-28)
Only pilots exist so far: pilot2 cam_transfer (Opus), sonnet_pilot, L6 camera-only. Freehand A needs its own full model study before publishing.
- **A1 cold start:** raw camera view (no grid, paper edges hidden), unknown page→pixel homography. Measures:
  - strokes until the first first-try closure;
  - landing error (mm) by stroke index.
  - Ideal: about 2 strokes, since 4 endpoint correspondences fix a homography (3 with noise).
- **A2 camera shift:** mid-episode move with graded size (small translation → rotation → perspective tilt). Measure: strokes to recover. The ideal needs **0 new strokes**, because its own earlier ink is still visible and gives the correspondences. Does the model re-anchor on old marks, or spend new strokes?
- **Attribution:** does it blame the camera or the plotter? The pilots blamed the plotter 12/12; that needs a behavioural test, not a regex.
- **Models:** the full lineup (Opus, Astra, Sol, GPT-5.5, Sonnet crop_px, Flash crop_px, an open-weight model), with memory. Arms: silent vs informed ("the camera may move"). Use `one_shot` mode too.
- **Code references first (free):** an ideal homography estimator, plus a re-anchoring vs non-re-anchoring agent.
