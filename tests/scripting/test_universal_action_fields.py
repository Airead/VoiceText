"""Tests for universal_action field on ChooserSource and CommandEntry."""

from wenzi.scripting.sources import ChooserSource
from wenzi.scripting.sources.command_source import CommandEntry


class TestUniversalActionFields:
    def test_chooser_source_default_false(self):
        src = ChooserSource(name="test", search=lambda q: [])
        assert src.universal_action is False

    def test_chooser_source_explicit_true(self):
        src = ChooserSource(name="test", search=lambda q: [], universal_action=True)
        assert src.universal_action is True

    def test_command_entry_default_false(self):
        entry = CommandEntry(name="test", title="Test")
        assert entry.universal_action is False

    def test_command_entry_explicit_true(self):
        entry = CommandEntry(name="test", title="Test", universal_action=True)
        assert entry.universal_action is True
