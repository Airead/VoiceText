"""Floating overlay panel that displays partial transcription during recording."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Panel dimensions
_PANEL_WIDTH = 350
_PANEL_MIN_HEIGHT = 40
_PANEL_MAX_HEIGHT = 160
_PADDING = 10
_CORNER_RADIUS = 10
_SCREEN_Y_OFFSET = 80  # offset below center (below recording indicator)


class LiveTranscriptionOverlay:
    """Non-interactive floating overlay that shows partial STT text during recording.

    Must be created, shown, updated, and hidden on the main thread
    (or via AppHelper.callAfter).
    """

    def __init__(self) -> None:
        self._panel: object = None
        self._text_field: object = None
        self._content_view: object = None
        self._screen_center_y: float = 0  # cached for repositioning

    @staticmethod
    def _dynamic_bg_color():
        """Create a dynamic background color matching RecordingIndicatorPanel."""
        from AppKit import NSColor

        def _provider(appearance):
            name = appearance.bestMatchFromAppearancesWithNames_(
                ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"]
            )
            if name and "Dark" in str(name):
                return NSColor.colorWithSRGBRed_green_blue_alpha_(0.9, 0.9, 0.9, 0.85)
            return NSColor.colorWithSRGBRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.85)

        return NSColor.colorWithName_dynamicProvider_(None, _provider)

    @staticmethod
    def _dynamic_text_color():
        """Create a dynamic text color that contrasts with the background."""
        from AppKit import NSColor

        def _provider(appearance):
            name = appearance.bestMatchFromAppearancesWithNames_(
                ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"]
            )
            if name and "Dark" in str(name):
                return NSColor.colorWithSRGBRed_green_blue_alpha_(0.1, 0.1, 0.1, 1.0)
            return NSColor.colorWithSRGBRed_green_blue_alpha_(0.95, 0.95, 0.95, 1.0)

        return NSColor.colorWithName_dynamicProvider_(None, _provider)

    def show(self) -> None:
        """Create and show the overlay panel. Must be called on the main thread."""
        try:
            from AppKit import (
                NSColor,
                NSFont,
                NSPanel,
                NSScreen,
                NSStatusWindowLevel,
                NSTextField,
                NSView,
            )
            from Foundation import NSMakeRect

            if self._panel is not None:
                self.hide()

            init_h = _PANEL_MIN_HEIGHT
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, _PANEL_WIDTH, init_h),
                0,  # NSBorderlessWindowMask
                2,  # NSBackingStoreBuffered
                False,
            )
            panel.setLevel_(NSStatusWindowLevel + 1)
            panel.setOpaque_(False)
            panel.setBackgroundColor_(NSColor.clearColor())
            panel.setIgnoresMouseEvents_(True)
            panel.setHasShadow_(True)
            panel.setHidesOnDeactivate_(False)
            panel.setCollectionBehavior_(1 << 4)  # canJoinAllSpaces

            # Content view with rounded background
            content = NSView.alloc().initWithFrame_(
                NSMakeRect(0, 0, _PANEL_WIDTH, init_h)
            )
            content.setWantsLayer_(True)
            content.layer().setCornerRadius_(_CORNER_RADIUS)
            content.layer().setMasksToBounds_(True)

            bg_color = self._dynamic_bg_color()
            content.layer().setBackgroundColor_(bg_color.CGColor())

            # Text field for partial transcription (no line limit, wraps freely)
            inner_width = _PANEL_WIDTH - 2 * _PADDING
            inner_height = init_h - 2 * _PADDING
            tf = NSTextField.wrappingLabelWithString_("")
            tf.setFrame_(NSMakeRect(_PADDING, _PADDING, inner_width, inner_height))
            tf.setFont_(NSFont.systemFontOfSize_(14.0))
            tf.setTextColor_(self._dynamic_text_color())
            tf.setMaximumNumberOfLines_(0)  # unlimited lines
            tf.setAlignment_(1)  # NSTextAlignmentCenter
            content.addSubview_(tf)
            self._text_field = tf
            self._content_view = content

            panel.setContentView_(content)

            # Position at screen center, offset below the recording indicator
            screen = NSScreen.mainScreen()
            if screen:
                sf = screen.visibleFrame()
                x = sf.origin.x + (sf.size.width - _PANEL_WIDTH) / 2
                self._screen_center_y = (
                    sf.origin.y + (sf.size.height - init_h) / 2 - _SCREEN_Y_OFFSET
                )
                panel.setFrameOrigin_((x, self._screen_center_y))

            panel.orderFront_(None)
            self._panel = panel
            logger.debug("Live transcription overlay shown")
        except Exception:
            logger.error("Failed to show live transcription overlay", exc_info=True)

    def hide(self) -> None:
        """Hide and clean up the overlay panel. Must be called on the main thread."""
        try:
            if self._panel is not None:
                self._panel.orderOut_(None)
                self._panel = None
            self._text_field = None
            self._content_view = None
            logger.debug("Live transcription overlay hidden")
        except Exception as e:
            logger.warning("Failed to hide live transcription overlay: %s", e)

    def update_text(self, text: str) -> None:
        """Update the displayed partial transcription text. Must be called on the main thread."""
        if self._text_field is None or self._panel is None:
            return

        self._text_field.setStringValue_(text)
        self._resize_panel()

    def _resize_panel(self) -> None:
        """Resize the panel to fit the current text content, up to _PANEL_MAX_HEIGHT."""
        from Foundation import NSMakeRect, NSMakeSize

        tf = self._text_field
        panel = self._panel
        content = self._content_view
        if tf is None or panel is None or content is None:
            return

        # Calculate the height the text needs at the available width
        inner_width = _PANEL_WIDTH - 2 * _PADDING
        # cellSizeForBounds_ returns the size needed to render the text
        needed = tf.cell().cellSizeForBounds_(
            NSMakeRect(0, 0, inner_width, 10000)
        )
        text_h = needed.height
        new_h = min(max(text_h + 2 * _PADDING, _PANEL_MIN_HEIGHT), _PANEL_MAX_HEIGHT)

        old_frame = panel.frame()
        if abs(old_frame.size.height - new_h) < 1:
            return  # no meaningful change

        # Grow upward: keep the top edge stable by adjusting y origin
        new_y = old_frame.origin.y + old_frame.size.height - new_h
        panel.setFrame_display_(
            NSMakeRect(old_frame.origin.x, new_y, _PANEL_WIDTH, new_h), True
        )
        content.setFrame_(NSMakeRect(0, 0, _PANEL_WIDTH, new_h))

        # Reposition text field: pin to top of the content view
        inner_height = new_h - 2 * _PADDING
        tf.setFrame_(NSMakeRect(_PADDING, _PADDING, inner_width, inner_height))

    def close(self) -> None:
        """Alias for hide() for consistency with other panels."""
        self.hide()
