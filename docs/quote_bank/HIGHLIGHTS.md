# Freehand quote bank: highlights

Curated quotes from the model episodes, with the run and condition each comes from. Source rows:
`quotes_notes_memory.csv.gz` (notes, memory) or the full bank (reasoning summaries); run names are the historical
folders. Every quote below was checked verbatim against the episode logs on 2026-09-29. The 2026-09-27 section is the
first curation (also kept as written in [../provenance/quote_bank_2026-09-27.md](../provenance/quote_bank_2026-09-27.md)),
with its one unsupported claim corrected; the 2026-09-28 section covers the informed runs. Claim boundaries:
[../findings.md](../findings.md).

## Self-monitoring, unprompted
- **Opus 5.5, turn 1 (told the plotter was accurate to 0.5 mm):** "If the stroke is offset, correct next turn." (pilot2, offset10)
- **Opus 5.5:** "Sq1-4 each closed with one stroke, so coordinates read from the photo are accurate." (pilot2, offset10)

## Diagnosing a silent tool change
- **Opus 5.5:** "commanded (154.8,42.8)-(191.8,42.0) but ink landed at about (146.3,37.5)-(182.8,36.8), an offset of about (-8.6,-5.3)… If this lands right, the offset is persistent; keep compensating." (pilot2, offset10)
- **GPT-6 Astra:** names the offset "8.75 mm left and 5.25 mm up" on turn 2. (astra_pilot, offset10)

## Reverse-engineering the broken tool (the headline)
- **Opus 5.5, scale 0.73:** "Refit: actual x = 0.70*cmd + 30.7, actual y = 0.727*cmd + 37.7 … so cmd = (actual-30.7)/0.70." (hard_pilot, scale73)
- **Opus 5.5, rotation 13°:** "landed x' = 1.03x - 0.23y + 32.3". sin 13° ≈ 0.225. (hard_pilot, rot13)
- **Opus 5.5:** "The distortion looks global, not local." (hard_pilot, rot13)
- **GPT-6 Astra, scale:** "actual = 0.75*command + (28.5,35.0), not just translation." (hard_pilot_reasoning)
- **GPT-6 Astra, shear:** "Reliable mapping: actual X≈1.121*x+0.1412*y−33.06 …" (objective_pilot, shear)
- **Opus 5.5, 1 mm tolerance:** "rotation about 12.4°" (true 13°). (ladder, L7)

## Camera moved: re-anchoring on its own marks (Freehand A)
- **Opus 5.5, first turn after the camera moved:** "The camera view changed at turn 24 (rotated about -5 deg…). Refs in new view: page (85.5,91.9) is at px (343,228), (138.2,83.5) at px (655,148)…" (pilot2, cam_transfer)
- **Opus 5.5:** "The camera view has changed, so I recalibrated from my closing strokes on squares 1, 3 and 4." (pilot2, cam_transfer)
- **Opus 5.5, turn 1 on an uncalibrated view:** "The page-to-pixel mapping is unknown, so this first stroke is a 20 mm horizontal probe near page center to calibrate." (pilot2, cam_transfer)

## Knowing ≠ using, and "hacking" the task
- **Opus 5.5, rotation:** writes "landed = R(+13.8deg)*cmd + t", then still hits only 2/9 later squares first try. (objective_pilot, rot13 silent)
- **Opus 5.5, shear:** "on each square check where the first stroke lands and correct by the observed per-endpoint offset". (objective_pilot, shear)
- **Opus 5.5, told to minimise strokes:** "Approach: try the plain target first; if the stroke lands off, invert the measured offset", then "noisy distortion that varied per stroke". (objective_pilot, rot13 objective)

## Describing a camera move as pen offsets (attribution)
- Where only the camera moved, the notes describe pen offsets. No note or memory in these episodes names the camera
  (a keyword screen; whether the models *blame the plotter* is untested, [../findings.md](../findings.md) section 6).
  **Opus:** "landed … roughly (-2,-2) off"; **Astra:** "Two attempts landed visibly above/left". (ladder L6,
  objective_pilot L6cam)
- **Opus 5.5, drift:** notices "offset … seems to grow per stroke", then "my growing-drift model is unreliable". (ladder, L5)

