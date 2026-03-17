"""Tests for the Quick Look preview panel."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def _mock_appkit():
    """Patch AppKit / Quartz imports used by QuickLookPanel."""
    mock_panel_cls = MagicMock()
    mock_panel_instance = MagicMock()
    mock_panel_cls.alloc.return_value.initWithContentRect_styleMask_backing_defer_.return_value = (
        mock_panel_instance
    )
    mock_panel_instance.isVisible.return_value = False
    mock_panel_instance.contentView.return_value.bounds.return_value = (0, 0, 680, 520)

    mock_ql_view = MagicMock()
    mock_ql_view_cls = MagicMock()
    mock_ql_view_cls.alloc.return_value.initWithFrame_style_.return_value = mock_ql_view

    mock_delegate_cls = MagicMock()
    mock_delegate = MagicMock()
    mock_delegate_cls.alloc.return_value.init.return_value = mock_delegate

    with patch(
        "wenzi.scripting.ui.quicklook_panel._get_ql_panel_class",
        return_value=mock_panel_cls,
    ), patch(
        "wenzi.scripting.ui.quicklook_panel._get_ql_delegate_class",
        return_value=mock_delegate_cls,
    ), patch.dict("sys.modules", {
        "AppKit": MagicMock(),
        "Foundation": MagicMock(),
        "Quartz": MagicMock(**{"QLPreviewView": mock_ql_view_cls}),
    }):
        yield {
            "panel_cls": mock_panel_cls,
            "panel": mock_panel_instance,
            "ql_view_cls": mock_ql_view_cls,
            "ql_view": mock_ql_view,
            "delegate": mock_delegate,
        }


class TestQuickLookPanel:
    def test_initial_state(self):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        assert not ql.is_visible
        assert ql._panel is None
        assert ql._current_path is None

    def test_show_nonexistent_path_is_noop(self):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        with patch("os.path.exists", return_value=False):
            ql.show("/no/such/file", anchor_panel=MagicMock())
        assert ql._panel is None

    def test_show_creates_panel_and_sets_preview(self, _mock_appkit):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        anchor = MagicMock()

        with patch("os.path.exists", return_value=True):
            ql.show("/tmp/test.pdf", anchor_panel=anchor)

        assert ql._panel is not None
        assert ql._ql_view is not None
        ql._panel.center.assert_called_once()
        ql._panel.orderFront_.assert_called_once_with(None)

    def test_show_again_does_not_recenter(self, _mock_appkit):
        """Reopening for a different file should not reset position."""
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        anchor = MagicMock()

        with patch("os.path.exists", return_value=True):
            ql.show("/tmp/a.pdf", anchor_panel=anchor)
            ql._panel.center.reset_mock()
            # Panel already exists, show again
            ql.show("/tmp/b.pdf", anchor_panel=anchor)

        ql._panel.center.assert_not_called()

    def test_update_changes_preview_item(self, _mock_appkit):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        anchor = MagicMock()

        with patch("os.path.exists", return_value=True):
            ql.show("/tmp/a.pdf", anchor_panel=anchor)
            ql.update("/tmp/b.pdf")

        assert ql._current_path == "/tmp/b.pdf"

    def test_update_same_path_is_noop(self, _mock_appkit):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        anchor = MagicMock()

        with patch("os.path.exists", return_value=True):
            ql.show("/tmp/a.pdf", anchor_panel=anchor)
            # Reset mock to track subsequent calls
            ql._ql_view.setPreviewItem_.reset_mock()
            ql.update("/tmp/a.pdf")

        ql._ql_view.setPreviewItem_.assert_not_called()

    def test_close_cleans_up(self, _mock_appkit):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        anchor = MagicMock()

        with patch("os.path.exists", return_value=True):
            ql.show("/tmp/test.pdf", anchor_panel=anchor)

        panel_ref = ql._panel
        delegate_ref = ql._delegate
        ql.close()

        panel_ref.setDelegate_.assert_called_with(None)
        panel_ref.orderOut_.assert_called_once_with(None)
        assert delegate_ref._panel_ref is None
        assert ql._panel is None
        assert ql._ql_view is None
        assert ql._delegate is None
        assert ql._current_path is None

    def test_close_when_not_open_is_noop(self):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        ql.close()  # Should not raise

    def test_update_when_not_open_is_noop(self):
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        ql = QuickLookPanel()
        with patch("os.path.exists", return_value=True):
            ql.update("/tmp/test.pdf")  # Should not raise

    def test_on_resign_key_callback(self, _mock_appkit):
        """on_resign_key callback should be stored."""
        from wenzi.scripting.ui.quicklook_panel import QuickLookPanel

        callback = MagicMock()
        ql = QuickLookPanel(on_resign_key=callback)
        assert ql._on_resign_key is callback
