# Freehand: adaptation to changing tools

Freehand measures whether an agent can use the consequences of its own strokes to adapt to an unfamiliar plotting rule. Ink is permanent. A visually plausible final drawing can conceal repeated local repairs, so evaluation reports first-stroke transfer, total strokes, completion, and ink together.

This directory is an isolated publication-development copy of `freehand_b`, created September 28, 2026. **It is not a completed benchmark release.** Historical model pilots and new offline controls are separate. No new frontier-model runs were performed in this revision.

## Start here

- [Latest continuation: 896 new-seed episodes and stronger baselines](CONTINUATION_REPORT.md)
- [Earlier verified work and limitations](PUBLICATION_REPORT.md)
- [New offline controls: 240 episodes, 16 page seeds](publication/control_study/REPORT.md)
- [Experiment specification and next validation](PUBLICATION_PLAN.md)
- [Reproducibility and claim audit](publication/replay-audit.json)
- [Test results](publication/test-results.txt)

## Reproduce without model access

Python 3.12 was used. The simulation no longer needs the neighboring hardware project.

```sh
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python publication_experiments.py --out publication/my_controls
.venv/bin/python replay_audit.py runs publication/my_controls --out publication/my_replay.json
```

The control runner refuses to overwrite an existing output directory. It writes the seed list, source hashes, parameter settings, and access assumptions before executing episodes. No API keys are needed for these commands. `requirements-observed.txt` records direct versions; `requirements.lock` pins transitive dependencies and hashes. A fresh local Python 3.12 environment was installed offline from cached distributions and passed the regression suite. Strict hash-enforced offline installation could not finish because the original OpenCV wheel was absent from cache; see the continuation report. Other operating systems have not been tested.

## Experimental rules

Three candidate extensions are implemented in `perturbations.py`:

1. **Command dynamics:** executed endpoints lag commanded endpoints, with persistent state across strokes. A miss changes the next command's starting state.
2. **Latent mirror mode:** the previous command's start side determines whether the next stroke is mirrored. This tests tracking action-dependent state.
3. **Cross-axis warp:** a smooth sinusoidal deformation requires spatial generalization and, for long vertical strokes, a curved inverse command.

These are exploratory candidates. The nonlinear warp remains relatively easy for local correction on the current short-target pages. Difficulty against language models is unmeasured.

## Scoring and references

`scoring.py` distinguishes observed first-stroke accuracy from coverage and fixed-budget attainment. An interrupted target with an already failed first stroke is an observed miss. A target never attempted remains unknown. Fixed-budget attainment divides successes by all planned targets; missing targets in that measure are not evidence of model reasoning errors.

The oracle knows hidden state and parameters. The family estimator knows the rule family and change timing and receives numeric endpoints. Those are privileged controls, not perception-matched model competitors or mathematical optima. Report their access alongside every comparison.

Historical language mentioning an "ideal estimator" or "knowing but not using" is not a validated mechanistic conclusion. [Current claim boundaries](KEY_FINDINGS.md) supersede the older narrative documents. `PREREGISTRATION.md` remains historical; the September 28 control study is explicitly exploratory.

## Release boundaries

`runs/`, `cache.sqlite`, and the copied `.venv/` are local evidence/runtime material, not a proposed public distribution. The local review bundle uses an explicit allowlist and SHA-256 manifest. It is not published and does not grant a license. Original model adapters still have machine-specific credential fallbacks; no credentials are embedded in the new modules. Publishing, model replication, license selection, and external review remain outstanding.

## Continued validation

`baseline_study.py` adds numeric-observation local secant and unknown-family/time library references. The 32-seed evaluation and its failures are documented in [CONTINUATION_REPORT.md](CONTINUATION_REPORT.md).

```sh
python baseline_study.py --out publication/my_baselines --seeds 3001 3002 3003 3004
python model_study.py --out publication/my_model_plan
python build_review_bundle.py --out release/my_review.zip
```

The first command is a reproducibility subset, not the full 32-seed study. The second only writes a plan; paid execution requires explicit arguments and configured credentials. See [MODEL_STUDY.md](MODEL_STUDY.md).
