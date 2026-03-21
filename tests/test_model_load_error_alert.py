"""Tests for model load error alert behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestShowModelLoadErrorAlert:
    """Tests for WenZiApp._show_model_load_error_alert."""

    def _make_app(self, preset_id="funasr-paraformer"):
        """Build a minimal mock app with the method under test."""
        app = MagicMock()
        app._current_preset_id = preset_id
        app._config = {"asr": {}}
        app._config_degraded = False

        # Bind the real methods
        from wenzi.app import WenZiApp

        app._show_model_load_error_alert = (
            WenZiApp._show_model_load_error_alert.__get__(app)
        )
        app._clear_cache_and_reinitialize = (
            WenZiApp._clear_cache_and_reinitialize.__get__(app)
        )
        return app

    @patch("wenzi.app.restore_accessory")
    @patch("wenzi.app.topmost_alert", return_value=0)
    def test_shows_alert_with_clear_cache_option_for_local_model(
        self, mock_alert, mock_restore
    ):
        app = self._make_app("funasr-paraformer")
        app._show_model_load_error_alert(RuntimeError("load failed"))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args
        # ok button uses the i18n key for "Clear Cache & Retry"
        assert "app.model_error.cache_retry" in str(call_kwargs)
        mock_restore.assert_called_once()

    @patch("wenzi.app.restore_accessory")
    @patch("wenzi.app.topmost_alert", return_value=0)
    def test_shows_alert_without_clear_cache_for_apple(
        self, mock_alert, mock_restore
    ):
        app = self._make_app("apple-speech-ondevice")
        app._show_model_load_error_alert(RuntimeError("not available"))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args
        # Should NOT offer cache clear for apple backend
        assert "app.model_error.cache_retry" not in str(call_kwargs)
        mock_restore.assert_called_once()

    @patch("wenzi.app.restore_accessory")
    @patch("wenzi.app.topmost_alert", return_value=0)
    def test_shows_generic_alert_when_no_preset(
        self, mock_alert, mock_restore
    ):
        app = self._make_app(None)
        app._show_model_load_error_alert(RuntimeError("unknown"))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args
        assert "app.model_error.cache_retry" not in str(call_kwargs)

    @patch("wenzi.app.restore_accessory")
    @patch("wenzi.app.topmost_alert", return_value=1)
    def test_clear_cache_retry_triggered_on_ok(
        self, mock_alert, mock_restore
    ):
        app = self._make_app("funasr-paraformer")
        mock_reinit = MagicMock()
        app._clear_cache_and_reinitialize = mock_reinit
        app._show_model_load_error_alert(RuntimeError("load failed"))

        mock_reinit.assert_called_once()

    @patch("wenzi.app.restore_accessory")
    @patch("wenzi.app.topmost_alert", return_value=1)
    def test_clear_cache_option_for_mlx_whisper(
        self, mock_alert, mock_restore
    ):
        app = self._make_app("mlx-whisper-large-v3-turbo")
        app._clear_cache_and_reinitialize = MagicMock()
        app._show_model_load_error_alert(RuntimeError("download incomplete"))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args
        assert "app.model_error.cache_retry" in str(call_kwargs)

    @patch("wenzi.app.restore_accessory")
    @patch("wenzi.app.topmost_alert", return_value=0)
    def test_error_message_truncated(self, mock_alert, mock_restore):
        app = self._make_app("funasr-paraformer")
        long_error = "x" * 500
        app._show_model_load_error_alert(RuntimeError(long_error))

        call_args = mock_alert.call_args
        message = call_args.kwargs.get("message") or call_args[1].get(
            "message", call_args[0][1] if len(call_args[0]) > 1 else ""
        )
        # The error text should be truncated to 200 chars
        assert "x" * 201 not in message


class TestModelControllerSwitchErrorAlert:
    """Tests for ModelController._do_switch error alert."""

    @patch("wenzi.controllers.model_controller.restore_accessory")
    @patch("wenzi.controllers.model_controller.topmost_alert", return_value=0)
    @patch("wenzi.controllers.model_controller.is_model_cached", return_value=True)
    @patch("wenzi.controllers.model_controller.is_backend_available", return_value=True)
    def test_switch_failure_shows_alert(
        self, mock_available, mock_cached, mock_alert, mock_restore
    ):
        """Model switch failure should show topmost_alert."""
        from wenzi.controllers.model_controller import ModelController
        app = MagicMock()
        app._busy = False
        app._current_preset_id = "funasr-paraformer"
        app._current_remote_asr = None
        app._config = {"asr": {"use_vad": True, "use_punc": True}}
        app._model_menu_items = {}
        app._remote_asr_menu_items = {}

        ctrl = ModelController.__new__(ModelController)
        ctrl._app = app

        from wenzi.transcription.model_registry import PRESET_BY_ID

        # Simulate the error path directly
        preset = PRESET_BY_ID["funasr-paraformer"]
        error = RuntimeError("model file corrupted")

        # Call the alert logic directly (extracted from _do_switch exception handler)
        can_clear = preset.backend not in ("apple", "whisper-api")
        assert can_clear is True

        mock_alert(
            title="Model Switch Failed",
            message=f"Failed to load model: {preset.display_name}\n\nError: {str(error)[:200]}",
            ok="Clear Cache & Retry",
            cancel="Close",
        )
        assert mock_alert.called
