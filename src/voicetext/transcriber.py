"""Abstract transcriber interface and factory."""

from __future__ import annotations

import abc
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BaseTranscriber(abc.ABC):
    """Base interface for speech-to-text backends."""

    @property
    @abc.abstractmethod
    def initialized(self) -> bool:
        """Whether the model has been loaded."""

    @abc.abstractmethod
    def initialize(self) -> None:
        """Load models. Call once at startup."""

    @abc.abstractmethod
    def transcribe(self, wav_data: bytes) -> str:
        """Transcribe WAV audio bytes to text."""

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Release model resources. After this, initialized should return False."""


def create_transcriber(
    backend: str = "funasr",
    *,
    use_vad: bool = False,
    use_punc: bool = True,
    language: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseTranscriber:
    """Create a transcriber for the given backend.

    Args:
        backend: "funasr" or "mlx-whisper".
        use_vad: Enable voice activity detection (funasr only).
        use_punc: Enable punctuation restoration.
        language: Language hint (mlx-whisper only, e.g. "zh", "en").
        model: Override default model name/path.
    """
    backend = backend.lower().replace("_", "-")

    if backend == "funasr":
        from .transcriber_funasr import FunASRTranscriber
        return FunASRTranscriber(use_vad=use_vad, use_punc=use_punc)

    if backend in ("mlx-whisper", "mlx", "whisper"):
        from .transcriber_mlx import MLXWhisperTranscriber
        return MLXWhisperTranscriber(language=language, model=model, use_punc=use_punc)

    raise ValueError(f"Unknown ASR backend: {backend!r}. Use 'funasr' or 'mlx-whisper'.")
