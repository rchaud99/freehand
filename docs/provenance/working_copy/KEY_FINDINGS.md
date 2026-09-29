# Freehand: key surprising findings so far (2026-09-27)

These are leads from one episode per cell, and need seed replication before public claims. Evidence and quotes: `reports/quote_bank/HIGHLIGHTS.md` and `all_quotes.csv`. Numbers: `BENCHMARK_LADDER.md`.

1. **Frontier models reverse-engineer a silently broken tool.**
   - Opus 5.5 and GPT-6 Astra, never told anything could change, notice their strokes landing wrong and write explicit mathematical models of the fault.
   - Opus on a 13° rotation: "landed x' = 1.03x − 0.23y + 32.3" (sin 13° ≈ 0.225). Opus on a 0.73 scale: fitted 0.70–0.73. Astra: "actual = 0.75·command + (28.5, 35.0)".
   - With memory they recover about as fast as an ideal statistical estimator on simple changes.
2. **They "hack" the task by patching each square locally.**
   - After a change they usually miss first on every new square, see the gap next to the target, and correct, instead of carrying a global model forward.
   - First-try hits on later squares across the ladder: Opus about 8/42, Astra about 12/39, the ideal estimator nearly all.
   - Squares still close, so success-rate and ink metrics made the benchmark look saturated. The primary metric is now the first-try learning curve after the evidence.
3. **Knowing ≠ using: Opus writes the correct model and doesn't apply it.**
   - Opus wrote "landed = R(+13.8°)·cmd + t" (correct) and still hit only 2/9 later squares first try; shear 0/15.
   - Astra carries its model forward: rotation 14/15, camera move 13/14.
   - Telling models to "minimise strokes, VERY important" didn't fix it. Opus explicitly adopted patching ("try the plain target first; if the stroke lands off, invert the measured offset"). The informed + objective arm (told there's a pattern to deduce) is running now.
4. **Every model blames the plotter when the camera moved.**
   - Where only the camera moved, the models attributed the change to the plotter or pen in 12/12 runs.
     (*Correction, 2026-09-29:* the keyword screen's label, not a verified belief; see [../../findings.md](../../findings.md), section 6.)
   - Local patching hides the error, because a camera move and a plotter shift look the same near one square. Blind targets (coordinates given only in text) will make the wrong attribution cost points.

**Supporting results:**
- Smaller models attempt the same strategies but can't execute them: Flash writes the right affine model and is too noisy to use it; Sonnet forms no model.
- An apparent "can't see" failure was our interface: Sonnet's error went from 334 mm to 0.5 mm with crop plus pixel coordinates.
- Memory is essential: without notes carried forward, every turn starts from scratch.
