# Perturbation ideas: the design document (2026-09-27)

The 28-rule design the implemented rules came from, kept verbatim below as a design record (it is not maintained).
The implemented registry is in [../perturbations.md](../perturbations.md); the roadmap in [../roadmap.md](../roadmap.md).

<!-- Verbatim from the working copy's INTELLIGENCE_PERTURBATIONS.md (identical to the Codex copy's apart from the
notice the Codex copy added: "Historical research document. See KEY_FINDINGS.md and PUBLICATION_REPORT.md for
corrected claim boundaries and verified new work. Predictions below are not new model results."). Of the 28
candidates, the implemented ones are A1 (command_memory), A4 (latent_mirror), a smooth warp from C, and F1's
camera-vs-plotter attribution (L6_attribution). The coloured-pen carousel (A5), convention drift (D1), which-clock
drift (E1), latent affordance (B5) and recurring contexts (E3/E4) are not implemented. Headings are demoted one
level. -->

## Freehand: perturbations that test intelligence (design, 2026-09-27)

This is the design for the core of Freehand. It proposes hidden tool rules that reward inferring a law
and running experiments, not eyesight, retrying, or patching each square locally.

Grounding: `sim.py`, `episode.py`, `levels.py` and `BENCHMARK_LADDER.md` as of today. No code was
changed and no API calls were made. Related benchmarks are in section 8.

---

### 0. The key observation: why the current ladder saturates

**Local patching is fixed-point iteration.** A model that misses, looks at the gap and corrects is
running `u ← u + (T − f(u))`, where `u` is the command, `T` the target and `f` the hidden
command-to-ink map. Linearise `f(u) = J·u + b_t`. The error after each patch is then:

```
e_{t+1} = (I − J)·e_t  +  (b_{t+1} − b_t)
          └ contraction ┘  └ state change caused by the attempt itself ┘
```

**When patching converges.** It converges within a square only if both of these hold:
- **(a) Contraction:** the spectral radius ρ(I − J) < 1.
- **(b) No state change between attempts:** the offset term `b` does not change from one attempt to
  the next.

It gets within the 2 mm tolerance in one correction when ρ(I − J)·|e₁| < 2 mm.

**Every level built so far is inside this fast-patching regime:**

| Perturbation | ρ(I − J) |
|---|---|
| Offset | 0 |
| Rotation 13° | 2·sin(6.5°) = 0.23 |
| Scale 0.73 | 0.27 |
| Shear (1.12, 0.90, 7°) | ≈ 0.2 |
| Camera bump | ≈ 0 |
| Backlash, drift | ≈ 0; the offset term `b` changes by less than the tolerance between attempts |

This is exactly the "miss, then fix" pattern seen in Opus. For patching to fail, a rule must break (a)
or (b), or make the error signal itself untrustworthy:

| Way to break patching | Mechanism | Examples in this doc |
|---|---|---|
| **B1: non-contracting Jacobian** | ρ(I − J) ≥ 1: mirror, axis swap, rotation > 60°, scale > 2 or < ~0.3, unit changes | Conventions (D1), mirror modes (A4) |
| **B2: the attempt changes the state** | `b_{t+1} ≠ b_t` because the miss itself moved hidden state: pen position, mode, carousel slot, clock | ARX (A1), FSM (A4), carousel (A5), clocks (E1), ringing (B5) |
| **B3: the error signal lies** | Patching converges to a wrong fixed point: W(f(u*)) = t gives f(u*) = W⁻¹(t) ≠ t | Camera/plotter attribution with blind targets (F1) |
| **B4: the context changes after learning** | A carried-forward model goes stale; carrying it forward is worse than patching until the change is detected | Recurring contexts (E3/E4) |
| **B5: a cheaper non-geometric route exists** | Patching "works" but costs 2–3 strokes a square; discovering a hidden control removes the error | Latent affordance (B5) |

**Design rule 0.** Every Tier-2+ perturbation must defeat patching by at least one of B1–B5, **as verified
by a code patching baseline**. That baseline is a smart local patcher: a secant (Broyden) update within the
square, carrying nothing across squares. It is the ceiling a model must beat, and the regret metric
(section 7) is normalised against it.

#### Other design rules (from the runs to date and this analysis)

1. **Natural play must trigger the rule.** At least 30–50% of natural closing strokes must be affected,
   otherwise it never costs (criterion 1). Closing strokes are axis-aligned and 16–40 mm long, so their
   features are narrow. Triggers that need long or diagonal strokes only fire on probes. Options: rotate the
   hand-drawn squares, or use the T2 dots task.
2. **No retry lotteries.** If retrying the unchanged command succeeds with probability ≥ 1/2, retry
   beats the rule. Examples: a mode toggled by the closing stroke itself, or a carousel of k−1 good pens.
3. **Errors from a wrong hypothesis must be at least 3× the tolerance (≥ 6 mm),** so that eyesight is
   never the bottleneck (criterion 8). The one exception is the early phase of drift.
4. **Every cell passes the existing oracle reachability check** (`levels.pick_seed`). Rules that
   reinterpret the command use `clamps_itself = True`, so the tool clamps after mapping.
5. **The prompt must not hint.** New action fields, such as `speed`, are documented neutrally from turn 1,
   before the change.
6. **Run controls on every tier:** no change, and nuisance-only (random no-ops). An intelligent agent
   should not invent laws from noise. Invented laws are measured as false alarms (section 7).

---

### 1. Candidate perturbations (28)

**Notation.** `u` = commanded vertices (page mm). `x` = executed vertices. The ink is `x` plus the
existing scatter (0.3 mm per stroke + 0.4 mm wobble). `T` = target corners.

**Scores.** Each criterion is scored 1–5:
- **C1** lawful and costly until understood
- **C2** not beatable by retrying or patching
- **C3** exploitable once inferred
- **C4** rewards hypotheses and active experiments
- **C5** has a complexity knob
- **C6** plausible
- **C7** has a computable ideal
- **C8** independent of perception

**Σ** is out of 40.

#### A. Stateful / tool dynamics

