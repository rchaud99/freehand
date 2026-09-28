"""Named seed streams: legacy tags are the historical integers; new streams are hashed and independent."""
import numpy as np
import pytest

from freehand import seeding


def test_legacy_streams_are_the_historical_generators():
    # The historical code drew page layout from default_rng([seed, 1]), plotter-change draws from [seed, 99],
    # landing noise from [seed, 1000 + stroke], landed-end measurement noise from [seed, 23, stroke].
    for stream, keys, entropy in (("page.layout", (), [10, 1]), ("plotter.map", (), [10, 99]),
                                  ("landing", (7,), [10, 1007]), ("measure.landed", (3,), [10, 23, 3]),
                                  ("page.highlight", (5,), [10, 3, 5]), ("camera.pose", (2,), [10, 50, 2]),
                                  ("study.configuration", (), [10, 883])):
        a = seeding.rng(10, stream, *keys).normal(size=5)
        b = np.random.default_rng(entropy).normal(size=5)
        np.testing.assert_array_equal(a, b)


def test_hashed_tags_are_stable_and_outside_the_legacy_range():
    t = seeding.hashed_tag("one_shot.targets")
    assert t == 3248845801                       # pinned: renaming or re-hashing would change new suites' data
    assert t >= seeding.HASHED_TAG_BASE > max(s.tag or 0 for s in seeding.STREAMS.values())


def test_streams_are_independent():
    # Drawing any amount from one stream does not shift another.
    a = seeding.rng(3, "page.layout").uniform(size=3)
    _ = seeding.rng(3, "plotter.map").uniform(size=1000)
    b = seeding.rng(3, "page.layout").uniform(size=3)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(seeding.rng(3, "page.layout").uniform(size=3),
                              seeding.rng(3, "warp.phase").uniform(size=3))


def test_unknown_stream_is_an_error():
    with pytest.raises(KeyError, match="unknown random stream"):
        seeding.rng(1, "no.such.stream")
