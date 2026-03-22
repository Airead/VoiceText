"""Tests for the command source."""

import pytest

from wenzi.scripting.sources import ChooserItem, ModifierAction
from wenzi.scripting.sources.command_source import (
    COMMAND_PREFIX,
    CommandEntry,
    CommandSource,
)


class TestCommandEntry:
    def test_valid_name(self):
        src = CommandSource()
        src.register(CommandEntry(name="reload-scripts", title="Reload"))
        assert "reload-scripts" in src._commands

    def test_invalid_name_space(self):
        src = CommandSource()
        with pytest.raises(ValueError, match="Invalid command name"):
            src.register(CommandEntry(name="reload scripts", title="Reload"))

    def test_invalid_name_empty(self):
        src = CommandSource()
        with pytest.raises(ValueError, match="Invalid command name"):
            src.register(CommandEntry(name="", title="Reload"))

    def test_invalid_name_starts_with_hyphen(self):
        src = CommandSource()
        with pytest.raises(ValueError, match="Invalid command name"):
            src.register(CommandEntry(name="-reload", title="Reload"))

    def test_valid_name_with_colon(self):
        src = CommandSource()
        src.register(CommandEntry(name="cc-sessions:clear-cache", title="Clear"))
        assert "cc-sessions:clear-cache" in src._commands

    def test_valid_name_with_underscores(self):
        src = CommandSource()
        src.register(CommandEntry(name="reload_scripts", title="Reload"))
        assert "reload_scripts" in src._commands

    def test_overwrite_warning(self):
        src = CommandSource()
        src.register(CommandEntry(name="foo", title="Foo v1"))
        src.register(CommandEntry(name="foo", title="Foo v2"))
        assert src._commands["foo"].title == "Foo v2"


class TestCommandSourceSearch:
    def _make_source(self):
        src = CommandSource()
        src.register(CommandEntry(
            name="reload", title="Reload Scripts",
            subtitle="Reload all user scripts",
            action=lambda args: None,
        ))
        src.register(CommandEntry(
            name="greet", title="Greet",
            subtitle="Say hello",
            action=lambda args: None,
        ))
        src.register(CommandEntry(
            name="greet-all", title="Greet All",
            subtitle="Say hello to everyone",
            action=lambda args: None,
        ))
        return src

    def test_empty_query_returns_all(self):
        src = self._make_source()
        items = src.search("")
        assert len(items) == 3
        # Sorted by name
        assert items[0].title == "Greet"
        assert items[1].title == "Greet All"
        assert items[2].title == "Reload Scripts"

    def test_fuzzy_match_title(self):
        src = self._make_source()
        items = src.search("reload")
        assert len(items) == 1
        assert items[0].title == "Reload Scripts"

    def test_fuzzy_match_name(self):
        src = self._make_source()
        items = src.search("gre")
        titles = [i.title for i in items]
        assert "Greet" in titles
        assert "Greet All" in titles

    def test_no_match(self):
        src = self._make_source()
        items = src.search("xyz")
        assert items == []

    def test_args_mode_exact_match(self):
        src = self._make_source()
        items = src.search("greet Alice")
        assert len(items) == 1
        assert items[0].title == "Greet"
        assert "Alice" in items[0].subtitle

    def test_args_mode_empty_args(self):
        src = self._make_source()
        items = src.search("greet ")
        assert len(items) == 1
        assert items[0].title == "Greet"

    def test_args_mode_no_exact_match_falls_through(self):
        """If first word doesn't exactly match a command, treat as fuzzy search."""
        src = self._make_source()
        # "gre Alice" — "gre" is not an exact command name
        items = src.search("gre Alice")
        # No fuzzy match for "gre Alice" as a whole against any title/name
        assert items == []

    def test_leading_spaces_stripped(self):
        src = self._make_source()
        items = src.search("  greet")
        assert len(items) >= 1
        assert any(i.title == "Greet" for i in items)

    def test_item_id_prefixed(self):
        src = self._make_source()
        items = src.search("")
        for item in items:
            assert item.item_id.startswith("cmd:")


