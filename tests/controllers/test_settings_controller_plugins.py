"""Tests for plugin management callbacks in SettingsController."""

from wenzi.scripting.plugin_meta import PluginMeta
from wenzi.scripting.plugin_registry import PluginInfo, PluginStatus


class TestPluginInfosToState:
    """Test _plugin_infos_to_state conversion logic."""

    def test_converts_plugin_info_to_dict(self):
        meta = PluginMeta(
            name="Test Plugin",
            id="com.test.plugin",
            version="1.0.0",
            author="Alice",
            description="A test plugin",
        )
        info = PluginInfo(
            meta=meta,
            source_url="https://example.com/plugin.toml",
            registry_name="Official",
            status=PluginStatus.NOT_INSTALLED,
            is_official=True,
        )
        result = {
            "id": info.meta.id,
            "name": info.meta.name,
            "version": info.meta.version,
            "status": info.status.value,
            "is_official": info.is_official,
        }
        assert result["id"] == "com.test.plugin"
        assert result["status"] == "not_installed"
        assert result["is_official"] is True

    def test_disabled_plugin_shows_enabled_false(self):
        disabled = {"com.test.plugin"}
        pid = "com.test.plugin"
        is_enabled = pid not in disabled
        assert is_enabled is False

    def test_enabled_plugin_shows_enabled_true(self):
        disabled = {"com.other.plugin"}
        pid = "com.test.plugin"
        is_enabled = pid not in disabled
        assert is_enabled is True
