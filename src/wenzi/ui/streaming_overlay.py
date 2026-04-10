"""Floating overlay panel for Direct mode streaming AI enhancement output.

Uses native AppKit views (NSVisualEffectView + NSTextView) for instant
rendering, dynamic height, and seamless visual transition from the
recording indicator.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

# Panel dimensions
_PANEL_WIDTH = 420
_MIN_HEIGHT = 80
_MAX_HEIGHT = 360
_CORNER_RADIUS = 10
_PADDING_H = 14
_PADDING_V = 10
_SECTION_SPACING = 8
_ASR_MAX_HEIGHT = 60  # max before ASR section scrolls

# Key codes
_ESC_KEY_CODE = 53
_RETURN_KEY_CODE = 36

# Delayed close
_CLOSE_DELAY = 1.0
_HOVER_RECHECK_INTERVAL = 0.5
_FADE_OUT_DURATION = 0.3

# NSVisualEffectView constants
_VFX_MATERIAL_HUD = 13
_VFX_BLENDING_BEHIND = 0
_VFX_STATE_ACTIVE = 1

# Height recalc debounce flag
_RECALC_PENDING_KEY = "_recalc_pending"


class StreamingOverlayPanel:
    """Non-interactive floating overlay that displays streaming AI enhancement.

    Shows ASR original text at top, streaming enhanced text below.
    Uses native AppKit views with NSVisualEffectView for frosted-glass
    appearance matching the recording indicator.
    """

    def __init__(self) -> None:
        self._panel: object = None
        self._vfx_view: object = None
        self._asr_title_label: object = None
        self._asr_text_view: object = None
        self._asr_scroll: object = None
        self._separator: object = None
        self._status_label: object = None
        self._stream_text_view: object = None
        self._stream_scroll: object = None
        self._tap_runner: object = None
        self._cancel_event: threading.Event | None = None
        self._on_cancel: object = None
        self._on_confirm_asr: object = None
        self._loading_timer: object = None
        self._loading_seconds: int = 0
        self._llm_info: str = ""
        self._close_timer: object = None
        self._has_thinking: bool = False
        self._transcribing: bool = False  # animate "Transcribing..." dots
        # Screen centre anchor (for height growth animation)
        self._center_x: float = 0.0
        self._center_y: float = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ai_label(self, suffix: str) -> str:
        """Build the AI status label with optional LLM info prefix."""
        base = "\u2728 AI"
        if self._llm_info:
            base += f" ({self._llm_info})"
        if suffix:
            return f"{base}  {suffix}"
        return base

    @staticmethod
    def _make_label(text: str):
        """Create a small, muted section header label."""
        from AppKit import NSColor, NSFont, NSTextField

        label = NSTextField.labelWithString_(text)
        label.setFont_(NSFont.systemFontOfSize_weight_(9.5, 0.23))
        label.setTextColor_(NSColor.tertiaryLabelColor())
        label.setSelectable_(False)
        label.setDrawsBackground_(False)
        label.setBezeled_(False)
        label.setEditable_(False)
        return label

    @staticmethod
    def _make_text_view(width: float, font_size: float = 13.0):
        """Create a scrollable NSTextView pair. Returns (scroll_view, text_view)."""
        from AppKit import (
            NSColor,
            NSFont,
            NSScrollView,
            NSTextView,
        )
        from Foundation import NSMakeRect

        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, 0, width, 20)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setHasHorizontalScroller_(False)
        scroll.setAutohidesScrollers_(True)
        scroll.setDrawsBackground_(False)
        scroll.setBorderType_(0)  # NSNoBorder

        tv = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, width, 20)
        )
        tv.setEditable_(False)
        tv.setSelectable_(True)
        tv.setDrawsBackground_(False)
        tv.setRichText_(True)
        tv.setFont_(NSFont.systemFontOfSize_(font_size))
        tv.setTextColor_(NSColor.labelColor())
        tv.setTextContainerInset_((0, 0))
        # Allow unlimited height, fixed width
        tv.textContainer().setWidthTracksTextView_(True)
        tv.textContainer().setContainerSize_((width, 1e7))
        tv.setHorizontallyResizable_(False)
        tv.setVerticallyResizable_(True)
        # Hide scrollbar visually but keep scrolling
        scroll.setScrollerStyle_(1)  # NSScrollerStyleOverlay

        scroll.setDocumentView_(tv)
        return scroll, tv

    # ------------------------------------------------------------------
    # Show / position
    # ------------------------------------------------------------------

    def show(
        self,
        asr_text: str = "",
        cancel_event: threading.Event | None = None,
        animate_from_frame: object = None,
        stt_info: str = "",
        llm_info: str = "",
        on_cancel: object = None,
        on_confirm_asr: object = None,
    ) -> None:
        """Create and show the overlay panel. Must be called on main thread."""
        try:
            from AppKit import (
                NSColor,
                NSPanel,
                NSScreen,
                NSStatusWindowLevel,
                NSVisualEffectView,
            )
            from Foundation import NSMakeRect

            if self._panel is not None:
                self._do_close()

            self._cancel_event = cancel_event
            self._on_cancel = on_cancel
            self._on_confirm_asr = on_confirm_asr
            self._loading_seconds = 0
            self._llm_info = llm_info
            self._has_thinking = False

            # -- Build labels --
            asr_title_text = "\U0001f3a4 ASR"
            if stt_info:
                asr_title_text += f"  ({stt_info})"

            content_w = _PANEL_WIDTH - _PADDING_H * 2
            self._asr_title_label = self._make_label(asr_title_text)
            self._asr_scroll, self._asr_text_view = self._make_text_view(
                content_w, font_size=12,
            )
            if asr_text:
                self._set_text(self._asr_text_view, asr_text)
                self._transcribing = False
            else:
                self._set_text(
                    self._asr_text_view, "Transcribing",
                    secondary=True, italic=True,
                )
                self._transcribing = True

            # Soft separator (thin semi-transparent view)
            from AppKit import NSView as _NSView

            sep = _NSView.alloc().initWithFrame_(NSMakeRect(0, 0, content_w, 1))
            sep.setWantsLayer_(True)
            sep.layer().setBackgroundColor_(
                NSColor.separatorColor().CGColor()
            )
            sep.layer().setOpacity_(0.4)
            self._separator = sep

            self._status_label = self._make_label(self._ai_label(""))
            self._stream_scroll, self._stream_text_view = self._make_text_view(
                content_w, font_size=12,
            )

            # -- Panel --
            init_h = self._compute_height()
            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, _PANEL_WIDTH, init_h),
                0, 2, False,
            )
            panel.setLevel_(NSStatusWindowLevel + 1)
            panel.setOpaque_(False)
            panel.setBackgroundColor_(NSColor.clearColor())
            panel.setIgnoresMouseEvents_(False)
            panel.setHasShadow_(True)
            panel.setHidesOnDeactivate_(False)
            panel.setCollectionBehavior_(
                (1 << 0) | (1 << 4) | (1 << 8)
            )

            # -- VFX background --
            vfx = NSVisualEffectView.alloc().initWithFrame_(
                NSMakeRect(0, 0, _PANEL_WIDTH, init_h)
            )
            vfx.setMaterial_(_VFX_MATERIAL_HUD)
            vfx.setBlendingMode_(_VFX_BLENDING_BEHIND)
            vfx.setState_(_VFX_STATE_ACTIVE)
            vfx.setWantsLayer_(True)
            vfx.layer().setCornerRadius_(_CORNER_RADIUS)
            vfx.layer().setMasksToBounds_(True)
            vfx.setAutoresizingMask_(0x12)  # flex W+H
            panel.setContentView_(vfx)
            self._vfx_view = vfx

            self._panel = panel

            # -- Position at screen centre --
            screen = NSScreen.mainScreen()
            if screen:
                sf = screen.visibleFrame()
                self._center_x = sf.origin.x + sf.size.width / 2.0
                self._center_y = sf.origin.y + sf.size.height / 2.0

            # Layout subviews, position, and show
            self._layout_subviews(init_h)
            target_frame = self._frame_for_height(init_h)
            print(f"[SO] init_h={init_h}, center=({self._center_x},{self._center_y}), target={target_frame}")
            panel.setFrame_display_(target_frame, True)
            panel.orderFront_(None)
            print(f"[SO] panel.frame()={panel.frame()}, alpha={panel.alphaValue()}, visible={panel.isVisible()}")
            print(f"[SO] vfx subviews={self._vfx_view.subviews().count() if self._vfx_view else 'None'}")

            self._register_key_tap()
            self._start_loading_timer()
            logger.debug("Streaming overlay shown")
        except Exception as exc:
            import traceback
            print(f"[SO] EXCEPTION in show(): {exc}")
            traceback.print_exc()
            logger.error("Failed to show streaming overlay", exc_info=True)

    def _frame_for_height(self, h: float):
        """Return an NSRect centred on screen with the given height."""
        from Foundation import NSMakeRect

        x = self._center_x - _PANEL_WIDTH / 2.0
        y = self._center_y - h / 2.0
        return NSMakeRect(x, y, _PANEL_WIDTH, h)

    def _layout_subviews(self, panel_h: float) -> None:
        """Position all subviews within the VFX view for a given panel height."""
        from Foundation import NSMakeRect

        if self._vfx_view is None:
            return

        # Remove existing subviews
        for sv in list(self._vfx_view.subviews()):
            sv.removeFromSuperview()

        cw = _PANEL_WIDTH - _PADDING_H * 2
        y = panel_h - _PADDING_V  # start from top

        # ASR title
        lh = 14
        y -= lh
        self._asr_title_label.setFrame_(
            NSMakeRect(_PADDING_H, y, cw, lh)
        )
        self._vfx_view.addSubview_(self._asr_title_label)

        # ASR text
        y -= 2  # small gap
        asr_h = min(self._text_content_height(self._asr_text_view), _ASR_MAX_HEIGHT)
        asr_h = max(asr_h, 16)
        y -= asr_h
        self._asr_scroll.setFrame_(NSMakeRect(_PADDING_H, y, cw, asr_h))
        self._vfx_view.addSubview_(self._asr_scroll)

        # Separator
        y -= _SECTION_SPACING
        self._separator.setFrame_(NSMakeRect(_PADDING_H, y, cw, 1))
        self._vfx_view.addSubview_(self._separator)
        y -= _SECTION_SPACING

        # Status label
        y -= lh
        self._status_label.setFrame_(NSMakeRect(_PADDING_H, y, cw, lh))
        self._vfx_view.addSubview_(self._status_label)

        # Stream text (fill remaining space)
        y -= 2
        stream_h = max(y - _PADDING_V, 16)
        self._stream_scroll.setFrame_(
            NSMakeRect(_PADDING_H, _PADDING_V, cw, stream_h)
        )
        self._vfx_view.addSubview_(self._stream_scroll)

    def _compute_height(self) -> float:
        """Compute ideal panel height from content."""
        asr_h = min(
            self._text_content_height(self._asr_text_view), _ASR_MAX_HEIGHT,
        )
        asr_h = max(asr_h, 16)
        stream_h = self._text_content_height(self._stream_text_view)
        stream_h = max(stream_h, 16)

        total = (
            _PADDING_V
            + 14  # asr title
            + 2 + asr_h
            + _SECTION_SPACING + 1 + _SECTION_SPACING  # separator
            + 14  # status label
            + 2 + stream_h
            + _PADDING_V
        )
        return max(_MIN_HEIGHT, min(total, _MAX_HEIGHT))

    def _recalculate_height(self) -> None:
        """Recompute panel height and animate the change."""
        if self._panel is None:
            return

        new_h = self._compute_height()
        try:
            old_h = float(self._panel.frame().size.height)
        except (TypeError, ValueError):
            old_h = 0.0
        if abs(new_h - old_h) < 2:
            # Still relayout at current height (content may have changed)
            self._layout_subviews(old_h)
            return

        from AppKit import NSAnimationContext

        target = self._frame_for_height(new_h)
        NSAnimationContext.beginGrouping()
        ctx = NSAnimationContext.currentContext()
        ctx.setDuration_(0.12)

        def _after_resize():
            self._layout_subviews(new_h)
            self._vfx_view.setFrame_(
                self._panel.contentView().bounds()
                if self._panel
                else self._vfx_view.frame()
            )

        ctx.setCompletionHandler_(_after_resize)
        self._panel.animator().setFrame_display_(target, True)
        NSAnimationContext.endGrouping()

    @staticmethod
    def _text_content_height(text_view) -> float:
        """Measure the used height of an NSTextView's content."""
        if text_view is None:
            return 0
        try:
            lm = text_view.layoutManager()
            tc = text_view.textContainer()
            lm.ensureLayoutForTextContainer_(tc)
            h = lm.usedRectForTextContainer_(tc).size.height
            return float(h)
        except (TypeError, ValueError, AttributeError):
            return 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Text manipulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_text(
        text_view, text: str,
        secondary: bool = False,
        italic: bool = False,
    ) -> None:
        """Replace all text in an NSTextView."""
        from AppKit import NSColor, NSFont, NSFontManager
        from Foundation import (
            NSAttributedString,
            NSMutableDictionary,
        )

        attrs = NSMutableDictionary.dictionary()
        if italic:
            attrs["NSFont"] = NSFontManager.sharedFontManager().convertFont_toHaveTrait_(
                    NSFont.systemFontOfSize_(13), 1,  # NSItalicFontMask
                )
        else:
            attrs["NSFont"] = NSFont.systemFontOfSize_(13)
        if secondary:
            attrs["NSColor"] = NSColor.secondaryLabelColor()
        else:
            attrs["NSColor"] = NSColor.labelColor()

        astr = NSAttributedString.alloc().initWithString_attributes_(
            text, attrs,
        )
        text_view.textStorage().setAttributedString_(astr)

    @staticmethod
    def _append_attributed(text_view, text: str, attrs: dict) -> None:
        """Append attributed text and auto-scroll to bottom."""
        from Foundation import NSAttributedString, NSMakeRange

        astr = NSAttributedString.alloc().initWithString_attributes_(
            text, attrs,
        )
        ts = text_view.textStorage()
        ts.appendAttributedString_(astr)
        text_view.scrollRangeToVisible_(NSMakeRange(ts.length(), 0))

    # ------------------------------------------------------------------
    # Key tap (ESC / Enter) — CGEventTap swallows the keys
    # ------------------------------------------------------------------

    def _register_key_tap(self) -> None:
        if self._tap_runner is not None:
            return
        from wenzi import _cgeventtap as cg

        self._tap_runner = cg.CGEventTapRunner()
        mask = cg.CGEventMaskBit(cg.kCGEventKeyDown)
        self._tap_runner.start(mask, self._key_tap_callback)

    def _key_tap_callback(self, proxy, event_type, event, refcon):
        from wenzi import _cgeventtap as cg

        try:
            if event_type == cg.kCGEventTapDisabledByTimeout:
                if self._tap_runner is not None and self._tap_runner.tap is not None:
                    cg.CGEventTapEnable(self._tap_runner.tap, True)
                return event

            if event_type != cg.kCGEventKeyDown:
                return event

            keycode = cg.CGEventGetIntegerValueField(
                event, cg.kCGKeyboardEventKeycode,
            )

            if keycode == _ESC_KEY_CODE:
                if self._tap_runner is not None and self._tap_runner.tap is not None:
                    cg.CGEventTapEnable(self._tap_runner.tap, False)
                if self._cancel_event is not None:
                    self._cancel_event.set()
                from PyObjCTools import AppHelper

                on_cancel = self._on_cancel
                if on_cancel is not None:
                    AppHelper.callAfter(on_cancel)
                AppHelper.callAfter(self._do_close)
                logger.info("Streaming cancelled via ESC key")
                return None

            if keycode == _RETURN_KEY_CODE and self._on_confirm_asr is not None:
                if self._tap_runner is not None and self._tap_runner.tap is not None:
                    cg.CGEventTapEnable(self._tap_runner.tap, False)
                from PyObjCTools import AppHelper

                on_confirm = self._on_confirm_asr
                AppHelper.callAfter(on_confirm)
                logger.info("ASR confirmed via Enter key")
                return None

        except Exception:
            logger.warning("Key tap callback error", exc_info=True)
        return event

    def _remove_key_tap(self) -> None:
        if self._tap_runner is not None:
            self._tap_runner.stop()
            self._tap_runner = None

    # ------------------------------------------------------------------
    # Loading timer
    # ------------------------------------------------------------------

    def _start_loading_timer(self) -> None:
        self._stop_loading_timer()
        self._loading_seconds = 0
        self._tick_count = 0
        try:
            from Foundation import NSTimer

            self._loading_timer = (
                NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    0.5, self, b"tickLoadingTimer:", None, True,
                )
            )
        except Exception:
            logger.error("Failed to start loading timer", exc_info=True)

    def _stop_loading_timer(self) -> None:
        if self._loading_timer is not None:
            try:
                self._loading_timer.invalidate()
            except Exception:
                pass
            self._loading_timer = None

    def tickLoadingTimer_(self, timer) -> None:
        self._tick_count += 1

        # Animate "Transcribing..." dots (cycles every 3 ticks)
        if self._transcribing and self._asr_text_view is not None:
            dots = "." * ((self._tick_count % 3) + 1)
            self._set_text(
                self._asr_text_view, f"Transcribing{dots}",
                secondary=True, italic=True,
            )

        # Update AI status every second (every 2 ticks at 0.5s interval)
        if self._tick_count % 2 == 0:
            self._loading_seconds += 1
            if self._status_label is not None:
                self._status_label.setStringValue_(
                    self._ai_label(f"\u23f3 {self._loading_seconds}s")
                )

    # ------------------------------------------------------------------
    # Streaming text updates (all thread-safe via callAfter)
    # ------------------------------------------------------------------

    def append_text(self, chunk: str, completion_tokens: int = 0) -> None:
        """Append content text to the streaming text view. Thread-safe."""
        from PyObjCTools import AppHelper

        def _append():
            self._stop_loading_timer()
            if self._stream_text_view is None:
                return

            from AppKit import NSColor, NSFont

            # Clear thinking text if present
            if self._has_thinking:
                self._stream_text_view.textStorage().setAttributedString_(
                    __import__("Foundation").NSAttributedString.alloc().init()
                )
                self._has_thinking = False

            attrs = {
                "NSFont": NSFont.systemFontOfSize_(13),
                "NSColor": NSColor.labelColor(),
            }
            self._append_attributed(self._stream_text_view, chunk, attrs)

            if completion_tokens and self._status_label:
                self._status_label.setStringValue_(
                    self._ai_label(f"Chars: \u2193{completion_tokens}")
                )

            self._recalculate_height()

        AppHelper.callAfter(_append)

    def append_thinking_text(self, chunk: str, thinking_tokens: int = 0) -> None:
        """Append thinking/reasoning text in italic. Thread-safe."""
        from PyObjCTools import AppHelper

        def _append():
            self._stop_loading_timer()
            if self._stream_text_view is None:
                return

            from AppKit import NSColor, NSFont, NSFontManager

            self._has_thinking = True
            attrs = {
                "NSFont": NSFontManager.sharedFontManager().convertFont_toHaveTrait_(
                    NSFont.systemFontOfSize_(13), 1,  # NSItalicFontMask
                ),
                "NSColor": NSColor.tertiaryLabelColor(),
            }
            self._append_attributed(self._stream_text_view, chunk, attrs)

            if thinking_tokens and self._status_label:
                self._status_label.setStringValue_(
                    self._ai_label(f"\u25b6 Thinking: {thinking_tokens} chars")
                )

            self._recalculate_height()

        AppHelper.callAfter(_append)

    def set_status(self, text: str) -> None:
        """Update the status label. Thread-safe."""
        from PyObjCTools import AppHelper

        def _update():
            if self._status_label is not None:
                self._status_label.setStringValue_(text)

        AppHelper.callAfter(_update)

    def set_asr_text(self, text: str) -> None:
        """Update the ASR text after transcription completes. Thread-safe."""
        from PyObjCTools import AppHelper

        def _update():
            if self._asr_text_view is None:
                return
            self._transcribing = False
            self._set_text(self._asr_text_view, text)
            self._recalculate_height()

        AppHelper.callAfter(_update)

    def set_cancel_event(self, cancel_event: threading.Event) -> None:
        """Attach a cancel event and register ESC monitor. Thread-safe."""
        from PyObjCTools import AppHelper

        def _update():
            self._cancel_event = cancel_event
            if self._tap_runner is None:
                self._register_key_tap()

        AppHelper.callAfter(_update)

    def set_complete(self, usage: dict | None = None) -> None:
        """Mark enhancement complete, show final token usage. Thread-safe."""
        from PyObjCTools import AppHelper

        def _update():
            self._stop_loading_timer()
            if self._status_label is None:
                return

            if usage and usage.get("total_tokens"):
                prompt = usage.get("prompt_tokens", 0)
                completion = usage.get("completion_tokens", 0)
                total = usage["total_tokens"]
                cached = usage.get("prompt_tokens_details", {}).get(
                    "cached_tokens", 0
                )
                if cached:
                    up = f"\u2191{cached}+{prompt - cached}"
                else:
                    up = f"\u2191{prompt}"
                label = (
                    f"{self._ai_label('')}  "
                    f"Tokens: {total} ({up} \u2193{completion})"
                )
            else:
                label = self._ai_label("")
            self._status_label.setStringValue_(label)

        AppHelper.callAfter(_update)

    def clear_text(self) -> None:
        """Clear the streaming text view. Thread-safe."""
        from PyObjCTools import AppHelper

        def _clear():
            if self._stream_text_view is None:
                return
            self._stream_text_view.textStorage().setAttributedString_(
                __import__("Foundation").NSAttributedString.alloc().init()
            )
            self._has_thinking = False
            self._recalculate_height()

        AppHelper.callAfter(_clear)

    # ------------------------------------------------------------------
    # Delayed close with hover detection
    # ------------------------------------------------------------------

    def close_with_delay(self, delay: float = _CLOSE_DELAY) -> None:
        """Close after *delay* seconds, postponed if mouse is hovering. Thread-safe."""
        from PyObjCTools import AppHelper

        def _schedule():
            self._stop_close_timer()
            try:
                from Foundation import NSTimer

                self._close_timer = (
                    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        delay, self, b"_delayedCloseCheck:", None, False,
                    )
                )
            except Exception:
                logger.error("Failed to schedule delayed close", exc_info=True)

        AppHelper.callAfter(_schedule)

    def _delayedCloseCheck_(self, timer) -> None:
        self._close_timer = None
        if self._panel is None:
            return

        if self._is_mouse_over_panel():
            try:
                from Foundation import NSTimer

                self._close_timer = (
                    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        _HOVER_RECHECK_INTERVAL,
                        self, b"_delayedCloseCheck:", None, False,
                    )
                )
            except Exception:
                self._do_close()
        else:
            self._fade_out_and_close()

    def _is_mouse_over_panel(self) -> bool:
        try:
            from AppKit import NSEvent
            from Foundation import NSPointInRect

            mouse_loc = NSEvent.mouseLocation()
            return bool(NSPointInRect(mouse_loc, self._panel.frame()))
        except Exception:
            return False

    def _fade_out_and_close(self) -> None:
        if self._panel is None:
            return
        try:
            from AppKit import NSAnimationContext

            NSAnimationContext.beginGrouping()
            ctx = NSAnimationContext.currentContext()
            ctx.setDuration_(_FADE_OUT_DURATION)
            ctx.setCompletionHandler_(self._do_close)
            self._panel.animator().setAlphaValue_(0.0)
            NSAnimationContext.endGrouping()
        except Exception:
            self._do_close()

    def _stop_close_timer(self) -> None:
        if self._close_timer is not None:
            try:
                self._close_timer.invalidate()
            except Exception:
                pass
            self._close_timer = None

    def _do_close(self) -> None:
        self._stop_loading_timer()
        self._stop_close_timer()
        self._remove_key_tap()
        self._cancel_event = None
        self._on_cancel = None
        self._on_confirm_asr = None
        self._has_thinking = False
        self._transcribing = False

        if self._panel is not None:
            from wenzi.ui_helpers import release_panel_surfaces

            release_panel_surfaces(self._panel)
            self._panel.orderOut_(None)
            self._panel = None

        self._vfx_view = None
        self._asr_title_label = None
        self._asr_text_view = None
        self._asr_scroll = None
        self._separator = None
        self._status_label = None
        self._stream_text_view = None
        self._stream_scroll = None
        logger.debug("Streaming overlay closed")

    def close_now(self) -> None:
        """Close and clean up immediately. Must be on main thread."""
        self._do_close()

    def close(self) -> None:
        """Close and clean up immediately. Thread-safe."""
        from PyObjCTools import AppHelper

        AppHelper.callAfter(self._do_close)
