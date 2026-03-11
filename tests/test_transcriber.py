"""Tests for the transcriber module."""

import pytest

from voicetext.transcriber import BaseTranscriber, create_transcriber
from voicetext.transcriber_funasr import FunASRTranscriber


class TestVadHasSpeech:
    def test_empty_result(self):
        assert FunASRTranscriber._vad_has_speech(None) is False
        assert FunASRTranscriber._vad_has_speech([]) is False

    def test_no_speech_segments(self):
        # VAD returns empty segment lists when no speech detected
        assert FunASRTranscriber._vad_has_speech([[]]) is False

    def test_has_speech_segments(self):
        # VAD returns [[start_ms, end_ms], ...] per audio
        assert FunASRTranscriber._vad_has_speech([[[0, 1000]]]) is True
        assert FunASRTranscriber._vad_has_speech([[[100, 500], [800, 1200]]]) is True

    def test_non_list_result(self):
        assert FunASRTranscriber._vad_has_speech("unexpected") is False
        assert FunASRTranscriber._vad_has_speech(0) is False


class TestCreateTranscriber:
    def test_create_funasr_backend(self):
        t = create_transcriber(backend="funasr")
        assert isinstance(t, FunASRTranscriber)
        assert isinstance(t, BaseTranscriber)

    def test_create_mlx_backend(self):
        try:
            t = create_transcriber(backend="mlx-whisper")
            assert isinstance(t, BaseTranscriber)
        except ImportError:
            pytest.skip("mlx-whisper not installed")

    def test_create_mlx_aliases(self):
        """'mlx' and 'whisper' are aliases for 'mlx-whisper'."""
        try:
            for alias in ("mlx", "whisper"):
                t = create_transcriber(backend=alias)
                assert isinstance(t, BaseTranscriber)
        except ImportError:
            pytest.skip("mlx-whisper not installed")

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown ASR backend"):
            create_transcriber(backend="unknown")


class TestCleanup:
    def test_funasr_cleanup(self):
        t = FunASRTranscriber(use_vad=False, use_punc=False)
        # Simulate initialized state
        t._initialized = True
        t._asr_model = "fake_model"
        t.cleanup()
        assert t.initialized is False
        assert t._asr_model is None
        assert t._vad_model is None
        assert t._punc_restorer is None

    def test_mlx_cleanup(self):
        try:
            from voicetext.transcriber_mlx import MLXWhisperTranscriber
        except ImportError:
            pytest.skip("mlx-whisper not installed")

        t = MLXWhisperTranscriber()
        t._initialized = True
        t._mlx_whisper = "fake_module"
        t.cleanup()
        assert t.initialized is False
        assert t._mlx_whisper is None
