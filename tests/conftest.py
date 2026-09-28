import pytest


@pytest.fixture
def results_root(tmp_path, monkeypatch):
    """An isolated results root (FREEHAND_RESULTS) for tests that run experiments."""
    root = tmp_path / "results"
    monkeypatch.setenv("FREEHAND_RESULTS", str(root))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return root
