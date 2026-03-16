"""Tests for vt.app API."""

from unittest.mock import MagicMock, patch

from voicetext.scripting.api.app import AppAPI


class TestAppAPI:
    @patch("AppKit.NSWorkspace")
    def test_launch_success(self, mock_ws_cls):
        ws = MagicMock()
        ws.launchApplication_.return_value = True
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        assert api.launch("Safari") is True
        ws.launchApplication_.assert_called_once_with("Safari")

    @patch("AppKit.NSWorkspace")
    def test_launch_failure(self, mock_ws_cls):
        ws = MagicMock()
        ws.launchApplication_.return_value = False
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        assert api.launch("NonexistentApp") is False

    @patch("AppKit.NSWorkspace")
    def test_launch_with_app_path(self, mock_ws_cls):
        ws = MagicMock()
        ws.launchApplication_.return_value = True
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        assert api.launch("/Applications/Safari.app") is True
        ws.launchApplication_.assert_called_once_with("/Applications/Safari.app")

    @patch("AppKit.NSWorkspace")
    def test_frontmost(self, mock_ws_cls):
        mock_app = MagicMock()
        mock_app.localizedName.return_value = "Finder"
        ws = MagicMock()
        ws.frontmostApplication.return_value = mock_app
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        assert api.frontmost() == "Finder"

    @patch("AppKit.NSWorkspace")
    def test_frontmost_none(self, mock_ws_cls):
        ws = MagicMock()
        ws.frontmostApplication.return_value = None
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        assert api.frontmost() is None


class TestAppRunning:
    @patch("AppKit.NSWorkspace")
    def test_running_filters_regular_apps(self, mock_ws_cls):
        regular = MagicMock()
        regular.activationPolicy.return_value = 0
        regular.localizedName.return_value = "Safari"
        regular.bundleIdentifier.return_value = "com.apple.Safari"
        regular.processIdentifier.return_value = 123

        daemon = MagicMock()
        daemon.activationPolicy.return_value = 2

        ws = MagicMock()
        ws.runningApplications.return_value = [regular, daemon]
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        apps = api.running()
        assert len(apps) == 1
        assert apps[0]["name"] == "Safari"
        assert apps[0]["bundle_id"] == "com.apple.Safari"
        assert apps[0]["pid"] == 123

    @patch("AppKit.NSWorkspace")
    def test_running_empty(self, mock_ws_cls):
        ws = MagicMock()
        ws.runningApplications.return_value = []
        mock_ws_cls.sharedWorkspace.return_value = ws

        api = AppAPI()
        assert api.running() == []

    @patch("AppKit.NSWorkspace")
    def test_running_exception(self, mock_ws_cls):
        mock_ws_cls.sharedWorkspace.side_effect = RuntimeError("boom")
        api = AppAPI()
        assert api.running() == []


class TestAppHide:
    @patch("voicetext.scripting.api.app.AppAPI._find_running_app")
    def test_hide_success(self, mock_find):
        mock_app = MagicMock()
        mock_find.return_value = mock_app

        api = AppAPI()
        assert api.hide("Safari") is True
        mock_app.hide.assert_called_once()

    @patch("voicetext.scripting.api.app.AppAPI._find_running_app")
    def test_hide_not_found(self, mock_find):
        mock_find.return_value = None
        api = AppAPI()
        assert api.hide("Nonexistent") is False

    @patch("voicetext.scripting.api.app.AppAPI._find_running_app")
    def test_hide_exception(self, mock_find):
        mock_app = MagicMock()
        mock_app.hide.side_effect = RuntimeError("boom")
        mock_find.return_value = mock_app

        api = AppAPI()
        assert api.hide("Safari") is False


class TestAppQuit:
    @patch("voicetext.scripting.api.app.AppAPI._find_running_app")
    def test_quit_success(self, mock_find):
        mock_app = MagicMock()
        mock_find.return_value = mock_app

        api = AppAPI()
        assert api.quit("TextEdit") is True
        mock_app.terminate.assert_called_once()

    @patch("voicetext.scripting.api.app.AppAPI._find_running_app")
    def test_quit_not_found(self, mock_find):
        mock_find.return_value = None
        api = AppAPI()
        assert api.quit("Nonexistent") is False

    @patch("voicetext.scripting.api.app.AppAPI._find_running_app")
    def test_quit_exception(self, mock_find):
        mock_app = MagicMock()
        mock_app.terminate.side_effect = RuntimeError("boom")
        mock_find.return_value = mock_app

        api = AppAPI()
        assert api.quit("TextEdit") is False


class TestFindRunningApp:
    @patch("AppKit.NSWorkspace")
    def test_find_by_name(self, mock_ws_cls):
        app1 = MagicMock()
        app1.localizedName.return_value = "Safari"
        app2 = MagicMock()
        app2.localizedName.return_value = "Finder"

        ws = MagicMock()
        ws.runningApplications.return_value = [app1, app2]
        mock_ws_cls.sharedWorkspace.return_value = ws

        found = AppAPI._find_running_app("Finder")
        assert found is app2

    @patch("AppKit.NSWorkspace")
    def test_find_not_found(self, mock_ws_cls):
        ws = MagicMock()
        ws.runningApplications.return_value = []
        mock_ws_cls.sharedWorkspace.return_value = ws

        found = AppAPI._find_running_app("Nonexistent")
        assert found is None
