"""Tests for model registry module."""

from pathlib import Path

import pytest

from voicetext.model_registry import (
    PRESET_BY_ID,
    PRESETS,
    ModelPreset,
    get_model_cache_dir,
    resolve_preset_from_config,
)


class TestPresets:
    def test_all_ids_unique(self):
        ids = [p.id for p in PRESETS]
        assert len(ids) == len(set(ids))

    def test_preset_by_id_matches(self):
        for preset in PRESETS:
            assert preset.id in PRESET_BY_ID
            assert PRESET_BY_ID[preset.id] is preset

    def test_preset_by_id_count(self):
        assert len(PRESET_BY_ID) == len(PRESETS)

    def test_all_presets_have_required_fields(self):
        for preset in PRESETS:
            assert preset.id
            assert preset.display_name
            assert preset.backend in ("funasr", "mlx-whisper")

    def test_funasr_preset_exists(self):
        assert "funasr-paraformer" in PRESET_BY_ID
        p = PRESET_BY_ID["funasr-paraformer"]
        assert p.backend == "funasr"
        assert p.model is None

    def test_mlx_presets_have_model(self):
        for preset in PRESETS:
            if preset.backend == "mlx-whisper":
                assert preset.model is not None
                assert preset.model.startswith("mlx-community/")


class TestResolvePresetFromConfig:
    def test_resolve_funasr_default(self):
        result = resolve_preset_from_config("funasr")
        assert result == "funasr-paraformer"

    def test_resolve_mlx_whisper_large_v3_turbo(self):
        result = resolve_preset_from_config(
            "mlx-whisper", "mlx-community/whisper-large-v3-turbo"
        )
        assert result == "mlx-whisper-large-v3-turbo"

    def test_resolve_mlx_whisper_tiny(self):
        result = resolve_preset_from_config(
            "mlx-whisper", "mlx-community/whisper-tiny"
        )
        assert result == "mlx-whisper-tiny"

    def test_resolve_unknown_model(self):
        result = resolve_preset_from_config("mlx-whisper", "some/unknown-model")
        assert result is None

    def test_resolve_unknown_backend(self):
        result = resolve_preset_from_config("unknown-backend")
        assert result is None

    def test_resolve_normalizes_backend(self):
        result = resolve_preset_from_config("MLX_Whisper", "mlx-community/whisper-tiny")
        assert result == "mlx-whisper-tiny"


class TestGetModelCacheDir:
    def test_funasr_cache_dir(self):
        preset = PRESET_BY_ID["funasr-paraformer"]
        cache_dir = get_model_cache_dir(preset)
        assert isinstance(cache_dir, Path)
        assert "modelscope" in str(cache_dir)
        assert "iic" in str(cache_dir)

    def test_mlx_whisper_cache_dir(self):
        preset = PRESET_BY_ID["mlx-whisper-large-v3-turbo"]
        cache_dir = get_model_cache_dir(preset)
        assert isinstance(cache_dir, Path)
        assert "huggingface" in str(cache_dir)
        assert "models--mlx-community--whisper-large-v3-turbo" in str(cache_dir)

    def test_mlx_whisper_tiny_cache_dir(self):
        preset = PRESET_BY_ID["mlx-whisper-tiny"]
        cache_dir = get_model_cache_dir(preset)
        assert "models--mlx-community--whisper-tiny" in str(cache_dir)
