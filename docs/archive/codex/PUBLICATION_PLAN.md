# Publication experiment plan — September 28 revision

## Scope and interpretation

The defensible question is whether learned tool behavior transfers to subsequent targets under a fixed interaction budget. More perturbations alone do not establish a better benchmark. Every candidate needs a solvability control, a competent local-repair baseline, a global learner, and an unchanged-tool control.

## Offline exploratory study actually executed

The specification is serialized in `publication/control_study/manifest.json` before the first episode. Sixteen contiguous page seeds (2001–2016), twelve targets per page, change after target three. Targets are placed in a central region to avoid confounding inverse feasibility with difficulty. All seeds are retained. Three new rule families and identity; oracle, naive, local patcher, and known-family estimator (the identity condition has no separate estimator). Total: 240 episodes.

The oracle is subject to the same command bounds, ink noise, and closure tolerance. The family estimator receives exact target coordinates and noisy executed endpoints, plus family and change timing. These reference privileges are explicit and forbid treating their score as a vision-matched comparison to language models. Headless execution is allowed only for code agents. A rendered/headless equivalence test checks identical command and ink records.

Primary descriptive outputs: first-try attainment over all nine post-change targets, total post-change strokes, completed targets, and clamping. Bootstrap intervals resample whole page seeds; paired differences use matched seeds. These intervals reflect variation within this generator and family, not uncertainty over model families or real devices. If all observed values are identical, percentile bootstrap bounds collapse; that does not establish zero population uncertainty. All comparisons are exploratory with no confirmatory significance claim.

## What the controls suggest

Persistent command dynamics is the best next model experiment: local correction completes the pages but requires substantially more strokes, while a fitted family model transfers. Latent state provides a different failure mode and strong separation in completion. The smooth warp currently yields modest extra retry cost; do not present it as equally promising without longer targets or a direct transfer test. The mirror patcher's clamping is itself a consequence of an unstable correction strategy, not evidence of unreachable oracle targets.

## Next model study (not run)

Freeze two families first: command dynamics and latent mode. Add identity and an existing affine condition. Fix page seeds before running models and use both a development split and an untouched evaluation split. Hold page area, target sizes, image resolution, context policy, and per-episode budgets constant across paired conditions. Record exact model IDs, route, reasoning settings, prompts, seeds, stop reasons, and spend. Use at least several independent pages before interpreting model rankings.

Include an image-only arm and a numeric-endpoint arm to separate perception from rule learning. Include silent and rule-exists disclosures, with matching text length where practicable. Do not tune difficulty using held-out model runs. Score all planned cells, disclose incomplete episodes, and show both conditional observed accuracy and fixed-budget attainment.

## Candidate follow-ups, in priority order

1. Numeric-endpoint ablation and frozen model replication of ARX/state.
2. Blind targets plus stable fiducials to test camera-vs-plotter attribution behaviorally.
3. An equally informed general-purpose system-identification baseline, and a stronger local secant/Newton baseline.
4. Held-out parameter values and compositions. Keep evaluator cases private if needed, while disclosing the task specification, access assumptions, and scoring. Hidden cases do not prove absence of training contamination.

## Claim restrictions

Do not infer correct model use from a rationale, or incorrect attribution from the presence of words such as "landed." The old attribution regex is a search aid only. Do not call the family estimator optimal. Do not describe historical one-page pilots as saturation. Do not turn the exploratory specification into a retrospective preregistration. The new results demonstrate reference-agent separation, not frontier-model failure or benchmark novelty against all prior work.

## September 28 continuation

The stronger local secant and unknown-family/time candidate-library controls have now been implemented and evaluated on 32 unused page seeds after two four-seed development runs. See CONTINUATION_REPORT.md. This updates the status of those controls without reclassifying the work as preregistered. The prospective model plan is saved but has not been executed against paid providers.
