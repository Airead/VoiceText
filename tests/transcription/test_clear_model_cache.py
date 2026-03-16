"""Tests for clear_model_cache function."""

from unittest.mock import patch

from wenzi.transcription.model_registry import (
    ModelPreset,
    clear_model_cache,
)


class TestClearModelCache:
    def test_clears_existing_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "model_cache"
        cache_dir.mkdir()
        (cache_dir / "model.onnx").write_bytes(b"fake model data")
        (cache_dir / "config.json").write_text("{}")

        preset = ModelPreset(
            id="test-model",
            display_name="Test",
            backend="funasr",
            model=None,
            language=None,
        )

        with patch(
            "wenzi.transcription.model_registry.get_model_cache_dir",
            return_value=cache_dir,
        ):
            result = clear_model_cache(preset)

        assert result is True
        assert not cache_dir.exists()

    def test_returns_false_when_no_cache(self, tmp_path):
        cache_dir = tmp_path / "nonexistent"

        preset = ModelPreset(
            id="test-model",
            display_name="Test",
            backend="funasr",
            model=None,
            language=None,
        )

        with patch(
            "wenzi.transcription.model_registry.get_model_cache_dir",
            return_value=cache_dir,
        ):
            result = clear_model_cache(preset)

        assert result is False

    def test_clears_nested_directory(self, tmp_path):
        cache_dir = tmp_path / "model_cache"
        sub = cache_dir / "subdir"
        sub.mkdir(parents=True)
        (sub / "weights.bin").write_bytes(b"x" * 100)

        preset = ModelPreset(
            id="test-model",
            display_name="Test",
            backend="mlx-whisper",
            model="mlx-community/test",
            language=None,
        )

        with patch(
            "wenzi.transcription.model_registry.get_model_cache_dir",
            return_value=cache_dir,
        ):
            result = clear_model_cache(preset)

        assert result is True
        assert not cache_dir.exists()
