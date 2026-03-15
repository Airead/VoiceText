"""Clipboard change monitor.

Polls NSPasteboard.changeCount() in a background thread and records
text entries, excluding concealed/transient clipboard content from
password managers and VoiceText itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Pasteboard types that indicate concealed/transient content
_CONCEALED_TYPE = "org.nspasteboard.ConcealedType"
_TRANSIENT_TYPE = "com.nspasteboard.TransientType"


_DEFAULT_IMAGE_DIR = os.path.expanduser("~/.config/VoiceText/clipboard_images")


@dataclass
class ClipboardEntry:
    """A single clipboard history entry."""

    text: str = ""
    timestamp: float = field(default_factory=time.time)
    source_app: str = ""
    image_path: str = ""  # filename in clipboard_images/ (empty = text entry)
    image_width: int = 0
    image_height: int = 0
    image_size: int = 0  # file size in bytes


class ClipboardMonitor:
    """Background monitor that records clipboard text changes.

    Polls NSPasteboard.changeCount() at a configurable interval and
    stores entries in memory, with optional JSON persistence.
    """

    def __init__(
        self,
        max_items: int = 50,
        poll_interval: float = 0.5,
        persist_path: Optional[str] = None,
        image_dir: Optional[str] = None,
    ) -> None:
        self._max_items = max_items
        self._poll_interval = poll_interval
        self._persist_path = persist_path
        self._image_dir = image_dir or _DEFAULT_IMAGE_DIR
        self._entries: List[ClipboardEntry] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_change_count: int = -1

        if persist_path:
            self._load_from_disk()

    @staticmethod
    def default_image_dir() -> str:
        """Return the default directory for clipboard image storage."""
        return _DEFAULT_IMAGE_DIR

    @property
    def entries(self) -> List[ClipboardEntry]:
        """Return a copy of the history (newest first)."""
        with self._lock:
            return list(self._entries)

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()

        # Capture current changeCount so we don't record existing content
        try:
            from AppKit import NSPasteboard

            pb = NSPasteboard.generalPasteboard()
            self._last_change_count = pb.changeCount()
        except Exception:
            self._last_change_count = -1

        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Clipboard monitor started (interval=%.1fs)", self._poll_interval)

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("Clipboard monitor thread did not stop in time")
            self._thread = None
        logger.info("Clipboard monitor stopped")

    def clear(self) -> None:
        """Clear all history entries and associated image files."""
        with self._lock:
            self._entries.clear()
        self._save_to_disk()
        self._clear_image_dir()

    def _poll_loop(self) -> None:
        """Main polling loop running in a background thread."""
        while not self._stop_event.is_set():
            try:
                self._check_clipboard()
            except Exception:
                logger.debug("Clipboard poll error", exc_info=True)
            self._stop_event.wait(self._poll_interval)

    def _check_clipboard(self) -> None:
        """Check if the clipboard has changed and record new content."""
        from AppKit import NSPasteboard, NSPasteboardTypeString, NSPasteboardTypePNG, NSPasteboardTypeTIFF

        pb = NSPasteboard.generalPasteboard()
        current_count = pb.changeCount()

        if current_count == self._last_change_count:
            return

        self._last_change_count = current_count

        # Skip concealed/transient content (password managers, VoiceText paste)
        if self._is_concealed(pb):
            logger.debug("Skipping concealed/transient clipboard entry")
            return

        # Try text first
        text = pb.stringForType_(NSPasteboardTypeString)
        if text and str(text).strip():
            text_str = str(text).strip()
            source_app = self._get_frontmost_app()
            self._add_entry(text_str, source_app)
            return

        # Try image (PNG first, then TIFF)
        image_data = pb.dataForType_(NSPasteboardTypePNG)
        image_type = "png"
        if image_data is None:
            image_data = pb.dataForType_(NSPasteboardTypeTIFF)
            image_type = "tiff"
        if image_data is not None:
            source_app = self._get_frontmost_app()
            self._add_image_entry(bytes(image_data), image_type, source_app)

    @staticmethod
    def _is_concealed(pb) -> bool:
        """Check if the pasteboard contains concealed/transient markers."""
        types = pb.types()
        if types is None:
            return False
        type_list = list(types)
        return _CONCEALED_TYPE in type_list or _TRANSIENT_TYPE in type_list

    @staticmethod
    def _get_frontmost_app() -> str:
        """Return the name of the frontmost application."""
        try:
            from AppKit import NSWorkspace

            workspace = NSWorkspace.sharedWorkspace()
            app = workspace.frontmostApplication()
            if app and app.localizedName():
                return str(app.localizedName())
        except Exception:
            pass
        return ""

    def promote(self, text: str) -> None:
        """Move an existing entry to the top of the history list.

        If found, updates its timestamp. If not found, does nothing.
        """
        with self._lock:
            for i, entry in enumerate(self._entries):
                if entry.text == text:
                    self._entries.pop(i)
                    entry.timestamp = time.time()
                    self._entries.insert(0, entry)
                    snapshot = [asdict(e) for e in self._entries]
                    break
            else:
                return
        self._save_to_disk(snapshot)

    def promote_image(self, image_path: str) -> None:
        """Move an existing image entry to the top of the history list."""
        with self._lock:
            for i, entry in enumerate(self._entries):
                if entry.image_path == image_path:
                    self._entries.pop(i)
                    entry.timestamp = time.time()
                    self._entries.insert(0, entry)
                    snapshot = [asdict(e) for e in self._entries]
                    break
            else:
                return
        self._save_to_disk(snapshot)

    def _add_image_entry(
        self, image_data: bytes, image_type: str, source_app: str = ""
    ) -> None:
        """Save image data to disk and add an image clipboard entry."""
        result = self._save_image(image_data, image_type)
        if result is None:
            return

        filename, width, height, file_size = result

        with self._lock:
            # Skip if same as the most recent entry (by filename hash)
            if self._entries and self._entries[0].image_path == filename:
                return

            entry = ClipboardEntry(
                text="",
                timestamp=time.time(),
                source_app=source_app,
                image_path=filename,
                image_width=width,
                image_height=height,
                image_size=file_size,
            )
            self._entries.insert(0, entry)

            # Trim to max size — collect removed image paths
            removed = []
            if len(self._entries) > self._max_items:
                removed_entries = self._entries[self._max_items:]
                self._entries = self._entries[: self._max_items]
                removed = [e.image_path for e in removed_entries if e.image_path]
            snapshot = [asdict(e) for e in self._entries]

        if self._save_to_disk(snapshot) and removed:
            self._cleanup_image_files(removed)
        logger.debug("Clipboard image entry added: %s (%dx%d)", filename, width, height)

    def _save_image(
        self, image_data: bytes, image_type: str
    ) -> Optional[tuple]:
        """Save image data as PNG, return (filename, width, height, size) or None."""
        try:
            from AppKit import NSBitmapImageRep, NSPNGFileType
            from Foundation import NSData

            ns_data = NSData.dataWithBytes_length_(image_data, len(image_data))
            rep = NSBitmapImageRep.imageRepWithData_(ns_data)
            if rep is None:
                return None

            width = int(rep.pixelsWide())
            height = int(rep.pixelsHigh())

            # Convert to PNG if needed
            if image_type == "png":
                png_data = image_data
            else:
                png_ns = rep.representationUsingType_properties_(NSPNGFileType, {})
                if png_ns is None:
                    return None
                png_data = bytes(png_ns)

            # Generate filename: timestamp + hash of full content
            ts = int(time.time())
            content_hash = hashlib.sha256(png_data).hexdigest()[:12]
            filename = f"{ts}_{content_hash}.png"

            os.makedirs(self._image_dir, exist_ok=True)
            filepath = os.path.join(self._image_dir, filename)
            # Avoid overwriting an existing file (hash collision)
            if os.path.isfile(filepath):
                filename = f"{ts}_{content_hash}_1.png"
                filepath = os.path.join(self._image_dir, filename)
            with open(filepath, "wb") as f:
                f.write(png_data)

            return filename, width, height, len(png_data)
        except Exception:
            logger.debug("Failed to save clipboard image", exc_info=True)
            return None

    def _cleanup_image_files(self, filenames: List[str]) -> None:
        """Delete image files that are no longer referenced."""
        for fname in filenames:
            if not fname:
                continue
            path = os.path.join(self._image_dir, fname)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    logger.debug("Removed old clipboard image: %s", fname)
            except Exception:
                logger.debug("Failed to remove image %s", fname, exc_info=True)

    def _clear_image_dir(self) -> None:
        """Remove all files in the image directory."""
        try:
            if os.path.isdir(self._image_dir):
                for fname in os.listdir(self._image_dir):
                    fpath = os.path.join(self._image_dir, fname)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
        except Exception:
            logger.debug("Failed to clear image directory", exc_info=True)

    def _add_entry(self, text: str, source_app: str = "") -> None:
        """Add a new entry, deduplicating consecutive identical texts."""
        with self._lock:
            # Skip if same as the most recent entry
            if self._entries and self._entries[0].text == text:
                return

            entry = ClipboardEntry(
                text=text,
                timestamp=time.time(),
                source_app=source_app,
            )
            self._entries.insert(0, entry)

            # Trim to max size — collect removed image paths
            removed = []
            if len(self._entries) > self._max_items:
                removed_entries = self._entries[self._max_items:]
                self._entries = self._entries[: self._max_items]
                removed = [e.image_path for e in removed_entries if e.image_path]
            snapshot = [asdict(e) for e in self._entries]

        if self._save_to_disk(snapshot) and removed:
            self._cleanup_image_files(removed)
        logger.debug("Clipboard entry added: %s...", text[:40])

    def _save_to_disk(self, snapshot: Optional[list] = None) -> bool:
        """Persist entries to JSON file. Returns True on success.

        *snapshot* should be a pre-serialized list of dicts captured inside
        the lock to avoid race conditions.  When ``None``, a fresh snapshot
        is taken (legacy / ``clear()`` path).
        """
        if not self._persist_path:
            return True
        try:
            path = os.path.expanduser(self._persist_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if snapshot is None:
                with self._lock:
                    snapshot = [asdict(e) for e in self._entries]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.debug("Failed to save clipboard history", exc_info=True)
            return False

    def _load_from_disk(self) -> None:
        """Load entries from JSON file."""
        if not self._persist_path:
            return
        path = os.path.expanduser(self._persist_path)
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = []
            dropped = 0
            for d in data:
                if not isinstance(d, dict):
                    continue
                if "text" not in d and "image_path" not in d:
                    continue
                img = d.get("image_path", "")
                # Drop image entries whose file no longer exists
                if img and not os.path.isfile(
                    os.path.join(self._image_dir, img)
                ):
                    dropped += 1
                    continue
                entries.append(
                    ClipboardEntry(
                        text=d.get("text", ""),
                        timestamp=d.get("timestamp", 0),
                        source_app=d.get("source_app", ""),
                        image_path=img,
                        image_width=d.get("image_width", 0),
                        image_height=d.get("image_height", 0),
                        image_size=d.get("image_size", 0),
                    )
                )
            with self._lock:
                self._entries = entries
            if dropped:
                logger.info(
                    "Dropped %d clipboard image entries (files missing)", dropped
                )
                self._save_to_disk()
            logger.info("Loaded %d clipboard history entries", len(self._entries))
        except Exception:
            logger.debug("Failed to load clipboard history", exc_info=True)