| ID | Perturbation (rule sketch) | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | **ARX command dynamics.** Executed vertices are low-pass filtered through the command history: `x_j = x_{j−1} + α(u_j − x_{j−1}) (+ momentum)` | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 5 | **39** | Stylus "streamline" smoothing; jerk-limited motion planner |
| A2 | **Incremental mode (G90→G91).** Each vertex is relative to the last pen position | 5 | 4 | 5 | 3 | 2 | 5 | 5 | 5 | 34 | G-code absolute/incremental modal switch; SVG `l` vs `L` |
| A3 | **Backlash / hysteresis** (existing L4) | 4 | 2 | 4 | 4 | 3 | 5 | 5 | 3 | 30 | Gear or belt play |
| A4 | **Latent modal state machine.** A hidden mode, set by features of earlier strokes, selects the transform | 5 | 5 | 5 | 5 | 5 | 4 | 4 | 5 | **38** | Modal G-code state left by the last command (G20 inches is a classic crash); API session state (`SET`, `USE`, `cd`) |
| A5 | **Tool carousel.** k pens in round robin, each with its own offset or transform | 4 | 5 | 5 | 5 | 4 | 5 | 5 | 4 | **37** | Tool-changer / IDEX nozzle offsets; round-robin load balancer with a stale replica |
| A6 | **Ringing after fast moves.** The start error decays with time since the last move, along the approach direction | 4 | 4 | 4 | 3 | 3 | 5 | 4 | 3 | 30 | Gantry resonance; servo settle time |
| A7 | **Execution queue lag.** Stroke n draws command n−1 | 5 | 5 | 4 | 2 | 2 | 4 | 5 | 5 | 32 | Buffered command queue; eventual consistency |
| A8 | **Co-adaptive firmware.** The plotter's own auto-trim undoes a fraction η of the agent's last correction | 4 | 5 | 3 | 3 | 4 | 3 | 3 | 4 | 29 | Two controllers fighting (autoscaler vs load balancer; integrator wind-up) |

#### B. Memoryless, conditioned on stroke features

| ID | Perturbation | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | **Pen-lift lag.** Ink shifted d mm along the direction of travel | 4 | 2 | 4 | 4 | 2 | 4 | 5 | 4 | 29 | Laser firing delay; pen servo lag |
| B2 | **Length nonlinearity.** End overshoot `a·L^p`, or saturating | 4 | 3 | 4 | 4 | 3 | 4 | 5 | 3 | 30 | Acceleration-limited planner |
| B3 | **Conditional transform (Bongard-style).** `if pred(stroke) then T1 else T2`; the predicate is over direction, length or position | 4 | 3 | 5 | 5 | 5 | 4 | 5 | 5 | 36 | Code path chosen by input magnitude or shape (fast path vs slow path) |
| B4 | **Curl field in the stroke.** Lateral push ∝ s², so ink bows; closing needs a pre-curved polyline command | 5 | 4 | 4 | 4 | 3 | 5 | 4 | 3 | 32 | Shadmehr force-field adaptation; crosswind on a drone; conveyor under the pen |
| B5 | **Latent affordance.** A documented "cosmetic" field (`settle_ms`, `speed`) is what removes the error | 4 | 4 | 5 | 5 | 3 | 5 | 4 | 5 | 35 | CNC dwell or feed rate vs accuracy; API `consistency=strong`; sleep before reading a sensor |

#### C. Position-dependent

| ID | Perturbation | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | **Piecewise region distortion.** A hidden partition with a transform per cell | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 4 | 30 | Tiled bed; sharded service with one shard per schema version |
| C2 | **Smooth nonlinear field** (radial `k1·r²` or bed mesh) | 4 | 3 | 4 | 3 | 4 | 4 | 5 | 3 | 30 | Lens distortion; bed-levelling mesh |
| C3 | **Large-Jacobian maps:** mirror, axis swap, rotation > 60°, scale > 2 | 5 | 5 | 5 | 2 | 3 | 4 | 5 | 5 | 34 | Reversed motor wiring; sign error in a control loop |
| C4 | **Hidden keep-out zone.** Segments are clipped at a geofence | 2 | 3 | 4 | 5 | 3 | 4 | 4 | 4 | 29 | Geofence; permission-scoped API returning partial results |

#### D. Semantics / schema

| ID | Perturbation | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | **Convention drift library.** The command is reinterpreted through a composition of real conventions (swap, y-up, inches, vector or polar second point, centre origin, …) | 5 | 4 | 5 | 4 | 5 | 5 | 5 | 5 | **38** | GeoJSON [lon, lat]; PDF y-up; inches vs mm; API v2 "second point is now a vector" |
| D2 | **Type-dependent semantics.** Integer-valued numbers are read as 0.1 mm; decimals as mm | 4 | 3 | 5 | 4 | 2 | 5 | 4 | 5 | 32 | JSON int/float coercion; timestamps in seconds vs milliseconds decided by magnitude |

#### E. Clocks and non-stationarity

| ID | Perturbation | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E1 | **Which-clock drift (+ hidden reset).** The drift is driven by one of several correlated counters (strokes, ink mm, travel mm, turns); a hidden homing action resets it | 4 | 4 | 4 | 5 | 4 | 5 | 4 | 4 | 34 | Thermal drift ∝ motor duty cycle; wear by cycles vs distance vs hours; rate limits by requests vs tokens |
| E2 | **Rate-limit degradation.** Strokes issued too soon are executed degraded; pacing with a wait fixes it | 3 | 4 | 4 | 4 | 3 | 5 | 4 | 4 | 31 | HTTP 429 or degraded-quality tiers; thermal throttling |
| E3 | **Recurring contexts.** The rule switches A→B→A→C…; tests stale-model detection and savings | 4 | 4 | 4 | 3 | 4 | 5 | 4 | 4 | 32 | Blue/green deploys; feature-flag flips; day/night calibration |
| E4 | **Cued contexts with distractors.** A tool-response field (e.g. `temp_c`) predicts the context; other fields are noise | 4 | 5 | 5 | 3 | 4 | 4 | 4 | 5 | 34 | A firmware or version header predicts behaviour; spurious dashboard metrics |

#### F. Observation × action

| ID | Perturbation | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | **Dual-channel attribution.** Camera, plotter or both change; blind text-coordinate targets make attribution count | 4 | 5 | 5 | 4 | 3 | 5 | 5 | 3 | 34 | Hand-eye calibration drift; "is it the sensor or the process?" in incidents |
| F2 | **Observation lag.** The photo is one stroke stale | 4 | 3 | 4 | 2 | 2 | 5 | 5 | 4 | 29 | Teleoperation video latency; stale dashboard |
| F3 | **Telemetry in a hidden frame, or a lying report.** The JSON "drawn" path is in machine coordinates, or echoes the command rather than the ink | 3 | 3 | 4 | 3 | 3 | 5 | 4 | 5 | 30 | ENU vs NED telemetry; API returns 200 but the side effect differs |
| F4 | **Contact stop.** A stroke is truncated where it first crosses existing ink | 3 | 4 | 4 | 3 | 2 | 4 | 4 | 4 | 28 | Cobot force-limit stop; lock contention |

