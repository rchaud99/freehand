# Freehand A: independent review, 2026-09-30

Two read-only reviews ran: one on the code, one adversarial on the design and claims. Each finding below was
re-checked before it was recorded here. No API money was spent.

## Code: no published number or preregistered verdict changes

An independent recomputation from the raw `episode.json` files reproduced everything:
- every aim error;
- every summary;
- claims 1–3;
- the transfer vs fresh numbers;
- the pilot's says-vs-does medians.

Photos re-render bit-exactly, and `photo_sha256` matches 418/418.

Bugs to fix before any new table or video is made:

1. **Fresh overwrites transfer in `report.episodes()`.** It keys episodes by (agent, seed), so in a run with both
   arms the fresh episode replaces the transfer one. This breaks `freehand camera3d report`, the table printed after
   `run`, and the showcase end card/chart for the replication run. The current video is unaffected: it uses the
   single-arm pilot run.
2. **`hook()` finds the camera move from the first agent only.** It is aligned only on page 3017. On the other pages
   Astra has already moved and re-matched before the clip starts. The current video uses page 3017, so it is correct.
3. **`score_claims` doesn't enforce the "capped, stopped or failed counts against" rule** for claims 1 and 3, and it
   silently keeps only the last episode when a study mixes runs with the same keys. Neither happened in these runs.
4. **Video: the camera-move animation plays before the stroke that closed square 4 is drawn.**
5. **Fresh episodes in the video:** `pose_no_at` is wrong at the end, the square dots show 8 plus a move tick, and
   the framing includes pose 1. All latent.
6. **A turn's cost is lost from `episode.json`** if a later call in the same turn raises. The ledger is still
   right, and it did not happen here.
7. **Doc and prompt errors:**
   - The prompt says "the camera sees part of [the reachable] area". Every pose sees well beyond it.
   - The Data section claims a code snapshot and `photo_sha256` for every run. The pilot runs have neither.
   - The Limits text on the spend reservation is out of date.
   - The "4.6–6.0 px/mm" range holds only across the tilt direction.
   - The video docstring says the blue corners lie on the corner rays, which isn't true after the PnP refit.
8. **The estimator is weaker than "ideal".** 4 times it produced non-convex corner quads, scored as infinite
   error, and its noise is set by where ink lands (about 0.5 mm), not the stated 1 px.

## Design and claims: the claims survive only in narrower wording

**S1. The 3 mm bar on a four-corner readout mostly tests whether a model writes down perspective.**
- The best parallelogram (affine) camera for the true view misses 3 mm on 7 of 12 poses (2.1–4.1 mm; recomputed).
- Sol and Flash always write exact parallelograms (median deviation 0.0 mm). Opus writes near-parallelograms
  (5 mm). Only Astra writes perspective quads (36 mm).
- No corner-order, reflection or axis-swap convention error explains any model's beliefs.
- So "only Astra matched" largely means "only Astra wrote down a perspective camera". That is still a real finding,
  but it is a different one.

**S2. The says-vs-does gap is Opus's stated error, not independent evidence.**
- Correlation 0.97 between the gap and its stated error at the target.
- Opus copied its previous estimate verbatim in 68 of 108 turns.
- Its reasoning builds global maps, then switches to local ink-referenced corrections it never writes back.
- The data can't tell "no global camera" from "doesn't keep the field up to date".
- Sol's gap is 2.0 mm, so acting on the stated camera is not unique to Astra. The estimator control is 0.3 mm.
- Drop the wording "says one thing and does another".

**S3. The orange "strokes imply" plane fails its positive control.**
- For the estimator, which acts on its own belief by construction, blue and orange still differ by a median of
  3.9 mm.
- The plane mostly measures closed-loop correction, since retries are in the window.
- Don't use it as evidence. Drop it, or relabel it and show the estimator beside it.

**S4. "Transfer" is re-anchoring on known landmarks.** The old ink plus the stroke log are free calibration points,
and the estimator gets the same benefit by construction. The fresh arm also lacks squares 1–4 and the conversation
history. Call it re-anchoring; this is the design's H3.

**M1. Threshold and provenance.**
- Astra's 5/6 holds from 2 to 4 mm. At 5 mm Sol matches 2/4 pages.
- The "stays matched" rule makes 3004's match a single value.
- The 3 mm value cannot be shown to predate the pilot: nothing was committed, and the pilot has no snapshot.

**M2. Statistics.** One sample per cell and no re-query noise.
- Preregistered pages only: 3/4 vs 0/4, Fisher p = 0.14.
- The "5/6" figure includes the 2 pilot pages, which generated the hypothesis.
- Claim 3 holds on every page (Opus 8.5–22.8 mm vs Astra 0.5–1.7 mm).

**M3. Not tested:** Fable 5.1 and Sonnet 5 (the design's Claude models). Name "Claude Opus 5.5", never "Claude".
Opus's thinking cap was not binding.

**M4. Correction.** Opus did update its camera at the move on all 6 pages (by 46–150 mm), then stopped updating.
"Stale belief" was wrong. The accurate wording is "updated badly, then stopped updating".

**M5. No control without the camera-estimate field.**

**Minor:**
- The glide animation shows beliefs that were never stated.
- Mirror seams in the rendered sheet are faintly visible.
- The camera always centres within 10 mm of the work area.
- It's a perfect pinhole camera.
- Provider image resizing is unverified.

## Wording that survives

- **Instead of "Only Astra's stated camera matched":** "GPT-6 Astra wrote down a camera that, used as written, aims
  within 3 mm across the work area on 3 of 4 preregistered pages (5/6 with the pilot); Claude Opus 5.5 and GPT-6
  Sol never did. Astra was the only one whose written camera included perspective."
- **Instead of says vs does:** "Opus's first stroke at each square missed by a median of 3 mm, but the camera it
  wrote down would have missed by about 18 mm there, and it copied the same estimate turn to turn about 60% of the
  time: its strokes weren't using the camera it reported."
- **Transfer:** descriptive only, as re-anchoring on its own marks, like the ideal estimator.

## Cheapest strengthening checks

1. **Offline ($0).**
   - Floors per pose for parallelogram and similarity cameras.
   - A threshold sweep.
   - The fresh-arm cold starts: 9/12 vs 0/12, not preregistered.
   - The estimator control for the gap and for the planes.
2. **Re-elicit beliefs from saved conversations (about $10–20).** At checkpoints, ask each model twice for the page
   mm of 6 marked pixels. This gives a format-free belief plus run-to-run noise, the design v3.1 "ghost" readout.
   It separates bookkeeping from a missing model.
3. **Run without the `camera_estimate` field (about $15–20).**
4. **Add Fable 5.1 (about $12), and a fresh arm with pre-drawn, logged landmarks (about $15).**
