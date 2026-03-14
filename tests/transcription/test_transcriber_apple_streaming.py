"""Tests for Apple Speech streaming transcription."""

from __future__ import annotations

import sys
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _mock_apple_frameworks(monkeypatch):
    """Mock Speech, AVFoundation, CoreFoundation for headless testing."""
    mock_speech = MagicMock()
    mock_avfoundation = MagicMock()
    mock_corefoundation = MagicMock()
    mock_foundation = MagicMock()

    monkeypatch.setitem(sys.modules, "Speech", mock_speech)
    monkeypatch.setitem(sys.modules, "AVFoundation", mock_avfoundation)
    monkeypatch.setitem(sys.modules, "CoreFoundation", mock_corefoundation)
    monkeypatch.setitem(sys.modules, "Foundation", mock_foundation)

    # Make CFRunLoopRunInMode a no-op
    mock_corefoundation.CFRunLoopRunInMode = MagicMock()
    mock_corefoundation.kCFRunLoopDefaultMode = "default"

    return {
        "Speech": mock_speech,
        "AVFoundation": mock_avfoundation,
        "CoreFoundation": mock_corefoundation,
        "Foundation": mock_foundation,
    }


def _make_transcriber():
    """Create an AppleSpeechTranscriber with mocked initialization."""
    from voicetext.transcription.apple import AppleSpeechTranscriber

    t = AppleSpeechTranscriber(language="zh", on_device=True)
    t._initialized = True
    t._recognizer = MagicMock()
    return t


class TestAppleSpeechStreaming:
    def test_supports_streaming(self):
        t = _make_transcriber()
        assert t.supports_streaming is True

    def test_start_streaming_creates_request(self):
        t = _make_transcriber()
        on_partial = MagicMock()

        t.start_streaming(on_partial)

        assert t._stream_request is not None
        # Task is created on RunLoop thread; wait briefly for it
        t._stream_runloop_thread.join(timeout=1.0)
        assert t._stream_task is not None
        t._recognizer.recognitionTaskWithRequest_resultHandler_.assert_called_once()

        # Cleanup
        t.cancel_streaming()

    def test_feed_audio_appends_buffer(self):
        t = _make_transcriber()
        on_partial = MagicMock()

        t.start_streaming(on_partial)

        samples = np.array([100, 200, 300], dtype=np.int16)
        t.feed_audio(samples)

        assert t._stream_request.appendAudioPCMBuffer_.called

        t.cancel_streaming()

    def test_feed_audio_noop_when_no_session(self):
        t = _make_transcriber()
        samples = np.array([100, 200], dtype=np.int16)
        # Should not raise
        t.feed_audio(samples)

    def test_stop_streaming_calls_end_audio(self):
        t = _make_transcriber()
        on_partial = MagicMock()

        t.start_streaming(on_partial)

        # Simulate final result
        t._stream_final_text = "hello world"
        t._stream_final_event.set()

        result = t.stop_streaming()
        assert result == "hello world"

    def test_stop_streaming_timeout_returns_empty(self):
        from voicetext.transcription import apple

        original_timeout = apple.STREAMING_FINAL_TIMEOUT

        t = _make_transcriber()
        on_partial = MagicMock()
        t.start_streaming(on_partial)

        # Don't set final event — will timeout
        apple.STREAMING_FINAL_TIMEOUT = 0.1
        try:
            result = t.stop_streaming()
            assert result == ""
        finally:
            apple.STREAMING_FINAL_TIMEOUT = original_timeout

    def test_cancel_streaming_cancels_task(self):
        t = _make_transcriber()
        on_partial = MagicMock()

        t.start_streaming(on_partial)
        # Wait for task to be created on RunLoop thread
        t._stream_runloop_thread.join(timeout=1.0)
        task = t._stream_task

        t.cancel_streaming()

        task.cancel.assert_called_once()
        assert t._stream_request is None

    def test_cleanup_cancels_active_stream(self):
        t = _make_transcriber()
        on_partial = MagicMock()

        t.start_streaming(on_partial)
        t.cleanup()

        assert t._initialized is False
        assert t._stream_request is None

    def test_handler_invokes_on_partial(self):
        """Verify the recognition handler calls on_partial correctly."""
        t = _make_transcriber()
        partials = []

        def on_partial(text, is_final):
            partials.append((text, is_final))

        t.start_streaming(on_partial)
        # Wait for RunLoop thread to create task
        t._stream_runloop_thread.join(timeout=1.0)
        call_args = t._recognizer.recognitionTaskWithRequest_resultHandler_.call_args
        handler = call_args[0][1]

        # Simulate partial results (formattedString returns FULL text)
        mock_result = MagicMock()
        mock_result.bestTranscription().formattedString.return_value = "hello"
        mock_result.isFinal.return_value = False
        handler(mock_result, None)

        assert partials == [("hello", False)]

        # Longer partial — updates
        mock_result2 = MagicMock()
        mock_result2.bestTranscription().formattedString.return_value = "hello world"
        mock_result2.isFinal.return_value = False
        handler(mock_result2, None)

        assert partials[-1] == ("hello world", False)

        # Shorter partial — also delivered (no filtering in fanrenhao approach)
        mock_result3 = MagicMock()
        mock_result3.bestTranscription().formattedString.return_value = "hello"
        mock_result3.isFinal.return_value = False
        handler(mock_result3, None)

        assert len(partials) == 3
        assert partials[-1] == ("hello", False)

        # Final result — sets final event
        mock_result4 = MagicMock()
        mock_result4.bestTranscription().formattedString.return_value = "hello world"
        mock_result4.isFinal.return_value = True
        handler(mock_result4, None)

        assert t._stream_final_event.is_set()
        assert t._stream_final_text == "hello world"

        t.cancel_streaming()

    def test_sample_rate_property(self):
        t = _make_transcriber()
        assert t.sample_rate == 16000
