"""Frozen suites: every file verifies; (suite, seed) data is deterministic, order-independent and pinned."""
import dataclasses
import hashlib
from importlib import metadata

import pytest

from freehand.sim import png_bytes, render_view
from freehand.suites import data_hash, episode_setup, list_suites, load_suite, page, seed_data, seed_hash
from freehand.suites.generate import freeze, scan_seeds
from freehand.suites.spec import parse_suite

GOLDEN_SEED_HASHES = {
    ("core-v1", 1000): "deafae3fc30e74cffa3c232259b089fca8dcfb46e93be01f29f98561104a04cc",
    ("discriminating-v1", 5000): "f29eb9ad1f29be80d23e5e8a836465022bc899c13be283c1bc1f31d3de459afc",
    ("camera-v1", 2000): "d1eba6d347476b6dc70d0835fd1731687227f6814fce2cdb65fee186033d6f10",
    ("smoke-v1", 1): "f76ba8c8608b914e6be8dc5ed1f6d4eb69ff08b4136a7298a89119b249adfdf0",
    ("legacy-objective-v0", 10): "81e7ddf0e2199df4dce47e2c756254ed09a9622e93e5aead7298ecc69631a7a0",
    ("legacy-b8-v0", 7): "ae52d35d0eee2a9078c1ab61ae3109e4ff9093bfe35186d263b5cd3f66dc0d3f",
}
LOCKED_RENDERING = metadata.version("numpy") == "2.5.3" and metadata.version("opencv-python-headless") == "5.0.0.93"


@pytest.mark.parametrize("suite", list_suites(), ids=lambda s: s.id)
def test_every_suite_verifies_against_its_frozen_hash(suite):
    assert suite.data_hash, f"{suite.id} is not frozen (run `freehand suite freeze {suite.id}`)"
    assert data_hash(suite)[0] == suite.data_hash


@pytest.mark.parametrize("key", GOLDEN_SEED_HASHES, ids=lambda k: f"{k[0]}-s{k[1]}")
def test_golden_seed_hashes(key):
    assert seed_hash(load_suite(key[0]), key[1]) == GOLDEN_SEED_HASHES[key]


def test_generation_is_deterministic_and_order_independent():
    s = load_suite("core-v1")
    first = seed_data(s, 1000)
    _ = [seed_data(s, x) for x in (1004, 1001)]          # other seeds, other order
    assert seed_data(s, 1000) == first
    assert page(s, 1000)[0].to_dict() != page(s, 1001)[0].to_dict()


def test_adding_or_reordering_perturbations_never_changes_pages_or_other_rules():
    s = load_suite("core-v1")
    base = seed_data(s, 1002)
    more = dict(s.perturbations)
    more["zz_new_rule"] = {"type": "offset", "params": {"mm": 3.0}}
    reordered = dict(reversed(list(more.items())))
    s2 = dataclasses.replace(s, perturbations=reordered)
    d2 = seed_data(s2, 1002)
    assert d2["page"] == base["page"] and d2["schedule"] == base["schedule"]
    for name, desc in base["perturbations"].items():
        assert d2["perturbations"][name] == desc


def test_legacy_suite_regenerates_the_historical_page():
    # From the informed pilot's log (runs/informed_pilot_20260928_170744, seed 10, square 1).
    sq = page(load_suite("legacy-objective-v0"), 10)[0]
    assert (sq.idx, sq.x0, sq.y0, sq.side, sq.missing) == (1, 138.12, 213.06, 17.83, "top")
    assert sq.open_ends == [[156.71941544103265, 214.00349674400644], [138.44162479157708, 212.61267330060429]]


@pytest.mark.skipif(not LOCKED_RENDERING, reason="image bytes are pinned for the locked numpy/opencv builds")
def test_golden_rendered_images():
    s = load_suite("core-v1")
    sq = page(s, 1000)
    assert hashlib.sha256(png_bytes(render_view(1000, sq, [], sq[0]))).hexdigest() == \
        "b87b63497783be021b26cdd67585feedf2c9e3a6f0e6a94997e4a1b04e0f9792"
    # Byte-identical to the historical pilot2 turn-1 photo (runs/pilot2_20260927_150151/.../t001.png).
    s = load_suite("legacy-b8-v0")
    sq = page(s, 7)
    assert hashlib.sha256(png_bytes(render_view(7, sq, [], sq[0]))).hexdigest() == \
        "f62d54904e0cb482d0f1db0e3514269ba21752977cfa3e25057e4c992ec91fcf"


def test_verify_detects_a_changed_suite(tmp_path):
    src = load_suite("smoke-v1").path.read_text()
    p = tmp_path / "smoke-v1.yaml"
    p.write_text(src.replace("degrees: 13.0", "degrees: 12.0"))
    import yaml
    changed = parse_suite(yaml.safe_load(p.read_text()), p)
    assert data_hash(changed)[0] != changed.data_hash
    assert freeze(changed) == data_hash(changed)[0]         # re-freezing writes the new hash
    assert yaml.safe_load(p.read_text())["data_hash"] == data_hash(changed)[0]


def test_suite_validation_errors():
    good = {"id": "x", "version": 1, "track": "plotter", "page": {"n_squares": 4},
            "change": {"schedule": "fixed", "after_square": 2}, "perturbations": {"r": {"type": "L2_rotation"}},
            "seeds": {"dev": [1], "test": []}}
    parse_suite(good)
    with pytest.raises(ValueError, match="unknown parameter"):
        parse_suite({**good, "perturbations": {"r": {"type": "L2_rotation", "params": {"deg": 3}}}})
    with pytest.raises(ValueError, match="camera track"):
        parse_suite({**good, "perturbations": {"c": {"type": "camera_move"}}})
    with pytest.raises(ValueError, match="twice"):
        parse_suite({**good, "seeds": {"dev": [1], "test": [1]}})
    with pytest.raises(KeyError, match="unknown perturbation type"):
        parse_suite({**good, "perturbations": {"r": {"type": "teleport"}}})


def test_camera_fresh_works_on_the_later_squares_renumbered():
    s = load_suite("camera-v1")
    full = page(s, 2000)
    st = episode_setup(s, 2000, "fresh")
    assert st.perturb_after == 0 and [q.idx for q in st.squares] == [1, 2, 3, 4]
    assert [q.open_ends for q in st.squares] == [q.open_ends for q in full[4:]]


def test_seed_scan_uses_only_feasibility():
    assert scan_seeds(load_suite("smoke-v1"), 1, 2) == [1, 2]
