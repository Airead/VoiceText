"""Tests for the WebView-based settings panel."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from tests.conftest import mock_panel_close_delegate


@pytest.fixture(autouse=True)
def _mock_appkit(mock_appkit_modules, monkeypatch):
    """Mock AppKit, Foundation, and WebKit modules for headless testing."""
    mock_webkit = MagicMock()
    monkeypatch.setitem(sys.modules, "WebKit", mock_webkit)

    import wenzi.ui.settings_window_web as _sw

    _sw._PanelCloseDelegate = None
    mock_panel_close_delegate(monkeypatch, _sw)

    # Mock message handler class
    mock_handler_cls = MagicMock()
    mock_handler_instance = MagicMock()
    mock_handler_cls.alloc.return_value.init.return_value = mock_handler_instance
    monkeypatch.setattr(_sw, "_get_message_handler_class", lambda: mock_handler_cls)

    return mock_appkit_modules


def _make_state():
    """Create a minimal settings state dict for testing."""
    return {
        "language": "auto",
        "hotkeys": {"fn": True, "right_command": False},
        "sound_enabled": True,
        "visual_indicator": True,
        "preview": True,
        "current_preset_id": "funasr-paraformer",
        "current_remote_asr": None,
        "stt_presets": [
            ("funasr-paraformer", "FunASR Paraformer", True),
            ("apple-speech", "Apple Speech", True),
        ],
        "stt_remote_models": [],
        "llm_models": [
            ("ollama", "qwen2.5:7b", "ollama / qwen2.5:7b"),
        ],
        "current_llm": ("ollama", "qwen2.5:7b"),
        "enhance_modes": [
            ("proofread", "Proofread", 10),
            ("format", "Format", 30),
        ],
        "current_enhance_mode": "proofread",
        "model_timeout": 10,
        "thinking": False,
        "vocab_enabled": True,
        "vocab_count": 42,
        "auto_build": True,
        "history_enabled": False,
        "history_max_entries": 100,
        "history_refresh_threshold": 50,
        "input_context_level": "basic",
        "config_dir": "/tmp/test-config",
        "scripting_enabled": False,
        "launcher": {
            "enabled": True,
            "hotkey": {"key": "space", "modifiers": ["option"]},
            "sources": {},
        },
        "last_tab": "general",
    }


def _make_callbacks():
    """Create a dict of mock callbacks matching SettingsController."""
    names = [
        "on_hotkey_toggle", "on_hotkey_mode_select", "on_hotkey_delete",
        "on_record_hotkey", "on_restart_key_select", "on_cancel_key_select",
        "on_scripting_toggle", "on_sound_toggle", "on_visual_toggle",
        "on_device_name_toggle", "on_preview_toggle",
        "on_stt_select", "on_stt_remote_select",
        "on_stt_add_provider", "on_stt_remove_provider",
        "on_llm_select", "on_llm_add_provider", "on_llm_remove_provider",
        "on_model_timeout",
        "on_enhance_mode_select", "on_enhance_mode_edit", "on_enhance_add_mode",
        "on_thinking_toggle", "on_vocab_toggle", "on_auto_build_toggle",
        "on_history_toggle", "on_history_max_entries",
        "on_history_refresh_threshold", "on_input_context_change",
        "on_vocab_build_model_select", "on_vocab_build",
        "on_tab_change", "on_reveal_config_folder",
        "on_config_dir_browse", "on_config_dir_reset",
        "on_launcher_toggle", "on_launcher_hotkey_record",
        "on_launcher_hotkey_clear", "on_launcher_source_toggle",
        "on_launcher_prefix_change", "on_launcher_usage_learning_toggle",
        "on_launcher_switch_english_toggle", "on_launcher_refresh_icons",
        "on_launcher_source_hotkey_record", "on_launcher_source_hotkey_clear",
        "on_new_snippet_hotkey_record", "on_new_snippet_hotkey_clear",
        "on_language_change", "_reopen",
    ]
    return {name: MagicMock(name=name) for name in names}


class TestSettingsWebPanelInit:
    def test_init_defaults(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        assert panel._panel is None
        assert panel._webview is None
        assert not panel.is_visible

    def test_show_creates_panel(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        assert panel._panel is not None
        assert panel._webview is not None

    def test_show_stores_callbacks(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        callbacks = _make_callbacks()
        panel.show(_make_state(), callbacks)
        assert panel._callbacks is callbacks

    def test_close_clears_delegate(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        panel.close()
        assert panel._close_delegate is None

    def test_is_visible_after_show(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        # Mock panel.isVisible() returns MagicMock (truthy)
        assert panel.is_visible

    def test_close_then_reopen(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        panel.close()
        assert panel._panel is None
        # Reopen should work
        panel.show(_make_state(), _make_callbacks())
        assert panel._panel is not None

    def test_message_after_close_ignored(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel

        panel = SettingsWebPanel()
        cbs = _make_callbacks()
        panel.show(_make_state(), cbs)
        panel.close()
        # Should not raise or call callback
        panel._handle_js_message({"type": "callback", "name": "on_sound_toggle", "args": [True]})
        cbs["on_sound_toggle"].assert_not_called()


class TestCallbackDispatch:
    def _make_panel(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        callbacks = _make_callbacks()
        panel.show(_make_state(), callbacks)
        return panel, callbacks

    def test_callback_with_no_args(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "callback", "name": "on_record_hotkey", "args": []})
        cbs["on_record_hotkey"].assert_called_once_with()

    def test_callback_with_one_arg(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "callback", "name": "on_sound_toggle", "args": [True]})
        cbs["on_sound_toggle"].assert_called_once_with(True)

    def test_callback_with_two_args(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "callback", "name": "on_hotkey_toggle", "args": ["fn", False]})
        cbs["on_hotkey_toggle"].assert_called_once_with("fn", False)

    def test_callback_with_two_args_llm(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "callback", "name": "on_llm_select", "args": ["ollama", "qwen2.5:7b"]})
        cbs["on_llm_select"].assert_called_once_with("ollama", "qwen2.5:7b")

    def test_unknown_callback_ignored(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "callback", "name": "nonexistent", "args": []})

    def test_callback_exception_logged_not_raised(self):
        panel, cbs = self._make_panel()
        cbs["on_sound_toggle"].side_effect = RuntimeError("boom")
        panel._handle_js_message({"type": "callback", "name": "on_sound_toggle", "args": [True]})

    def test_tab_change_callback(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "callback", "name": "on_tab_change", "args": ["llm"]})
        cbs["on_tab_change"].assert_called_once_with("llm")

    def test_unknown_message_type_ignored(self):
        panel, cbs = self._make_panel()
        panel._handle_js_message({"type": "unknown", "data": "foo"})


class TestPrepareState:
    def test_stt_presets_converted(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        prepared = panel._prepare_state(state)
        assert prepared["stt_presets"] == [
            {"id": "funasr-paraformer", "name": "FunASR Paraformer", "available": True},
            {"id": "apple-speech", "name": "Apple Speech", "available": True},
        ]

    def test_llm_models_converted(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        prepared = panel._prepare_state(state)
        assert prepared["llm_models"] == [
            {"provider": "ollama", "model": "qwen2.5:7b", "display": "ollama / qwen2.5:7b"},
        ]

    def test_current_llm_converted(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        prepared = panel._prepare_state(state)
        assert prepared["current_llm"] == {"provider": "ollama", "model": "qwen2.5:7b"}

    def test_enhance_modes_converted(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        prepared = panel._prepare_state(state)
        assert prepared["enhance_modes"] == [
            {"id": "proofread", "name": "Proofread", "order": 10},
            {"id": "format", "name": "Format", "order": 30},
        ]

    def test_stt_remote_models_converted(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        state["stt_remote_models"] = [("openai", "whisper-1", "OpenAI / whisper-1")]
        prepared = panel._prepare_state(state)
        assert prepared["stt_remote_models"] == [
            {"provider": "openai", "model": "whisper-1", "display": "OpenAI / whisper-1"},
        ]

    def test_non_tuple_fields_preserved(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        prepared = panel._prepare_state(state)
        assert prepared["sound_enabled"] is True
        assert prepared["vocab_count"] == 42
        assert prepared["config_dir"] == "/tmp/test-config"

    def test_last_tab_models_mapped_to_speech(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        state = _make_state()
        state["last_tab"] = "models"
        prepared = panel._prepare_state(state)
        assert prepared["last_tab"] == "speech"


class TestUpdateState:
    def test_update_state_calls_evaluate_js(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        panel.update_state({"sound_enabled": False})
        panel._webview.evaluateJavaScript_completionHandler_.assert_called()
        js_call = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "_updateState(" in js_call
        assert '"sound_enabled": false' in js_call

    def test_update_state_noop_when_not_visible(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        panel.update_state({"sound_enabled": False})

    def test_update_state_runs_prepare_state(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        panel.update_state({
            "stt_presets": [("apple-speech", "Apple Speech", True)],
        })
        js_call = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert '"id": "apple-speech"' in js_call


class TestPrepareStateExtended:
    """Tests for new _prepare_state transformations."""

    def test_hotkeys_converted_to_structured(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"hotkeys": {"fn": True, "right_command": False}}
        prepared = SettingsWebPanel._prepare_state(state)
        assert prepared["hotkeys"]["fn"] == {
            "enabled": True, "mode": None, "label": "fn",
        }
        assert prepared["hotkeys"]["right_command"]["enabled"] is False

    def test_hotkeys_dict_value_extracts_mode(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"hotkeys": {"fn": {"mode": "toggle"}}}
        prepared = SettingsWebPanel._prepare_state(state)
        assert prepared["hotkeys"]["fn"]["mode"] == "toggle"
        assert prepared["hotkeys"]["fn"]["enabled"] is True

    def test_vocab_build_model_tuple_to_string(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"vocab_build_model": ("ollama", "qwen2.5:7b")}
        prepared = SettingsWebPanel._prepare_state(state)
        assert prepared["vocab_build_model"] == "ollama/qwen2.5:7b"

    def test_vocab_build_model_none_to_empty(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"vocab_build_model": None}
        prepared = SettingsWebPanel._prepare_state(state)
        assert prepared["vocab_build_model"] == ""

    def test_current_remote_asr_tuple_to_list(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"current_remote_asr": ("openai", "whisper-1")}
        prepared = SettingsWebPanel._prepare_state(state)
        assert prepared["current_remote_asr"] == ["openai", "whisper-1"]

    def test_current_remote_asr_none_preserved(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"current_remote_asr": None}
        prepared = SettingsWebPanel._prepare_state(state)
        assert prepared["current_remote_asr"] is None

    def test_i18n_injected(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        state = {"sound_enabled": True}
        prepared = SettingsWebPanel._prepare_state(state)
        # Should have i18n key (even if empty dict due to test env)
        assert "i18n" in prepared


class TestUpdateMethods:
    """Tests for update_stt_model, update_config_dir, etc."""

    def _make_panel(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        panel.show(_make_state(), _make_callbacks())
        return panel

    def test_update_stt_model(self):
        panel = self._make_panel()
        panel.update_stt_model("apple-speech", None)
        panel._webview.evaluateJavaScript_completionHandler_.assert_called()
        js_call = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "_updateSttSelection(" in js_call
        assert "apple-speech" in js_call

    def test_update_config_dir(self):
        panel = self._make_panel()
        panel.update_config_dir("/new/path")
        panel._webview.evaluateJavaScript_completionHandler_.assert_called()
        js_call = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "/new/path" in js_call

    def test_update_launcher_hotkey(self):
        panel = self._make_panel()
        panel.update_launcher_hotkey("cmd+space")
        panel._webview.evaluateJavaScript_completionHandler_.assert_called()
        js_call = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "cmd+space" in js_call

    def test_update_source_hotkey(self):
        panel = self._make_panel()
        panel.update_source_hotkey("clipboard", "cmd+shift+v")
        panel._webview.evaluateJavaScript_completionHandler_.assert_called()

    def test_update_new_snippet_hotkey(self):
        panel = self._make_panel()
        panel.update_new_snippet_hotkey("cmd+shift+n")
        panel._webview.evaluateJavaScript_completionHandler_.assert_called()
        js_call = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "cmd+shift+n" in js_call

    def test_update_methods_noop_when_not_visible(self):
        from wenzi.ui.settings_window_web import SettingsWebPanel
        panel = SettingsWebPanel()
        # Should not raise
        panel.update_stt_model("x", None)
        panel.update_config_dir("/x")
        panel.update_launcher_hotkey("x")
        panel.update_source_hotkey("x", "y")
        panel.update_new_snippet_hotkey("x")
