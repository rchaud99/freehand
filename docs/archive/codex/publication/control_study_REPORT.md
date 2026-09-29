# Exploratory offline controls

These are code-agent experiments, not evidence of frontier-model difficulty.
Intervals resample page seeds. Family references have privileged numeric perception, rule-family knowledge, and change timing.
Fixed-budget first-try attainment uses all nine planned post-change targets. No seed is discarded for poor oracle performance.

| Family | Agent | First-try mean [95% seed bootstrap] | Mean post strokes | Mean closed / 9 | Clamped strokes |
|---|---|---:|---:|---:|---:|
| identity | oracle | 0.972 [0.938, 1.000] | 9.25 | 9.00 | 0 |
| identity | naive | 0.972 [0.938, 1.000] | 9.25 | 9.00 | 0 |
| identity | local_patcher | 0.972 [0.938, 1.000] | 9.69 | 9.00 | 0 |
| arx | oracle | 0.972 [0.938, 1.000] | 9.25 | 9.00 | 0 |
| arx | naive | 0.007 [0.000, 0.021] | 92.56 | 2.50 | 0 |
| arx | local_patcher | 0.000 [0.000, 0.000] | 39.88 | 9.00 | 0 |
| arx | family_estimator | 0.750 [0.715, 0.778] | 11.50 | 9.00 | 0 |
| mode | oracle | 0.972 [0.938, 1.000] | 9.25 | 9.00 | 0 |
| mode | naive | 0.535 [0.458, 0.611] | 29.06 | 7.44 | 0 |
| mode | local_patcher | 0.542 [0.465, 0.611] | 29.44 | 7.75 | 221 |
| mode | family_estimator | 0.854 [0.819, 0.889] | 10.38 | 9.00 | 0 |
| warp | oracle | 0.972 [0.938, 1.000] | 9.25 | 9.00 | 0 |
| warp | naive | 0.076 [0.028, 0.132] | 95.19 | 1.38 | 0 |
| warp | local_patcher | 0.062 [0.028, 0.104] | 19.50 | 9.00 | 0 |
| warp | family_estimator | 0.799 [0.757, 0.840] | 10.88 | 9.00 | 1 |

Completed 240 episodes across 16 planned seeds. Page-generation errors: 0.
No paid requests were made. All episode commands, dense ink, stop reasons, and manifests are retained.
