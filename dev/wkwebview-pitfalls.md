# WKWebView Pitfalls in PyObjC Statusbar Apps

Lessons learned from migrating the Preview panel to a WKWebView-based implementation.
These pitfalls apply to any WKWebView-based UI panel in this project.

## 1. JS Call Queue — Page Load Race Condition

**Commit:** `a46d3c8`

**Problem:** Fast backends (e.g. FunASR) can return results before WKWebView finishes
loading the HTML page. Calls to `evaluateJavaScript_completionHandler_` during this
window are **silently dropped** — no error, no callback, just lost.

**Symptom:** ASR field stuck on "Transcribing..." while downstream AI results are
already displayed.

**Solution:** Implement a pending JS queue:

```python
def _eval_js(self, js_code: str) -> None:
    if self._webview is None:
        return
    if not self._page_loaded:
        self._pending_js.append(js_code)
        return
    self._webview.evaluateJavaScript_completionHandler_(js_code, None)
```

Flush the queue in `webView:didFinishNavigation:` via a `WKNavigationDelegate`.

**Key takeaway:** Never assume the page is ready when `show()` returns. Always
gate JS execution behind a page-loaded flag.

## 2. Atomic JS Flush — Async Interleaving

**Commit:** `189402c`

**Problem:** Flushing queued JS calls one-by-one via separate `evaluateJavaScript`
calls is **not safe**. Each call is asynchronous, and WKWebView may interleave other
callbacks (e.g. message handler responses) between evaluations. This causes DOM state
inconsistencies — e.g. streaming text leaking into the final-text textarea.

**Solution:** Combine all pending JS into a single string joined by `;` and execute
as one atomic evaluation:

```python
def _on_page_loaded(self) -> None:
    pending = self._pending_js[:]
    self._pending_js.clear()
    self._page_loaded = True
    if pending and self._webview is not None:
        combined = ";".join(pending)
        self._webview.evaluateJavaScript_completionHandler_(combined, None)
```

**Key takeaway:** One `evaluateJavaScript` call = one atomic unit. Multiple calls
have no ordering guarantee.

## 3. Edit Menu — ⌘C/⌘V/⌘A Not Working

**Commit:** `a2c35c0`

**Problem:** In a statusbar app (`NSApplicationActivationPolicyAccessory`), there is
no menu bar and no Edit menu. WKWebView relies on the responder chain's Edit menu
to handle ⌘C, ⌘V, ⌘A. Without it, these shortcuts are silently swallowed.

**Solution:** Call `_ensure_edit_menu()` (defined in `result_window.py`) during
`_build_panel()` to inject a minimal Edit menu with Cut/Copy/Paste/Select All items.

```python
from voicetext.ui.result_window import _ensure_edit_menu
_ensure_edit_menu()
```

**Key takeaway:** Any WKWebView panel with editable fields must call
`_ensure_edit_menu()` in its build phase.

## 4. WKScriptMessageHandler Protocol Binding

**Commit:** `588695e`

**Problem:** Simply subclassing `NSObject` and defining
`userContentController_didReceiveScriptMessage_` is **not enough**. PyObjC needs
explicit protocol conformance for WKScriptMessageHandler, otherwise the method is
never called.

**Solution:** Use `objc.protocolNamed()` and declare the protocol in the class
definition:

```python
import objc
import WebKit  # noqa: F401 — must import to register the protocol

WKScriptMessageHandler = objc.protocolNamed("WKScriptMessageHandler")

class MyMessageHandler(NSObject, protocols=[WKScriptMessageHandler]):
    def userContentController_didReceiveScriptMessage_(self, controller, message):
        ...
```

**Key takeaway:** Always explicitly declare WebKit protocols via
`objc.protocolNamed`. Implicit method-name matching does not work for WebKit
delegate protocols.

## 5. NSDictionary ≠ Python dict

**Commit:** `588695e`

**Problem:** `message.body()` from WKScriptMessageHandler returns ObjC types
(`NSDictionary`, `NSNumber`, `NSString`), not Python-native types. Direct Python
operations like `body.get("key")` may work for strings but fail silently for nested
structures or booleans (`NSNumber` 1/0 vs Python `True`/`False`).

