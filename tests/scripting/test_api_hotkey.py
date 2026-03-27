"""Tests for wz.hotkey API — leader-key logic and custom key registration."""

from unittest.mock import patch, MagicMock

from wenzi.hotkey import _SPECIAL_VK, _VK_TO_NAME, _ALL_KEY_NAMES, unregister_custom_keys
from wenzi.scripting.registry import LeaderMapping, RemapEntry, ScriptingRegistry
from wenzi.scripting.api.hotkey import HotkeyAPI


class TestHotkeyAPI:
    def _make_api(self):
        reg = ScriptingRegistry()
        reg.register_leader("cmd_r", [
            LeaderMapping(key="w", app="WeChat"),
            LeaderMapping(key="d", desc="date", func=lambda: None),
        ])
        api = HotkeyAPI(reg)
        return reg, api

    def test_bind_registers(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.bind("ctrl+cmd+v", lambda: None)
        assert len(reg.hotkeys) == 1
        assert reg.hotkeys[0].hotkey_str == "ctrl+cmd+v"

    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_leader_press_activates(self, mock_helper):
        _, api = self._make_api()
        result = api._on_press("cmd_r")
        assert result is False  # Don't swallow FlagsChanged
        assert api._active_leader is not None
        assert api._active_leader.trigger_key == "cmd_r"

    @patch.object(HotkeyAPI, "_execute_mapping")
    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_leader_subkey_executes(self, mock_helper, mock_exec):
        _, api = self._make_api()
        api._on_press("cmd_r")
        result = api._on_press("w")
        assert result is True  # Swallowed
        assert api._leader_triggered is True

    @patch.object(HotkeyAPI, "_execute_mapping")
    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_leader_release_deactivates(self, mock_helper, mock_exec):
        _, api = self._make_api()
        api._on_press("cmd_r")
        api._on_press("w")
        api._on_release("cmd_r")
        assert api._active_leader is None

    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_leader_tap_without_subkey(self, mock_helper):
        _, api = self._make_api()
        api._on_press("cmd_r")
        api._on_release("cmd_r")
        assert api._active_leader is None
        assert api._leader_triggered is False

    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_non_leader_key_ignored(self, mock_helper):
        _, api = self._make_api()
        result = api._on_press("shift")
        assert result is False

    @patch.object(HotkeyAPI, "_execute_mapping")
    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_unmatched_subkey_still_swallowed(self, mock_helper, mock_exec):
        _, api = self._make_api()
        api._on_press("cmd_r")
        result = api._on_press("z")
        assert result is True  # Still swallowed during leader mode
        mock_exec.assert_not_called()  # No mapping for "z"

    def test_execute_mapping_app(self):
        _, api = self._make_api()
        with patch("AppKit.NSWorkspace") as mock_ws_cls:
            ws = MagicMock()
            ws.launchApplication_.return_value = True
            mock_ws_cls.sharedWorkspace.return_value = ws
            api._execute_mapping(LeaderMapping(key="w", app="WeChat"))
            ws.launchApplication_.assert_called_once_with("WeChat")

    def test_execute_mapping_func(self):
        result = []
        mapping = LeaderMapping(key="d", func=lambda: result.append(1))
        _, api = self._make_api()
        api._execute_mapping(mapping)
        assert result == [1]

    @patch("wenzi.scripting.api.execute.subprocess")
    def test_execute_mapping_exec(self, mock_sp):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_sp.run.return_value = mock_result

        _, api = self._make_api()
        mapping = LeaderMapping(key="i", exec_cmd="echo hello")
        api._execute_mapping(mapping)
        mock_sp.run.assert_called_once()

    @patch("PyObjCTools.AppHelper.callAfter")
    def test_stop_closes_leader_alert(self, mock_call_after):
        """stop() should close the leader alert panel to prevent orphaned panels."""
        _, api = self._make_api()
        api._leader_alert = MagicMock()
        api.stop()
        mock_call_after.assert_called_with(api._leader_alert.close)


class TestDefineKeys:
    """Tests for HotkeyAPI.define_key / define_keys."""

    def setup_method(self):
        unregister_custom_keys()

    def teardown_method(self):
        unregister_custom_keys()

    def test_define_key(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.define_key("kp+", 69)
        assert _SPECIAL_VK["kp+"] == 69
        assert _VK_TO_NAME[69] == "kp+"
        assert "kp+" in _ALL_KEY_NAMES

    def test_define_keys_batch(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.define_keys({"kp-": 78, "kp*": 67, "kp/": 75})
        assert _SPECIAL_VK["kp-"] == 78
        assert _SPECIAL_VK["kp*"] == 67
        assert _SPECIAL_VK["kp/"] == 75

    @patch.object(HotkeyAPI, "_execute_mapping")
    @patch("wenzi.scripting.api.hotkey.AppHelper", create=True)
    def test_leader_with_custom_key(self, mock_helper, mock_exec):
        """Custom keys should work in leader mappings."""
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.define_key("kp+", 69)
        reg.register_leader("cmd_r", [
            LeaderMapping(key="kp+", desc="plus", func=lambda: None),
        ])
        api._on_press("cmd_r")
        result = api._on_press("kp+")
        assert result is True
        assert api._leader_triggered is True


class TestRemap:
    """Tests for HotkeyAPI.remap / unremap."""

    def test_remap_registers_modifier_source(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.remap("shift_r", "f19")
        assert 60 in reg.remaps  # shift_r vk = 60
        entry = reg.remaps[60]
        assert entry.source_name == "shift_r"
        assert entry.target_name == "f19"
        assert entry.source_vk == 60
        assert entry.target_vk == 80  # f19 vk = 80
        assert entry.is_modifier is True
        assert entry.mod_flag == 0x020000  # shift flag

    def test_remap_registers_regular_key(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.remap("f13", "esc")
        assert 105 in reg.remaps  # f13 vk = 105
        entry = reg.remaps[105]
        assert entry.is_modifier is False
        assert entry.mod_flag == 0

    def test_unremap_removes(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.remap("shift_r", "f19")
        assert 60 in reg.remaps
        api.unremap("shift_r")
        assert 60 not in reg.remaps

    def test_unremap_nonexistent_is_noop(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api.unremap("shift_r")  # should not raise

    def test_remap_unknown_key_raises(self):
        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        import pytest
        with pytest.raises(ValueError, match="Unknown key"):
            api.remap("nonexistent", "f19")

    @patch("wenzi.hotkey.KeyRemapListener")
    def test_remap_starts_listener_when_started(self, mock_listener_cls):
        mock_listener = MagicMock()
        mock_listener.is_running.return_value = False
        mock_listener_cls.return_value = mock_listener

        reg = ScriptingRegistry()
        api = HotkeyAPI(reg)
        api._started = True
        api.remap("shift_r", "f19")

        mock_listener.add.assert_called_once_with(60, 80, True, 0x020000)
        mock_listener.start.assert_called_once()

    def test_registry_clear_clears_remaps(self):
        reg = ScriptingRegistry()
        reg.register_remap(RemapEntry(
            source_name="shift_r", target_name="f19",
            source_vk=60, target_vk=80,
            is_modifier=True, mod_flag=0x020000,
        ))
        reg.remap_listener = MagicMock()
        reg.clear()
        assert len(reg.remaps) == 0
        assert reg.remap_listener is None
