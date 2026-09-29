# Freehand quote bank: highlights

The full, searchable bank is in `all_quotes.csv`: 3,273 notes, memory entries and reasoning summaries from 91 model episodes, each with run, episode, turn and square. These are the curated highlights for video overlays and the write-up. Each is quoted from the logs; check the source row before publishing.

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

## Blaming the wrong cause (attribution)
- (*Correction, 2026-09-29:* the keyword screen's label; see [../findings.md](../findings.md), section 6.) In 12/12 runs where only the camera moved, the models blamed the plotter. **Opus:** "landed … roughly (-2,-2) off"; **Astra:** "Two attempts landed visibly above/left". (ladder L6, objective_pilot L6cam)
- **Opus 5.5, drift:** notices "offset … seems to grow per stroke", then "my growing-drift model is unreliable". (ladder, L5)

## Failure modes of other models
- **GPT-6 Sol treats everything as an offset:** "Two commands at x59.5 appeared near x72.5; trying x46.5 to compensate." (hard_pilot, scale73)
- **Gemini Flash has the right idea but noisy execution:** fits "affine transformation [x_act, y_act] = [1.05*x_cmd + 0.22*y_cmd …]" and still fails. (hard_pilot, rot13)
- **Sonnet 5 forms no model:** "Squares 5,6 abandoned after 12 failed attempts each (mystery non-registration issue)". (hard_pilot)
- **Sonnet 5 is overconfident:** "SOLID CALIBRATION … Verified against 3 known stroke pairs - consistent to <1px." The square was then abandoned. (sonnet_pilot, cam_transfer)
- **Sonnet 5 reflects on its own process:** "CRITICAL LESSON for squares 3-8: Stop recalibrating repeatedly each turn - it wastes strokes without improving accuracy." (sonnet_pilot)

## Keeping the bank current
Re-run the extraction after new runs. The script logic is in the session notes; fold it into `reports/` tooling during the end-of-project cleanup.
