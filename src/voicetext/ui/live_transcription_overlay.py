"""Floating overlay panel for real-time streaming transcription text."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Layout constants
_PANEL_WIDTH = 350
_PANEL_MIN_HEIGHT = 60
_PANEL_MAX_HEIGHT = 160
_CORNER_RADIUS = 10
_PADDING = 12
_FONT_SIZE = 15.0


def _dynamic_color(light_rgba, dark_rgba):
    """Create an appearance-aware dynamic NSColor."""
    from AppKit import NSColor

    def _provider(appearance):
        name = appearance.bestMatchFromAppearancesWithNames_(
            ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"]
        )
        rgba = dark_rgba if name and "Dark" in str(name) else light_rgba
        return NSColor.colorWithSRGBRed_green_blue_alpha_(*rgba)

    return NSColor.colorWithName_dynamicProvider_(None, _provider)


# Cached delegate class
_PanelCloseDelegate = None


def _get_panel_close_delegate_class():
    global _PanelCloseDelegate
    if _PanelCloseDelegate is not None:
        return _PanelCloseDelegate

    from Foundation import NSObject
    import objc

    class LiveTranscriptionCloseDelegate(NSObject):
        _panel_ref = None

        @objc.python_method
        def windowWillClose_(self, notification):
            if self._panel_ref is not None:
                self._panel_ref.close()

    _PanelCloseDelegate = LiveTranscriptionCloseDelegate
    return _PanelCloseDelegate


class LiveTranscriptionOverlay:
    """Non-interactive floating overlay showing real-time transcription text.

    Positioned at screen center, below the recording indicator.
    Auto-resizes height to fit text content.
    """

    def __init__(self) -> None:
        self._panel = None
        self._text_field = None
        self._close_delegate = None
        self._current_text = ""

    @property
    def is_visible(self) -> bool:
        return self._panel is not None and self._panel.isVisible()

    def show(self) -> None:
        """Show the overlay panel."""
        from AppKit import (
            NSBackingStoreBuffered,
            NSBorderlessWindowMask,
            NSColor,
            NSFont,
            NSPanel,
            NSStatusWindowLevel,
            NSTextField,
        )
        from Foundation import NSMakeRect, NSScreen

        if self._panel is not None:
            self._panel.orderOut_(None)
            self._panel = None

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, _PANEL_WIDTH, _PANEL_MIN_HEIGHT),
            NSBorderlessWindowMask,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel + 1)
        panel.setFloatingPanel_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setIgnoresMouseEvents_(True)
        panel.setOpaque_(False)

        # Background color
        bg_color = _dynamic_color(
            (0.95, 0.95, 0.95, 0.92),  # light mode
            (0.15, 0.15, 0.15, 0.92),  # dark mode
        )
        panel.setBackgroundColor_(bg_color)

        content = panel.contentView()
        content.setWantsLayer_(True)
        layer = content.layer()
        if layer:
            layer.setCornerRadius_(_CORNER_RADIUS)
            layer.setMasksToBounds_(True)

        # Text field
        text_field = NSTextField.labelWithString_("")
        text_field.setFrame_(NSMakeRect(
            _PADDING, _PADDING,
            _PANEL_WIDTH - 2 * _PADDING,
            _PANEL_MIN_HEIGHT - 2 * _PADDING,
        ))
        text_field.setFont_(NSFont.systemFontOfSize_(_FONT_SIZE))
        text_field.setTextColor_(NSColor.labelColor())
        text_field.setMaximumNumberOfLines_(0)  # unlimited
        text_field.setLineBreakMode_(0)  # NSLineBreakByWordWrapping
        text_field.setPreferredMaxLayoutWidth_(_PANEL_WIDTH - 2 * _PADDING)

        content.addSubview_(text_field)
        self._text_field = text_field
        self._panel = panel
        self._current_text = ""

        # Center on screen
        screen = NSScreen.mainScreen()
        if screen:
            screen_frame = screen.frame()
            cx = screen_frame.origin.x + screen_frame.size.width / 2 - _PANEL_WIDTH / 2
            cy = screen_frame.origin.y + screen_frame.size.height / 2 - _PANEL_MIN_HEIGHT / 2
            panel.setFrameOrigin_((cx, cy))

        panel.makeKeyAndOrderFront_(None)
        logger.debug("Live transcription overlay shown")

    def hide(self) -> None:
        """Hide the overlay without destroying it."""
        if self._panel is not None:
            self._panel.orderOut_(None)

    def update_text(self, text: str) -> None:
        """Update the displayed transcription text and auto-resize."""
        if self._text_field is None:
            return

        from Foundation import NSMakeRect

        self._current_text = text
        self._text_field.setStringValue_(text)

        # Auto-resize height based on text content
        self._text_field.sizeToFit()
        text_height = self._text_field.frame().size.height
        new_height = max(_PANEL_MIN_HEIGHT, min(_PANEL_MAX_HEIGHT, text_height + 2 * _PADDING))

        if self._panel is not None:
            frame = self._panel.frame()
            # Adjust from bottom (keep top edge fixed)
            old_height = frame.size.height
            frame.origin.y += old_height - new_height
            frame.size.height = new_height
            self._panel.setFrame_display_(frame, True)

            # Reposition text field
            self._text_field.setFrame_(NSMakeRect(
                _PADDING, _PADDING,
                _PANEL_WIDTH - 2 * _PADDING,
                new_height - 2 * _PADDING,
            ))

    def close(self) -> None:
        """Close and destroy the overlay."""
        if self._panel is not None:
            self._panel.orderOut_(None)
            self._panel = None
        self._text_field = None
        self._close_delegate = None
        self._current_text = ""
        logger.debug("Live transcription overlay closed")
