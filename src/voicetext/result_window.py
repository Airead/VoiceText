"""Floating preview panel for ASR and AI enhancement results."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ResultPreviewPanel:
    """Floating NSPanel that shows ASR result, optional AI enhancement, and editable final text.

    Layout (with AI enhance):
        ┌──────────────────────────────────┐
        │ ASR Result                        │
        │ ┌──────────────────────────────┐  │
        │ │ (read-only NSTextView)       │  │
        │ └──────────────────────────────┘  │
        │ AI Enhancement  ⏳ Processing...  │
        │ ┌──────────────────────────────┐  │
        │ │ (read-only NSTextView)       │  │
        │ └──────────────────────────────┘  │
        │ Final Result (editable)           │
        │ ┌──────────────────────────────┐  │
        │ │ (editable NSTextField)       │  │
        │ └──────────────────────────────┘  │
        │           [Cancel]  [Confirm ⏎]   │
        └──────────────────────────────────┘

    Without AI enhance, the middle section is hidden.
    """

    # Panel dimensions
    _PANEL_WIDTH = 480
    _TEXT_HEIGHT = 60
    _EDIT_HEIGHT = 80
    _LABEL_HEIGHT = 20
    _BUTTON_HEIGHT = 32
    _PADDING = 12
    _BUTTON_WIDTH = 90

    def __init__(self) -> None:
        self._panel = None
        self._asr_text_view = None
        self._enhance_label = None
        self._enhance_scroll = None
        self._enhance_text_view = None
        self._final_text_field = None
        self._on_confirm: Optional[Callable[[str, Optional[dict]], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None
        self._user_edited = False
        self._show_enhance = False
        self._asr_text = ""
        self._delegate = None

    def show(
        self,
        asr_text: str,
        show_enhance: bool,
        on_confirm: Callable[[str, Optional[dict]], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """Show the preview panel with ASR text.

        Args:
            asr_text: The raw ASR transcription result.
            show_enhance: Whether to show the AI enhancement section.
            on_confirm: Callback with final text when user confirms.
            on_cancel: Callback when user cancels.
        """
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._user_edited = False
        self._show_enhance = show_enhance
        self._asr_text = asr_text

        self._build_panel(asr_text, show_enhance)

        self._panel.makeKeyAndOrderFront_(None)
        self._panel.makeFirstResponder_(self._final_text_field)

        from AppKit import NSApp

        NSApp.activateIgnoringOtherApps_(True)

    def set_enhance_result(self, text: str) -> None:
        """Update the AI enhancement result.

        If the user has not manually edited the final text, update it too.
        """
        if self._enhance_text_view is None:
            return

        from PyObjCTools import AppHelper

        def _update():
            if self._enhance_text_view is None:
                return
            self._enhance_text_view.setString_(text)
            # Update label to remove spinner
            if self._enhance_label is not None:
                self._enhance_label.setStringValue_("AI Enhancement")
            # Auto-update final text if user hasn't edited
            if not self._user_edited and self._final_text_field is not None:
                self._final_text_field.setStringValue_(text)

        AppHelper.callAfter(_update)

    def close(self) -> None:
        """Close the panel."""
        if self._panel is not None:
            self._panel.orderOut_(None)
            self._panel = None

    def _build_panel(self, asr_text: str, show_enhance: bool) -> None:
        """Build the NSPanel and all subviews."""
        from AppKit import (
            NSApp,
            NSBackingStoreBuffered,
            NSBezelBorder,
            NSButton,
            NSClosableWindowMask,
            NSFloatingWindowLevel,
            NSFont,
            NSLineBreakByWordWrapping,
            NSPanel,
            NSScrollView,
            NSTextField,
            NSTextView,
            NSTitledWindowMask,
        )
        from Foundation import NSMakeRect

        # Calculate total height
        content_height = self._PADDING  # bottom padding
        content_height += self._BUTTON_HEIGHT + self._PADDING  # buttons
        content_height += self._EDIT_HEIGHT + self._PADDING  # final edit
        content_height += self._LABEL_HEIGHT  # final label
        if show_enhance:
            content_height += self._TEXT_HEIGHT + self._PADDING  # enhance text
            content_height += self._LABEL_HEIGHT  # enhance label
        content_height += self._TEXT_HEIGHT + self._PADDING  # asr text
        content_height += self._LABEL_HEIGHT  # asr label
        content_height += self._PADDING  # top padding

        # Create panel
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, self._PANEL_WIDTH, content_height),
            NSTitledWindowMask | NSClosableWindowMask,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("Preview")
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setFloatingPanel_(True)
        panel.center()

        content_view = panel.contentView()
        inner_width = self._PANEL_WIDTH - 2 * self._PADDING

        # Layout from bottom to top
        y = self._PADDING

        # Buttons row
        cancel_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(
                self._PANEL_WIDTH - self._PADDING - 2 * self._BUTTON_WIDTH - 8,
                y,
                self._BUTTON_WIDTH,
                self._BUTTON_HEIGHT,
            )
        )
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)  # NSRoundedBezelStyle
        cancel_btn.setKeyEquivalent_("\x1b")  # Escape
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_(b"cancelClicked:")
        content_view.addSubview_(cancel_btn)

        confirm_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(
                self._PANEL_WIDTH - self._PADDING - self._BUTTON_WIDTH,
                y,
                self._BUTTON_WIDTH,
                self._BUTTON_HEIGHT,
            )
        )
        confirm_btn.setTitle_("Confirm ⏎")
        confirm_btn.setBezelStyle_(1)
        confirm_btn.setKeyEquivalent_("\r")  # Enter
        confirm_btn.setTarget_(self)
        confirm_btn.setAction_(b"confirmClicked:")
        content_view.addSubview_(confirm_btn)

        y += self._BUTTON_HEIGHT + self._PADDING

        # Final result label
        final_label = NSTextField.labelWithString_("Final Result (editable)")
        final_label.setFrame_(NSMakeRect(self._PADDING, y + self._EDIT_HEIGHT, inner_width, self._LABEL_HEIGHT))
        final_label.setFont_(NSFont.boldSystemFontOfSize_(12))
        content_view.addSubview_(final_label)

        # Final result editable text field (NSTextField with wrapping)
        final_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(self._PADDING, y, inner_width, self._EDIT_HEIGHT)
        )
        final_field.setEditable_(True)
        final_field.setBezeled_(True)
        final_field.setFont_(NSFont.userFixedPitchFontOfSize_(12.0))
        final_field.setStringValue_(asr_text)
        final_field.setUsesSingleLineMode_(False)
        final_field.cell().setWraps_(True)
        final_field.cell().setScrollable_(False)
        final_field.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
        # Enter triggers confirm via the button's keyEquivalent
        content_view.addSubview_(final_field)
        self._final_text_field = final_field

        # Set up delegate to track user edits
        self._delegate = _TextFieldEditDelegate.alloc().init()
        self._delegate._panel_ref = self
        final_field.setDelegate_(self._delegate)

        y += self._EDIT_HEIGHT + self._LABEL_HEIGHT + self._PADDING

        # AI Enhancement section (optional)
        if show_enhance:
            enhance_label = NSTextField.labelWithString_("AI Enhancement  ⏳ Processing...")
            enhance_label.setFrame_(NSMakeRect(self._PADDING, y + self._TEXT_HEIGHT, inner_width, self._LABEL_HEIGHT))
            enhance_label.setFont_(NSFont.boldSystemFontOfSize_(12))
            content_view.addSubview_(enhance_label)
            self._enhance_label = enhance_label

            enhance_scroll, enhance_tv = self._make_text_view(
                NSMakeRect(self._PADDING, y, inner_width, self._TEXT_HEIGHT),
            )
            enhance_tv.setString_("")
            content_view.addSubview_(enhance_scroll)
            self._enhance_text_view = enhance_tv
            self._enhance_scroll = enhance_scroll

            y += self._TEXT_HEIGHT + self._LABEL_HEIGHT + self._PADDING
        else:
            self._enhance_label = None
            self._enhance_text_view = None
            self._enhance_scroll = None

        # ASR Result label
        asr_label = NSTextField.labelWithString_("ASR Result")
        asr_label.setFrame_(NSMakeRect(self._PADDING, y + self._TEXT_HEIGHT, inner_width, self._LABEL_HEIGHT))
        asr_label.setFont_(NSFont.boldSystemFontOfSize_(12))
        content_view.addSubview_(asr_label)

        # ASR Result text view (read-only)
        asr_scroll, asr_tv = self._make_text_view(
            NSMakeRect(self._PADDING, y, inner_width, self._TEXT_HEIGHT),
        )
        asr_tv.setString_(asr_text)
        content_view.addSubview_(asr_scroll)
        self._asr_text_view = asr_tv

        self._panel = panel

    @staticmethod
    def _make_text_view(frame):
        """Create a read-only NSScrollView + NSTextView pair."""
        from AppKit import NSBezelBorder, NSColor, NSFont, NSScrollView, NSTextView
        from Foundation import NSMakeRect

        scroll = NSScrollView.alloc().initWithFrame_(frame)
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(NSBezelBorder)

        tv = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, frame.size.width, frame.size.height)
        )
        tv.setMinSize_(NSMakeRect(0, 0, frame.size.width, 0).size)
        tv.setMaxSize_(NSMakeRect(0, 0, 1e7, 1e7).size)
        tv.setVerticallyResizable_(True)
        tv.setHorizontallyResizable_(False)
        tv.textContainer().setWidthTracksTextView_(True)
        tv.setFont_(NSFont.userFixedPitchFontOfSize_(12.0))
        tv.setEditable_(False)
        tv.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.95, 0.95, 0.95, 1.0
            )
        )

        scroll.setDocumentView_(tv)
        return scroll, tv

    def _on_user_edit(self) -> None:
        """Called when user edits the final text field."""
        self._user_edited = True

    def confirmClicked_(self, sender) -> None:
        """Handle confirm button click."""
        if self._final_text_field is not None and self._on_confirm is not None:
            text = self._final_text_field.stringValue()
            correction_info = None
            if self._user_edited and self._show_enhance and self._enhance_text_view is not None:
                enhanced = self._enhance_text_view.string()
                correction_info = {
                    "asr_text": self._asr_text,
                    "enhanced_text": enhanced,
                    "final_text": text,
                }
            self.close()
            self._on_confirm(text, correction_info)

    def cancelClicked_(self, sender) -> None:
        """Handle cancel button click."""
        self.close()
        if self._on_cancel is not None:
            self._on_cancel()


def _create_text_field_delegate_class():
    """Create an NSObject subclass for NSTextFieldDelegate."""
    from Foundation import NSObject

    class TextFieldEditDelegate(NSObject):
        """NSTextFieldDelegate that tracks user edits."""

        _panel_ref = None

        def controlTextDidChange_(self, notification):
            if self._panel_ref is not None:
                self._panel_ref._on_user_edit()

    return TextFieldEditDelegate


_TextFieldEditDelegate = _create_text_field_delegate_class()
