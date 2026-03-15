"""App search data source for the Chooser.

Scans /Applications, /System/Applications, and ~/Applications for .app
bundles, checks running status via NSWorkspace, and provides substring
matching with running apps ranked first.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import List

from voicetext.scripting.sources import ChooserItem, ChooserSource

logger = logging.getLogger(__name__)

_ICON_SIZE = 32

# Directories to scan for applications
_APP_DIRS = [
    "/Applications",
    "/System/Applications",
    "/System/Applications/Utilities",
    "/System/Library/CoreServices/Applications",
    os.path.expanduser("~/Applications"),
]


def _get_display_name(path: str, fallback: str) -> str:
    """Return the localized display name for an app bundle path."""
    try:
        from Foundation import NSFileManager

        fm = NSFileManager.defaultManager()
        display = fm.displayNameAtPath_(path)
        if display:
            name = str(display)
            # displayNameAtPath_ may include ".app" for non-localized names
            if name.endswith(".app"):
                name = name[:-4]
            return name
    except Exception:
        pass
    return fallback


def _get_app_icon_data_uri(path: str) -> str:
    """Return a data:image/png;base64 URI for the app icon, or empty string."""
    try:
        from AppKit import (
            NSBitmapImageRep,
            NSCompositingOperationCopy,
            NSImage,
            NSPNGFileType,
            NSWorkspace,
        )
        from Foundation import NSMakeRect, NSSize

        ws = NSWorkspace.sharedWorkspace()
        icon = ws.iconForFile_(path)
        if icon is None:
            return ""

        # Render into a fixed-size image to control pixel output
        size = NSSize(_ICON_SIZE, _ICON_SIZE)
        target = NSImage.alloc().initWithSize_(size)
        target.lockFocus()
        icon.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, _ICON_SIZE, _ICON_SIZE),
            NSMakeRect(0, 0, icon.size().width, icon.size().height),
            NSCompositingOperationCopy,
            1.0,
        )
        target.unlockFocus()

        rep = NSBitmapImageRep.imageRepWithData_(target.TIFFRepresentation())
        png_data = rep.representationUsingType_properties_(NSPNGFileType, None)
        b64 = base64.b64encode(bytes(png_data)).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        logger.debug("Failed to get icon for %s", path, exc_info=True)
        return ""


def _scan_apps() -> list[dict]:
    """Scan application directories and return a list of app info dicts.

    Each dict has keys: name (str), display_name (str), path (str).
    ``name`` is the English bundle name (for dedup and running-status matching),
    ``display_name`` is the localized name shown to the user.
    Icons are extracted lazily on first access to avoid slow startup.
    """
    apps = []
    seen = set()

    for app_dir in _APP_DIRS:
        if not os.path.isdir(app_dir):
            continue
        try:
            entries = os.listdir(app_dir)
        except OSError:
            continue

        for entry in entries:
            if not entry.endswith(".app"):
                continue
            full_path = os.path.join(app_dir, entry)
            name = entry[:-4]  # Strip ".app"
            if name in seen:
                continue
            seen.add(name)
            display_name = _get_display_name(full_path, name)
            apps.append({
                "name": name,
                "display_name": display_name,
                "path": full_path,
            })

    logger.info("Scanned %d apps from %s", len(apps), _APP_DIRS)
    return apps


def _get_running_app_names() -> set[str]:
    """Return a set of currently running application names."""
    try:
        from AppKit import NSWorkspace

        workspace = NSWorkspace.sharedWorkspace()
        running = workspace.runningApplications()
        return {
            str(app.localizedName())
            for app in running
            if app.localizedName()
        }
    except Exception:
        logger.debug("Failed to get running apps", exc_info=True)
        return set()


def _launch_app(path: str) -> None:
    """Launch or activate an application by path."""
    try:
        from AppKit import NSWorkspace

        workspace = NSWorkspace.sharedWorkspace()
        workspace.launchApplication_(path)
    except Exception:
        logger.exception("Failed to launch app: %s", path)


class AppSource:
    """Application search data source.

    Scans app directories once on init and caches the list.
    Running status is checked on every search for fresh results.
    Icons are extracted lazily and cached per app path.
    """

    def __init__(self) -> None:
        self._apps: list[dict] = []
        self._scanned = False
        self._icon_cache: dict[str, str] = {}  # path → data URI

    def _get_icon(self, path: str) -> str:
        """Return cached icon data URI, extracting on first call."""
        if path not in self._icon_cache:
            self._icon_cache[path] = _get_app_icon_data_uri(path)
        return self._icon_cache[path]

    def _ensure_scanned(self) -> None:
        if not self._scanned:
            self._apps = _scan_apps()
            self._scanned = True

    def rescan(self) -> None:
        """Force a rescan of application directories."""
        self._apps = _scan_apps()
        self._scanned = True

    def search(self, query: str) -> List[ChooserItem]:
        """Search apps by substring matching, running apps first.

        Matches against both the English bundle name and the localized
        display name so users can search in any language.
        """
        self._ensure_scanned()

        if not query.strip():
            return []

        q = query.lower()
        running = _get_running_app_names()

        matches = []
        for app in self._apps:
            name = app["name"]
            display_name = app["display_name"]
            if q not in name.lower() and q not in display_name.lower():
                continue
            # Match running status against both English and localized names
            is_running = name in running or display_name in running
            path = app["path"]
            matches.append((is_running, display_name, path))

        # Sort: running apps first, then alphabetical
        matches.sort(key=lambda x: (not x[0], x[1].lower()))

        return [
            ChooserItem(
                title=display_name,
                subtitle="Running" if is_running else "Application",
                icon=self._get_icon(path),
                action=lambda p=path: _launch_app(p),
                reveal_path=path,
            )
            for is_running, display_name, path in matches
        ]

    def as_chooser_source(self) -> ChooserSource:
        """Return a ChooserSource wrapping this AppSource."""
        return ChooserSource(
            name="apps",
            prefix=None,
            search=self.search,
            priority=10,
        )
