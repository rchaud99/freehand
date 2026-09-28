"""Named, independent random substreams.

Every random draw in the simulation comes from `rng(seed, "<stream name>", *keys)`, which is
`numpy.random.default_rng([seed, *tag(keys)])`, i.e. a PCG64 generator seeded by a `SeedSequence` whose entropy is
the page seed followed by the stream's integer tag (and any per-use keys such as a stroke number).

Why this scheme:
  * Streams are independent: drawing more numbers from one stream (say, a new perturbation's parameters) never shifts
    another stream (say, the page layout). Adding a perturbation therefore never changes an existing page.
  * The tags of the streams that existed before this package are the integers the historical code used
    (`default_rng([seed, 1])` for the page layout, `[seed, 99]` for the plotter change, `[seed, 1000 + stroke]` for
    landing noise, ...). Historical pages, perturbations and ink are therefore regenerated bit for bit, with no
    separate legacy generator. `tests/test_seeding.py` pins this.
  * Streams added later get their tag from a hash of their name, offset into a range the legacy tags never use, so
    they cannot collide with an existing stream.

To add a stream: add a `Stream(...)` to `STREAMS` with a new name and NO explicit tag (the hash tag is derived);
never change an existing tag.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

HASHED_TAG_BASE = 2**31          # legacy tags are all < 2**16; hashed tags live above 2**31


def hashed_tag(name: str) -> int:
    """A stable integer tag for a stream name (above every legacy tag)."""
    return HASHED_TAG_BASE + int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big") % HASHED_TAG_BASE


@dataclass(frozen=True)
class Stream:
    name: str
    doc: str
    tag: int | None = None                                   # None: derived from the name
    key_fn: Callable[..., tuple[int, ...]] | None = None     # maps per-use keys to the entropy suffix

    def entropy_suffix(self, *keys: int) -> tuple[int, ...]:
        if self.key_fn is not None:
            return self.key_fn(*keys)
        tag = self.tag if self.tag is not None else hashed_tag(self.name)
        return (tag, *(int(k) for k in keys))


def _landing(stroke_no: int) -> tuple[int, ...]:
    return (1000 + int(stroke_no),)                          # historical: default_rng([seed, 1000 + stroke_no])


STREAMS: dict[str, Stream] = {s.name: s for s in (
    Stream("page.layout", "square count, sizes, positions, missing sides, hand wobble", 1),
    Stream("page.paper", "paper tone, texture, ghost marks, ink tone field, sensor noise (rendering only)", 2),
    Stream("page.highlight", "jitter of the green outline around the current square; key: square idx", 3),
    Stream("measure.landed", "measurement noise on landed ends reported to stateless-numeric arms; key: stroke", 23),
    Stream("camera.pose", "Freehand A camera homography; key: pose number (1 before, 2 after the move)", 50),
    Stream("camera.noise", "Freehand A raw-frame sensor noise (rendering only)", 60),
    Stream("drift.direction", "L5 drift direction", 71),
    Stream("drift.skip", "L5 skipped-step draws; key: stroke index", 77),
    Stream("attribution.geometry", "L6 camera bump angle / rotation sign / plotter offset direction", 81),
    Stream("plotter.map", "offset direction and rotation sign of the plotter-map changes (also L7's sign)", 99),
    Stream("mirror.threshold", "latent-mirror mode threshold (mm) when not given explicitly", 581),
    Stream("warp.phase", "cross-axis warp phase", 582),
    Stream("study.configuration", "per-seed change time and family parameters of the baseline/model studies", 883),
    Stream("landing", "per-stroke landing offset and wobble; key: stroke number", key_fn=_landing),
)}


def entropy(seed: int, stream: str, *keys: int) -> list[int]:
    """The SeedSequence entropy for (seed, stream, keys)."""
    try:
        s = STREAMS[stream]
    except KeyError:
        raise KeyError(f"unknown random stream {stream!r}; register it in freehand.seeding.STREAMS") from None
    return [int(seed), *s.entropy_suffix(*keys)]


def rng(seed: int, stream: str, *keys: int) -> np.random.Generator:
    """A fresh generator for one named substream of one page seed."""
    return np.random.default_rng(entropy(seed, stream, *keys))


# Fixed seeds of agent-internal and analysis randomness (not page randomness). Kept from the historical code so the
# reference agents and bootstrap intervals reproduce exactly.
AGENT_SEEDS = {
    "map_adaptive": 5,          # B plotter-map adaptive estimator: measurement noise
    "camera_agents": 11,        # Freehand A code agents: pixel perception noise
    "level_adaptive": 13,       # ladder ideal estimator: measurement noise
}
BOOTSTRAP_SEED = 9481           # seed-bootstrap intervals (publication/baseline studies)
PLAN_SHUFFLE_SEED = 281026      # deterministic cell order of the 48-cell model study