#### G. Composition operator

| ID | Perturbation | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Σ | Real-world analogue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G1 | **Two independent causes** (for example camera + carousel, or ARX + convention); the agent must factorise | 5 | 5 | 4 | 4 | 5 | 4 | 4 | 3 | 34 | Two simultaneous faults in production |

**Scoring notes:**
- **Folded in:**
  - B3 (conditional) is the memoryless special case of A4 and is folded into it;
  - A2 (incremental mode) is a special case of A1, and D1 also contains it (the REL convention);
  - A6 (ringing) is the physics behind B5;
  - D2 is a member of the D1 library.
- **Dropped:**
  - A7 (queue lag) scores high on C1 and C2, but as noted it behaves like a nuisance: the agent
    cannot plan one stroke ahead across a square change without knowing the next square.
  - A8 is elegant, but its ideal is an adaptive-control game (hard to certify as optimal).
- **Ladder operators, not stand-alone picks:** C3 and G1.

---

### 2. The top 8 at a glance

**Selection.** The picks are chosen by score and by coverage: each needs a different cognitive move.

| # | Pick | Breaks patching by | Cognitive demand | Ideal strokes to competence (k1) |
|---|---|---|---|---|
| 1 | A1 ARX command dynamics | B2 | System identification of a dynamical model, and planning under command bounds | 1–2 |
| 2 | A4 Latent modal state machine | B1 + B2 | Tracking a hidden state and inducing its trigger (Bongard/Zendo) | 3–6 |
| 3 | A5 Tool carousel | B2 | Finding the period and telling a lawful sequence from "flakiness" | 2k−1 (mostly dots) |
| 4 | D1 Convention drift | B1 | Discrete semantic abduction and designing a discriminating experiment | 1–2 |
| 5 | E1 Which-clock drift + reset | B2 | Causal discovery by intervention (breaking the confound); affordance search | 3–5 |
| 6 | B5 Latent affordance | B5 (+B2) | Curiosity: screening "irrelevant" controls | about the number of parameters |
| 7 | F1 Dual-channel attribution | B3 | Causal attribution between observation and action; a retrace test | 1–2 |
| 8 | E3+E4 Recurring and cued contexts | B4 | Change detection, context memory (savings), learning from cues | 1 per switch (0 if cued) |

---

### 3. Top-8 specifications

#### Shared protocol for all picks

**Arms, references and budgets:**
- **Page and timing.** Pages are as in the objective pilot: 12–20 squares in far-apart order; the change
  comes after square 4.
- **Feedback arms.**
  - **image:** the current rectified view.
  - **numeric:** the tool response adds the landed ink endpoints to 0.1 mm (`tool_responses`, which
    already exists), and no image is sent after the change. The numeric arm removes perception entirely
    (criterion 8) and cuts input tokens by a large factor, since no images are sent.
- **Probes.**
  - A stroke may be labelled `"kind": "probe"`. Probes cost strokes and ink like any other stroke, but
    they are not counted as closing attempts.
  - First-try means the first attempt closes.
  - Probes must lie in empty paper, at least 4 mm from any ink or target.
- **References:** oracle, naive, **smart patcher** (secant within the square, no memory), **family-ideal**
  (knows the family, fits parameters), and **DSL-Bayes** (knows only the grammar in section 5).

#### 3.1 A1: ARX command dynamics ("the firmware now smooths your commands")

**Rule.**
- **Filter.** Commanded vertices form one sequence across the episode (both vertices of every stroke,
  in order). Executed vertices follow

  ```
  x_j = x_{j−1} + A·(u_j − x_{j−1}) + B·(x_{j−1} − x_{j−2})
  ```

  The steady-state gain is 1, so a repeated command converges to itself.
- **Ink.** Ink is the straight segment between a stroke's executed vertices, plus the existing scatter.
  Pen-up travel is not a vertex.
- **Clamping.** Executed vertices are clamped to the reachable region (`clamps_itself`), and the
  filter state stores the clamped values.

**Knob.**

| Level | Setting | Effect |
|---|---|---|
| k1 | `A = αI`, α ∈ [0.55, 0.70], B = 0 | EMA. With far-apart ordering, the first vertex of each square is pulled 30–60 mm toward the last ink end, and every stroke comes out α× short |
| k2 | `A = diag(αx, αy)` with \|αx − αy\| ≥ 0.15 | Anisotropic |
| k3 | B = βI, β ∈ [0.2, 0.4] | Momentum: underdamped overshoot; needs 3 vertices of history |
| k4 | k3 + parking between turns: the state decays toward HOME, `x₀ ← ρ·x_last + (1−ρ)·HOME` | ρ and α are only separable using start versus end vertices, which is an identifiability puzzle |
| k2′ (G91 variant) | `x_j = x_{j−1} + u_j` | An integrator; the easy form |

**Why patching fails (B2).**
- The start vertex is filtered from the previous stroke's end. On a retry that end is the far corner of
  the missed attempt.
- Retrying the unchanged command therefore stays off by about (1−α)·side ≈ 8–12 mm, and never converges.
- An offset patch computed on attempt 1 (whose state came from the previous square, 100+ mm away) is
  applied under a new state, so it overshoots.
- A patcher needs 3–4 strokes per square and nothing transfers.

**Optimal agent.**
- **Identify.** One post-change stroke gives 4 scalar equations,
  `α = (x_j − x_{j−1}) / (u_j − x_{j−1})` per axis. That is enough for k1–k2; k3 needs 2 strokes.
- **Invert (deadbeat):** `u₁ = x_prev + (T₁ − x_prev)/α`, then `u₂ = T₁ + (T₂ − T₁)/α`.
- **Plan.**
  - Start from the corner nearer the previous ink end; this minimises the command magnitude.
  - If the inverse command falls outside the region (small α, far previous end), first spend a cheap
    **set-up dot** near T₁ to walk the state closer. This is the one non-trivial probe decision.
- **Probing.** None is needed beyond the natural first miss.

**Reference implementation.**
- Recursive least squares per axis on the regressors (x_{j−1}, u_j − x_{j−1}, x_{j−1} − x_{j−2}, and
  an indicator for "turn boundary").
