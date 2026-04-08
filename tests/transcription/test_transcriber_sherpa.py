"""Tests for Sherpa-ONNX streaming transcription backend."""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

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
        from wenzi.transcription.sherpa import SHERPA_MODELS

        assert "zipformer-zh" in SHERPA_MODELS
        assert "paraformer-zh" in SHERPA_MODELS

        for model_id, info in SHERPA_MODELS.items():
            assert "display_name" in info
            assert "language" in info
            assert "repo" in info
            assert "type" in info

    def test_cache_root(self):
        from wenzi.transcription.sherpa import _get_model_cache_root

        root = _get_model_cache_root()
        assert "sherpa-onnx-models" in str(root)

    def test_get_model_dir(self):
        from wenzi.transcription.sherpa import _get_model_dir

        path = _get_model_dir("zipformer-zh")
        assert isinstance(path, Path)
        assert "sherpa-onnx-models" in str(path)

    def test_get_model_dir_unknown_raises(self):
        from wenzi.transcription.sherpa import _get_model_dir

        with pytest.raises(ValueError, match="Unknown sherpa model"):
            _get_model_dir("nonexistent")


class TestSherpaTranscriberInit:
    def test_default_properties(self):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber()
        assert t._model_id == "zipformer-zh"
        assert t.initialized is False
        assert t.supports_streaming is True
        assert t.skip_punc is True

    def test_display_name_known(self):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="zipformer-zh")
        assert "Zipformer" in t.model_display_name

    def test_display_name_unknown(self):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="custom-model")
        assert "custom-model" in t.model_display_name


class TestSherpaStreaming:
    def _make_transcriber(self, _mock_sherpa):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

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

        samples = struct.pack("<3h", 100, 200, 300)
        t.feed_audio(samples)

        t._stream.accept_waveform.assert_called()
        call_args = t._stream.accept_waveform.call_args
        assert call_args[0][0] == 16000
        expected = np.array([100, 200, 300], dtype=np.float32) / 32768.0
        np.testing.assert_array_almost_equal(call_args[0][1], expected)

        t.cancel_streaming()

    def test_feed_audio_noop_when_no_session(self, _mock_sherpa):
        t = self._make_transcriber(_mock_sherpa)
        samples = struct.pack("<2h", 100, 200)
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
        from wenzi.transcription.base import create_transcriber
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = create_transcriber(backend="sherpa")
        assert isinstance(t, SherpaOnnxTranscriber)
        assert t._model_id == "zipformer-zh"

    def test_create_sherpa_onnx_alias(self):
        from wenzi.transcription.base import create_transcriber
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = create_transcriber(backend="sherpa-onnx")
        assert isinstance(t, SherpaOnnxTranscriber)

    def test_create_sherpa_with_model(self):
        from wenzi.transcription.base import create_transcriber

        t = create_transcriber(backend="sherpa", model="paraformer-zh")
        assert t._model_id == "paraformer-zh"

    def test_create_sherpa_with_hotwords(self):
        from wenzi.transcription.base import create_transcriber

        t = create_transcriber(backend="sherpa", hotwords=["Python", "Kubernetes"])
        assert t._hotwords == ["Python", "Kubernetes"]


class TestSherpaHotwords:
    def test_hotwords_stored(self):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(hotwords=["Python", "Kubernetes"])
        assert t._hotwords == ["Python", "Kubernetes"]

    def test_hotwords_default_none(self):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber()
        assert t._hotwords is None

    def test_zipformer_with_hotwords(self, _mock_sherpa, tmp_path, monkeypatch):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        fake_path = tmp_path / "sherpa_hotwords.txt"
        monkeypatch.setattr(SherpaOnnxTranscriber, "_hotwords_path", staticmethod(lambda: fake_path))

        t = SherpaOnnxTranscriber(model="zipformer-zh", hotwords=["Python", "测试"])

        # Create fake model files in tmp_path
        (tmp_path / "encoder.onnx").touch()
        (tmp_path / "decoder.onnx").touch()
        (tmp_path / "joiner.onnx").touch()
        (tmp_path / "tokens.txt").touch()

        t._create_zipformer_recognizer(_mock_sherpa, tmp_path)

        call_kwargs = _mock_sherpa.OnlineRecognizer.from_transducer.call_args[1]
        assert "hotwords_file" in call_kwargs
        assert call_kwargs["hotwords_score"] == 1.5
        assert call_kwargs["decoding_method"] == "modified_beam_search"

        # Verify the hotwords file content
        hotwords_content = Path(call_kwargs["hotwords_file"]).read_text(encoding="utf-8")
        assert "Python :1.5" in hotwords_content
        assert "测试 :1.5" in hotwords_content

    def test_zipformer_without_hotwords(self, _mock_sherpa, tmp_path):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="zipformer-zh")

        (tmp_path / "encoder.onnx").touch()
        (tmp_path / "decoder.onnx").touch()
        (tmp_path / "joiner.onnx").touch()
        (tmp_path / "tokens.txt").touch()

        t._create_zipformer_recognizer(_mock_sherpa, tmp_path)

        call_kwargs = _mock_sherpa.OnlineRecognizer.from_transducer.call_args[1]
        assert "hotwords_file" not in call_kwargs
        assert "decoding_method" not in call_kwargs

    def test_paraformer_ignores_hotwords(self, _mock_sherpa, tmp_path):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        t = SherpaOnnxTranscriber(model="paraformer-zh", hotwords=["Python"])

        (tmp_path / "encoder.onnx").touch()
        (tmp_path / "decoder.onnx").touch()
        (tmp_path / "tokens.txt").touch()

        t._create_paraformer_recognizer(_mock_sherpa, tmp_path)

        call_kwargs = _mock_sherpa.OnlineRecognizer.from_paraformer.call_args[1]
        assert "hotwords_file" not in call_kwargs

    def test_cleanup_removes_hotwords_file(self, monkeypatch, tmp_path):
        from wenzi.transcription.sherpa import SherpaOnnxTranscriber

        fake_path = tmp_path / "sherpa_hotwords.txt"
        monkeypatch.setattr(SherpaOnnxTranscriber, "_hotwords_path", staticmethod(lambda: fake_path))

        t = SherpaOnnxTranscriber(hotwords=["Python"])
        fake_path.write_text("Python :1.5\n", encoding="utf-8")
        assert fake_path.exists()

        t.cleanup()

        assert not fake_path.exists()
