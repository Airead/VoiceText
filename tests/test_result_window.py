"""Tests for the result preview panel."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


# Mock AppKit/Foundation before importing the module
@pytest.fixture(autouse=True)
def mock_appkit(monkeypatch):
    """Provide mock AppKit and Foundation modules for headless testing."""
    mock_nsobj = MagicMock()

    mock_appkit_mod = MagicMock()
    # Set real integer values for keyboard event constants
    mock_appkit_mod.NSCommandKeyMask = 1 << 20
    mock_appkit_mod.NSShiftKeyMask = 1 << 17
    mock_appkit_mod.NSDeviceIndependentModifierFlagsMask = 0xFFFF0000
    mock_appkit_mod.NSKeyDownMask = 1 << 10

    modules = {
        "AppKit": mock_appkit_mod,
        "Foundation": MagicMock(),
        "objc": MagicMock(),
        "PyObjCTools": MagicMock(),
        "PyObjCTools.AppHelper": MagicMock(),
    }

    for name, mod in modules.items():
        monkeypatch.setitem(__import__("sys").modules, name, mod)


def _setup_panel_with_final_field(panel):
    """Set up a panel with mocked _final_text_field for testing."""
    panel._build_panel = MagicMock()
    panel._panel = MagicMock()
    panel._final_text_field = MagicMock()
    return panel


class TestResultPreviewPanelCallbacks:
    """Test confirm/cancel callback mechanism."""

    def test_confirm_triggers_callback_with_text(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "final text"
        confirmed_text = []

        panel.show(
            asr_text="raw asr",
            show_enhance=False,
            on_confirm=lambda t, info=None: confirmed_text.append(t),
            on_cancel=MagicMock(),
        )

        panel.confirmClicked_(None)

        assert confirmed_text == ["final text"]

    def test_cancel_triggers_callback(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()
        cancelled = []

        panel.show(
            asr_text="raw asr",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=lambda: cancelled.append(True),
        )

        panel.cancelClicked_(None)

        assert cancelled == [True]

    def test_confirm_closes_panel(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "text"
        mock_panel = panel._panel

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        panel.confirmClicked_(None)

        mock_panel.orderOut_.assert_called_once_with(None)

    def test_cancel_closes_panel(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        mock_panel = MagicMock()
        panel._panel = mock_panel

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        panel.cancelClicked_(None)

        mock_panel.orderOut_.assert_called_once_with(None)


class TestResultPreviewPanelCorrectionInfo:
    """Test correction_info passed via on_confirm callback."""

    def test_correction_info_when_user_edited_with_enhance(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "user corrected"
        panel._enhance_text_view = MagicMock()
        panel._enhance_text_view.string.return_value = "ai enhanced"

        results = []

        panel.show(
            asr_text="raw asr",
            show_enhance=True,
            on_confirm=lambda text, info: results.append((text, info)),
            on_cancel=MagicMock(),
        )

        # Simulate user editing
        panel._on_user_edit()
        panel.confirmClicked_(None)

        assert len(results) == 1
        text, info = results[0]
        assert text == "user corrected"
        assert info is not None
        assert info["asr_text"] == "raw asr"
        assert info["enhanced_text"] == "ai enhanced"
        assert info["final_text"] == "user corrected"

    def test_correction_info_none_when_not_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "text"
        panel._enhance_text_view = MagicMock()

        results = []

        panel.show(
            asr_text="raw asr",
            show_enhance=True,
            on_confirm=lambda text, info: results.append((text, info)),
            on_cancel=MagicMock(),
        )

        # No user edit
        panel.confirmClicked_(None)

        assert results[0][1] is None

    def test_correction_info_none_when_no_enhance(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "text"

        results = []

        panel.show(
            asr_text="raw asr",
            show_enhance=False,
            on_confirm=lambda text, info: results.append((text, info)),
            on_cancel=MagicMock(),
        )

        panel._on_user_edit()
        panel.confirmClicked_(None)

        assert results[0][1] is None


class TestResultPreviewPanelEnhanceUpdate:
    """Test AI enhancement result update logic."""

    def test_set_enhance_result_updates_text_when_not_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = False
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_field = MagicMock()

        # Simulate callAfter executing immediately
        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("enhanced text")

        panel._enhance_text_view.setString_.assert_called_with("enhanced text")
        panel._final_text_field.setStringValue_.assert_called_with("enhanced text")

    def test_set_enhance_result_skips_final_when_user_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = True
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_field = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("enhanced text")

        panel._enhance_text_view.setString_.assert_called_with("enhanced text")
        panel._final_text_field.setStringValue_.assert_not_called()

    def test_set_enhance_result_updates_label(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = False
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_field = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("done")

        panel._enhance_label.setStringValue_.assert_called_with("AI Enhancement")

    def test_set_enhance_result_noop_when_no_enhance_view(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._enhance_text_view = None

        # Should not raise
        panel.set_enhance_result("text")


class TestResultPreviewPanelKeyHandling:
    """Test that Enter confirms and the text field uses NSTextField behavior."""

    def test_enter_triggers_confirm_via_button_key_equivalent(self):
        """NSTextField does not consume Enter, so the confirm button's
        keyEquivalent (\\r) fires directly. Verify confirmClicked_ works."""
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "text"

        confirmed = []
        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=lambda t, info=None: confirmed.append(t),
            on_cancel=MagicMock(),
        )

        panel.confirmClicked_(None)
        assert confirmed == ["text"]


class TestResultPreviewPanelUserEdit:
    """Test user edit tracking."""

    def test_user_edit_flag_set_on_edit(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        assert panel._user_edited is False

        panel._on_user_edit()

        assert panel._user_edited is True

    def test_user_edit_flag_reset_on_show(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = True
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="text",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._user_edited is False


class TestResultPreviewPanelVisibility:
    """Test is_visible and bring_to_front."""

    def test_is_visible_true_when_panel_visible(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._panel = MagicMock()
        panel._panel.isVisible.return_value = True

        assert panel.is_visible is True

    def test_is_visible_false_when_panel_none(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        assert panel.is_visible is False

    def test_is_visible_false_when_panel_hidden(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._panel = MagicMock()
        panel._panel.isVisible.return_value = False

        assert panel.is_visible is False

    def test_bring_to_front_when_visible(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._panel = MagicMock()
        panel._panel.isVisible.return_value = True

        panel.bring_to_front()

        panel._panel.makeKeyAndOrderFront_.assert_called_once_with(None)

    def test_bring_to_front_noop_when_no_panel(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        # Should not raise
        panel.bring_to_front()

    def test_bring_to_front_noop_when_hidden(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._panel = MagicMock()
        panel._panel.isVisible.return_value = False

        panel.bring_to_front()

        panel._panel.makeKeyAndOrderFront_.assert_not_called()


class TestResultPreviewPanelLayout:
    """Test layout switching based on show_enhance."""

    def test_show_enhance_false_hides_enhance_section(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="text",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._show_enhance is False

    def test_show_enhance_true_shows_enhance_section(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        panel.show(
            asr_text="text",
            show_enhance=True,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._show_enhance is True


class TestResultPreviewPanelThreading:
    """Test that callbacks work correctly with threading.Event pattern."""

    def test_confirm_unblocks_waiting_thread(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        panel._final_text_field.stringValue.return_value = "result"

        event = threading.Event()
        result_holder = {"text": None}

        def on_confirm(text, correction_info=None):
            result_holder["text"] = text
            event.set()

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=on_confirm,
            on_cancel=lambda: event.set(),
        )

        # Simulate confirm from another thread
        panel.confirmClicked_(None)

        assert event.wait(timeout=1)
        assert result_holder["text"] == "result"

    def test_cancel_unblocks_waiting_thread(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._build_panel = MagicMock()
        panel._panel = MagicMock()

        event = threading.Event()
        cancelled = []

        def on_cancel():
            cancelled.append(True)
            event.set()

        panel.show(
            asr_text="asr",
            show_enhance=False,
            on_confirm=lambda t, info=None: event.set(),
            on_cancel=on_cancel,
        )

        panel.cancelClicked_(None)

        assert event.wait(timeout=1)
        assert cancelled == [True]


class TestResultPreviewPanelModeSwitch:
    """Test mode switcher (NSSegmentedControl) in preview panel."""

    def test_show_stores_available_modes(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        modes = [("off", "Off"), ("proofread", "Proofread"), ("format", "Format")]

        panel.show(
            asr_text="text",
            show_enhance=True,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
            available_modes=modes,
            current_mode="proofread",
        )

        assert panel._available_modes == modes
        assert panel._current_mode == "proofread"

    def test_mode_change_callback_invoked(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())
        modes = [("off", "Off"), ("proofread", "Proofread"), ("format", "Format")]
        changed_modes = []

        panel.show(
            asr_text="text",
            show_enhance=True,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
            available_modes=modes,
            current_mode="off",
            on_mode_change=lambda m: changed_modes.append(m),
        )

        # Simulate selecting segment index 2 ("format")
        panel._on_segment_changed(2)

        assert changed_modes == ["format"]
        assert panel._current_mode == "format"

    def test_set_enhance_loading_resets_user_edited(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._user_edited = True
        panel._enhance_label = MagicMock()
        panel._enhance_text_view = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_loading()

        assert panel._user_edited is False

    def test_set_enhance_loading_shows_spinner_label(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._enhance_label = MagicMock()
        panel._enhance_text_view = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_loading()

        panel._enhance_label.setStringValue_.assert_called_with(
            "AI Enhancement  \u23f3 Processing..."
        )
        panel._enhance_text_view.setString_.assert_called_with("")

    def test_set_enhance_off_clears_and_restores_asr(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._asr_text = "original asr"
        panel._user_edited = False
        panel._enhance_label = MagicMock()
        panel._enhance_text_view = MagicMock()
        panel._final_text_field = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_off()

        panel._enhance_label.setStringValue_.assert_called_with(
            "AI Enhancement (Off)"
        )
        panel._enhance_text_view.setString_.assert_called_with("")
        panel._final_text_field.setStringValue_.assert_called_with("original asr")
        assert panel._show_enhance is False

    def test_set_enhance_result_ignores_stale_request_id(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._enhance_request_id = 3
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_field = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            # Send result with stale request_id=1
            panel.set_enhance_result("stale result", request_id=1)

        # Should not update anything because request_id is stale
        panel._enhance_text_view.setString_.assert_not_called()

    def test_set_enhance_result_accepts_current_request_id(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = ResultPreviewPanel()
        panel._enhance_request_id = 3
        panel._user_edited = False
        panel._enhance_text_view = MagicMock()
        panel._enhance_label = MagicMock()
        panel._final_text_field = MagicMock()

        with patch("PyObjCTools.AppHelper") as mock_helper:
            mock_helper.callAfter.side_effect = lambda fn: fn()
            panel.set_enhance_result("current result", request_id=3)

        panel._enhance_text_view.setString_.assert_called_with("current result")
        panel._final_text_field.setStringValue_.assert_called_with("current result")

    def test_backward_compat_show_without_modes(self):
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())

        # Call show() without the new parameters — should work as before
        panel.show(
            asr_text="text",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._available_modes == []
        assert panel._current_mode == "off"
        assert panel._on_mode_change is None
        assert panel._mode_segment is None


def _make_key_event(char, command=True, shift=False):
    """Create a mock NSEvent for keyboard shortcut testing."""
    event = MagicMock()
    event.charactersIgnoringModifiers.return_value = char

    # Build modifier flags: NSCommandKeyMask = 1 << 20, NSShiftKeyMask = 1 << 17
    # NSDeviceIndependentModifierFlagsMask = 0xFFFF0000
    flags = 0
    if command:
        flags |= 1 << 20  # NSCommandKeyMask
    if shift:
        flags |= 1 << 17  # NSShiftKeyMask
    event.modifierFlags.return_value = flags
    return event


def _make_panel_with_modes(modes=None, current_mode="off"):
    """Create a ResultPreviewPanel set up with modes for keyboard shortcut testing."""
    from voicetext.result_window import ResultPreviewPanel

    if modes is None:
        modes = [
            ("off", "Off"),
            ("proofread", "Proofread"),
            ("format", "Format"),
            ("complete", "Complete"),
            ("enhance", "Enhance"),
            ("translate_en", "Translate EN"),
        ]

    panel = _setup_panel_with_final_field(ResultPreviewPanel())
    panel._mode_segment = MagicMock()
    changed_modes = []

    panel.show(
        asr_text="text",
        show_enhance=True,
        on_confirm=MagicMock(),
        on_cancel=MagicMock(),
        available_modes=modes,
        current_mode=current_mode,
        on_mode_change=lambda m: changed_modes.append(m),
    )

    return panel, changed_modes


class TestResultPreviewPanelKeyboardShortcuts:
    """Test ⌘1~⌘N keyboard shortcuts for mode switching."""

    def test_cmd_number_switches_mode(self):
        """⌘2 should switch to index 1 (proofread), update segment and trigger callback."""
        panel, changed_modes = _make_panel_with_modes()
        panel._panel.isKeyWindow.return_value = True

        event = _make_key_event("2", command=True)
        result = panel._handle_key_event(event)

        assert result is None  # Event consumed
        panel._mode_segment.setSelectedSegment_.assert_called_with(1)
        assert changed_modes == ["proofread"]

    def test_cmd_number_out_of_range_ignored(self):
        """⌘9 with only 6 modes should pass through."""
        panel, changed_modes = _make_panel_with_modes()
        panel._panel.isKeyWindow.return_value = True

        event = _make_key_event("9", command=True)
        result = panel._handle_key_event(event)

        assert result is event  # Event not consumed
        panel._mode_segment.setSelectedSegment_.assert_not_called()
        assert changed_modes == []

    def test_plain_number_key_passthrough(self):
        """Number key without Command modifier should pass through."""
        panel, changed_modes = _make_panel_with_modes()
        panel._panel.isKeyWindow.return_value = True

        event = _make_key_event("2", command=False)
        result = panel._handle_key_event(event)

        assert result is event
        panel._mode_segment.setSelectedSegment_.assert_not_called()
        assert changed_modes == []

    def test_event_monitor_installed_on_show(self):
        """show() with available_modes should install event monitor."""
        panel, _ = _make_panel_with_modes()

        assert panel._event_monitor is not None

    def test_event_monitor_removed_on_close(self):
        """close() should remove event monitor."""
        panel, _ = _make_panel_with_modes()
        assert panel._event_monitor is not None

        panel.close()

        assert panel._event_monitor is None

    def test_event_ignored_when_panel_not_key_window(self):
        """When panel is not key window, events should pass through."""
        panel, changed_modes = _make_panel_with_modes()
        panel._panel.isKeyWindow.return_value = False

        event = _make_key_event("1", command=True)
        result = panel._handle_key_event(event)

        assert result is event
        assert changed_modes == []

    def test_no_monitor_when_no_modes(self):
        """Without available_modes, no event monitor should be installed."""
        from voicetext.result_window import ResultPreviewPanel

        panel = _setup_panel_with_final_field(ResultPreviewPanel())

        panel.show(
            asr_text="text",
            show_enhance=False,
            on_confirm=MagicMock(),
            on_cancel=MagicMock(),
        )

        assert panel._event_monitor is None

    def test_cmd_shift_number_passthrough(self):
        """⌘+Shift+number should not be intercepted."""
        panel, changed_modes = _make_panel_with_modes()
        panel._panel.isKeyWindow.return_value = True

        event = _make_key_event("2", command=True, shift=True)
        result = panel._handle_key_event(event)

        assert result is event
        assert changed_modes == []