- Model order chosen by BIC over {k1, k2, k3, k4}.
- Command by a bound-constrained least-squares solve (`scipy.optimize.lsq_linear`) over this stroke's
  vertices, plus an optional set-up dot. The dot is used when predicted closure probability < 0.9.

**Expected frontier behaviour (prediction).**
- Errors are huge and structured: short strokes, pulled toward where the last one ended.
- A GPT-6 Astra-class model will probably verbalise "pulled toward the previous position" and
  compensate qualitatively. Competent around square 7–9 at k1.
- Opus-style patching loops at 3+ strokes per square.
- Both break at k3–k4: momentum overshoot reads as "inconsistent".

#### 3.2 A4: Latent modal state machine ("some earlier action flipped a mode")

**Rule.**
- A hidden mode `s ∈ {0..K−1}`; stroke n executes under transform `M_{s_n}`.
- After execution, `s_{n+1} = δ(s_n, φ(stroke_n))`.
- **Feature library** φ:
  - start half (left or right of a hidden x = m);
  - end half;
  - travel sign (±x, ±y);
  - orientation (H or V);
  - length above or below ℓ*;
  - parity of the executed-stroke index.
- **Transform library:**
  - mirror-x about a hidden line x = m;
  - mirror-y;
  - axis swap about the centre;
  - rot180;
  - offset of 12 mm.

**Base (k1):** K = 2, `M₀ = I`, `M₁ = mirror about x = m` (m ∈ [80, 136] mm). A stroke that **starts** left
of m arms the mirror for the *next* stroke; one that starts right of m disarms it.

**Knob.**

| Level | Setting |
|---|---|
| k1 | The base above |
| k2 | Feature and transform drawn from the libraries |
| k3 | K = 3 cyclic (the feature advances the mode), or a conjunctive trigger (vertical AND top half) |
| k4 | A Mealy machine with K ≤ 4 and a 2-bit input from two features: about 10⁵ hypotheses |
| Memoryless variant (B3) | The mode is set by the current stroke's own feature (e.g. strokes longer than 30 mm are mirrored). The agent can then *choose* stroke direction or order to avoid the transform |

**Why patching fails (B1 + B2).**
- Mirror has J-eigenvalue −1, so offset patching diverges (ρ(I−J) = 2).
- The agent's own miss sets the mode for its fix. For a left-half square, attempt 1 arms the mirror,
  so every retry is mirrored: retrying is stuck forever and patching diverges.
- **Why the user's "a vertical stroke toggles" example is weaker.** A closing stroke that toggles the
  mode makes identical retries alternate between modes, so retry hits within 2 strokes. That is a retry
  lottery (rule 2). The set/reset-by-start-half design avoids it.

**Optimal agent.**
- **The key insight.** The mode on the *first* attempt of a square depends on the *previous* stroke, not
  on this target. Only first attempts break the confound between "left-half target" and "left-half
  previous stroke".
- **Probing.** Hypothesis-splitting probes are 3 mm strokes in empty space. Starting just left or right
  of a suspected boundary, a binary search locates m to 2 mm in about 4 probes; natural data supply part
  of that.
- **Exploiting.** Predict `s_n`, send `M_{s_n}⁻¹(T)`. Alternatively, spend a cheap **mode-setting dot**
  (start right of m) when the inverse would be out of range.

**Reference implementation.**
- An enumerative Bayesian filter over (feature, threshold at 1 mm, δ table, transforms, initial state).
  Every hypothesis predicts each landing deterministically, with likelihood σ = 0.7 mm.
- **Action choice:** compare the expected cost of attempting now against each candidate probe; a probe
  is valued as expected information gain × the strokes it saves. Exact up to about 10⁵ hypotheses.
- Ideal strokes to competence at k1 ≈ 3–6.

**Expected frontier behaviour (prediction).**
- The model will see "sometimes my stroke appears mirrored across the page".
- It will call it intermittent or flaky and retry, or form the **wrong, target-based** hypothesis
  ("left-half squares are mirrored"). That hypothesis fits every retry, but fails first attempts after
  a right-half stroke.
- Both break at k1–k2. This is the cleanest test of "hypothesis about my own actions" against
  "hypothesis about the world".

#### 3.3 A5: Tool carousel ("the machine indexes to the next pen every stroke")

**Rule.**
- There are k pens. The pen for executed stroke n is `π((n − n₀ + φ) mod k)`.
- `n` counts every executed stroke, including probes and misses. Turns without a valid stroke do not
  count.
- Pen i adds offset `v_i` (5–10 mm, directions ≥ 60° apart, so no pen is near the identity).

**Knob.**

| Level | Setting |
|---|---|
| k1 | k = 2 |
| k2 | k = 3 |
| k3 | k = 4–5, each pen a small similarity (±3°, ±3%) |
| k4 | A non-rotational period (e.g. slot sequence 1,2,1,3), or the pen is chosen by the stroke's direction quadrant (composition with B3) |
| "Stale replica" variant (diagnostic only) | k−1 pens are the identity and one is off by 12 mm. It violates rule 2 (retry works most of the time), so score it by **how often the bad pen is used for a closing attempt**, not by strokes |

**Why patching fails (B2).**
- Consecutive attempts use different pens. The patch from attempt n lands with error `v_{i+1} − v_i`
  (up to 20 mm).
