"""MLX Whisper speech-to-text transcriber for Apple Silicon."""

from __future__ import annotations

import gc
import logging
import os
import tempfile
import time
from typing import Optional

from .transcriber import BaseTranscriber

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


class MLXWhisperTranscriber(BaseTranscriber):
    """Speech-to-text using mlx-whisper on Apple Silicon GPU."""

    def __init__(
        self,
        language: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._model_name = model or DEFAULT_MODEL
        self._language = language
        self._initialized = False
        self._mlx_whisper = None

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self) -> None:
        """Import mlx_whisper and warm up the model."""
        if self._initialized:
            return

        logger.info("Initializing mlx-whisper with model: %s", self._model_name)
        start = time.time()

        try:
            import mlx_whisper
        except ImportError:
            raise ImportError(
                "mlx-whisper is not installed. "
                "Install it with: uv add mlx-whisper"
            )

        self._mlx_whisper = mlx_whisper

        # Warm up: run a short silent audio to trigger model download and JIT
        self._warmup()

        elapsed = time.time() - start
        self._initialized = True
        logger.info("mlx-whisper ready in %.1fs", elapsed)

    def cleanup(self) -> None:
        """Release mlx-whisper model and free GPU memory."""
        self._mlx_whisper = None
        self._initialized = False
        gc.collect()
        try:
            import mlx.core as mx

            mx.metal.clear_cache()
        except Exception:
            pass
        logger.info("mlx-whisper model cleaned up")

    def _warmup(self) -> None:
        """Run a tiny transcription to preload the model."""
        import wave
        import numpy as np

        samples = np.zeros(int(16000 * 0.1), dtype=np.int16)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(samples.tobytes())

        try:
            self._mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo=self._model_name,
                language=self._language,
            )
            logger.info("mlx-whisper warmup done")
        except Exception as e:
            logger.warning("mlx-whisper warmup failed (non-fatal): %s", e)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def transcribe(self, wav_data: bytes) -> str:
        """Transcribe WAV audio bytes to text."""
        if not self._initialized:
            self.initialize()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_data)
            tmp_path = f.name

        try:
            result = self._mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo=self._model_name,
                language=self._language,
            )

            text = result.get("text", "")
            logger.info("Transcription result: %s", text[:100])
            return text

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
