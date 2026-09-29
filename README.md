# Freehand

**When a tool silently changes, does an AI agent learn the change, or patch each mistake locally?**

An agent draws on a simulated page through a pen plotter and sees the result through a camera. The page holds
hand-drawn squares, each missing one side; the agent closes them one stroke per turn, commanding endpoints in page
millimetres, and ink is permanent. Partway through, the tool silently changes (the plotter's map rotates, shears,
lags, mirrors or warps, or the camera moves) and nobody tells the agent.

## Why it matters

Agents that act in the world (robots, computer-use agents, lab automation) meet tools that drift, get recalibrated
or break without notice. Completion hides whether they understood the change: missing, looking at the gap and
correcting still closes every square. So Freehand scores **transfer**: after the change, does each *new* square close
on its *first* stroke? That only happens reliably once the agent has a model of the change. The first-try curve is
reported with strokes, wasted ink, tokens and cost, next to code reference agents on the same pages (an oracle, a
naive agent, an ideal estimator, a local patcher, and others).

## Result so far

![First-try rate on later squares, told a rule exists, seven models](docs/figures/first_try_bars.png)

These are pilots: one page (seed 10), one episode per cell, and no model has run the frozen `core-v1` benchmark yet.
Told *"The plotter/tool can be perturbed at any time and in any way, but always following a consistent pattern or
rule. Be intelligent: observe where your strokes actually land, form hypotheses about the rule, test them
efficiently, and deduce it. YOUR OBJECTIVE — THIS IS VERY, VERY IMPORTANT: minimise the total number of strokes; you
are benchmarked on it."*, on the squares after the first post-change square (6–20):

- **GPT-6 Astra** hit 14/15, 13/15 and 11/15 on the first stroke under a 13° rotation, a shear and a moved camera, and
  **Claude Opus 5.5** 11/15, 8/15 and 13/15 (the code estimator: 14/15, 13/15, 15/15).
- **GPT-6 Sol** did so on rotation only (11/15); **Gemini 3.8 Flash** fitted late (6/15, 5/15, 0/15); **Claude Sonnet
  5** had no first-try hit after the change; **GPT-5.5** and **Kimi K3** were capped or stopped after 1–4 later
  squares, with no hit.
- Without that prompt, Opus patched each square locally after the rotation (2/9, capped) and the shear (0/15), but
  carried its fix forward after the camera move (12/15).
- In the 13 camera-only episodes, no model's notes or memory name the camera (a keyword screen; whether models blame
  the plotter is untested).

With n = 1 per cell this is a spread of behaviours, not a ranking; several cells were capped or stopped
(inconclusive), and Kimi K3 passed the basic-task gate only at its threshold. Numbers, quotes and claim boundaries:
[docs/findings.md](docs/findings.md).

## Quickstart (offline, no key, nothing charged)

Python 3.12 on macOS or Linux, from a clone (only `pip install -e .` from a clone is supported: the configs, suites
and results tree live in the checkout):

```sh
git clone <repository-url> freehand && cd freehand
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
freehand run smoke --fake-models     # the whole pipeline with a scripted fake model; its "$0.32" is simulated
freehand ls
RUN=$(ls -d results/smoke/*/ | tail -1)
freehand report "$RUN"               # tables and charts in $RUN/report/
freehand replay "$RUN" --render      # re-simulate every stroke and regenerate every image: 0 mismatches
pytest                               # offline, about 2 minutes
```

## Run a real model

```sh
echo 'OPENROUTER_API_KEY=sk-or-v1-...' > .env     # gitignored; read only when a live call is needed, never logged
freehand episode --model flash --suite smoke-v1 --seed 1 --perturbation rot13 --max-usd 1.50   # 4 squares
freehand run core-v1 --model <registry-id-or-openrouter-slug> --dry-run     # the plan: cells, settings; no calls
freehand run core-v1 --model <registry-id-or-openrouter-slug> --split dev --max-usd 20
```

`--model` takes a registry id (`freehand models`) or any OpenRouter slug. Budgets: every paid call is recorded in
`results/ledger.sqlite`; `--max-usd` caps new spend per invocation, the config's tag cap caps a study, an episode cap
ends an episode as `capped` (inconclusive), and paid runs first lower the cap to what the OpenRouter balance covers
(all local estimates, not provider limits). A full `core-v1` run is 120 episodes per model (test seeds; report
those, develop on `--split dev`); the pilots cost $0.70–10 per episode. If openrouter.ai's IPv6 route fails on your
network, set `FREEHAND_FORCE_IPV4=1`.

## Suites