**Solution:** JSON-roundtrip through `NSJSONSerialization` to convert to Python
native types:

```python
from Foundation import NSJSONSerialization

raw = message.body()
json_data, _ = NSJSONSerialization.dataWithJSONObject_options_error_(raw, 0, None)
body = json.loads(bytes(json_data))
```

**Key takeaway:** Always JSON-roundtrip WKWebView message bodies before processing
in Python.

## 6. ObjC Class Name Global Uniqueness

**Context:** CLAUDE.md project rule

**Problem:** Objective-C class names are globally unique across the entire process.
If two modules both define `class PanelCloseDelegate(NSObject)`, the second import
crashes with `objc.error: PanelCloseDelegate is overriding existing Objective-C class`.

**Solution:** Prefix all NSObject subclasses with the module/component name:

```
WebResultPanelCloseDelegate        (result_window_web.py)
HistoryBrowserCloseDelegate        (history_browser_window.py)
HistoryBrowserWebCloseDelegate     (history_browser_window_web.py)
```

Also use lazy creation + global cache to avoid re-defining on repeated imports:

```python
_MyDelegate = None

def _get_delegate_class():
    global _MyDelegate
    if _MyDelegate is None:
        class MyUniqueDelegate(NSObject):
            ...
        _MyDelegate = MyUniqueDelegate
    return _MyDelegate
```

**Key takeaway:** Every NSObject subclass must have a project-wide unique name.
Use module-prefixed names and lazy-cached factory functions.

## 7. Statusbar App Window Lifecycle

**Context:** CLAUDE.md project rule

**Problem:** In a statusbar app, clicking a menu item briefly activates the app for
menu tracking. When the callback returns, the app falls back to accessory mode. If
window `show()` is deferred via `AppHelper.callAfter()`, the window is created but
never appears on screen.

**Solution:** Always show windows **synchronously** within the menu callback. Inside
`show()`, follow this order:

1. `NSApp.setActivationPolicy_(0)` — switch to Regular
2. Build/configure the panel
3. `panel.makeKeyAndOrderFront_(None)`
4. `NSApp.activateIgnoringOtherApps_(True)`

Inside `close()`:
1. `panel.orderOut_(None)`
2. `NSApp.setActivationPolicy_(1)` — back to Accessory

**Key takeaway:** Never defer window display in a statusbar app. The activation
window is extremely short.

## 8. AppKit Objects Don't Support Arbitrary Attributes

**Context:** CLAUDE.md project rule

**Problem:** Real AppKit objects (`NSButton`, `NSTextField`, etc.) do not allow
setting arbitrary Python attributes. `btn._my_data = "foo"` raises `AttributeError`
at runtime but works fine with `MagicMock` in tests — a classic test/runtime
divergence.

**Solution:** Use a Python-side `dict` keyed by `id(obj)`:

```python
self._btn_meta: Dict[int, Dict] = {}
self._btn_meta[id(btn)] = {"key": "value"}
```

**Key takeaway for web panels:** This issue is largely eliminated by moving to
WKWebView (all UI state lives in JS/DOM), but still applies to any NSObject
delegate instances.

## Checklist for New WKWebView Panels

- [ ] Implement `_eval_js` with `_page_loaded` gate and `_pending_js` queue
- [ ] Implement `_on_page_loaded` with atomic `;`-joined flush
- [ ] Add `WKNavigationDelegate` (lazy-cached, unique class name)
- [ ] Add `WKScriptMessageHandler` with `objc.protocolNamed` (lazy-cached, unique class name)
- [ ] Add `PanelCloseDelegate` (lazy-cached, unique class name)
- [ ] Call `_ensure_edit_menu()` if panel has editable fields
- [ ] JSON-roundtrip all `message.body()` from JS
- [ ] Show panel synchronously in menu callback (no `callAfter`)
- [ ] Use `prefers-color-scheme: dark` CSS media query for dark mode
- [ ] Reset `_page_loaded = False` and clear `_pending_js` in `close()`
