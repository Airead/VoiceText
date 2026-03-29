"""wz.menu — read-only access to the app's statusbar menu items."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _ax_attr(element, attr):
    """Read an AXUIElement attribute, returning None on failure."""
    from ApplicationServices import AXUIElementCopyAttributeValue
    err, val = AXUIElementCopyAttributeValue(element, attr, None)
    if err != 0:
        return None
    return val


def _build_shortcut(cmd_char: str, modifiers: int) -> str:
    """Build a human-readable shortcut string from AX modifier flags.
    macOS AXMenuItemCmdModifiers bit flags:
      bit 0 (1) = Shift → ⇧
      bit 1 (2) = Control → ⌃
      bit 2 (4) = Option → ⌥
      Cmd (⌘) is always implied when cmd_char is non-empty.
    """
    if not cmd_char:
        return ""
    parts = []
    if modifiers & 4:
        parts.append("⌥")
    if modifiers & 2:
        parts.append("⌃")
    if modifiers & 1:
        parts.append("⇧")
    parts.append("⌘")
    parts.append(cmd_char)
    return "".join(parts)


class MenuAPI:
    """Enumerate and trigger the app's statusbar menu items — ``wz.menu``."""

    def __init__(self) -> None:
        self._root = None  # StatusMenuItem (app's root menu)
        self._chooser_api = None  # ChooserAPI for previous-app pid

    def _set_root(self, root: Any) -> None:
        """Inject the app's root StatusMenuItem. Called by ScriptEngine."""
        self._root = root

    def list(self, flat: bool = False) -> List[Dict[str, Any]]:
        """Return the menu item tree as a list of dicts.

        Each dict contains: ``title``, ``key``, ``state``, ``has_action``,
        and optionally ``children`` (nested list).

        When *flat* is True, the tree is flattened and each item gets a
        ``path`` field (e.g. ``"Parent > Child"``).
        """
        if self._root is None:
            return []
        items = self._walk(self._root)
        if flat:
            return self._flatten(items)
        return items

    def trigger(self, title: str) -> bool:
        """Trigger a menu item by its title.

        Supports nested items using ``" > "`` as separator
        (e.g. ``"Parent > Child"``).  The callback is dispatched on the
        main thread.

        Returns True if the item was found and triggered.
        """
        if self._root is None:
            return False
        item = self._find(title)
        if item is None:
            return False

        from wenzi.statusbar import _ns_to_callback

        entry = _ns_to_callback.get(id(item._menuitem))
        if entry is None:
            return False

        smitem, callback = entry
        try:
            from PyObjCTools import AppHelper

            AppHelper.callAfter(callback, smitem)
        except Exception:
            logger.exception("Failed to trigger menu item: %s", title)
            return False
        return True

    def _find(self, title: str) -> Any:
        """Find a StatusMenuItem by title or path (``"A > B"``)."""
        from wenzi.statusbar import SeparatorMenuItem

        parts = [p.strip() for p in title.split(" > ")]
        node = self._root
        for part in parts:
            found = None
            for _key, child in node._items.items():
                if isinstance(child, SeparatorMenuItem):
                    continue
                if child.title == part:
                    found = child
                    break
            if found is None:
                return None
            node = found
        return node

    def _walk(self, parent: Any) -> List[Dict[str, Any]]:
        """Recursively walk the menu tree."""
        from wenzi.statusbar import SeparatorMenuItem, _ns_to_callback

        results: List[Dict[str, Any]] = []
        for key, item in parent._items.items():
            if isinstance(item, SeparatorMenuItem):
                continue
            entry: Dict[str, Any] = {
                "title": item.title,
                "key": key,
                "state": item.state,
                "has_action": id(item._menuitem) in _ns_to_callback,
            }
            if item._items:
                entry["children"] = self._walk(item)
            results.append(entry)
        return results

    def _flatten(
        self, items: List[Dict[str, Any]], prefix: str = "",
    ) -> List[Dict[str, Any]]:
        """Flatten a nested item list, adding ``path`` to each item."""
        flat: List[Dict[str, Any]] = []
        for item in items:
            path = f"{prefix} > {item['title']}" if prefix else item["title"]
            children = item.pop("children", None)
            item["path"] = path
            flat.append(item)
            if children:
                flat.extend(self._flatten(children, path))
        return flat

    # ------------------------------------------------------------------
    # AX-based app menu introspection
    # ------------------------------------------------------------------

    def _set_chooser_api(self, chooser_api):
        """Inject the ChooserAPI for accessing previous-app pid."""
        self._chooser_api = chooser_api

    def app_menu(self, pid=None):
        """Return the menu items of an application as a flat list.
        Each dict has: title, path, enabled, shortcut, _ax_element.
        pid defaults to the app frontmost before chooser opened.
        Returns empty list on failure.
        """
        if pid is None:
            pid = self._get_previous_pid()
        if pid is None:
            return []
        try:
            from ApplicationServices import AXUIElementCreateApplication
            ax_app = AXUIElementCreateApplication(pid)
            ax_menu_bar = _ax_attr(ax_app, "AXMenuBar")
            if ax_menu_bar is None:
                return []
            return self._walk_ax_menu(ax_menu_bar)
        except Exception:
            logger.debug("Failed to read app menu for pid=%s", pid, exc_info=True)
            return []

    def app_menu_trigger(self, item):
        """Trigger an app menu item from app_menu(). Returns True if dispatched."""
        ax_element = item.get("_ax_element")
        if ax_element is None:
            return False
        try:
            from ApplicationServices import AXUIElementPerformAction
            AXUIElementPerformAction(ax_element, "AXPress")
            return True
        except Exception:
            logger.debug("Failed to trigger app menu item", exc_info=True)
            return False

    def _get_previous_pid(self):
        """Get pid of app that was frontmost before chooser opened."""
        if self._chooser_api is None:
            return None
        try:
            prev_app = self._chooser_api.panel._previous_app
            if prev_app is not None:
                return prev_app.processIdentifier()
        except Exception:
            logger.debug("Failed to get previous app pid", exc_info=True)
        return None

    def _walk_ax_menu(self, ax_menu_bar, _prefix=""):
        """Recursively walk an AX menu bar, returning a flat list."""
        from ApplicationServices import AXUIElementCopyAttributeValue

        results = []
        err, children = AXUIElementCopyAttributeValue(ax_menu_bar, "AXChildren", None)
        if err != 0 or not children:
            return results

        for child in children:
            err, title = AXUIElementCopyAttributeValue(child, "AXTitle", None)
            if err != 0 or not title:
                continue
            title = str(title)

            err, enabled = AXUIElementCopyAttributeValue(child, "AXEnabled", None)
            enabled = bool(enabled) if err == 0 else True

            err, cmd_char = AXUIElementCopyAttributeValue(child, "AXMenuItemCmdChar", None)
            cmd_char = str(cmd_char) if err == 0 and cmd_char else ""

            err, cmd_mods = AXUIElementCopyAttributeValue(child, "AXMenuItemCmdModifiers", None)
            cmd_mods = int(cmd_mods) if err == 0 and cmd_mods is not None else 0

            err, sub_children = AXUIElementCopyAttributeValue(child, "AXChildren", None)
            if err == 0 and sub_children:
                for sub in sub_children:
                    results.extend(self._walk_ax_menu(sub, _prefix=f"{_prefix}{title} > "))
            else:
                shortcut = _build_shortcut(cmd_char, cmd_mods)
                path = f"{_prefix}{title}"
                results.append({
                    "title": title,
                    "path": path,
                    "enabled": enabled,
                    "shortcut": shortcut,
                    "_ax_element": child,
                })

        return results
