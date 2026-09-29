# Baseline challenge (exploratory)

Change timing, ARX gains, affine coefficients, and warp magnitude vary by page seed. No seeds are discarded.
Library and Broyden receive the same numeric observation schema, with no hidden scenario or change timing.
The library is restricted to engineered candidate families, not arbitrary rule discovery.
Means weight each page seed equally. Intervals in summary.json are descriptive seed bootstraps, not population guarantees.

| Family | Agent | First-try | Completed | Strokes/target | Clamped |
|---|---|---:|---:|---:|---:|
| identity | adaptive_library | 0.984 | 1.000 | 1.02 | 0 |
| identity | local_broyden | 0.984 | 1.000 | 1.03 | 0 |
| identity | local_patcher | 0.984 | 1.000 | 1.03 | 0 |
| identity | naive | 0.984 | 1.000 | 1.02 | 0 |
| identity | oracle | 0.984 | 1.000 | 1.02 | 0 |
| affine | adaptive_library | 0.673 | 0.975 | 1.86 | 1 |
| affine | local_broyden | 0.395 | 1.000 | 1.74 | 0 |
| affine | local_patcher | 0.395 | 1.000 | 1.74 | 0 |
| affine | naive | 0.380 | 0.640 | 5.81 | 0 |
| affine | oracle | 0.988 | 1.000 | 1.01 | 0 |
| arx | adaptive_library | 0.744 | 1.000 | 1.29 | 0 |
| arx | family_estimator | 0.738 | 1.000 | 1.30 | 0 |
| arx | local_broyden | 0.010 | 1.000 | 5.31 | 0 |
| arx | local_patcher | 0.010 | 1.000 | 4.13 | 0 |
| arx | naive | 0.010 | 0.400 | 9.02 | 0 |
| arx | oracle | 0.984 | 1.000 | 1.02 | 0 |
| mode | adaptive_library | 0.782 | 1.000 | 1.36 | 10 |
| mode | family_estimator | 0.936 | 1.000 | 1.07 | 0 |
| mode | local_broyden | 0.625 | 0.933 | 3.00 | 0 |
| mode | local_patcher | 0.575 | 0.867 | 3.12 | 335 |
| mode | naive | 0.582 | 0.858 | 2.84 | 0 |
| mode | oracle | 0.984 | 1.000 | 1.02 | 0 |
| warp | adaptive_library | 0.726 | 0.992 | 1.45 | 0 |
| warp | family_estimator | 0.760 | 1.000 | 1.25 | 4 |
| warp | local_broyden | 0.083 | 1.000 | 2.09 | 0 |
| warp | local_patcher | 0.091 | 1.000 | 2.09 | 0 |
| warp | naive | 0.095 | 0.201 | 10.24 | 0 |
| warp | oracle | 0.984 | 1.000 | 1.02 | 0 |

896 episodes; 0 page generation failures; 0 stopped episodes.