A suite is frozen, seeded data: the same suite and seed give the same pages, targets, rules and change schedule on
any machine (`freehand suite verify --all` checks the stored hashes).

| Suite | What it measures |
|---|---|
| `core-v1` | 20 squares visited far apart, change after square 4. Rules: an unchanged control, a 13° rotation, scale + shear, a bumped camera under a stale rectification, a latent mirror mode, a smooth warp. |
| `discriminating-v1` | Rules on which local patching fails (command memory, latent mirror mode, smooth warp) and a control; the change time is hidden and varies by seed. |
| `camera-v1` | The camera track ("Freehand A"): a raw, uncalibrated camera view; the camera moves after square 4 (transfer) vs the same squares at the new pose (fresh). |
| `smoke-v1` | 4 squares, for smoke tests. |
| `legacy-*-v0` | Regenerate the historical pilot pages bit for bit, so old results stay comparable. |

Each suite has `dev` seeds (develop on these) and `test` seeds (report these). The test seeds are public, so they are
held out by convention. An *arm* is what the agent is told and remembers: memory with a notepad, or stateless; silent,
told to minimise strokes, or told a rule exists ([docs/method.md](docs/method.md)).

## Reproduce the figures

The logged episodes behind [docs/figures/](docs/figures/) are a release asset (4.3 MB):

```sh
DATA_URL="TODO-RELEASE-URL"   # TODO(release): the release-asset URL of freehand_figure_runs_v1.tar.gz
curl -L -o freehand_figure_runs_v1.tar.gz "$DATA_URL"
mkdir -p data && tar -xzf freehand_figure_runs_v1.tar.gz -C data
freehand figures data/freehand_figure_runs_v1/runs/* --out figures    # = docs/figures, byte for byte
freehand replay data/freehand_figure_runs_v1/runs/informed_models_20260928_174709   # every stroke exact
```

The logged episodes plus `freehand replay` are the record. Re-running a study from the request cache
(`freehand run <study> --max-usd 0`) is not an exact reproduction when concurrent episodes sent identical requests.
Checksums, rendering the images and the details: [docs/reproducing.md](docs/reproducing.md).

## Extend

Add a model, an arm, a perturbation, a suite or an experiment: [docs/extending.md](docs/extending.md).

## Status and limitations

Research code, not an externally reviewed benchmark release.

- The model evidence is pilot-scale: one page, one episode per cell, seven models; the frozen v1 suites have not
  been run by a model. The next step is replication on `core-v1`'s test seeds ([docs/roadmap.md](docs/roadmap.md)).
- The attribution screen (camera vs plotter) and the quote bank are keyword based and unvalidated.
- Rendered images are byte-identical only under the pinned numpy and OpenCV (CPython 3.12); the data hashes are the
  portable guarantee. Tested on macOS arm64; CI runs macOS and Linux.
- Every imported historical episode (1,901) replays exactly, and the new episode loop sends byte-identical requests
  to the original code (`tests/test_legacy_parity.py`, 150 cases).

## Docs

| Doc | What it holds |
|---|---|
| [findings.md](docs/findings.md) | The results, with claim boundaries and evidence levels |
| [method.md](docs/method.md) | The task, what the agent sees, arms, rules, reference agents, scoring |
| [reproducing.md](docs/reproducing.md) | The data bundle, regenerating the figures, replay |
| [extending.md](docs/extending.md) | Adding a model, arm, perturbation, suite or experiment |
| [perturbations.md](docs/perturbations.md) | The implemented rules; the design space is [design/perturbation_ideas.md](docs/design/perturbation_ideas.md) |
| [architecture.md](docs/architecture.md), [results_format.md](docs/results_format.md) | Code layout and design decisions; the results tree and JSON Schemas |
| [roadmap.md](docs/roadmap.md) | Status, next steps and open design questions |
| [HISTORY.md](docs/HISTORY.md) | The project's chronology, corrections and spend, with a glossary |
| [preregistration.md](docs/preregistration.md) | The preregistration and its dated addenda, verbatim |
| [related_work.md](docs/related_work.md) | Related benchmarks |
| [quote_bank/](docs/quote_bank/README.md) | Notes and memories from every model episode, and curated highlights |
| [provenance/](docs/provenance/README.md) | Historical documents and how the two earlier copies became this repository |

## Citation

If you use Freehand, please cite it (metadata in [CITATION.cff](CITATION.cff)):

```bibtex
@software{chaudhary_freehand_2026,
  author  = {Chaudhary, Raghav},
  title   = {Freehand: learning a silently changed tool from the consequences of one's own strokes},
  year    = {2026},
  version = {0.1.0}
}
```

**License: TODO** (not chosen yet).
