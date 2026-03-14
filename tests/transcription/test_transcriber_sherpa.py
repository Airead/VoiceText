"""Tests for Sherpa-ONNX streaming transcription backend."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _mock_sherpa(monkeypatch):
    """Mock sherpa_onnx for headless testing."""
    mock_sherpa = MagicMock()
    monkeypatch.setitem(sys.modules, "sherpa_onnx", mock_sherpa)
    return mock_sherpa


class TestSherpaModels:
    def test_model_definitions(self):
        from voicetext.transcription.sherpa import SHERPA_MODELS

        assert "zipformer-zh" in SHERPA_MODELS
        assert "paraformer-zh" in SHERPA_MODELS

        for model_id, info in SHERPA_MODELS.items():
            assert "display_name" in info
            assert "language" in info
            assert "repo" in info
            assert "type" in info

    def test_cache_root(self):
        from voicetext.transcription.sherpa import _get_model_cache_root

        root = _get_model_cache_root()
        assert "sherpa-onnx-models" in str(root)

    def test_get_model_dir(self):
        from voicetext.transcription.sherpa import _get_model_dir

        path = _get_model_dir("zipformer-zh")
        assert isinstance(path, Path)
        assert "sherpa-onnx-models" in str(path)

    def test_get_model_dir_unknown_raises(self):
        from voicetext.transcription.sherpa import _get_model_dir

        with pytest.raises(ValueError, match="Unknown sherpa model"):
            _get_model_dir("nonexistent")


class TestSherpaTranscriberInit:
    def test_default_properties(self):
        from voicetext.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber()
        assert t._model_id == "zipformer-zh"
        assert t.initialized is False
        assert t.supports_streaming is True
        assert t.skip_punc is True

    def test_display_name_known(self):
        from voicetext.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="zipformer-zh")
        assert "Zipformer" in t.model_display_name

    def test_display_name_unknown(self):
        from voicetext.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="custom-model")
        assert "custom-model" in t.model_display_name


class TestSherpaStreaming:
    def _make_transcriber(self, _mock_sherpa):
        from voicetext.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="zipformer-zh")
        # Mock initialized state
        t._initialized = True
        t._recognizer = MagicMock()

        # Make is_ready return False (no decode needed)
        t._recognizer.is_ready.return_value = False

        # Make get_result return a mock result
        mock_result = MagicMock()
        mock_result.text = "test result"
        t._recognizer.get_result.return_value = mock_result

        return t

    def test_start_streaming(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        on_partial = MagicMock()

        t.start_streaming(on_partial)
        assert t._stream is not None
        assert t._decode_thread is not None

        t.cancel_streaming()

    def test_feed_audio(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        on_partial = MagicMock()

        t.start_streaming(on_partial)

        samples = np.array([100, 200, 300], dtype=np.int16)
        t.feed_audio(samples)

        t._stream.accept_waveform.assert_called()
        call_args = t._stream.accept_waveform.call_args
        assert call_args[0][0] == 16000
        np.testing.assert_array_almost_equal(
            call_args[0][1],
            samples.astype(np.float32) / 32768.0,
        )

        t.cancel_streaming()

    def test_feed_audio_noop_when_no_session(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        samples = np.array([100, 200], dtype=np.int16)
        # Should not raise
        t.feed_audio(samples)

    def test_stop_streaming_returns_text(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        on_partial = MagicMock()

        t.start_streaming(on_partial)

        result = t.stop_streaming()
        assert result == "test result"
        assert t._stream is None

    def test_cancel_streaming(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        on_partial = MagicMock()

        t.start_streaming(on_partial)
        t.cancel_streaming()

        assert t._stream is None
        assert t._decode_thread is None

    def test_cleanup_cancels_stream(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        on_partial = MagicMock()

        t.start_streaming(on_partial)
        t.cleanup()

        assert t._initialized is False
        assert t._recognizer is None
        assert t._stream is None


class TestSherpaFactory:
    def test_create_sherpa_backend(self):
        from voicetext.transcription.base import create_transcriber
        from voicetext.transcription.sherpa import SherpaOnnxTranscriber

        t = create_transcriber(backend="sherpa")
        assert isinstance(t, SherpaOnnxTranscriber)
        assert t._model_id == "zipformer-zh"

    def test_create_sherpa_onnx_alias(self):
        from voicetext.transcription.base import create_transcriber
        from voicetext.transcription.sherpa import SherpaOnnxTranscriber

        t = create_transcriber(backend="sherpa-onnx")
        assert isinstance(t, SherpaOnnxTranscriber)

    def test_create_sherpa_with_model(self):
        from voicetext.transcription.base import create_transcriber

        t = create_transcriber(backend="sherpa", model="paraformer-zh")
        assert t._model_id == "paraformer-zh"
