"""Tests for global scripting events fired by RecordingController."""

from unittest.mock import MagicMock, patch

from wenzi.controllers.recording_controller import RecordingController


def _make_controller():
    """Create a RecordingController with a mocked app and script engine."""
    app = MagicMock()
    app._config_degraded = False
    app._busy = False
    app._config = {"hotkeys": {}}
    ctrl = RecordingController(app)
    return ctrl, app


class TestFireScriptingEvent:
    def test_fire_event_calls_registry(self):
        ctrl, app = _make_controller()
        app._script_engine.wz._registry.fire_event = MagicMock()
        ctrl._fire_scripting_event("test_event", key="value")
        app._script_engine.wz._registry.fire_event.assert_called_once_with(
            "test_event", key="value"
        )

    def test_fire_event_no_engine(self):
        ctrl, app = _make_controller()
        # Simulate no _script_engine attribute
        del app._script_engine
        # Should not raise when _script_engine doesn't exist
        ctrl._fire_scripting_event("test_event")

    def test_fire_event_exception_handled(self):
        ctrl, app = _make_controller()
        app._script_engine.wz._registry.fire_event.side_effect = RuntimeError(
            "boom"
        )
        # Should not raise
        ctrl._fire_scripting_event("test_event")


class TestRecordingStartEvent:
    def test_recording_start_fired_on_hotkey_press(self):
        ctrl, app = _make_controller()
        fire_event = MagicMock()
        app._script_engine.wz._registry.fire_event = fire_event
        app._sound_manager.enabled = False
        app._recorder.start.return_value = "mic"
        app._recorder.is_recording = True
        app._recording_indicator.show_device_name = False
        app._transcriber.supports_streaming = False
        app._recording_started = MagicMock()

        ctrl.on_hotkey_press()
        fire_event.assert_any_call("recording_start")


class TestRecordingStopEvent:
    @patch("wenzi.controllers.recording_controller.threading")
    def test_recording_stop_fired_on_hotkey_release(self, mock_threading):
        ctrl, app = _make_controller()
        fire_event = MagicMock()
        app._script_engine.wz._registry.fire_event = fire_event
        app._recording_started.wait.return_value = True
        app._recorder.is_recording = True
        app._recorder.stop.return_value = b"wav_data"
        app._recorder.clear_on_audio_chunk = MagicMock()
        app._preview_enabled = False
        app._enhancer = None
        ctrl._streaming_active = False

        ctrl.on_hotkey_release()
        fire_event.assert_any_call("recording_stop", audio_duration=0.0)


class TestTranscriptionDoneEvent:
    def test_transcription_done_fired(self):
        ctrl, app = _make_controller()
        fire_event = MagicMock()
        app._script_engine.wz._registry.fire_event = fire_event
        app._enhance_mode = "off"
        app._enhancer = None
        app._append_newline = False
        app._output_method = "auto"

        with patch("wenzi.controllers.recording_controller.type_text"):
            ctrl.do_transcribe_direct("hello world", use_enhance=False)

        fire_event.assert_any_call(
            "transcription_done", asr_text="hello world"
        )

    def test_transcription_done_fired_in_streaming_preview_path(self):
        """transcription_done should fire even when preview mode is enabled."""
        ctrl, app = _make_controller()
        fire_event = MagicMock()
        app._script_engine.wz._registry.fire_event = fire_event
        app._recording_started.wait.return_value = True
        app._recorder.is_recording = True
        app._recorder.stop.return_value = b"wav_data"
        app._recorder.clear_on_audio_chunk = MagicMock()
        app._preview_enabled = True
        app._enhancer = None
        app._transcriber.stop_streaming.return_value = "hello preview"
        ctrl._streaming_active = True

        with patch("wenzi.controllers.recording_controller.threading") as mock_threading:
            ctrl.on_hotkey_release()
            thread_target = mock_threading.Thread.call_args[1]["target"]
            thread_target()

        fire_event.assert_any_call(
            "transcription_done", asr_text="hello preview"
        )


class TestOutputTextEvent:
    def test_output_text_fired_before_type(self):
        ctrl, app = _make_controller()
        fire_event = MagicMock()
        app._script_engine.wz._registry.fire_event = fire_event
        app._enhance_mode = "off"
        app._enhancer = None
        app._append_newline = False
        app._output_method = "auto"

        with patch("wenzi.controllers.recording_controller.type_text"):
            ctrl.do_transcribe_direct("hello world", use_enhance=False)

        fire_event.assert_any_call(
            "output_text", final_text="hello world"
        )
