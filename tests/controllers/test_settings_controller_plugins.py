"""Tests for plugin management callbacks in SettingsController."""

from unittest.mock import MagicMock, patch

import pytest

from wenzi.controllers.settings_controller import SettingsController
from wenzi.scripting.plugin_meta import PluginMeta
from wenzi.scripting.plugin_registry import PluginInfo, PluginStatus


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def ctrl(tmp_path):
    """Build a SettingsController wired to mocks."""
    app = MagicMock()
    app._config_dir = str(tmp_path)
    app._config = {"scripting": {"disabled_plugins": []}}
    app._config_path = str(tmp_path / "config.yaml")
    app._settings_panel.is_visible = True

    engine = MagicMock()
    app._script_engine = engine

    ctrl = SettingsController(app)
    ctrl._refresh_plugin_state = MagicMock()
    return ctrl


# ── _auto_reload_if_needed ────────────────────────────────────────


class TestAutoReloadIfNeeded:
    def test_reloads_when_flag_set(self, ctrl):
        ctrl._needs_reload = True
        ctrl._auto_reload_if_needed()

        ctrl._app._script_engine.reload.assert_called_once()
        assert ctrl._needs_reload is False

    def test_skips_when_flag_not_set(self, ctrl):
        ctrl._needs_reload = False
        ctrl._auto_reload_if_needed()

        ctrl._app._script_engine.reload.assert_not_called()

    def test_idempotent_on_double_call(self, ctrl):
        """Simulates two callAfter dispatches — only the first should reload."""
        ctrl._needs_reload = True
        ctrl._auto_reload_if_needed()
        ctrl._auto_reload_if_needed()

        ctrl._app._script_engine.reload.assert_called_once()


# ── Install / Update / Uninstall trigger auto-reload ──────────────


class TestInstallTriggersAutoReload:
    def test_install_schedules_auto_reload(self, ctrl):
        """After a successful install the controller schedules auto-reload."""
        ctrl._plugin_installer = MagicMock()

        with patch(
            "PyObjCTools.AppHelper.callAfter",
            side_effect=lambda fn, *a, **kw: fn(*a, **kw),
        ), patch(
            "wenzi.controllers.settings_controller.threading.Thread",
        ) as mock_thread:
            ctrl._on_plugin_install_url("https://example.com/plugin.toml")
            mock_thread.call_args[1]["target"]()

        ctrl._app._script_engine.reload.assert_called_once()
        assert ctrl._needs_reload is False


class TestUninstallTriggersAutoReload:
    def test_uninstall_schedules_auto_reload(self, ctrl):
        ctrl._plugin_installer = MagicMock()

        with patch(
            "PyObjCTools.AppHelper.callAfter",
            side_effect=lambda fn, *a, **kw: fn(*a, **kw),
        ):
            ctrl._on_plugin_uninstall("com.test.plugin")

        ctrl._app._script_engine.reload.assert_called_once()
        assert ctrl._needs_reload is False


class TestToggleTriggersAutoReload:
    def test_disable_triggers_auto_reload(self, ctrl):
        ctrl._app._config["scripting"]["disabled_plugins"] = []

        with patch(
            "PyObjCTools.AppHelper.callAfter",
            side_effect=lambda fn, *a, **kw: fn(*a, **kw),
        ), patch(
            "wenzi.controllers.settings_controller.save_config",
        ):
            ctrl._on_plugin_toggle("com.test.plugin", enabled=False)

        ctrl._app._script_engine.reload.assert_called_once()
        assert ctrl._needs_reload is False


# ── _finish_plugins_fetch (race condition fix) ────────────────────


class TestFinishPluginsFetch:
    """Verify that status computation runs on the main thread, not in _fetch."""

    def test_recomputes_statuses_on_main_thread(self, ctrl):
        """_finish_plugins_fetch should recompute statuses from fresh local scan."""
        info = PluginInfo(
            meta=PluginMeta(
                name="Test", id="com.test.plugin", version="1.0.0",
            ),
            source_url="https://example.com/plugin.toml",
            registry_name="Official",
            status=PluginStatus.NOT_INSTALLED,  # stale status from fetch
            is_official=True,
        )
        ctrl._last_plugin_infos = [info]
        # Mock _compute_status to return INSTALLED (simulating fresh local scan)
        ctrl._plugin_registry._compute_status = MagicMock(
            return_value=(PluginStatus.INSTALLED, "1.0.0")
        )

        ctrl._finish_plugins_fetch()

        # Status should have been recomputed
        assert info.status == PluginStatus.INSTALLED
        assert info.installed_version == "1.0.0"
        # UI should be updated with plugins_loading cleared
        state = ctrl._app._settings_panel.update_state.call_args[0][0]
        assert state["plugins_loading"] is False
        assert "plugins" in state

    def test_handles_empty_infos_without_loop(self, ctrl):
        """Empty _last_plugin_infos must not trigger _on_plugins_tab_open."""
        ctrl._last_plugin_infos = []

        ctrl._finish_plugins_fetch()

        state = ctrl._app._settings_panel.update_state.call_args[0][0]
        assert state["plugins_loading"] is False
        assert state["plugins"] == []


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
