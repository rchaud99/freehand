# Freehand: three-model pilot comparison (seed 7, one episode per cell)

One episode per model and condition, so treat these as leads, not estimates. `abandoned` = squares failed before / after the change. `noticed` = first post-change turn whose note or memory states the change. Code rows (oracle / adaptive / naive) have perfect perception.

- Hard, position-dependent changes (seed 10; ×0.73 scale or 13° rotation about the page centre) break the ceiling. Only Opus handles them: it fits the right family ('actual x = 0.70*cmd + 30.7' for the scale; for the rotation, an affine with cross-terms of ±0.22, i.e. sin 13°). It needs 4 and 8 strokes to its first first-try closure after the change, against a 5-stroke floor for the code estimator, with 0 squares abandoned. GPT-6 Sol treats the change as a constant offset ('compensates for that offset') and abandons 3 of 4 squares in both conditions. Flash (crop pixels) fits offsets, then 'skew/affine' maps, but still abandons 3 and 1. Sonnet (crop pixels) never models a change ('mystery non-registration') and abandons 3 in each.
- Forcing reasoning on for every model (seed 10, scale73 / rot13) does not change the ranking. Opus and GPT-6 Astra both fit the right model and finish with low ink regret: Astra 0.03 / -0.03, Opus 0.07 / 0.15; Astra writes 'actual = 0.75*command + (28.5,35.0), not just translation'. GPT-6 Sol still reasons in offsets ('shifted this command left by 4 mm') with ink regret 0.97 / 0.61, and a scaffolded prompt helps only on the rotation (regret 0.40). Flash improves a lot at thinking level high (0 and 1 squares abandoned, regret 0.39 / 0.51) but uses ~15k reasoning tokens a turn and hits the $2 episode cap. Sonnet (crop pixels) abandons all 4 squares after the change in both conditions, and still skips reasoning on some turns despite the forced budget.
- Frontier models do the basic task; the rest fail it because of units, not eyesight. Opus 5.5, GPT-6 Astra and GPT-6 Sol closed 8/8 squares on the first stroke on the gridded view. Sonnet 5 and Flash failed at first, but the perception probe shows why: asked for pixels in a magnified crop, Sonnet locates free ends with a 0.49 mm median error (24/24 ends within 2 mm) against 334 mm when asked for page mm. With that crop-pixel mode Sonnet closed 8/8 squares first try ($0.07).
- Plotter offset (10 mm), memory on: Opus and Astra behave identically. Each names the offset in its note on the 2nd post-change turn ('landed about 8.75 mm left and 5.25 mm up'), writes the correction into memory and closes every later square first try. That is 3 strokes to the first first-try closure and 5 after the change, the same as the code estimator. Without memory (pilot 1) Opus needed 9. Flash also names the offset but can't read its own marks well enough to use it (44 strokes after the change, 3 squares abandoned).
- Camera move: Opus and Astra both recalibrate from their own old marks on the first turn after the move and close that square first try (1 stroke, the same as the code estimator). From a fresh start at the same camera angle, Opus needs 6 strokes to its first first-try closure, and Astra never closes a square first try (11 strokes for 4 squares), so the old marks save both of them strokes. Flash never states the move (25 strokes after it); Sonnet never got past the uncalibrated start in page-mm mode.
- OpenAI ladder on the basic task (gridded view, no change): GPT-6 Astra, GPT-5.5 and GPT-6 Sol pass. GPT-5.6 Terra fails in page mm but passes with crop pixels. GPT-5.4-mini and GPT-5.4-nano fail in both modes, so the threshold sits between Sol/Terra and mini.
- Cost per episode with memory: Opus $0.16-1.07, Astra $0.40-0.88, Flash $0.15-1.52, Sonnet capped at ~$1.3 in page-mm mode. One episode per cell: leads, not estimates.

