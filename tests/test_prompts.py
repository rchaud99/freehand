"""Prompt text files: well-formed, and the assembled prompts are the historical strings (full coverage of every arm
and turn is in test_legacy_parity.py; these are readable spot checks)."""

import pytest

from freehand import prompts
from freehand.agents.arms import PRESETS, Arm
from freehand.agents.prompting import SystemPromptSpec, build_system, state_block


def test_every_component_is_well_formed():
    ids = prompts.component_ids()
    assert len(ids) >= 20
    for pid in ids:
        t = prompts.text(pid)
        assert t and t == t.strip("\n")


def test_system_prompt_snapshot_memory_silent():
    s, ids = build_system(SystemPromptSpec(view="rect", memory=True))
    assert s.startswith("You are controlling a pen plotter through a camera.")
    assert "Always give page millimeters read from the grid labels, never pixels." in s
    assert "It counts as closed when the ink of one stroke lands within 2 mm of both free ends" in s
    assert "at most about 150 words" in s and "the previous 2 photos (smaller)" in s
    assert s.endswith("Points outside it are clamped to its edge.")
    assert ids[0] == "v1/system/plotter"


def test_crop_px_and_raw_views():
    crop, _ = build_system(SystemPromptSpec(view="rect", memory=False, output_mode="crop_px"))
    assert "never pixels" not in crop and '"strokes": [[[px1,py1],[px2,py2]]] (crop pixels)' in crop
    raw, _ = build_system(SystemPromptSpec(view="raw", memory=True, disclosure="alerted"))
    assert "raw, uncalibrated photo (960 x 960 px)" in raw and "may change at any time" in raw
    with pytest.raises(ValueError):
        build_system(SystemPromptSpec(view="raw", memory=True, output_mode="crop_px"))


def test_state_block_snapshot():
    full, compact = state_block("rect", 7, 7, 20, 1, 12, ["sq1: (61.0,40.2) -> (61.1,62.3)"], True, None, landed=False)
    assert full == (
        "Turn 7. Allowed region (page mm): x 5 to 211, y 5 to 274. Current square: #7 of 20 (outlined in "
        "green). Strokes used on this square: 1 of 12. Strokes you have already drawn (page mm): sq1: "
        "(61.0,40.2) -> (61.1,62.3)"
    )
    assert compact.endswith("Strokes used on this square: 1 of 12.")


def test_arms():
    assert PRESETS["stateless_numeric"].history_landed and not PRESETS["stateless_numeric"].memory
    assert "YOUR OBJECTIVE" in PRESETS["informed_objective"].block_text()
    with pytest.raises(ValueError, match="scaffolded"):
        Arm("x", memory=False, disclosure="scaffolded")
    with pytest.raises(ValueError, match="unknown prompt block"):
        Arm("x", blocks=("nope",))