- This cycles forever, and naive retry never hits.
- Averaging the offsets, the "noise" model that Opus already reached for ("noisy distortion that varied
  per stroke"), misses on every pen.

**Optimal agent.**
- **Hypothesis.** After the first two misses have different offsets, hypothesise a period.
- **Probes.**
  - Cheap **1 mm dots** in empty paper measure consecutive pens: k dots give every offset, and a few
    more confirm the period.
  - Ink cost ≈ 0; stroke cost ≈ 2k.
- **Exploit.** Predict the pen, send `T − v_{p(n)}`.
- **Phase alignment.** Optionally spend dots to rotate the carousel to the best-measured pen before a
  closing stroke.

**Reference implementation.**
- For each k ∈ {1..6} and phase, assign past strokes to slots.
- Estimate each slot's mean residual and compute the Gaussian likelihood. The Bayes factor carries an
  Occam penalty.
- Probe with dots until P(k) > 0.95 and every slot has at least one observation; then exploit.

**Expected frontier behaviour (prediction).**
- Astra-class may catch alternation at k = 2.
- At k ≥ 3, both will call it noise, average it, and retry: this is the "flaky tool" heuristic the
  earlier nuisance runs rewarded. A likely break for both at k2.
- This separates **lawful sequence** from **flakiness** better than anything else here.

#### 3.4 D1: Convention drift ("the API's semantics changed; figure out which convention")

**Library (each item is a real, documented bug class):**

| Code | Reinterpretation of command u | Analogue |
|---|---|---|
| SWAP | (x, y) → (y, x) | GeoJSON [lon, lat] vs lat/lon |
| YUP | y → H − y | PDF / matplotlib vs image coordinates |
| XFLIP | x → W − x | Mirrored fixture; handedness |
| IN | × 25.4 | Inches vs mm (Mars Climate Orbiter) |
| CM | × 10 | Unit confusion |
| STEP | × 0.1 | Firmware steps-per-mm mismatch |
| CENTRE | + (W/2, H/2) | Centre-origin canvas |
| MACH | page = HOME + R·u | Machine vs work coordinates (G53/G54) |
| VEC2 | second vertex = first + u₂ | `line(x, y, dx, dy)` vs `line(x1, y1, x2, y2)` |
| POLAR2 | second vertex = first + u₂[0]·(cos u₂[1]°, sin u₂[1]°) | Polar vs Cartesian |
| REL | every vertex relative to the last executed vertex | SVG lowercase path commands |
| INTMM | integer-typed numbers are read as 0.1 mm | JSON int/float typing. Detectable before `float()`: `json.loads` returns an int for `120` and a float for `120.0` |

**Rule.** After the change, the tool executes `C(u) = c_d ∘ … ∘ c₁(u)`. Order matters, and the
conventions do not commute.

**Knob.**

| Level | Setting | Hypotheses |
|---|---|---|
| k1 | d = 1 | 12 |
| k2 | d = 2 | 132 |
| k3 | d = 3 | about 1,300 |
| k4 | d = 3 including one stateful (REL) or type-dependent (INTMM) element | — |

**Why patching fails (B1).**
- SWAP, YUP and XFLIP have ρ(I−J) = 2; IN gives 24.4 and CM gives 9: all diverge.
- STEP gives 0.9, which needs about 32 patches to shrink 60 mm to 2 mm, far beyond the 12-stroke cap.
- POLAR2 is nonlinear.
- Only CENTRE, MACH and VEC2 are patchable. They are allowed only inside compositions with a
  non-contracting element.

**Optimal agent.**
- **Abduction.** Given one landing, list the conventions that could produce it.
- **Design a discriminating stroke:**
  - asymmetric coordinates (x ≠ y, far from W/2 and H/2);
  - some integer and some decimal values;
  - a second vertex whose vector is unlike its position (to separate VEC2 and POLAR2).
- The natural first miss is already informative, so a second, designed stroke usually resolves
  everything. Ideal strokes to competence ≈ 1–2.
- **The trap tested here (Wason's 2-4-6):** a "round-number" probe such as (100, 100) cannot tell SWAP
  from the identity.

**Reference implementation.**
- Enumerate compositions and predict exactly.
- Eliminate hypotheses whose residual exceeds 3σ.
- If more than one survives, choose the probe that maximises the minimum pairwise distance between
  predicted landings, from an in-bounds candidate grid.
- Exploit with a closed-form `C⁻¹(T)`. For INTMM, simply send decimals.

**Expected frontier behaviour (prediction).**
- d = 1 with glaring landings (swap, y-flip) is probably solved by Astra-class models: it resembles
  rotation, and they recognise famous conventions.
- d ≥ 2 and INTMM break both. INTMM looks like erratic flakiness: some strokes collapse toward the
  origin.
- This is the most ARC-like pick: discrete abduction over a compositional library.

#### 3.5 E1: Which-clock drift, with a hidden reset ("what is the drift actually counting?")

**Rule.**
- Executed = `u + r·g(C)·û`, where g is linear at k1–k3 and saturating at k4.
- C is one hidden clock since the last reset:

  | Clock | What it counts |
  |---|---|
  | S | Executed strokes |
  | I | Pen-down ink mm (duty-cycle heating) |
  | P | Pen-up travel mm |
  | T | Turns, including `{"action": "wait"}` turns (a new, documented action) |
  | Q | Squares closed |

- Rates are set so that natural play reaches about 6 mm of drift after 3 squares (e.g. I: 0.02 mm per
  mm of ink; S: 0.6 mm per stroke).
- **Reset (k2+).** A stroke that touches the dashed boundary of the reachable region homes the machine
  and sets C to 0. This is like hitting a limit switch.

**Knob.**

| Level | Setting |
|---|---|
| k1 | Two candidate clocks (S vs I), no reset |
| k2 | Five clocks, and the edge-touch reset exists |
| k3 | Two clocks act at once along different directions (I along û₁, T along û₂) |
| k4 | Saturating drift, and the reset only partly restores (ρ) |

**Why patching fails (B2).**
- Drift grows between the miss and the fix.
- Under the I-clock, every wasted stroke **adds drift**, so the patcher's cost compounds. Wasted ink
  becomes self-punishing.
- Retrying never works.

**Optimal agent.**
- **Detect drift.** Recognise that the drift grows, then list candidate clocks.
- **Break the confound with deliberate interventions (clocks are correlated in natural play):**
  - a long 100 mm probe against a 1 mm dot separates I from S;
  - a `wait` turn isolates T;
  - a long pen-up hop isolates P.
- Two or three such probes identify the clock by model selection.
- **Exploit.** Compensate feed-forward.
- **Reset (k2).** If the reset is found, home whenever the predicted drift uncertainty exceeds about
  τ/2. The tradeoff between homing cost and miss risk is computable.

**Reference implementation.**
- Bayesian linear regression per clock (and per pair at k3), with a BIC posterior.
- Probe choice maximises the expected KL divergence between the rival clock models' predictions, per
  unit cost.
- The reset triggers are part of the grammar (touching the edge, the `wait` action, a long travel);
  each is tested once when the drift residuals show an unexplained drop, or once proactively.

**Expected frontier behaviour (prediction).**
- The L5 evidence: Opus noticed a growing offset and gave up ("my growing-drift model is unreliable").
- Prediction: models default to per-stroke drift (the most salient clock). Under the I-clock that
  mispredicts short against long strokes.
- They run no dissociating probes unprompted, and nobody finds edge homing. Both break at k1–k2.

#### 3.6 B5: Latent affordance ("the fix is a knob you were told about but thought was cosmetic")

**Schema (documented from turn 1, before the change).** Each stroke may carry:
- `speed` (10–200 mm/s, default 100);
- `settle_ms` (0–500, default 0);
- `pressure` (1–5, default 3);
- `smoothing` (on or off, default off).

The descriptions are neutral: "drawing speed", "pause after the pen lowers", "pen pressure", "path
smoothing". Before the change, none of them affects landing.

**After the change: ringing.**
- A stroke's start lands off by `A·(speed_prev/100)·exp(−settle_ms/τ)·û_approach`, where:
  - A = 8–12 mm;
  - τ = 80 ms;
  - û_approach is the direction of the pen-up travel into this stroke.
- The end overshoots by `c·max(0, speed − s*)` along the stroke.
- **Cost of slowness.** Each stroke's duration (length/speed + settle) costs 1 stroke-equivalent per
  10 s, so slowness is not free. The optimum is the smallest sufficient `settle_ms` and the largest safe
  speed.

**Knob.**

| Level | Setting |
|---|---|
| k1 | Only `settle_ms` matters (threshold-like), with 2 documented fields |
| k2 | One field of 4 matters; the others are distractors |
| k3 | An interaction: errors vanish only when both settle is high and speed is at most s* |
| k4 | A non-monotone window (e.g. pressure 2–3), which needs a designed sweep |

**Why patching fails (mostly B2).**
- The error direction is the approach direction. For attempt 1 that is the travel from the previous
  square; for attempt 2 it is the travel from the missed attempt's end.
- So the correction learned on attempt 1 is wrong in direction on attempt 2.
- Patchers pay 2–3 strokes a square. A geometric model of ringing is possible but costly. The
  affordance route costs about one screening probe per field, once.

**Optimal agent.**
- **Screen.** When a lawful but awkward error appears, vary each documented field to its extreme,
  one per probe (dots).
- Find the field that removes the error, then line-search its threshold against the time cost.

**Reference implementation.**
- One-factor-at-a-time screening, then a 1-D golden-section search on the time–error tradeoff.
- An alternative branch fits the ringing model by least squares. The cheaper path is chosen by expected
  cost.

**Expected frontier behaviour (prediction).**
- Models almost never touch "cosmetic" fields once a geometric story is available.
- This is a pure **curiosity / screening** test, with large regret at k1 for both models.
- The one risk is hinting: the field names must stay neutral, and the fields must exist from turn 1.

#### 3.7 F1: Dual-channel attribution ("did the camera move, the plotter, or both?")

**Rule.**
- At the change, the cause is drawn uniformly from {camera, plotter, both}.
- **Camera:** a stale rectification W (similarity: 5–12 mm shift, 2–6° rotation), rendered by the
  existing `render_view_warp`.
- **Plotter:** P from Tier 1 (offset or similarity). At k3, P is any Tier-2 rule.
- **Targets alternate between two channels:**
  - image targets (the open squares);
  - **blind targets:** "draw a straight segment from (x₁, y₁) to (x₂, y₂) page mm", graded in true
    page mm and shown nowhere.
- The closure message ("closed" / "not closed") is ground truth. Under a camera move it therefore
  *contradicts the image*, and that contradiction is itself evidence.

**Knob.**

| Level | Setting |
|---|---|
| k1 | 4 printed fiducial crosses, whose page coordinates are stated in text |
| k2 | No fiducials: only the logged old marks serve as evidence |
| k3 | A homography camera change, or the camera moves twice |
| k4 | "Both", with W and P chosen to produce similar displacements on new ink, so only the old marks discriminate |

**The correct inverses:**
- image target: `u = P⁻¹(W⁻¹(t_disp))`;
- blind target: `u = P⁻¹(t)`.

**Why patching fails (B3).**
- On a blind target under a camera move, a patcher pushes the displayed ink onto the stated
  coordinates. It converges to `u* = W⁻¹(t)`, which looks right in the image and is wrong on paper.
  The tool says "not closed", and the patcher has no error signal left to follow.
- A plotter-blaming model "corrects" blind targets that needed no correction.
- Only the right causal model is first-try on both channels.

**Optimal agent.**
- **Check the invariant first.** On the first post-change turn, ask: do the old marks (whose commands
  are logged) still appear at their logged coordinates?
  - If they have moved, it is the camera: fit W from 2 or more old marks.
  - Any residual on new ink after removing W is the plotter.
- **The retrace probe** is the cleanest intervention. Re-command an old stroke exactly. If the new ink
  lands on top of the old ink, wherever the camera shows it, the plotter is unchanged. If not, the
  displacement (mapped through W⁻¹) is P. One probe, and near-zero wasted ink when it overlaps.

**Reference implementation.** The existing L6 `LAdaptive` (re-anchor on pre-change marks, then fit the
plotter), plus the retrace probe and blind-target handling.

**Expected frontier behaviour (prediction).**
- Plotter blame is the prior: 12/12 and 12/14 so far.
- Expect near-zero first-try hits on blind targets under camera-only, for both models, and patch
  loops when the closure message contradicts the image.
- Nobody retraces unprompted.
- This is the known unsolved failure, now made costly. Even k1, with fiducials, is informative.

#### 3.8 E3 + E4: Recurring and cued contexts ("it changed again, or changed back")

**Rule.**
- K contexts, each a rule R_i: Tier-1 maps at k1–k2; Tier-2 rules at k3–k4.
- A semi-Markov switching process: the dwell time is uniform over a range of squares, and
  P(return to a previously seen context) = 0.6.
- **Every tool response carries status fields:** `{"fw": "2.4.1", "temp_c": 31.4, "job": 1182, "queue": 0}`.
  - At k2+, `temp_c` bands predict the context with reliability ρ.
  - The other fields drift randomly (distractors).

**Knob.**

| Level | K | Dwell (squares) | Cue |
|---|---|---|---|
| k1 | 2 | 4–6 | None |
| k2 | 3 | 3–5 | ρ = 0.95 |
| k3 | 3–4, with Tier-2 rules | 2–4 | Switches may happen mid-square |
| k4 | 4 | 2–4 | ρ = 0.8; the cue-to-context mapping is itself learned |

**Why patching fails (B4).**
- Patching pays about one extra stroke per square forever.
- A single carried-forward model is *worse* than patching after a switch: it keeps compensating for the
  old context, which is perseveration, as in the Wisconsin Card Sorting Test.

**Optimal agent.**
- **Context library.** Keep one. After a surprising miss, score each known context against that one
  observation (a single stroke usually identifies it), alongside a "new context" option (a CRP prior).
- **Cues.** Learn the cue-to-context mapping and pre-select the context before the first attempt: zero
  misses on a cued switch.
- **Discriminating dot.** Place one where the known contexts' predictions differ most, when it is
  unclear which one is active.

**Reference implementation.**
- COIN-style Bayesian nonparametric context inference (sticky CRP-HMM, particle filter), with a
  logistic cue model.
- Exact for small K.

**Metrics:**
- **Detection latency:** strokes from the switch to changed behaviour.
- **False alarms,** measured in no-switch control episodes.
- **Savings:** strokes to competence on a revisit ÷ on the first visit.
- **Cue use.**

**Expected frontier behaviour (prediction).**
- Models overwrite their notes ("new offset now…"), relearn from scratch (no savings), and take 1–2
  strokes to detect a switch, blaming noise at first.
- They ignore the status fields unless told. Both break at k2.

---

### 4. What already exists in the code (implementation fit, for later; nothing was changed)

| Needed | Existing hook | New work |
|---|---|---|
| State-dependent execution (A1, A4, A5, E1, B5) | `Scenario.execute(cmd, seed, stroke_no, pen)` returns (ink, resp, pen); `needs_pen` for the oracle | Scenario classes plus their state |
| Commands reinterpreted before clamping (D1) | `clamps_itself` | Keep raw JSON number types for INTMM (parse before `float()` in `first_stroke`) |
| Cue fields and the numeric-feedback arm (E4, all picks) | `tool_responses`, `tool_response()` | Status fields; landed ends in the response |
| Stale camera (F1) | `render_view_warp`; the L6 reference | Blind text targets; fiducials; retrace analysis |
| Probes, waits, extra fields | — | `kind: probe`, `action: wait`, the `speed` and `settle_ms` fields; probes kept out of the 12-stroke square cap (count them separately) |
| Reachability | `levels.pick_seed` | Run per cell |

---

### 5. A generative grammar, so the knob is continuous (criterion 5)

All eight picks are nodes of one small DSL. The hidden rule of an episode is a sampled program. The
**difficulty knob is description length L**: the number of nodes plus discretised parameters.

```
Rule    := Map | Compose(Rule, Rule) | Cond(Pred, Rule, Rule) | Mode(FSM{Rule_1..K}, Trigger)
         | Cycle(k, Rule_1..k) | Dyn(ARX order, coeffs) ∘ Rule | Drift(Clock, rate, dir, Reset?)
         | Context(SwitchProc, cue?, Rule_1..K) | Afford(field, threshold) ∘ Rule
         | Camera(W) ⊗ Rule
Map     := Offset | Similarity | Affine | Mirror | Swap | Convention_i | Radial(k) | Piecewise(partition, Map_i)
Pred    := Feature ≷ θ | Pred ∧ Pred
Feature := start-x | start-y | end-x | travel-sign | orientation | length | stroke-index mod m | crosses-ink
Clock   := strokes | ink_mm | travel_mm | turns | squares
```

**How the grammar is used:**
- **Sampling.** Draw a program at length L. Reject it if the oracle cannot reach every target, or if
  natural play triggers it on under 30% of closing strokes (rule 1). The result is a cell.
- **DSL-Bayes reference.**
  - Up to L ≈ 5–6: exhaustive enumeration with a length prior (≤ 10⁶ programs, cheap in numpy).
  - Beyond that: sequential Monte Carlo over programs.
  - Actions: act if the posterior predictive closure probability exceeds 0.9, else probe by expected
    information gain per unit cost. This is near-optimal, and it is computable (criterion 7).
- **Contamination defence (as in ARC).** Publish the grammar and a public set. Hold out private
  primitives (for example a convention or a clock not in the public library) and private seeds. Add
  primitives yearly.

---

### 6. Difficulty ladder (tiers 1–5)

Every tier also runs the two controls: no change, and nuisance-only (random no-ops). They measure false
alarms: the agent should not invent a law.

| Tier | Contents | What it tests | Expected status (2026-09) |
|---|---|---|---|
| **1 Calibration** | Global stationary maps: offset, rotation ≤ 30°, scale, shear (the current L1–L3). Plus **patch-breakers**: mirror, swap, rotation 120°, IN units (C3) | Anchors the scale. The patch-breakers prove a "patch only" agent fails | Contracting maps: solved. Patch-breakers: Astra likely solves, Opus partly |
| **2 One hidden variable** | k1 of every top-8 pick: ARX EMA; FSM start-half mirror; carousel k = 2; conventions d = 1; clocks S vs I; affordance with 1 field; attribution with fiducials; contexts K = 2 uncued | Noticing a lawful rule and carrying it forward | Astra passes some; Opus fails most |
| **3 Designed experiments** | k2–k3: FSM with library triggers or conjunctions; carousel k = 3–4; conventions d = 2 + INTMM; clocks with a reset; affordance with distractors or interactions; attribution without fiducials, and "both"; ARX with momentum; cued contexts | Choosing *which* experiment to run: breaking confounds, screening | Both break (predicted) |
| **4 Composition + non-stationarity** | Two families composed (G1): camera + carousel; ARX + conventions; FSM whose modes are conventions; drift + region partition. The composed rule itself recurs (contexts over Tier-3 rules). Scarce ink (τ = 1 mm) and a one-shot blind exam | Factorising causes; detecting a stale model; savings | Far from solved |
| **5 Open grammar** | Programs sampled at L = 6, 8, 10, …; private primitives; look budget (k strokes per photo, from the T2 design); ink budget | Open-ended induction under resource limits | Unbounded by construction |

**Why the ladder stays unsaturated.** Tiers 1–4 are fixed and comparable across years. Tier 5 grows with
L, and it adds new private primitives, as ARC-AGI does with its private sets. A model's **breaking tier /
L** (section 7) is a scalar that keeps moving.

---

### 7. How to report "intelligence" behaviourally

#### Per episode (post-change segment)

1. **Strokes to competence (STC).** The number of post-change strokes (probes included) until the
   agent's next 3 closing attempts all hit first try. Report `STC_agent / STC_ideal`, where the ideal is
   DSL-Bayes (and the family-ideal as well).
2. **Regret against the right baselines.**
   - Formula: `(C_agent − C_ideal) / (C_patcher − C_ideal)`.
   - C = strokes + λ·wasted ink (λ = 1 stroke per 20 mm, fixed across the benchmark).
   - Values: 0 = ideal; 1 = no better than a smart local patcher; > 1 = worse than patching.
   - Using the patcher, not the naive agent, as the ceiling is what stops "miss then fix" from looking
     near-optimal.
3. **Split exploration from exploitation.** Replay the agent's own (command, ink) history into the
   DSL-Bayes observer. Let **n\*_data** be the first stroke after which that observer, holding only the
   agent's data, would be competent (predicted closure > 0.9 on the upcoming targets).
   - **Exploration efficiency** = `n*_data(ideal) / n*_data(agent)`: were the agent's strokes
     informative?
   - **Exploitation lag** = `STC_agent − n*_data(agent)`: did it use what it had?
   - This catches the Opus pathology directly. Opus wrote a correct map, so its data sufficed early,
     but its exploitation lag was large.
4. **Probe efficiency.**
   - The information of each labelled probe: the drop in posterior entropy for the DSL-Bayes observer
     (BoxingGym-style EIG).
   - Report bits per probe and bits per mm of probe ink, against the ideal's best probe.
   - Also the **probe rate**: the share of strokes that are designed experiments rather than attempts.
5. **One-shot exam** (last 3–5 turns).
   - 5 blind text targets, one attempt each, no feedback between them.
   - Plus 3 **prediction questions**: "where would this command land?", answered in numbers with no ink,
     scored in mm.
   - This is a direct behavioural read-out of the world model, in the WorldTest style. It separates
     "knows" from "does".
6. **Pick-specific metrics:**
   - **F1:** attribution accuracy (the regex in `levels.attribution`, plus a structured field the agent
     fills in: `cause ∈ {camera, plotter, both, unsure}`).
   - **E3/E4:** detection latency, false alarms, savings ratio, cue use.
   - **A5:** bad-pen use on closing attempts.
   - **B5:** whether and when the affordance was found.
7. **Cost:** tokens and dollars to competence, with a Pareto plot of cost against regret.

#### Across the benchmark

- **Ability scale.** Fit an item-response (IRT, 2PL) model across (pick × knob × seed) cells, with
  "regret < 0.3" as success. Report each model's ability θ with a confidence interval. Also report
  its **breaking point**: the tier or L at which P(success) = 0.5. Each cell's difficulty is calibrated
  from the pool of models and code references.
- **Learning-curve plot per pick:** P(first-try) against post-change square index, for the agent,
  DSL-Bayes, the family-ideal, the smart patcher and the naive agent. This is the headline figure.
- **Two feedback arms:** image and numeric. The gap between them is the **perception tax**. The numeric
  arm is the clean intelligence score, and it is much cheaper (no images).
- **Disclosure arms** as planned: silent, and informed + objective. The gap measures "doesn't bother"
  against "can't".
- **Tagline metrics for the post:**
  - "Strokes-to-competence: Astra 2.1× ideal, Opus 5.4× ideal on Tier 2."
  - "Exploitation lag: Opus knew the rule 9 strokes before it used it."
  - "Opus wasted X mm of ink; the ideal wasted Y."

#### Pilot suggestion (cost-aware)

- Tier-2 cells: the 8 picks × {Opus, Astra} × 1 seed, in the **numeric arm** first. Much cheaper per
  turn, since no images are sent: expect about $15–25 in total.
- Then the image arm on the 3 cells with the largest regret.
- Build the code references (patcher, family-ideal) and dry-run every cell before spending anything.

---

### 8. Positioning among related benchmarks

**Related work:**
- **ARC-AGI-3** ([arcprize.org](https://arcprize.org/arc-agi/3)): interactive turn-based games with no
  instructions; the agent must explore, model the mechanics and win efficiently. Freehand shares the
  "act efficiently, hidden mechanics" core. It differs in a continuous action space, a real-tool
  framing, and a *calibrated* continuous score against a computable Bayes-optimal reference.
- **WorldTest / AutumnBench** ([arXiv 2510.19788](https://arxiv.org/abs/2510.19788)): behaviour-based
  world-model evaluation, including change detection; it found humans ahead of the frontier models it
  evaluated. Freehand's exam and prediction questions borrow its "score behaviour, not representation"
  stance.
- **BoxingGym** ([arXiv 2501.01540](https://arxiv.org/abs/2501.01540)): experimental design scored by
  expected information gain; it found that LLMs struggle. Freehand's probe-efficiency metric is the
  embodied analogue.
- **NewtonBench** ([arXiv 2510.07172](https://arxiv.org/abs/2510.07172)): counterfactual law shifts,
  discovered interactively. Its finding that a code interpreter can cause *premature exploitation* is a
  prediction worth testing here. It suggests a "code tool" arm.
- **Motor-adaptation science:**
  - force-field adaptation (Shadmehr and Mussa-Ivaldi, 1994);
  - structural learning (Braun et al., 2009, [Curr. Biol.](https://www.cell.com/current-biology/fulltext/S0960-9822(09)00608-3));
  - contextual inference (the COIN model; Heald, Lengyel and Wolpert, 2021, [Nature](https://pubmed.ncbi.nlm.nih.gov/34819674/)).

  The "family-ideal vs DSL-Bayes" split is exactly structural learning; E3/E4 test COIN-style
  contextual inference.
- **Classic cognitive tests:**
  - Wisconsin Card Sorting (perseveration after a rule change): E3.
  - Wason 2-4-6 (positive-test bias): the D1 trap probe.
  - Zendo and Eleusis (rule induction by designed examples): A4 and B3.

**Freehand's niche:** an actuator whose hidden, lawful model is set by the benchmark, graded purely by
behaviour (strokes, ink, cost). References are computable at every difficulty. There is an explicit
**local-patching baseline**, which no benchmark above has, and it is the specific shortcut that frontier
agents take.

### User idea (2026-09-27): coloured-pen carousel with shapes
- **Setup:** the page has shapes to complete in different colours. Each coloured pen has its own hidden distortion (offset, skew, rotation or scale), and the agent must use the matching pen for each shape.
- **Measure:** strokes AND time/turns until the agent can **name the rule** (e.g. "red pen: +3 mm x; blue pen: 8° rotation"), checked by a probe question, plus first-try accuracy afterwards.
- **Knobs:** number of pens; distortion type per pen; whether distortions are independent or share structure (e.g. all rotations of different angles); shapes beyond squares.
- **Why it's good:** it's a lawful mapping from context (colour) to distortion, so a single global patch fails. It rewards separating evidence by context and naming the rule. And it looks great on video with the real rig and coloured pens.