| model | cond | memory | pre_first_try | first_perfect_after | strokes_after | abandoned | noticed | ink_total_mm | ink_wasted_mm | ink_wasted_ratio | ink_regret | tokens | turns | reasoning_median | zero_reasoning_turns | cost | stopped | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Flash 3.8 | offset10 | True | 0/4 | none in 44 | 44 (stopped) | 1 / 3 | yes, post-change turn 2 (note) | 2089.6 | 1995.5 | 0.955 | 1.1 | 974k / 10k / 245k | 65 | 3231 | 0 | $1.51 | episode cost cap | FP |
| GPT-6 Astra | offset10 | True | 4/4 | 3 | 5 | 0 / 0 | yes, post-change turn 2 (note) | 268.8 | 36.9 | 0.137 | 0.002 | 27k / 0k / 0k | 9 | 0 | 5 | $0.40 |  | AP |
| Opus 5.5 | offset10 | True | 4/4 | 3 | 5 | 0 / 0 | yes, post-change turn 2 (note) | 269.8 | 36.9 | 0.137 | 0.002 | 37k / 1k / 1k | 9 | 93 | 0 | $0.16 |  | P2 |
| Sonnet 5 | offset10 | True | 0/3 (stopped on square 4) | change not reached | — | 3 / 0 | not reached | 1473.2 | 1473.2 | 1.0 | -0.122 | 619k / 14k / 74k | 42 | 1663 | 0 | $1.27 | budget cap | SP |
| adaptive estimator (code) | offset10 | None | 4/4 | 3 | 5 | 0 / 0 | — | 266.5 | 37.1 | 0.139 | 0.0 | 0k / 0k / 0k | 9 | — | — | — |  | P2 |
| naive (never adapts) | offset10 | None | 4/4 | none in 48 | 48 | 0 / 4 | — | 1498.3 | 1382.3 | 0.923 | 1.0 | 0k / 0k / 0k | 52 | — | — | — |  | P2 |
| oracle (knows the map) | offset10 | None | 4/4 | 1 | 4 | 0 / 0 | — | 231.2 | 0.0 | 0.0 | -0.029 | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| Flash 3.8 (crop px) | scale73 | True | 3/4 | none in 46 | 46 | 0 / 3 | yes, post-change turn 2 (memory) | 1539.6 | 1376.6 | 0.894 | 1.322 | 788k / 8k / 208k | 53 | 3309 | 1 | $1.34 |  | HP |
| GPT-6 Sol | scale73 | True | 4/4 | none in 40 | 40 | 0 / 3 | yes, post-change turn 3 (note) | 1255.9 | 1116.4 | 0.889 | 1.038 | 322k / 4k / 17k | 44 | 412 | 0 | $1.03 |  | HP |
| Opus 5.5 | scale73 | True | 4/4 | 4 | 7 | 0 / 0 | yes, post-change turn 2 (note) | 356.9 | 112.9 | 0.316 | 0.038 | 51k / 2k / 4k | 11 | 334 | 0 | $0.26 |  | HP |
| Sonnet 5 (crop px) | scale73 | True | 3/4 | none in 41 | 41 (stopped) | 0 / 3 | yes, post-change turn 11 (memory) | 1203.8 | 1084.3 | 0.901 | 0.921 | 780k / 12k / 83k | 53 | 916 | 4 | $1.51 | episode cost cap | HP |
| adaptive estimator (code) | scale73 | None | 4/4 | 5 | 7 | 0 / 0 | — | 324.0 | 82.7 | 0.255 | 0.0 | 0k / 0k / 0k | 11 | — | — | — |  | HP |
| naive (never adapts) | scale73 | None | 4/4 | none in 48 | 48 | 0 / 4 | — | 1221.8 | 1104.8 | 0.904 | 1.0 | 0k / 0k / 0k | 52 | — | — | — |  | HP |
| oracle (knows the map) | scale73 | None | 4/4 | 1 | 4 | 0 / 0 | — | 244.8 | 0.0 | 0.0 | -0.088 | 0k / 0k / 0k | 8 | — | — | — |  | HP |
| Flash 3.8 (crop px) | scale73_rf | True | 3/4 | none in 24 | 24 (stopped) | 0 / 1 | yes, post-change turn 4 (note) | 1072.7 | 928.6 | 0.866 | 0.506 | 482k / 6k / 443k | 38 | 15356 | 0 | $2.05 | episode cost cap | HR |
| GPT-6 Astra | scale73_rf | True | 4/4 | 6 | 8 | 0 / 0 | yes, post-change turn 2 (note) | 346.4 | 104.4 | 0.301 | 0.026 | 45k / 1k / 2k | 12 | 185 | 0 | $0.75 |  | HR |
| GPT-6 Sol | scale73_rf | True | 4/4 | none in 31 | 31 | 0 / 1 | yes, post-change turn 3 (note) | 1194.9 | 988.5 | 0.827 | 0.971 | 215k / 3k / 26k | 35 | 779 | 0 | $0.84 |  | HR |
| Opus 5.5 | scale73_rf | True | 4/4 | 7 | 8 | 0 / 0 | yes, post-change turn 2 (note) | 382.4 | 138.6 | 0.362 | 0.066 | 59k / 2k / 5k | 12 | 393 | 0 | $0.30 |  | HR |
| Sonnet 5 (crop px) | scale73_rf | True | 3/4 | none in 48 | 48 | 0 / 4 | yes, post-change turn 11 (memory) | 1343.2 | 1223.7 | 0.911 | 1.076 | 986k / 14k / 99k | 60 | 954 | 4 | $1.90 |  | HR |
| adaptive estimator (code) | scale73_rf | None | 4/4 | 5 | 7 | 0 / 0 | — | 324.0 | 82.7 | 0.255 | 0.0 | 0k / 0k / 0k | 11 | — | — | — |  | HP |
| naive (never adapts) | scale73_rf | None | 4/4 | none in 48 | 48 | 0 / 4 | — | 1221.8 | 1104.8 | 0.904 | 1.0 | 0k / 0k / 0k | 52 | — | — | — |  | HP |
| oracle (knows the map) | scale73_rf | None | 4/4 | 1 | 4 | 0 / 0 | — | 244.8 | 0.0 | 0.0 | -0.088 | 0k / 0k / 0k | 8 | — | — | — |  | HP |
| GPT-6 Sol | scale73_rf_scaff | True | 4/4 | none in 37 | 37 | 0 / 2 | yes, post-change turn 1 (memory) | 1403.7 | 1223.5 | 0.872 | 1.204 | 364k / 7k / 33k | 41 | 816 | 0 | $1.32 |  | HR |
| Flash 3.8 (crop px) | rot13 | True | 3/4 | none in 41 | 41 | 0 / 1 | yes, post-change turn 3 (note) | 1574.9 | 1352.2 | 0.859 | 0.939 | 681k / 8k / 208k | 47 | 3728 | 0 | $1.28 |  | HP |
| GPT-6 Sol | rot13 | True | 4/4 | none in 39 | 39 | 0 / 3 | yes, post-change turn 3 (note) | 1396.9 | 1254.2 | 0.898 | 0.821 | 310k / 4k / 16k | 43 | 345 | 0 | $0.98 |  | HP |
| Opus 5.5 | rot13 | True | 4/4 | 8 | 8 | 0 / 0 | yes, post-change turn 2 (note) | 383.1 | 140.8 | 0.367 | 0.023 | 59k / 2k / 5k | 12 | 424 | 0 | $0.30 |  | HP |
| Sonnet 5 (crop px) | rot13 | True | 3/4 | none in 36 | 36 (stopped) | 0 / 3 | yes, post-change turn 8 (memory) | 1381.1 | 1261.6 | 0.913 | 0.767 | 627k / 11k / 96k | 47 | 1743 | 4 | $1.55 | budget cap | HP |
| adaptive estimator (code) | rot13 | None | 4/4 | 5 | 7 | 0 / 0 | — | 354.6 | 113.4 | 0.32 | 0.0 | 0k / 0k / 0k | 11 | — | — | — |  | HP |
| naive (never adapts) | rot13 | None | 4/4 | none in 48 | 48 | 0 / 4 | — | 1624.1 | 1507.1 | 0.928 | 1.0 | 0k / 0k / 0k | 52 | — | — | — |  | HP |
| oracle (knows the map) | rot13 | None | 4/4 | 1 | 4 | 0 / 0 | — | 242.8 | 0.0 | 0.0 | -0.088 | 0k / 0k / 0k | 8 | — | — | — |  | HP |
| Flash 3.8 (crop px) | rot13_rf | True | 3/4 | none in 23 | 23 (stopped) | 0 / 0 | yes, post-change turn 2 (memory) | 1131.6 | 909.5 | 0.804 | 0.387 | 431k / 6k / 493k | 35 | 15357 | 0 | $2.19 | episode cost cap | HR |
| GPT-6 Astra | rot13_rf | True | 4/4 | 4 | 6 | 0 / 0 | yes, post-change turn 2 (memory) | 322.1 | 77.6 | 0.241 | -0.025 | 34k / 1k / 1k | 10 | 106 | 0 | $0.58 |  | HR |
| GPT-6 Sol | rot13_rf | True | 4/4 | none in 32 | 32 | 0 / 2 | yes, post-change turn 4 (memory) | 1126.1 | 943.9 | 0.838 | 0.609 | 221k / 3k / 29k | 36 | 796 | 0 | $0.89 |  | HR |
| Opus 5.5 | rot13_rf | True | 4/4 | none in 13 | 13 | 0 / 0 | yes, post-change turn 2 (note) | 542.1 | 298.2 | 0.55 | 0.149 | 107k / 4k / 5k | 17 | 291 | 0 | $0.41 |  | HR |
| Sonnet 5 (crop px) | rot13_rf | True | 3/4 | none in 48 | 48 | 0 / 4 | yes, post-change turn 8 (memory) | 1652.3 | 1532.8 | 0.928 | 0.98 | 958k / 13k / 109k | 59 | 1508 | 8 | $1.92 |  | HR |
| adaptive estimator (code) | rot13_rf | None | 4/4 | 5 | 7 | 0 / 0 | — | 354.6 | 113.4 | 0.32 | 0.0 | 0k / 0k / 0k | 11 | — | — | — |  | HP |
| naive (never adapts) | rot13_rf | None | 4/4 | none in 48 | 48 | 0 / 4 | — | 1624.1 | 1507.1 | 0.928 | 1.0 | 0k / 0k / 0k | 52 | — | — | — |  | HP |
| oracle (knows the map) | rot13_rf | None | 4/4 | 1 | 4 | 0 / 0 | — | 242.8 | 0.0 | 0.0 | -0.088 | 0k / 0k / 0k | 8 | — | — | — |  | HP |
| GPT-6 Sol | rot13_rf_scaff | True | 4/4 | none in 20 | 20 | 0 / 1 | yes, post-change turn 2 (note) | 860.3 | 653.9 | 0.76 | 0.399 | 151k / 4k / 22k | 24 | 908 | 0 | $0.64 |  | HR |
| Flash 3.8 | cam_transfer | True | 1/4 | none in 25 | 25 | 0 / 1 | no | 706.1 | 536.5 | 0.76 | 0.469 | 342k / 6k / 168k | 33 | 4672 | 1 | $0.92 |  | FP |
| GPT-6 Astra | cam_transfer | True | 1/4 | 1 | 6 | 0 / 0 | yes, post-change turn 1 (note) | 315.9 | 123.9 | 0.392 | 0.051 | 52k / 2k / 2k | 13 | 149 | 0 | $0.88 |  | AP |
| Opus 5.5 | cam_transfer | True | 0/4 | 1 | 6 | 1 / 0 | yes, post-change turn 1 (note) | 754.1 | 588.6 | 0.781 | 0.048 | 299k / 8k / 24k | 29 | 783 | 0 | $1.07 |  | P2 |
| Sonnet 5 | cam_transfer | True | 0/2 (stopped on square 3) | change not reached | — | 2 / 0 | not reached | 703.1 | 703.1 | 1.0 | -0.092 | 260k / 9k / 102k | 25 | 3943 | 0 | $1.33 | budget cap | SP |
| adaptive estimator (code) | cam_transfer | None | 1/4 | 1 | 4 | 0 / 0 | — | 259.8 | 72.5 | 0.279 | 0.0 | 0k / 0k / 0k | 11 | — | — | — |  | P2 |
| naive (never adapts) | cam_transfer | None | 4/4 | none in 48 | 48 | 0 / 4 | — | 1129.2 | 1027.3 | 0.91 | 1.0 | 0k / 0k / 0k | 52 | — | — | — |  | P2 |
| oracle (knows the map) | cam_transfer | None | 4/4 | 1 | 4 | 0 / 0 | — | 189.6 | 0.0 | 0.0 | 0.001 | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| Flash 3.8 | cam_fresh | True | — | 5 | 7 | 0 | — | 163.5 | 74.6 | 0.456 | -0.013 | 31k / 1k / 33k | 7 | 4698 | 0 | $0.15 |  | FP |
| GPT-6 Astra | cam_fresh | True | — | none in 11 | 11 | 0 | — | 237.4 | 151.0 | 0.636 | 0.074 | 40k / 1k / 1k | 11 | 107 | 0 | $0.67 |  | AP |
| Opus 5.5 | cam_fresh | True | — | 6 | 8 | 0 | — | 161.8 | 75.0 | 0.463 | -0.015 | 36k / 2k / 5k | 8 | 646 | 0 | $0.25 |  | P2 |
| Sonnet 5 | cam_fresh | True | — | none in 16 | 16 (stopped) | 1 | — | 329.7 | 329.7 | 1.0 | 0.182 | 205k / 8k / 100k | 21 | 4915 | 0 | $1.26 | budget cap | SP |
| adaptive estimator (code) | cam_fresh | None | — | none in 8 | 8 | 0 | — | 174.2 | 89.4 | 0.513 | 0.0 | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| naive (never adapts) | cam_fresh | None | — | none in 48 | 48 | 4 | — | 1029.0 | 1029.0 | 1.0 | 1.0 | 0k / 0k / 0k | 48 | — | — | — |  | P2 |
| oracle (knows the map) | cam_fresh | None | — | 1 | 4 | 0 | — | 84.9 | 0.0 | 0.0 | -0.104 | 0k / 0k / 0k | 4 | — | — | — |  | P2 |
| Flash 3.8 | none | True | 0/4 | change not reached | — | 1 / 0 | — | 584.0 | 489.9 | 0.839 | None | 141k / 2k / 79k | 21 | 2351 | 0 | $0.41 | episode cost cap | P2 |
| Sonnet 5 | none | True | 0/3 (stopped on square 4) | change not reached | — | 2 / 0 | — | 770.4 | 734.1 | 0.953 | None | 202k / 4k / 19k | 26 | 676 | 1 | $0.42 | episode cost cap | P2 |
| adaptive estimator (code) | none | None | 4/4 | 1 | 4 | 0 / 0 | — | 231.2 | 0.0 | 0.0 | None | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| naive (never adapts) | none | None | 4/4 | 1 | 4 | 0 / 0 | — | 231.2 | 0.0 | 0.0 | None | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| oracle (knows the map) | none | None | 4/4 | 1 | 4 | 0 / 0 | — | 231.2 | 0.0 | 0.0 | None | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| Sonnet 5 (crop px) | none_crop_px | True | 4/4 | 1 | 4 | 0 / 0 | — | 235.0 | 0.0 | 0.0 | None | 36k / 0k / 0k | 8 | 45 | 1 | $0.07 |  | PE |
| Flash 3.8 | offset10 | False | 0/4 | none in 19 | 19 | 2 / 2 | yes, post-change turn 2 (note) | 1050.0 | 928.2 | 0.884 | 0.838 | 112k / 2k / 155k | 35 | 4544 | 0 | $0.68 |  | P1 |
| Opus 5.5 | offset10 | False | 4/4 | 9 | 9 | 0 / 0 | yes, post-change turn 2 (note) | 408.7 | 174.8 | 0.428 | 0.264 | 27k / 1k / 4k | 13 | 160 | 0 | $0.22 |  | P1 |
| Sonnet 5 | offset10 | False | 0/4 | none in 24 | 24 | 4 / 4 | no | 1033.3 | 1033.3 | 1.0 | 0.718 | 122k / 3k / 45k | 48 | 600 | 11 | $0.73 |  | P1 |
| Opus 5.5 | none | False | 4/4 | 1 | 4 | 0 / 0 | — | 233.7 | 0.0 | 0.0 | None | 16k / 0k / 0k | 8 | 117 | 1 | $0.10 |  | P1 |
| adaptive estimator (code) | cam_static | None | 1/4 | 1 | 4 | 0 / 0 | — | 260.1 | 72.5 | 0.279 | 0.0 | 0k / 0k / 0k | 11 | — | — | — |  | P2 |
| naive (never adapts) | cam_static | None | 4/4 | 1 | 4 | 0 / 0 | — | 189.5 | 0.0 | 0.0 | 1.0 | 0k / 0k / 0k | 8 | — | — | — |  | P2 |
| oracle (knows the map) | cam_static | None | 4/4 | 1 | 4 | 0 / 0 | — | 189.5 | 0.0 | 0.0 | 1.0 | 0k / 0k / 0k | 8 | — | — | — |  | P2 |

