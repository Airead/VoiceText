"""Tests for configuration module."""

import json
import os
import tempfile

import pytest

from voicetext.config import DEFAULT_CONFIG, load_config, save_config, _merge_dict


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
    def test_default_config_creates_file(self, tmp_path):
        config_file = tmp_path / "config.json"
        config = load_config(str(config_file))
        assert config["hotkeys"] == {"fn": True}
        assert config["audio"]["sample_rate"] == 16000
        # File should be created
        assert config_file.exists()
        written = json.loads(config_file.read_text())
        assert written["hotkeys"] == {"fn": True}
        assert written["asr"]["backend"] == "funasr"

    def test_default_config_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "sub" / "dir" / "config.json"
        config = load_config(str(config_file))
        assert config_file.exists()
        assert config["hotkeys"] == {"fn": True}

    def test_load_from_file(self):
        overrides = {"hotkeys": {"f5": True}, "audio": {"sample_rate": 44100}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(overrides, f)
            tmp_path = f.name

        try:
            config = load_config(tmp_path)
            assert config["hotkeys"]["f5"] is True
            assert config["audio"]["sample_rate"] == 44100
            # Defaults should be preserved for unset keys
            assert config["audio"]["block_ms"] == 20
        finally:
            os.unlink(tmp_path)

    def test_migrate_legacy_hotkey(self):
        """Old 'hotkey' string auto-migrates to 'hotkeys' dict."""
        overrides = {"hotkey": "f5"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(overrides, f)
            tmp_path = f.name

        try:
            config = load_config(tmp_path)
            assert "hotkey" not in config
            assert config["hotkeys"] == {"f5": True}
            # File should be updated on disk
            written = json.loads(open(tmp_path).read())
            assert "hotkey" not in written
            assert written["hotkeys"] == {"f5": True}
        finally:
            os.unlink(tmp_path)

    def test_explicit_missing_file_creates_default(self, tmp_path):
        config_file = tmp_path / "nonexistent.json"
        config = load_config(str(config_file))
        assert config_file.exists()
        assert config == DEFAULT_CONFIG

    def test_default_config_has_preset_field(self):
        assert "preset" in DEFAULT_CONFIG["asr"]
        assert DEFAULT_CONFIG["asr"]["preset"] is None


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path):
        config_file = tmp_path / "config.json"
        config = dict(DEFAULT_CONFIG)
        config["asr"] = dict(config["asr"])
        config["asr"]["preset"] = "mlx-whisper-tiny"
        save_config(config, str(config_file))

        assert config_file.exists()
        loaded = load_config(str(config_file))
        assert loaded["asr"]["preset"] == "mlx-whisper-tiny"

    def test_save_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "sub" / "dir" / "config.json"
        save_config(DEFAULT_CONFIG, str(config_file))
        assert config_file.exists()

    def test_save_overwrites_existing(self, tmp_path):
        config_file = tmp_path / "config.json"
        save_config(DEFAULT_CONFIG, str(config_file))

        modified = dict(DEFAULT_CONFIG)
        modified["hotkeys"] = {"f5": True}
        save_config(modified, str(config_file))

        loaded = load_config(str(config_file))
        assert loaded["hotkeys"]["f5"] is True
