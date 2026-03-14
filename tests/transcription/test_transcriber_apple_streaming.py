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

        # Simulate final result arriving
        t._stream_final_text = "hello world"
        t._stream_done.set()

        result = t.stop_streaming()
        assert result == "hello world"

    def test_stop_streaming_timeout_returns_empty(self):
        from voicetext.transcription import apple

        original_timeout = apple.STREAMING_FINAL_TIMEOUT

        t = _make_transcriber()
        on_partial = MagicMock()
        t.start_streaming(on_partial)

        # Don't set done event — will timeout
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

        # Capture the handler passed to recognitionTaskWithRequest_resultHandler_
        t.start_streaming(on_partial)
        call_args = t._recognizer.recognitionTaskWithRequest_resultHandler_.call_args
        handler = call_args[0][1]

        # Simulate a partial result
        mock_result = MagicMock()
        mock_result.bestTranscription().formattedString.return_value = "hello"
        mock_result.isFinal.return_value = False
        handler(mock_result, None)

        assert partials == [("hello", False)]

        # Simulate a final result
        mock_result2 = MagicMock()
        mock_result2.bestTranscription().formattedString.return_value = "hello world"
        mock_result2.isFinal.return_value = True
        handler(mock_result2, None)

        assert partials == [("hello", False), ("hello world", True)]
        assert t._stream_final_text == "hello world"
        assert t._stream_done.is_set()

        t.cancel_streaming()
