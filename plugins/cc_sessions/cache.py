"""Persistent disk cache for session metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_VERSION = 1


class SessionCache:
    """JSON-backed cache mapping file paths to (mtime, session_data).

    Stores two kinds of entries:
    - **session entries**: keyed by JSONL file path
    - **index entries**: keyed by sessions-index.json path, value is a list of sessions

    The cache file is only written when :meth:`save` is called and the
    cache has been modified since the last load/save.
    """

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._sessions: dict[str, dict[str, Any]] = {}
        self._indexes: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def get(self, file_path: str) -> tuple[float, dict[str, Any]] | None:
        """Return ``(mtime, session_data)`` or ``None``."""
        return self._get_entry(self._sessions, file_path)

    def put(self, file_path: str, mtime: float, data: dict[str, Any]) -> None:
        """Store or update a session entry."""
        self._put_entry(self._sessions, file_path, mtime, data)

    def get_index(self, index_path: str) -> tuple[float, list[dict[str, Any]]] | None:
        """Return ``(mtime, sessions_list)`` or ``None``."""
        return self._get_entry(self._indexes, index_path)

    def put_index(self, index_path: str, mtime: float, sessions: list[dict[str, Any]]) -> None:
        """Store or update an index entry."""
        self._put_entry(self._indexes, index_path, mtime, sessions)

    def prune(
        self,
        live_paths: set[str],
        live_index_paths: set[str] | None = None,
    ) -> None:
        """Remove entries whose paths are not in *live_paths*."""
        stale = [k for k in self._sessions if k not in live_paths]
        for k in stale:
            del self._sessions[k]
        if stale:
            self._dirty = True

        if live_index_paths is not None:
            stale_idx = [k for k in self._indexes if k not in live_index_paths]
            for k in stale_idx:
                del self._indexes[k]
            if stale_idx:
                self._dirty = True

    def save(self) -> None:
        """Write cache to disk if modified, using atomic rename."""
        if not self._dirty:
            return
        data = {
            "version": _CACHE_VERSION,
            "sessions": self._sessions,
            "indexes": self._indexes,
        }
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._path)
            self._dirty = False
            logger.debug("Session cache saved to %s", self._path)
        except OSError:
            logger.warning("Failed to save session cache", exc_info=True)

    def _get_entry(self, store: dict[str, dict[str, Any]], key: str) -> tuple[float, Any] | None:
        entry = store.get(key)
        if entry is None:
            return None
        try:
            return entry["mtime"], entry["data"]
        except (KeyError, TypeError):
            return None

    def _put_entry(self, store: dict[str, dict[str, Any]], key: str, mtime: float, data: Any) -> None:
        store[key] = {"mtime": mtime, "data": data}
        self._dirty = True

    def _load(self) -> None:
        """Load cache from disk. Silently starts empty on any error."""
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read session cache, starting fresh", exc_info=True)
            return

        if not isinstance(raw, dict) or raw.get("version") != _CACHE_VERSION:
            logger.info("Session cache version mismatch, starting fresh")
            return

        self._sessions = raw.get("sessions", {})
        self._indexes = raw.get("indexes", {})
