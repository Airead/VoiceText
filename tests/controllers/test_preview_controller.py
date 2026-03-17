"""Tests for PreviewController enhance mode debounce and history caching."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from wenzi.controllers.preview_controller import PreviewController
from wenzi.enhance.preview_history import PreviewRecord


@pytest.fixture
def mock_app():
    """Create a mock WenZiApp for PreviewController."""
    app = MagicMock()
    app._enhance_mode = "proofread"
    app._enhance_controller = MagicMock()
    app._enhance_controller.get_cached.return_value = None
    app._enhancer = MagicMock()
    app._enhancer._enabled = True
    app._enhancer.mode = "proofread"
    app._enhance_menu_items = {"off": MagicMock(), "proofread": MagicMock(), "translate": MagicMock()}
    app._preview_panel = MagicMock()
    app._preview_panel.enhance_request_id = 0
    app._current_preview_asr_text = "hello"
    app._config = {"ai_enhance": {"enabled": True, "mode": "proofread"}}
    app._config_path = "/tmp/test.json"
    return app


@pytest.fixture
def ctrl(mock_app):
    return PreviewController(mock_app)


class TestEnhanceModeDebounce:
    """Tests for debounced enhancement on mode switch."""

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_single_switch_fires_after_debounce(self, mock_save, ctrl, mock_app):
        """A single mode switch should fire enhancement after debounce delay."""
        # Use a very short debounce for testing
        ctrl._ENHANCE_DEBOUNCE_SECONDS = 0.05

        ctrl.on_preview_mode_change("translate")

        # Enhancement should NOT have started yet
        mock_app._enhance_controller.run.assert_not_called()
        # A debounce timer should be active
        assert ctrl._enhance_debounce_timer is not None

        # Wait for debounce to fire
        time.sleep(0.3)

        mock_app._enhance_controller.run.assert_called_once()

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_rapid_switches_fire_only_once(self, mock_save, ctrl, mock_app):
        """Rapid mode switches should only fire one enhancement request."""
        ctrl._ENHANCE_DEBOUNCE_SECONDS = 0.05

        ctrl.on_preview_mode_change("translate")
        ctrl.on_preview_mode_change("proofread")
        ctrl.on_preview_mode_change("translate")

        # Nothing fired yet
        mock_app._enhance_controller.run.assert_not_called()
        # Cancel should have been called for each switch
        assert mock_app._enhance_controller.cancel.call_count == 3

        # Wait for debounce (generous margin for slow CI machines)
        time.sleep(0.3)

        # Only one call should have fired (for the last mode)
        mock_app._enhance_controller.run.assert_called_once()

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_switch_to_off_cancels_immediately(self, mock_save, ctrl, mock_app):
        """Switching to Off should cancel immediately without debounce."""
        ctrl._ENHANCE_DEBOUNCE_SECONDS = 0.05

        ctrl.on_preview_mode_change("off")

        mock_app._enhance_controller.cancel.assert_called_once()
        # No debounce timer should be active
        assert ctrl._enhance_debounce_timer is None

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_switch_off_cancels_pending_debounce(self, mock_save, ctrl, mock_app):
        """Switching to Off should cancel any pending debounce timer."""
        ctrl._ENHANCE_DEBOUNCE_SECONDS = 0.05

        ctrl.on_preview_mode_change("translate")
        assert ctrl._enhance_debounce_timer is not None

        ctrl.on_preview_mode_change("off")
        assert ctrl._enhance_debounce_timer is None

        # Wait to ensure cancelled timer doesn't fire
        time.sleep(0.3)
        mock_app._enhance_controller.run.assert_not_called()

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_cached_result_replays_immediately(self, mock_save, ctrl, mock_app):
        """If cache hit, replay immediately without debounce."""
        cached = MagicMock()
        mock_app._enhance_controller.get_cached.return_value = cached

        ctrl.on_preview_mode_change("translate")

        mock_app._preview_panel.replay_cached_result.assert_called_once()
        # No debounce timer needed
        assert ctrl._enhance_debounce_timer is None
        # No enhancement run needed
        mock_app._enhance_controller.run.assert_not_called()

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_config_saved_immediately(self, mock_save, ctrl, mock_app):
        """Config should be saved immediately, not debounced."""
        ctrl._ENHANCE_DEBOUNCE_SECONDS = 0.05

        ctrl.on_preview_mode_change("translate")

        mock_save.assert_called_once()
        assert mock_app._config["ai_enhance"]["mode"] == "translate"

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_stale_timer_does_not_fire(self, mock_save, ctrl, mock_app):
        """A stale debounce timer should not fire if request_id changed."""
        ctrl._ENHANCE_DEBOUNCE_SECONDS = 0.05

        ctrl.on_preview_mode_change("translate")
        # Simulate another component bumping the request_id
        mock_app._preview_panel.enhance_request_id = 999

        time.sleep(0.3)

        # Timer fired but guard prevented run()
        mock_app._enhance_controller.run.assert_not_called()


def _make_record(**overrides) -> PreviewRecord:
    defaults = dict(
        timestamp="2026-01-01T00:00:00+00:00",
        created_at="2026-01-01T08:00:00",
        action="confirm",
        asr_text="hello",
        enhanced_text="Hello.",
        final_text="Hello.",
        enhance_mode="proofread",
        stt_model="funasr",
        llm_model="openai/gpt-4o",
        wav_data=b"\x00" * 100,
        audio_duration=2.5,
        source="voice",
    )
    defaults.update(overrides)
    return PreviewRecord(**defaults)


class TestSaveToPreviewHistory:
    """Tests for _save_to_preview_history including system_prompt/thinking_text."""

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_save_includes_system_prompt_and_thinking(self, _mock_save, ctrl, mock_app):
        result_holder = {
            "enhanced_text": "Hello.",
            "system_prompt": "Be helpful.",
            "thinking_text": "Hmm...",
        }
        mock_app._current_preview_asr_text = "hello"
        mock_app._enhance_mode = "proofread"
        mock_app._current_stt_model.return_value = "funasr"
        mock_app._current_llm_model.return_value = "openai/gpt-4o"

        ctrl._save_to_preview_history(
            "ts1", "confirm", result_holder, None, 0.0, "voice",
        )

        rec = ctrl._preview_history.get(0)
        assert rec.system_prompt == "Be helpful."
        assert rec.thinking_text == "Hmm..."

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_save_defaults_when_keys_missing(self, _mock_save, ctrl, mock_app):
        result_holder = {"enhanced_text": "Hello."}
        mock_app._current_preview_asr_text = "hello"
        mock_app._enhance_mode = "proofread"
        mock_app._current_stt_model.return_value = "funasr"
        mock_app._current_llm_model.return_value = "openai/gpt-4o"

        ctrl._save_to_preview_history(
            "ts1", "confirm", result_holder, None, 0.0, "voice",
        )

        rec = ctrl._preview_history.get(0)
        assert rec.system_prompt == ""
        assert rec.thinking_text == ""


class TestHandleHistoryConfirm:
    """Tests for _handle_history_confirm system_prompt/thinking_text update."""

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_updates_prompt_and_thinking_when_present(self, _mock_save, ctrl, mock_app):
        record = _make_record(system_prompt="old", thinking_text="old think")
        ctrl._preview_history.add(record)

        mock_app._enhance_mode = "proofread"
        mock_app._current_stt_model.return_value = "funasr"
        mock_app._current_llm_model.return_value = "openai/gpt-4o"

        result_holder = {
            "text": "Hello.",
            "enhanced_text": "Hello.",
            "system_prompt": "new prompt",
            "thinking_text": "new think",
        }

        ctrl._handle_history_confirm(0, result_holder, None, 0.0, "voice")
        assert record.system_prompt == "new prompt"
        assert record.thinking_text == "new think"

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_preserves_prompt_and_thinking_when_absent(self, _mock_save, ctrl, mock_app):
        record = _make_record(system_prompt="keep", thinking_text="keep think")
        ctrl._preview_history.add(record)

        mock_app._enhance_mode = "proofread"
        mock_app._current_stt_model.return_value = "funasr"
        mock_app._current_llm_model.return_value = "openai/gpt-4o"

        result_holder = {"text": "Hello.", "enhanced_text": "Hello."}

        ctrl._handle_history_confirm(0, result_holder, None, 0.0, "voice")
        assert record.system_prompt == "keep"
        assert record.thinking_text == "keep think"


class TestSelectHistory:
    """Tests for on_select_history passing system_prompt/thinking_text."""

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_passes_prompt_and_thinking_to_panel(self, _mock_save, ctrl, mock_app):
        record = _make_record(
            system_prompt="sys prompt",
            thinking_text="think text",
            wav_data=None,
            audio_duration=0.0,
        )
        ctrl._preview_history.add(record)

        ctrl.on_select_history(0)

        mock_app._preview_panel.load_history_record.assert_called_once()
        call_kwargs = mock_app._preview_panel.load_history_record.call_args
        assert call_kwargs.kwargs.get("system_prompt") == "sys prompt" or \
            call_kwargs[1].get("system_prompt") == "sys prompt"
        assert call_kwargs.kwargs.get("thinking_text") == "think text" or \
            call_kwargs[1].get("thinking_text") == "think text"


class TestModeChangeResultHolder:
    """Tests for on_preview_mode_change updating result_holder."""

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_mode_off_clears_result_holder(self, _mock_save, ctrl, mock_app):
        ctrl._result_holder = {
            "enhanced_text": "Hello.",
            "system_prompt": "old",
            "thinking_text": "old think",
        }

        ctrl.on_preview_mode_change("off")

        assert ctrl._result_holder["enhanced_text"] is None
        assert ctrl._result_holder["system_prompt"] == ""
        assert ctrl._result_holder["thinking_text"] == ""

    @patch("wenzi.controllers.preview_controller.save_config")
    def test_cache_hit_updates_result_holder(self, _mock_save, ctrl, mock_app):
        cached = MagicMock()
        cached.display_text = "Hello."
        cached.usage = None
        cached.system_prompt = "cached prompt"
        cached.thinking_text = "cached think"
        cached.final_text = "Hello."
        mock_app._enhance_controller.get_cached.return_value = cached

        ctrl._result_holder = {"enhanced_text": None}

        ctrl.on_preview_mode_change("translate")

        assert ctrl._result_holder["enhanced_text"] == "Hello."
        assert ctrl._result_holder["system_prompt"] == "cached prompt"
        assert ctrl._result_holder["thinking_text"] == "cached think"