## Perception / units probe

| model | mode | items | parse_fail | median_mm | p90_mm | ends_within_2mm | items_both_within_2mm | cost |
|---|---|---|---|---|---|---|---|---|
| claude-opus-5.5 | mm | 12 | 0 | 0.27 | 0.56 | 24/24 | 12/12 | 0.0989 |
| claude-opus-5.5 | px | 12 | 0 | 0.24 | 0.5 | 24/24 | 12/12 | 0.0791 |
| claude-opus-5.5 | crop | 12 | 0 | 0.15 | 0.39 | 24/24 | 12/12 | 0.0901 |
| claude-opus-5.5 | crop_px | 12 | 0 | 0.15 | 0.38 | 24/24 | 12/12 | 0.0531 |
| claude-sonnet-5 | mm | 12 | 0 | 333.69 | 629.36 | 1/24 | 0/12 | 0.0437 |
| claude-sonnet-5 | px | 12 | 0 | 2.16 | 5.84 | 11/24 | 4/12 | 0.0438 |
| claude-sonnet-5 | crop | 12 | 0 | 3.17 | 49.73 | 7/24 | 2/12 | 0.0259 |
| claude-sonnet-5 | crop_px | 12 | 0 | 0.49 | 0.75 | 24/24 | 12/12 | 0.0282 |
| gemini-3.8-flash | mm | 12 | 0 | 1.9 | 5.4 | 12/24 | 5/12 | 0.1444 |
| gemini-3.8-flash | px | 12 | 0 | 2.52 | 15.97 | 11/24 | 5/12 | 0.1221 |
| gemini-3.8-flash | crop | 12 | 0 | 1.06 | 2.26 | 21/24 | 9/12 | 0.1562 |
| gemini-3.8-flash | crop_px | 12 | 0 | 0.28 | 0.91 | 23/24 | 11/12 | 0.1013 |

