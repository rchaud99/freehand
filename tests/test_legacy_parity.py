"""Historical comparability: the new episode loop reproduces the legacy code exactly.

`fixtures/legacy_parity.json.gz` was recorded by running 150 cases through the ORIGINAL code (the Codex copy for the
discriminating rules / numeric feedback / P=0, the working copy for everything else): every plotter-map and camera
condition, every ladder level and rung, the discriminating rules, all reference agents, and a scripted fake model
through every arm (silent / alerted / scaffolded, no memory, no history, K=0, crop_px, objective, informed,
stateless image / numeric, L7's prompt line, numeric feedback, an episode cost cap). See tests/parity/README.md.

Compared per turn: the state block, the request-cache key (a hash of the system prompt, every message and the
bytes of every image sent), notepad and history bookkeeping, the parsed action and the executed stroke (ends to the
last bit); per episode: the system prompt, square results, stroke log, stop reason, metrics and ink.

A representative subset runs by default (~30 s); FREEHAND_FULL_PARITY=1 runs all 150 cases (~3.5 min).
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import pytest

from freehand.llm import Budget, Ledger, RequestCache

from .parity.cases import CASES
from .parity.comparable import from_new
from .parity.runner import run_case

FIXTURE = Path(__file__).parent / "fixtures" / "legacy_parity.json.gz"
QUICK = {
    "map_offset10_oracle", "map_offset10_adaptive", "map_scale73_adaptive", "cam_transfer_adaptive",
    "cam_fresh_oracle", "L3_k2_adaptive", "L4_k1_adaptive", "L5_k3_adaptive", "L6cam_k1_adaptive",
    "L6both_k2_naive", "L7_k3_adaptive", "L2rot_adaptive", "X_arx_adaptive_library", "X_mode_family_estimator",
    "X_warp_local_broyden", "X_identity_local_patcher", "X_arx_P0_oracle", "fake_offset10_silent",
    "fake_offset10_scaffolded", "fake_none_alerted", "fake_cam_transfer", "fake_nomem", "fake_nohist", "fake_k0",
    "fake_crop", "fake_L7", "fake_numeric_feedback_alerted", "fake_costcap",
}
FULL = os.environ.get("FREEHAND_FULL_PARITY") == "1"
SELECTED = [c for c in CASES if FULL or c["id"].split("_", 1)[1] in QUICK]


@pytest.fixture(scope="module")
def legacy():
    with gzip.open(FIXTURE, "rt") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def llm_store(tmp_path_factory):
    d = tmp_path_factory.mktemp("parity")
    return RequestCache(d / "cache.sqlite"), Budget(Ledger(d / "ledger.sqlite"), 1e9, "parity")


def test_quick_subset_is_representative():
    assert len({c["id"].split("_", 1)[1] for c in CASES} & QUICK) == len(QUICK)


@pytest.mark.parametrize("case", SELECTED, ids=[c["id"] for c in SELECTED])
def test_matches_legacy(case, legacy, llm_store):
    summary, turns = run_case(case, *llm_store)
    new = json.loads(json.dumps(from_new(summary, turns)))
    old = legacy[case["id"]]
    assert new["system_prompt"] == old["system_prompt"]
    assert len(new["turns"]) == len(old["turns"])
    for a, b in zip(old["turns"], new["turns"], strict=True):
        assert b == a, f"turn {a['turn']} differs"
    for k in ("squares_result", "strokes", "perturb_stroke", "complete", "stop", "metrics", "ink"):
        assert new[k] == old[k], k
    assert new["cost_original"] == pytest.approx(old["cost_original"], abs=1e-9)