## Failure modes of other models
- **GPT-6 Sol treats everything as an offset:** "Two commands at x59.5 appeared near x72.5; trying x46.5 to compensate." (hard_pilot, scale73)
- **Gemini Flash has the right idea but noisy execution:** fits "affine transformation [x_act, y_act] = [1.05*x_cmd + 0.22*y_cmd …]" and still fails. (hard_pilot, rot13)
- **Sonnet 5 forms no model:** "Squares 5,6 abandoned after 12 failed attempts each (mystery non-registration issue)". (hard_pilot)
- **Sonnet 5 is overconfident:** "SOLID CALIBRATION … Verified against 3 known stroke pairs - consistent to <1px." The square was then abandoned. (sonnet_pilot, cam_transfer)
- **Sonnet 5 reflects on its own process:** "CRITICAL LESSON for squares 3-8: Stop recalibrating repeatedly each turn - it wastes strokes without improving accuracy." (sonnet_pilot)

## Told a rule exists (informed + objective), 2026-09-28

### Carrying a fitted map forward
- **Opus 5.5, rotation (memory, turn 7):** "rotate the target CCW 13.5° about the centre: q=c+Rinv(t-c)". (informed_pilot, rot13)
- **Opus 5.5, shear (memory, turn 21):** "x'=1.17x+0.134y-37.6", a near-correct global affine, then local patches on top. (informed_pilot, L3shear)
- **GPT-6 Sol, rotation (final memory):** "Working command-to-ink mapping: ink x≈0.974x−0.225y+34; ink y≈0.225x+0.974y−21." cos/sin 13° = 0.974/0.225. (informed_models, rot13)
- **Gemini 3.8 Flash, shear (final memory):** "Calibrated affine model (cmd_x = 0.8929*tgt_x - 0.1336*tgt_y + 30.71, cmd_y = 1.1173*tgt_y - 16.42) maps tip 1 to commanded page mm (87.77, 90.09)". (informed_models, L3shear)

### Patching, denying, or no model
- **GPT-6 Sol, shear:** "The latest command (81.2,161)→(81.3,174) appears to land roughly (80,158)→(83,170), drifting right as it descends. This command aims to land near both original ends by shifting its lower endpoint left." (informed_models, L3shear)
- **GPT-5.5, rotation (final memory):** "Previous apparent perturbations were likely mostly misread/clutter; recent strokes look near commanded positions." (informed_models, rot13)
- **Kimi K3, shear (final memory):** "Strokes land at commanded coords (no perturbation)." (informed_models, L3shear)
- **Claude Sonnet 5, shear (final memory):** "severe unpredictable ink placement perturbation affected most squares throughout the task ... (rotation/shift/scale models never consistently worked)". (informed_models, L3shear)
- **Claude Sonnet 5, rotation (memory, turn 39):** "FIT: actual = R(13.13deg)*cmd + T" — then keeps aiming at raw crop coordinates. (informed_models, rot13)

### The camera moved; the notes blame the tool
- **Gemini 3.8 Flash, camera-only (final memory):** "Perturbation on sq #20 definitively proven: constant tool offset dx = -50 px (-4.17 mm), dy = -44 px (-3.67 mm)." (informed_models, L6cam)
- **Kimi K3, camera-only (final memory):** "Mapping is identity; every prior miss is explained by the tilt, not offsets." (informed_models, L6cam)
- **GPT-5.5, camera-only (reasoning, turn 57):** "maybe perturbation isn’t about global translation but rather a camera overlay or something reported" — never acted on. (informed_models, L6cam)
- **Kimi K3, camera-only (reasoning, turn 5, before the change took effect):** "Maybe the perturbation is a homography due to camera? But prompt says straightened so pixels map to mm; tool perturbed." (informed_models, L6cam)

### Probe marks
- **After the change, on the gridded view, one deliberate probe was found. Claude Sonnet 5, shear (note, turn 11):** "Diagnostic stroke: drawing an isolated vertical line at x=58mm (offset from the messy existing ink at x=50mm) to clearly observe how the plotter renders a simple vertical command". (informed_models, L3shear)
- **Calibration probes on an uncalibrated camera view (before any change):** Opus 5.5, "this first stroke is a 20 mm horizontal probe near page center to calibrate" (pilot2, cam_transfer); GPT-6 Astra, "Initial probe commanded (108,110) to (108,130)" (astra_pilot, cam_fresh); Gemini 3.8 Flash, "Initial probe stroke connecting estimated page coordinates for square #1's open right side" (flash_pilot, cam_fresh).
