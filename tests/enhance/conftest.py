"""Shared fixtures for wenzi.enhance tests."""

import pytest


@pytest.fixture(autouse=True)
def _fast_common_words(monkeypatch):
    """Skip loading 8MB word list files — not needed for enhance test logic."""
    monkeypatch.setattr(
        "wenzi.enhance.vocabulary_builder._load_common_words",
        lambda: set(),
    )