## Capability threshold (OpenAI ladder, basic task)

| tier | model | price | mode | squares | first_try | abandoned | strokes_per_square | reasoning_tokens_median | cost | status | passes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | gpt-6-astra | $10 / $50 | mm | 8/8 | 8/8 | 0 | 1.0 | 0 | 0.327 | complete | True |
| 2 | gpt-5.5 | $5 / $30 | mm | 8/8 | 7/8 | 1 | 2.38 | 1007 | 0.877 | complete | True |
| 3 | gpt-5.6-terra | $2 / $12 | crop_px | 8/8 | 4/8 | 1 | 3.0 | 274 | 0.467 | complete | True |
| 3 | gpt-5.6-terra | $2 / $12 | mm | 8/8 | 4/8 | 2 | 4.0 | 479 | 0.712 | complete | False |
| 4 | gpt-6-sol | $2 / $10 | mm | 8/8 | 8/8 | 0 | 1.0 | 56 | 0.077 | complete | True |
| 5 | gpt-5.4-mini | $0.75 / $4.5 | crop_px | 6/8 | 0/6 | 6 | 12.0 | 3086 | 1.521 | episode cost cap | False |
| 5 | gpt-5.4-mini | $0.75 / $4.5 | mm | 8/8 | 1/8 | 6 | 9.38 | 1304 | 0.78 | complete | False |
| 6 | gpt-5.4-nano | $0.2 / $1.25 | crop_px | 8/8 | 0/8 | 8 | 12.0 | 1663 | 0.348 | complete | False |
| 6 | gpt-5.4-nano | $0.2 / $1.25 | mm | 8/8 | 0/8 | 8 | 12.0 | 811 | 0.235 | complete | False |
