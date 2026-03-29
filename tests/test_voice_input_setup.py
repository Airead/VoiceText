"""Tests for voice input setup flow (Siri unavailable / no fallback)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from wenzi.transcription.apple import (
    SIRI_SETUP_DONT_ASK,
    SIRI_SETUP_LATER,
    SIRI_SETUP_OPEN_SETTINGS,
)


def _make_app_with_real_choice_handler(**overrides):
    """Create a MagicMock app with the real _handle_dictation_setup_choice bound."""
    from wenzi.app import WenZiApp

    app = MagicMock()
    app._config = {"asr": {}}
    app._config_path = "/tmp/config.json"
    app._voice_input_available = True
    app._hotkey_listener = MagicMock()
    for k, v in overrides.items():
        setattr(app, k, v)
    app._handle_dictation_setup_choice = (
        lambda choice: WenZiApp._handle_dictation_setup_choice(app, choice)
    )
    return app


class TestSiriSetupConstants:
    """Verify Siri setup dialog return value constants."""

    def test_open_settings(self):
        assert SIRI_SETUP_OPEN_SETTINGS == "open_settings"

    def test_later(self):
        assert SIRI_SETUP_LATER == "later"

    def test_dont_ask(self):
        assert SIRI_SETUP_DONT_ASK == "dont_ask"


class TestHandleNoVoiceBackend:
    """Tests for WenZiApp._handle_no_voice_backend."""

    def test_previously_disabled_skips_prompt(self):
        """If voice_input_disabled is already set, skip dialog."""
        from wenzi.app import WenZiApp

        app = _make_app_with_real_choice_handler()
        app._config["asr"]["voice_input_disabled"] = True

        with patch("wenzi.app.save_config"):
            WenZiApp._handle_no_voice_backend(app)

        assert app._voice_input_available is False
        assert app._set_status.call_args[0][0] == "statusbar.status.ready"

    def test_user_chooses_open_settings(self):
        """Open Settings: opens URL, voice input disabled, hotkeys stay."""
        from wenzi.app import WenZiApp

        app = _make_app_with_real_choice_handler()

        with patch(
            "wenzi.transcription.apple.prompt_siri_setup",
            return_value=SIRI_SETUP_OPEN_SETTINGS,
        ), patch("subprocess.Popen") as mock_popen, \
             patch("wenzi.app.save_config"):
            WenZiApp._handle_no_voice_backend(app)

        mock_popen.assert_called_once()
        assert app._voice_input_available is False
        assert app._set_status.call_args[0][0] == "statusbar.status.ready"

    def test_user_chooses_later(self):
        """Set Up Later: voice input disabled, hotkeys stay, no save."""
        from wenzi.app import WenZiApp

        app = _make_app_with_real_choice_handler()

        with patch(
            "wenzi.transcription.apple.prompt_siri_setup",
            return_value=SIRI_SETUP_LATER,
        ), patch("wenzi.app.save_config") as mock_save:
            WenZiApp._handle_no_voice_backend(app)

        mock_save.assert_not_called()
        assert app._voice_input_available is False
        assert "voice_input_disabled" not in app._config["asr"]

    def test_user_chooses_dont_ask(self):
        """Don't Ask Again: persists preference, stops hotkeys."""
        from wenzi.app import WenZiApp

        app = _make_app_with_real_choice_handler()

        with patch(
            "wenzi.transcription.apple.prompt_siri_setup",
            return_value=SIRI_SETUP_DONT_ASK,
        ), patch("wenzi.app.save_config") as mock_save:
            WenZiApp._handle_no_voice_backend(app)

        assert app._config["asr"]["voice_input_disabled"] is True
        mock_save.assert_called_once()
        assert app._voice_input_available is False


