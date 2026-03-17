"""Quick Look preview panel using QLPreviewView.

Provides a standalone NSPanel that displays a macOS Quick Look preview
for a given file path.  Used by the Chooser when the user toggles
Shift-preview mode.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Panel dimensions
_QL_WIDTH = 680
_QL_HEIGHT = 520
_QL_MIN_WIDTH = 300
_QL_MIN_HEIGHT = 200


class QuickLookPanel:
    """In-process Quick Look preview panel.

    Wraps an NSPanel containing a QLPreviewView.  The panel is centered
    on screen and supports resize, drag, and trackpad pinch-to-zoom.

    Parameters:
        on_resign_key: Called when the panel loses key window status.
            The caller (ChooserPanel) uses this to decide whether to
            close everything.
    """

    def __init__(self, on_resign_key=None) -> None:
        self._panel = None
        self._ql_view = None
        self._delegate = None
        self._current_path: Optional[str] = None
        self._on_resign_key = on_resign_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_visible(self) -> bool:
        return self._panel is not None and self._panel.isVisible()

    def show(self, path: str, anchor_panel) -> None:
        """Show the Quick Look panel for *path*, anchored to *anchor_panel*."""
        if not path or not os.path.exists(path):
            return

        if self._panel is None:
            self._build_panel(anchor_panel)
            self._center_on_screen()

        self._set_preview_item(path)

        # orderFront_ (not makeKeyAndOrderFront_) to avoid stealing focus
        self._panel.orderFront_(None)

    def update(self, path: str) -> None:
        """Update the preview to a different file."""
        if self._panel is None or not path or not os.path.exists(path):
            return
        self._set_preview_item(path)

    def close(self) -> None:
        """Close and release the panel."""
        if self._panel is not None:
            self._panel.setDelegate_(None)
            self._panel.orderOut_(None)
        if self._delegate is not None:
            self._delegate._panel_ref = None
        self._panel = None
        self._ql_view = None
        self._delegate = None
        self._current_path = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_preview_item(self, path: str) -> None:
        """Set the QLPreviewView's preview item to the given path."""
        if self._ql_view is None:
            return
        if path == self._current_path:
            return
        self._current_path = path
        try:
            from Foundation import NSURL

            url = NSURL.fileURLWithPath_(path)
            self._ql_view.setPreviewItem_(url)
        except Exception:
            logger.debug("Failed to set preview item: %s", path, exc_info=True)

    def _build_panel(self, anchor_panel) -> None:
        """Create the NSPanel with an embedded QLPreviewView."""
        try:
            from AppKit import (
                NSBackingStoreBuffered,
                NSColor,
                NSResizableWindowMask,
                NSStatusWindowLevel,
                NSTitledWindowMask,
            )
            from Foundation import NSMakeRect, NSSize
            from Quartz import QLPreviewView

            style = NSTitledWindowMask | NSResizableWindowMask
            panel = _get_ql_panel_class().alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, _QL_WIDTH, _QL_HEIGHT),
                style,
                NSBackingStoreBuffered,
                False,
            )
            panel.setLevel_(NSStatusWindowLevel + 1)
            panel.setHidesOnDeactivate_(True)
            panel.setFloatingPanel_(True)
            panel.setMovableByWindowBackground_(True)
            panel.setCollectionBehavior_(1 << 4)  # canJoinAllSpaces
            panel.setTitle_("Quick Look")
            panel.setBackgroundColor_(NSColor.windowBackgroundColor())
            panel.setMinSize_(NSSize(_QL_MIN_WIDTH, _QL_MIN_HEIGHT))

            # Resign-key delegate
            delegate_cls = _get_ql_delegate_class()
            delegate = delegate_cls.alloc().init()
            delegate._panel_ref = self
            panel.setDelegate_(delegate)

            # QLPreviewView fills the content area
            content_frame = panel.contentView().bounds()
            ql_view = QLPreviewView.alloc().initWithFrame_style_(
                content_frame, 0,
            )
            ql_view.setAutoresizingMask_(0x12)  # Width + Height sizable
            panel.contentView().addSubview_(ql_view)

            self._panel = panel
            self._ql_view = ql_view
            self._delegate = delegate
        except Exception:
            logger.exception("Failed to build Quick Look panel")
            self._panel = None
            self._ql_view = None

    def _center_on_screen(self) -> None:
        """Center the QL panel on the main screen."""
        if self._panel is None:
            return
        self._panel.center()


# ---------------------------------------------------------------------------
# NSPanel subclass (lazy-created, unique ObjC class name)
# ---------------------------------------------------------------------------
_QLPanel = None


def _get_ql_panel_class():
    """Return an NSPanel subclass that can become key for user interaction."""
    global _QLPanel
    if _QLPanel is not None:
        return _QLPanel

    from AppKit import NSPanel

    class QuickLookPreviewPanel(NSPanel):
        def canBecomeKeyWindow(self):
            return True

    _QLPanel = QuickLookPreviewPanel
    return _QLPanel


# ---------------------------------------------------------------------------
# Panel delegate (lazy-created, unique ObjC class name)
# ---------------------------------------------------------------------------
_QLDelegate = None


def _get_ql_delegate_class():
    """Return an NSObject subclass that forwards resign-key to the panel."""
    global _QLDelegate
    if _QLDelegate is not None:
        return _QLDelegate

    from Foundation import NSObject

    class QuickLookPanelDelegate(NSObject):
        _panel_ref = None

        def windowDidResignKey_(self, notification):
            if self._panel_ref is not None:
                cb = self._panel_ref._on_resign_key
                if cb is not None:
                    cb()

    _QLDelegate = QuickLookPanelDelegate
    return _QLDelegate
