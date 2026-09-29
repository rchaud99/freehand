# Legacy parity fixtures

`../fixtures/legacy_parity.json.gz` holds what the ORIGINAL code produced for the 150 cases in `cases.py`
(system prompts, every state block, every request-cache key, every stroke, square results, metrics and ink).
`../test_legacy_parity.py` runs the same cases through the new package and requires identical output.

The fixture was recorded on 2026-09-28 from copy A (`freehand_publish`, cases marked `legacy="a"`) and copy B
(`freehand_b`, all other cases; see the glossary in docs/HISTORY.md) with `record_legacy.py`, under the locked
environment (numpy 2.5.3, opencv-python-headless 5.0.0.93, CPython 3.12.7, macOS arm64). Re-recording needs those
two source folders; running the test does not.
