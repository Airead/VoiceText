"""Tests for configuration module."""

import json
import os
import tempfile

import pytest

from voicetext.config import DEFAULT_CONFIG, load_config, _merge_dict


class TestMergeDict:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        overrides = {"b": 3, "c": 4}
        result = _merge_dict(base, overrides)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        overrides = {"a": {"y": 99}}
        result = _merge_dict(base, overrides)
        assert result == {"a": {"x": 1, "y": 99}, "b": 3}

    def test_override_nested_with_scalar(self):
        base = {"a": {"x": 1}}
        overrides = {"a": "replaced"}
        result = _merge_dict(base, overrides)
        assert result == {"a": "replaced"}

    def test_empty_overrides(self):
        base = {"a": 1}
        assert _merge_dict(base, {}) == {"a": 1}


class TestLoadConfig:
    def test_default_config(self):
        config = load_config()
        assert config["hotkey"] == "f2"
        assert config["audio"]["sample_rate"] == 16000

    def test_load_from_file(self):
        overrides = {"hotkey": "f5", "audio": {"sample_rate": 44100}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(overrides, f)
            tmp_path = f.name

        try:
            config = load_config(tmp_path)
            assert config["hotkey"] == "f5"
            assert config["audio"]["sample_rate"] == 44100
            # Defaults should be preserved for unset keys
            assert config["audio"]["block_ms"] == 20
        finally:
            os.unlink(tmp_path)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")
