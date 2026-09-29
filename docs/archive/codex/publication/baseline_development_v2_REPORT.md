# Baseline challenge (exploratory)

Change timing, ARX gains, affine coefficients, and warp magnitude vary by page seed. No seeds are discarded.
Library and Broyden receive the same numeric observation schema, with no hidden scenario or change timing.
The library is restricted to engineered candidate families, not arbitrary rule discovery.
Means weight each page seed equally. Intervals in summary.json are descriptive seed bootstraps, not population guarantees.

| Family | Agent | First-try | Completed | Strokes/target | Clamped |
|---|---|---:|---:|---:|---:|
| identity | adaptive_library | 0.972 | 1.000 | 1.03 | 0 |
| identity | local_broyden | 0.972 | 1.000 | 1.11 | 0 |
| identity | local_patcher | 0.972 | 1.000 | 1.06 | 0 |
| identity | naive | 0.972 | 1.000 | 1.03 | 0 |
| identity | oracle | 0.972 | 1.000 | 1.03 | 0 |
| affine | adaptive_library | 0.751 | 1.000 | 1.67 | 0 |
| affine | local_broyden | 0.417 | 1.000 | 1.74 | 0 |
| affine | local_patcher | 0.417 | 1.000 | 1.77 | 0 |
| affine | naive | 0.503 | 0.692 | 4.82 | 0 |
| affine | oracle | 0.972 | 1.000 | 1.03 | 0 |
| arx | adaptive_library | 0.751 | 1.000 | 1.28 | 0 |
| arx | family_estimator | 0.751 | 1.000 | 1.25 | 0 |
| arx | local_broyden | 0.031 | 1.000 | 5.09 | 0 |
| arx | local_patcher | 0.000 | 1.000 | 3.99 | 0 |
| arx | naive | 0.000 | 0.233 | 10.42 | 0 |
| arx | oracle | 0.972 | 1.000 | 1.03 | 0 |
| mode | adaptive_library | 0.815 | 1.000 | 1.37 | 3 |
| mode | family_estimator | 0.913 | 1.000 | 1.09 | 0 |
| mode | local_broyden | 0.551 | 0.913 | 3.42 | 0 |
| mode | local_patcher | 0.582 | 0.826 | 3.52 | 62 |
| mode | naive | 0.551 | 0.799 | 3.46 | 0 |
| mode | oracle | 0.972 | 1.000 | 1.03 | 0 |
| warp | adaptive_library | 0.689 | 1.000 | 1.59 | 0 |
| warp | family_estimator | 0.725 | 1.000 | 1.28 | 0 |
| warp | local_broyden | 0.056 | 1.000 | 2.22 | 0 |
| warp | local_patcher | 0.056 | 1.000 | 2.16 | 0 |
| warp | naive | 0.095 | 0.189 | 10.17 | 0 |
| warp | oracle | 0.972 | 1.000 | 1.03 | 0 |

112 episodes; 0 page generation failures; 0 stopped episodes.
