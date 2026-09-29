# Perturbations

The hidden rules the tool follows after the change: the implemented registry (`src/freehand/perturbations/`). The
28-rule design document these rules came from is [design/perturbation_ideas.md](design/perturbation_ideas.md);
how to add a rule is also in [extending.md](extending.md).

## Implemented rules

| Type | Class | Params (typed, validated) | Tier | Ideal-estimator reference | Historical names |
|---|---|---|---|---|---|
| `identity` | `Perturbation` | none | control | `adaptive` = `LAdaptive("?")` (stays put) | publication `identity`; level `?` |
| `none` | `PlotterMapChange` | none | control | B `adaptive` (offset → similarity) | pilot `none` |
| `offset` | `OffsetChange` | `mm` | calibration | B `adaptive` | `offset5`, `offset10` |
| `rotation` | `RotationChange` | `degrees` | calibration | B `adaptive` | `rot3`, `rot6`, `rot13` (hard pilots) |
| `scale` | `ScaleChange` | `factor` | calibration | B `adaptive` | `scale95`, `scale73` |
| `L2_rotation` | `L2Rotation` | `degrees` | calibration | `LAdaptive("L2rot")` | `L2rot_k1`; objective pilots' `rot13` |
| `L3_affine` | `L3Affine` | `sx`, `sy`, `shear_deg` | calibration | `LAdaptive("L3")` (similarity, affine once marks are spread in 2-D) | `L3_k1..3`, `L3shear` |
| `L4_backlash` | `L4Backlash` | `play_mm` | calibration | `LAdaptive("L4")` (draws in one travel direction) | `L4_k1..3` |
| `L5_drift` | `L5Drift` | `mm_per_stroke`, `skip_prob`, `skip_mm` | calibration | `LAdaptive("L5")` (linear trend, restarts after a skip) | `L5_k1..3` |
| `L6_attribution` | `L6Attribution` | `camera_shift_mm`, `camera_rot_deg`, `plotter_offset_mm`, `variant` (cam/plot/both) | calibration | `LAdaptive("L6")` (re-anchors on its pre-change marks) | `L6cam/plot/both_k1..3`, `L6cam` |
| `L7_scarce` | `L7Scarce` | `tol_mm`, `degrees` | calibration | `LAdaptive("L7")` | `L7_k1..3` |
| `command_memory` | `CommandDynamics` | `gains` (x, y in (0, 1]) | discriminating | `family_estimator` | `X_ARX`, `arx` |
| `latent_mirror` | `LatentMirror` | `threshold_mm` (null: seeded, 85–130 mm) | discriminating | `family_estimator` | `X_MODE`, `mode` |
| `smooth_warp` | `CrossAxisWarp` | `amplitude_mm` | discriminating | `family_estimator` | `X_WARP`, `warp` |
| `camera_move` | `CameraMove` | `mode` (transfer / fresh / static) | camera | `CamAdaptive` (homography from its own marks) | `cam_transfer`, `cam_fresh`, `cam_static` |

Randomness per rule, each from its own stream:

- the offset direction and rotation sign (`plotter.map`, the historical `[seed, 99]` draws, in their order; L7
  takes the first draw);
- the L5 direction and skips;
- the L6 camera-bump geometry;
- the mirror threshold and warp phase;
- the camera poses.

**Why both `rotation` and `L2_rotation`.** Their physics is identical for 13° (L2 uses the historical
`make_map("rot13")`). The hard pilots paired `rotation` with the offset-then-similarity estimator; the ladder and
objective pilots paired `L2_rotation` with the level estimator. Keeping both types keeps each historical reference
curve reproducible.

**Feasibility.** A rule is only usable on a page where the oracle can reach every target without clamping.
Command memory's inverse overshoots when consecutive targets are far apart. So it appears in `discriminating-v1`
(central 12-target page), not in `core-v1` (far-apart full page). `freehand suite verify --oracle` checks every
seed.

## Adding a rule

1. Subclass `Perturbation` in `perturbations/` with a `type_name`, a frozen `Params` dataclass (validate in
   `__post_init__`), and:
   - `expected(pts, n)`: the noise-free landing of a dense commanded path for stroke `n`;
   - `oracle_cmd(target, n)`: the command whose ideal landing ends are the targets (must not change state);
   - `land(cmd, seed, n)` only if the rule has state (update it there, once per executed stroke);
   - `start(n0)` if state resets when the rule switches on;
   - `describe()` extras for anything needed to rebuild it.
2. Draw any random parameter from a new named stream in `seeding.STREAMS` (no explicit tag; the tag is derived
   from the name).
3. Register the class in `perturbations/__init__.py` (`_TYPES`, `TIERS`). Pick a reference estimator: set
   `reference_level` for `LAdaptive`, or add it to `FAMILY_OF_TYPE` for the family estimator.
4. Add unit tests (oracle inverse, no state mutation on query, determinism).
5. Use it in a **new** suite version (`<suite>-v2.yaml`), then `freehand suite scan` + `freehand suite freeze`.
   Never edit a frozen suite that has results.
