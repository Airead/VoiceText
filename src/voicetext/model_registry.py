"""Preset model registry for VoiceText ASR backends."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPreset:
    """A predefined ASR model configuration."""

    id: str
    display_name: str
    backend: str
    model: Optional[str]
    language: Optional[str]


PRESETS = [
    ModelPreset(
        id="funasr-paraformer",
        display_name="FunASR Paraformer (Chinese)",
        backend="funasr",
        model=None,
        language=None,
    ),
    ModelPreset(
        id="mlx-whisper-tiny",
        display_name="Whisper tiny (MLX)",
        backend="mlx-whisper",
        model="mlx-community/whisper-tiny",
        language=None,
    ),
    ModelPreset(
        id="mlx-whisper-base",
        display_name="Whisper base (MLX)",
        backend="mlx-whisper",
        model="mlx-community/whisper-base",
        language=None,
    ),
    ModelPreset(
        id="mlx-whisper-small",
        display_name="Whisper small (MLX)",
        backend="mlx-whisper",
        model="mlx-community/whisper-small",
        language=None,
    ),
    ModelPreset(
        id="mlx-whisper-medium",
        display_name="Whisper medium (MLX)",
        backend="mlx-whisper",
        model="mlx-community/whisper-medium",
        language=None,
    ),
    ModelPreset(
        id="mlx-whisper-large-v3-turbo",
        display_name="Whisper large-v3-turbo (MLX)",
        backend="mlx-whisper",
        model="mlx-community/whisper-large-v3-turbo",
        language=None,
    ),
]

PRESET_BY_ID: Dict[str, ModelPreset] = {p.id: p for p in PRESETS}


def resolve_preset_from_config(
    backend: str, model: Optional[str] = None
) -> Optional[str]:
    """Resolve a preset ID from a backend+model combination.

    Returns the preset ID if a match is found, otherwise None.
    """
    backend_norm = backend.lower().replace("_", "-")

    for preset in PRESETS:
        if preset.backend != backend_norm:
            continue
        if backend_norm == "funasr" and preset.model is None and model is None:
            return preset.id
        if backend_norm == "mlx-whisper" and preset.model == model:
            return preset.id

    return None


def get_model_cache_dir(preset: ModelPreset) -> Path:
    """Get the cache directory path for a preset's model files."""
    home = Path.home()

    if preset.backend == "funasr":
        # FunASR models are cached under modelscope
        from .config import MODELS

        asr_model = MODELS["asr"]
        short_name = asr_model.split("/")[-1] if "/" in asr_model else asr_model
        return home / ".cache" / "modelscope" / "hub" / "models" / "iic" / short_name

    if preset.backend == "mlx-whisper" and preset.model:
        # HuggingFace models are cached under huggingface hub
        repo_id = preset.model
        # HF cache uses -- as separator: models--org--name
        cache_name = "models--" + repo_id.replace("/", "--")
        return home / ".cache" / "huggingface" / "hub" / cache_name

    return home / ".cache" / "voicetext" / preset.id


def is_model_cached(preset: ModelPreset) -> bool:
    """Check if a preset's model files are already downloaded."""
    if preset.backend == "mlx-whisper" and preset.model:
        try:
            from huggingface_hub import try_to_load_from_cache

            result = try_to_load_from_cache(preset.model, "config.json")
            # Returns file path string if cached, _CACHED_NO_EXIST or None otherwise
            return isinstance(result, str)
        except Exception:
            logger.debug("Could not check HF cache for %s", preset.model)
            return False

    if preset.backend == "funasr":
        cache_dir = get_model_cache_dir(preset)
        if not cache_dir.exists():
            return False
        return (cache_dir / "model_quant.onnx").exists() or (
            cache_dir / "model.onnx"
        ).exists()

    return False