class TestCommandSourceAction:
    def test_action_receives_args(self):
        received = []
        src = CommandSource()
        src.register(CommandEntry(
            name="echo", title="Echo",
            action=lambda args: received.append(args),
        ))
        items = src.search("echo hello world")
        assert len(items) == 1
        items[0].action()
        assert received == ["hello world"]

    def test_action_receives_empty_args(self):
        received = []
        src = CommandSource()
        src.register(CommandEntry(
            name="echo", title="Echo",
            action=lambda args: received.append(args),
        ))
        items = src.search("echo ")
        items[0].action()
        assert received == [""]

    def test_action_without_args_mode(self):
        received = []
        src = CommandSource()
        src.register(CommandEntry(
            name="echo", title="Echo",
            action=lambda args: received.append(args),
        ))
        items = src.search("echo")
        items[0].action()
        assert received == [""]

    def test_modifier_action_receives_args(self):
        received = []
        src = CommandSource()
        src.register(CommandEntry(
            name="deploy", title="Deploy",
            action=lambda args: None,
            modifiers={
                "alt": ModifierAction(
                    subtitle="Force deploy",
                    action=lambda args: received.append(args),
                ),
            },
        ))
        items = src.search("deploy production")
        assert items[0].modifiers is not None
        items[0].modifiers["alt"].action()
        assert received == ["production"]


class TestCommandSourceComplete:
    def test_complete_returns_name_with_space(self):
        src = CommandSource()
        src.register(CommandEntry(name="greet", title="Greet"))
        items = src.search("gre")
        assert len(items) >= 1
        result = src.complete("gre", items[0])
        assert result == "greet "

    def test_complete_returns_none_for_unknown(self):
        src = CommandSource()
        item = ChooserItem(title="Unknown", item_id="cmd:unknown")
        result = src.complete("unk", item)
        assert result is None

    def test_complete_returns_none_for_non_command_item(self):
        src = CommandSource()
        item = ChooserItem(title="App", item_id="app:safari")
        result = src.complete("app", item)
        assert result is None


class TestCommandSourceUnregister:
    def test_unregister_existing(self):
        src = CommandSource()
        src.register(CommandEntry(name="foo", title="Foo"))
        src.unregister("foo")
        assert "foo" not in src._commands

    def test_unregister_nonexistent(self):
        src = CommandSource()
        src.unregister("foo")  # Should not raise

    def test_clear(self):
        src = CommandSource()
        src.register(CommandEntry(name="a", title="A"))
        src.register(CommandEntry(name="b", title="B"))
        src.clear()
        assert len(src._commands) == 0


class TestCommandSourcePromoted:
    def test_promoted_search_returns_only_promoted(self):
        src = CommandSource()
        src.register(CommandEntry(name="reload", title="Reload", promoted=True))
        src.register(CommandEntry(name="debug", title="Debug Log", promoted=False))
        items = src.promoted_search("re")
        assert len(items) == 1
        assert items[0].title == "Reload"

    def test_promoted_search_empty_query_returns_nothing(self):
        src = CommandSource()
        src.register(CommandEntry(name="reload", title="Reload", promoted=True))
        items = src.promoted_search("")
        assert items == []

    def test_promoted_search_no_promoted_commands(self):
        src = CommandSource()
        src.register(CommandEntry(name="debug", title="Debug Log"))
        items = src.promoted_search("debug")
        assert items == []

    def test_promoted_search_no_args_mode(self):
        """Promoted search does not support args mode — space is part of query."""
        src = CommandSource()
        src.register(CommandEntry(name="reload", title="Reload", promoted=True))
        # "reload foo" as a whole fuzzy-matches nothing (not exact+args)
        items = src.promoted_search("reload foo")
        assert items == []

    def test_promoted_command_also_in_prefixed_search(self):
        src = CommandSource()
        src.register(CommandEntry(name="reload", title="Reload", promoted=True))
        # Promoted commands still appear in the prefixed (>) search
        items = src.search("reload")
        assert len(items) == 1
        assert items[0].title == "Reload"

    def test_promoted_action_receives_empty_args(self):
        received = []
        src = CommandSource()
        src.register(CommandEntry(
            name="reload", title="Reload", promoted=True,
            action=lambda args: received.append(args),
        ))
        items = src.promoted_search("reload")
        items[0].action()
        assert received == [""]


class TestCommandSourceAsChooserSource:
    def test_returns_chooser_source(self):
        src = CommandSource()
        cs = src.as_chooser_source()
        assert cs.name == "commands"
        assert cs.prefix == COMMAND_PREFIX
        assert cs.search is not None
        assert cs.complete is not None
        assert "enter" in cs.action_hints
        assert "tab" in cs.action_hints

    def test_returns_promoted_chooser_source(self):
        src = CommandSource()
        cs = src.as_promoted_chooser_source()
        assert cs.name == "commands-promoted"
        assert cs.prefix is None
        assert cs.search is not None
        assert cs.complete is None
        assert cs.priority == 6
