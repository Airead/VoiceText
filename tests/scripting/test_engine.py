"""Tests for script engine."""

from unittest.mock import patch

from voicetext.scripting.engine import ScriptEngine


class TestScriptEngine:
    def test_init_creates_vt(self):
        engine = ScriptEngine(script_dir="/tmp/vt_test_scripts")
        assert engine.vt is not None
        assert engine.vt._reload_callback is not None

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_load_nonexistent_dir(self, mock_stop, mock_start):
        engine = ScriptEngine(script_dir="/tmp/nonexistent_vt_scripts")
        engine.start()
        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_load_script(self, mock_stop, mock_start, tmp_path):
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        init_py = script_dir / "init.py"
        init_py.write_text(
            'vt.leader("cmd_r", [{"key": "w", "app": "WeChat"}])\n'
        )

        engine = ScriptEngine(script_dir=str(script_dir))
        engine.start()

        assert "cmd_r" in engine._registry.leaders
        assert engine._registry.leaders["cmd_r"].mappings[0].app == "WeChat"

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_load_script_with_error(self, mock_stop, mock_start, tmp_path):
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        init_py = script_dir / "init.py"
        init_py.write_text("raise ValueError('test error')\n")

        engine = ScriptEngine(script_dir=str(script_dir))
        # Should not raise, error is caught
        with patch("voicetext.scripting.engine.logger") as mock_logger:
            engine.start()
            mock_logger.error.assert_called()
        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_reload(self, mock_stop, mock_start, tmp_path):
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        init_py = script_dir / "init.py"
        init_py.write_text(
            'vt.leader("cmd_r", [{"key": "w", "app": "WeChat"}])\n'
        )

        engine = ScriptEngine(script_dir=str(script_dir))
        engine.start()
        assert "cmd_r" in engine._registry.leaders

        # Modify script
        init_py.write_text(
            'vt.leader("alt_r", [{"key": "s", "app": "Slack"}])\n'
        )
        engine.reload()
        assert "alt_r" in engine._registry.leaders
        assert "cmd_r" not in engine._registry.leaders

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_chooser_disabled_skips_sources_and_hotkeys(self, mock_stop, mock_start):
        """When chooser.enabled is False, no sources are registered and no hotkeys bound."""
        config = {
            "chooser": {
                "enabled": False,
                "hotkey": "cmd+space",
                "app_search": True,
                "clipboard_history": True,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        # No sources should be registered on the chooser panel
        panel = engine.vt.chooser._get_panel()
        assert len(panel._sources) == 0

        # Clipboard monitor should not be started
        assert engine._clipboard_monitor is None

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_chooser_enabled_registers_sources(self, mock_stop, mock_start):
        """When chooser.enabled is True (default), sources are registered normally."""
        config = {
            "chooser": {
                "enabled": True,
                "hotkey": "cmd+space",
                "app_search": True,
                "clipboard_history": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        # App source should be registered
        panel = engine.vt.chooser._get_panel()
        assert len(panel._sources) > 0

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_enable_clipboard_at_runtime(self, mock_stop, mock_start):
        """enable_clipboard() starts monitor and registers source."""
        config = {
            "chooser": {
                "enabled": True,
                "clipboard_history": False,
                "app_search": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        # Clipboard should not be running
        assert engine._clipboard_monitor is None
        panel = engine.vt.chooser._get_panel()
        assert "clipboard" not in panel._sources

        # Enable at runtime
        engine.enable_clipboard()
        assert engine._clipboard_monitor is not None
        assert "clipboard" in panel._sources

        # Calling again should be a no-op (not raise)
        engine.enable_clipboard()

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_disable_clipboard_at_runtime(self, mock_stop, mock_start):
        """disable_clipboard() stops monitor and unregisters source."""
        config = {
            "chooser": {
                "enabled": True,
                "clipboard_history": True,
                "app_search": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        # Clipboard should be running
        assert engine._clipboard_monitor is not None
        panel = engine.vt.chooser._get_panel()
        assert "clipboard" in panel._sources

        # Disable at runtime
        engine.disable_clipboard()
        assert engine._clipboard_monitor is None
        assert "clipboard" not in panel._sources

        # Calling again should be a no-op (not raise)
        engine.disable_clipboard()

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_disable_chooser_at_runtime(self, mock_stop, mock_start):
        """disable_chooser() clears all sources, monitors, and hotkeys."""
        config = {
            "chooser": {
                "enabled": True,
                "hotkey": "cmd+space",
                "app_search": True,
                "clipboard_history": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        panel = engine.vt.chooser._get_panel()
        assert len(panel._sources) > 0

        engine.disable_chooser()
        assert len(panel._sources) == 0
        assert engine._clipboard_monitor is None
        assert engine._snippet_store is None
        assert engine._usage_tracker is None

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_enable_chooser_at_runtime(self, mock_stop, mock_start):
        """enable_chooser() re-registers sources after disable."""
        config = {
            "chooser": {
                "enabled": True,
                "hotkey": "cmd+space",
                "app_search": True,
                "clipboard_history": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        panel = engine.vt.chooser._get_panel()
        engine.disable_chooser()
        assert len(panel._sources) == 0

        # Re-enable — must bypass the config "enabled" check
        # since disable_chooser doesn't change config
        engine.enable_chooser()
        assert len(panel._sources) > 0

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_enable_disable_source_at_runtime(self, mock_stop, mock_start):
        """enable_source / disable_source toggle individual sources."""
        config = {
            "chooser": {
                "enabled": True,
                "hotkey": "cmd+space",
                "app_search": False,
                "clipboard_history": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        panel = engine.vt.chooser._get_panel()
        assert "apps" not in panel._sources

        engine.enable_source("app_search")
        assert "apps" in panel._sources

        engine.disable_source("app_search")
        assert "apps" not in panel._sources

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_rebind_chooser_hotkey(self, mock_stop, mock_start):
        """rebind_chooser_hotkey unbinds old and binds new hotkey."""
        config = {
            "chooser": {
                "enabled": True,
                "hotkey": "cmd+space",
                "app_search": False,
                "clipboard_history": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        # Rebind should not raise
        engine.rebind_chooser_hotkey("cmd+space", "alt+space")

        engine.stop()

    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.start")
    @patch("voicetext.scripting.api.hotkey.HotkeyAPI.stop")
    def test_set_usage_learning_at_runtime(self, mock_stop, mock_start):
        """set_usage_learning toggles the tracker on the panel."""
        config = {
            "chooser": {
                "enabled": True,
                "app_search": False,
                "clipboard_history": False,
                "file_search": False,
                "snippets": False,
                "bookmarks": False,
                "usage_learning": False,
            },
        }
        engine = ScriptEngine(
            script_dir="/tmp/nonexistent_vt_scripts",
            config=config,
        )
        engine.start()

        panel = engine.vt.chooser._get_panel()
        assert panel._usage_tracker is None

        engine.set_usage_learning(True)
        assert panel._usage_tracker is not None

        engine.set_usage_learning(False)
        assert panel._usage_tracker is None

        engine.stop()

    def test_vt_module_singleton(self):
        engine = ScriptEngine(script_dir="/tmp/vt_test_scripts")
        import voicetext.scripting.api as api_mod

        assert api_mod.vt is engine.vt
