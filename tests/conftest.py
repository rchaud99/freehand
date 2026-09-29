import pytest


@pytest.fixture(autouse=True)
def strict_episodes(monkeypatch):
    """A bug inside an episode fails the test (freehand.episode.loop.STRICT_ENV) instead of becoming status "error"."""
    monkeypatch.setenv("FREEHAND_STRICT", "1")


@pytest.fixture
def results_root(tmp_path, monkeypatch):
    """An isolated results root (FREEHAND_RESULTS) for tests that run experiments."""
    root = tmp_path / "results"
    monkeypatch.setenv("FREEHAND_RESULTS", str(root))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return root
