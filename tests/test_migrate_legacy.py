"""Tests for VoiceText → WenZi legacy path migration."""

from unittest.mock import patch

from wenzi.config import migrate_legacy_paths


class TestMigrateLegacyPaths:
    """Test migrate_legacy_paths() moves old directories to new locations."""

    def test_migrates_config_dir(self, tmp_path):
        old = tmp_path / ".config" / "VoiceText"
        new = tmp_path / ".config" / "WenZi"
        old.mkdir(parents=True)
        (old / "config.json").write_text("{}")

        with patch("wenzi.config._LEGACY_CONFIG_DIR", str(old)), \
             patch("wenzi.config.DEFAULT_CONFIG_DIR", str(new)), \
             patch("wenzi.config._LEGACY_CACHE_DIR", str(tmp_path / "no-cache")), \
             patch("wenzi.config._LEGACY_LOG_DIR", str(tmp_path / "no-logs")), \
             patch("wenzi.config.os.path.expanduser", side_effect=lambda p: p):
            migrate_legacy_paths()

        assert new.is_dir()
        assert (new / "config.json").exists()
        assert not old.exists()

    def test_migrates_cache_dir(self, tmp_path):
        old_cache = tmp_path / ".cache" / "voicetext"
        new_cache = tmp_path / ".cache" / "wenzi"
        old_cache.mkdir(parents=True)
        (old_cache / "models").mkdir()

        with patch("wenzi.config.os.path.expanduser", side_effect=lambda p: p):
            from wenzi.config import _migrate_dir
            _migrate_dir(str(old_cache), str(new_cache), "cache")

        assert new_cache.is_dir()
        assert (new_cache / "models").is_dir()
        assert not old_cache.exists()

    def test_skips_when_new_exists(self, tmp_path):
        old = tmp_path / ".config" / "VoiceText"
        new = tmp_path / ".config" / "WenZi"
        old.mkdir(parents=True)
        new.mkdir(parents=True)
        (old / "old.txt").write_text("old")
        (new / "new.txt").write_text("new")

        with patch("wenzi.config._LEGACY_CONFIG_DIR", str(old)), \
             patch("wenzi.config.DEFAULT_CONFIG_DIR", str(new)), \
             patch("wenzi.config._LEGACY_CACHE_DIR", str(tmp_path / "no-cache")), \
             patch("wenzi.config._LEGACY_LOG_DIR", str(tmp_path / "no-logs")), \
             patch("wenzi.config.os.path.expanduser", side_effect=lambda p: p):
            migrate_legacy_paths()

        # Both should remain untouched
        assert old.is_dir()
        assert new.is_dir()
        assert (old / "old.txt").exists()
        assert (new / "new.txt").exists()

    def test_skips_when_old_missing(self, tmp_path):
        old = tmp_path / ".config" / "VoiceText"
        new = tmp_path / ".config" / "WenZi"

        with patch("wenzi.config._LEGACY_CONFIG_DIR", str(old)), \
             patch("wenzi.config.DEFAULT_CONFIG_DIR", str(new)), \
             patch("wenzi.config._LEGACY_CACHE_DIR", str(tmp_path / "no-cache")), \
             patch("wenzi.config._LEGACY_LOG_DIR", str(tmp_path / "no-logs")), \
             patch("wenzi.config.os.path.expanduser", side_effect=lambda p: p):
            migrate_legacy_paths()

        assert not old.exists()
        assert not new.exists()

    def test_handles_rename_failure(self, tmp_path):
        old = tmp_path / ".config" / "VoiceText"
        new = tmp_path / ".config" / "WenZi"
        old.mkdir(parents=True)

        with patch("wenzi.config._LEGACY_CONFIG_DIR", str(old)), \
             patch("wenzi.config.DEFAULT_CONFIG_DIR", str(new)), \
             patch("wenzi.config._LEGACY_CACHE_DIR", str(tmp_path / "no-cache")), \
             patch("wenzi.config._LEGACY_LOG_DIR", str(tmp_path / "no-logs")), \
             patch("wenzi.config.os.path.expanduser", side_effect=lambda p: p), \
             patch("os.rename", side_effect=OSError("permission denied")):
            # Should not raise
            migrate_legacy_paths()

        # Old dir still exists since rename failed
        assert old.is_dir()
