"""Tests for wenzi.ui_helpers focus management utilities."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

from wenzi.ui_helpers import reactivate_app


class TestGetFrontmostApp:
    """Tests for get_frontmost_app()."""

    def test_returns_frontmost_application(self):
        """Should return the frontmost NSRunningApplication."""
        mock_app = MagicMock()
        mock_ws = MagicMock()
        mock_ws.sharedWorkspace.return_value.frontmostApplication.return_value = mock_app
        with patch.dict("sys.modules", {"AppKit": MagicMock(NSWorkspace=mock_ws)}):
            # Need to re-import since the function does `from AppKit import NSWorkspace`
            import importlib

            import wenzi.ui_helpers as mod

            importlib.reload(mod)
            result = mod.get_frontmost_app()
        assert result is mock_app

    def test_returns_none_on_exception(self):
        """Should return None when NSWorkspace raises."""
        mock_appkit = MagicMock()
        mock_appkit.NSWorkspace.sharedWorkspace.side_effect = Exception("fail")
        with patch.dict("sys.modules", {"AppKit": mock_appkit}):
            import importlib

            import wenzi.ui_helpers as mod

            importlib.reload(mod)
            result = mod.get_frontmost_app()
        assert result is None


class TestReactivateApp:
    """Tests for reactivate_app()."""

    @patch("threading.current_thread")
    @patch("threading.main_thread")
    def test_activates_without_all_windows_flag(self, mock_main, mock_current):
        """Should call activateWithOptions_ with only IgnoringOtherApps (2)."""
        mock_current.return_value = mock_main.return_value  # on main thread
        mock_running_app = MagicMock()
        reactivate_app(mock_running_app)
        mock_running_app.activateWithOptions_.assert_called_once_with(2)

    @patch("threading.current_thread")
    @patch("threading.main_thread")
    def test_none_app_is_noop(self, mock_main, mock_current):
        """Should do nothing when running_app is None."""
        mock_current.return_value = mock_main.return_value
        reactivate_app(None)  # Should not raise

    @patch("threading.current_thread")
    @patch("threading.main_thread")
    def test_defers_to_main_thread_when_not_on_main(self, mock_main, mock_current):
        """Should use AppHelper.callAfter when not on main thread."""
        mock_current.return_value = MagicMock()  # different from main thread
        mock_running_app = MagicMock()
        with patch("PyObjCTools.AppHelper") as mock_helper:
            reactivate_app(mock_running_app)
            mock_helper.callAfter.assert_called_once()


class TestConfigureGlassAppearance:
    """Tests for configure_glass_appearance()."""

    def _run_case(self, appearance_name: str):
        mock_sys_appearance = MagicMock()
        mock_sys_appearance.bestMatchFromAppearancesWithNames_.return_value = appearance_name

        mock_app = MagicMock()
        mock_app.effectiveAppearance.return_value = mock_sys_appearance

        mock_appkit = MagicMock(NSApp=mock_app)
        glass = MagicMock()
        glass.respondsToSelector_.return_value = True

        original = sys.modules.get("AppKit")
        with patch.dict(sys.modules, {"AppKit": mock_appkit}):
            import wenzi.ui_helpers as mod

            importlib.reload(mod)
            mod.configure_glass_appearance(glass)

        if original is not None:
            sys.modules["AppKit"] = original
        else:
            sys.modules.pop("AppKit", None)

        return glass, mock_sys_appearance

    def test_disables_adaptive_sampling_for_light_mode(self):
        glass, mock_sys_appearance = self._run_case("NSAppearanceNameAqua")

        glass.setAppearance_.assert_called_once_with(mock_sys_appearance)
        glass.set_adaptiveAppearance_.assert_called_once_with(1)

    def test_disables_adaptive_sampling_for_dark_mode(self):
        glass, mock_sys_appearance = self._run_case("NSAppearanceNameDarkAqua")

        glass.setAppearance_.assert_called_once_with(mock_sys_appearance)
        glass.set_adaptiveAppearance_.assert_called_once_with(1)
