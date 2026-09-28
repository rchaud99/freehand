# Findings and claim boundaries

A conservative merge of the two historical KEY_FINDINGS documents:

- the working copy's "key surprising findings" (2026-09-27; [archive/working_copy/KEY_FINDINGS.md](archive/working_copy/KEY_FINDINGS.md));
- the Codex copy's "evidence and claim boundaries" (2026-09-28; [archive/codex/KEY_FINDINGS.md](archive/codex/KEY_FINDINGS.md)).

This merge updates them with the results that came later and the corrected scorer. Where the two copies disagree,
this page states only what both support. Every disagreement is listed for a human decision in
[MIGRATION.md](MIGRATION.md#needs-a-human-decision).

**Evidence level.** These are pilots: one episode per cell, one page per design (seed 7 or 10), two to seven
models. They support *leads*, not model rankings or saturation claims. The frozen suites (`core-v1`,
`discriminating-v1`, `camera-v1`) exist to replicate them over held-out seeds.

## Claim boundaries (adopted from the Codex copy)

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
6. Replay verifies the logs' deterministic consistency (in this repo: every imported historical episode and 5,143
   observation images reproduce exactly). It does not verify the scientific validity of every historical claim.

## What the pilots show

All first-try figures are hits / squares reached, on the squares after the first post-change square (squares
6–20 of the 20-square learning-curve page, seed 10). They are recomputed with the corrected scorer; MIGRATION.md
lists every number that changed. `capped` = the episode cost cap was reached (inconclusive); `stopped` = cut by a
budget or provider limit.

### 1. Models write explicit models of a silent change

Opus 5.5 and GPT-6 Astra were never told anything could change. After their strokes landed wrong, they wrote down
quantitative models of the fault, for example:

- Opus on the 13° rotation: "landed x' = 1.03x − 0.23y + 32.3" (sin 13° ≈ 0.225);
- Opus on the 0.73 scale: fitted 0.70–0.73;
- Astra: "actual = 0.75·command + (28.5, 35.0)".

Quotes: [archive/quote_bank/HIGHLIGHTS.md](archive/quote_bank/HIGHLIGHTS.md). Boundary 3 applies: a written model
is a hypothesis about the model's reasoning, not proof it used it.

### 2. Completion hides local patching

Without being told a rule exists, Opus mostly missed the first stroke on each new square after the change, saw the
gap, and corrected locally; the squares still closed.

| Later first-try (squares 6–20) | rot13 | shear (L3 rung 2) | camera bumped (L6) |
|---|---|---|---|
| code estimator (`adaptive`) | 14/15 | 13/15 | 15/15 |
| Opus, silent | 2/9 (capped) | 0/15 | 12/15 |
| Opus, told to minimise strokes | 0/10 (capped) | 0/15 | 1/3 (stopped) |
| Astra, silent | 14/15 | 4/10 (capped) | 13/14 (stopped) |
| Astra, told to minimise strokes | 13/15 | 10/13 (capped) | 8/9 (stopped) |

So the primary metric is the first-try learning curve, not completion (both copies agree).

### 3. Being told a consistent rule exists changed Opus's behaviour

With the informed + objective prompt, the same page and the same settings (Addendum 9; the cut cells finished by
the Addendum 12 resumes):

| Later first-try | rot13 | shear | camera bumped |
|---|---|---|---|
| Opus, informed + objective | 11/15 | 8/15 | 13/15 |
| Astra, informed + objective | 14/15 | 13/15 | 11/15 |

- Opus rose from 2/9 to 11/15 on rotation (at about a third of the cost) and from 0/15 to 8/15 on shear. On
  rotation it fitted the change once, then aimed each new square through the fitted map.
- Astra was already near the estimator; the prompt helped it on shear.
- These are single episodes. Whether Opus's silent-arm behaviour was a *choice* (a framing effect) or a
  *capability* limit is not established by them; the one-shot mode in the roadmap is the proposed test. The
  working copy phrased this as "knowing ≠ using"; the Codex copy withdrew that phrasing. See MIGRATION.md.

### 4. Landed ends as numbers (stateless): helps on rotation, not (for Opus) on shear

Stateless (no conversation, no notes), with each stroke's landed ends given as measured numbers:

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

### 5. Camera vs plotter: a hypothesis, not a finding

The keyword screen labelled every camera-only (L6) episode as blaming the plotter (the working copy counted 12/12),
including under the informed prompt. Under boundary 4 this is a hypothesis to test behaviourally: blind targets
given only in text, or checking whether the model re-anchors on its own old marks (`camera-v1`: transfer vs fresh).

### 6. Offline controls: which rules separate learning from local repair

Code agents only (Codex copy; not model evidence), on 32 page seeds:

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

### 7. The interface can masquerade as a capability limit

Sonnet 5's end-location error went from 334 mm (answering in page mm read off the grid) to 0.5 mm (answering in
pixels of a magnified crop) (Addendum 5). Answer mode is therefore a per-model setting (`output_mode`), and `auto`
runs the K1 perception gate.

### 8. Smaller models

Flash wrote an approximately right affine model and was too imprecise to use it; Sonnet formed no model (working
copy; single episodes, keyword/quote based). Treat as anecdotes.

## What is not established

- Model rankings, saturation, or that any model "can't" do the task. These are single-episode pilots.
- That failing to apply a written model reflects a gap between knowledge and use. It may be estimation imprecision
  (boundary 3).
- Any causal attribution from wording (boundary 4).
- That the reference estimators are optimal (boundary 5).
- Novelty over prior work on hidden-law discovery ([related_work.md](related_work.md)).
