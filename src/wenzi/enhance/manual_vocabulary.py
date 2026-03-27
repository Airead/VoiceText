"""Manual vocabulary store — user-curated correction pairs.

Each entry represents a single variant→term pair that the user has explicitly
confirmed.  Entries carry rich metadata (app, model, timestamps) and are
persisted as JSON at ``~/.local/share/WenZi/manual_vocabulary.json``.
"""

from __future__ import annotations

import json
import logging
import os
import string
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_VERSION = 1

# Allowed values for ManualVocabEntry.source
SOURCE_ASR = "asr"
SOURCE_LLM = "llm"
SOURCE_USER = "user"


@dataclass
class ManualVocabEntry:
    """A single user-confirmed correction pair."""

    term: str  # correct form ("Kubernetes")
    variant: str  # ASR / LLM erroneous form ("库伯尼特斯")
    source: str = SOURCE_ASR
    frequency: int = 1  # times the user added/confirmed this pair
    hit_count: int = 0  # times this pair was actually used in correction
    first_seen: str = ""  # ISO 8601
    last_seen: str = ""  # ISO 8601
    last_hit: str = ""  # ISO 8601, last time this pair was hit
    app_bundle_id: str = ""  # e.g. "com.apple.dt.Xcode"
    asr_model: str = ""
    llm_model: str = ""
    enhance_mode: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_STRIP_CHARS = string.whitespace + string.punctuation + "\u3000\u3001\u3002\uff0c\uff01\uff1f"


def _normalize(s: str) -> str:
    """Strip leading/trailing whitespace and punctuation."""
    return s.strip(_STRIP_CHARS)


def _key(variant: str, term: str) -> tuple[str, str]:
    """Canonical key: (normalized + lowercased variant, normalized + lowercased term)."""
    return (_normalize(variant).lower(), _normalize(term).lower())


class ManualVocabularyStore:
    """Thread-safe store for user-curated correction pairs."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._entries: dict[tuple[str, str], ManualVocabEntry] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load entries from disk.  Missing / corrupt file → empty store."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            entries: dict[tuple[str, str], ManualVocabEntry] = {}
            for raw in data.get("entries", []):
                entry = ManualVocabEntry(
                    term=_normalize(raw["term"]),
                    variant=_normalize(raw["variant"]),
                    source=raw.get("source", SOURCE_ASR),
                    frequency=raw.get("frequency", 1),
                    hit_count=raw.get("hit_count", 0),
                    first_seen=raw.get("first_seen", ""),
                    last_seen=raw.get("last_seen", ""),
                    last_hit=raw.get("last_hit", ""),
                    app_bundle_id=raw.get("app_bundle_id", ""),
                    asr_model=raw.get("asr_model", ""),
                    llm_model=raw.get("llm_model", ""),
                    enhance_mode=raw.get("enhance_mode", ""),
                )
                k = _key(entry.variant, entry.term)
                existing = entries.get(k)
                if existing is not None:
                    # Merge duplicates caused by pre-normalization data
                    existing.frequency += entry.frequency
                    existing.hit_count += entry.hit_count
                    if entry.last_seen > existing.last_seen:
                        existing.last_seen = entry.last_seen
                    if entry.last_hit > existing.last_hit:
                        existing.last_hit = entry.last_hit
                else:
                    entries[k] = entry
            with self._lock:
                self._entries = entries
            logger.info("Manual vocabulary loaded: %d entries", len(entries))
        except Exception:
            logger.warning("Failed to load manual vocabulary", exc_info=True)

    def save(self) -> None:
        """Atomically persist entries to disk."""
        with self._lock:
            entries_list = list(self._entries.values())
        data = {
            "version": _VERSION,
            "entries": [asdict(e) for e in entries_list],
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self._path), suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            logger.warning("Failed to save manual vocabulary", exc_info=True)
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(
        self,
        variant: str,
        term: str,
        source: str = SOURCE_ASR,
        *,
        app_bundle_id: str = "",
        asr_model: str = "",
        llm_model: str = "",
        enhance_mode: str = "",
    ) -> ManualVocabEntry:
        """Add or update a correction pair.

        If the (variant, term) pair already exists, increment *frequency*
        and update *last_seen*.  Returns the (possibly updated) entry.
        """
        variant = _normalize(variant)
        term = _normalize(term)
        k = _key(variant, term)
        now = _now_iso()
        with self._lock:
            existing = self._entries.get(k)
            if existing is not None:
                existing.frequency += 1
                existing.last_seen = now
                if app_bundle_id:
                    existing.app_bundle_id = app_bundle_id
                if asr_model:
                    existing.asr_model = asr_model
                if llm_model:
                    existing.llm_model = llm_model
                if enhance_mode:
                    existing.enhance_mode = enhance_mode
                entry = existing
            else:
                entry = ManualVocabEntry(
                    term=term,
                    variant=variant,
                    source=source,
                    frequency=1,
                    hit_count=0,
                    first_seen=now,
                    last_seen=now,
                    last_hit="",
                    app_bundle_id=app_bundle_id,
                    asr_model=asr_model,
                    llm_model=llm_model,
                    enhance_mode=enhance_mode,
                )
                self._entries[k] = entry
        self.save()
        return entry

    def remove(self, variant: str, term: str) -> bool:
        """Remove a correction pair.  Returns True if it existed."""
        k = _key(variant, term)
        with self._lock:
            removed = self._entries.pop(k, None)
        if removed is not None:
            self.save()
            return True
        return False

    def contains(self, variant: str, term: str) -> bool:
        """Check whether a (variant, term) pair exists."""
        k = _key(variant, term)
        with self._lock:
            return k in self._entries

    # ------------------------------------------------------------------
    # Hit tracking
    # ------------------------------------------------------------------

    def record_hit(self, variant: str, term: str) -> None:
        """Record that this pair was used in a correction.

        Increments *hit_count* and updates *last_hit*.
        """
        self.record_hits([(variant, term)])

    def record_hits(self, pairs: list[tuple[str, str]]) -> None:
        """Record multiple hits in a single save operation."""
        now = _now_iso()
        changed = False
        with self._lock:
            for variant, term in pairs:
                entry = self._entries.get(_key(variant, term))
                if entry is not None:
                    entry.hit_count += 1
                    entry.last_hit = now
                    changed = True
        if changed:
            self.save()

    def find_hits_in_text(self, text: str) -> list[ManualVocabEntry]:
        """Return entries whose *variant* appears in *text* (case-insensitive)."""
        text_lower = text.lower()
        hits: list[ManualVocabEntry] = []
        with self._lock:
            for entry in self._entries.values():
                if entry.variant.lower() in text_lower:
                    hits.append(entry)
        return hits

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_all(self) -> list[ManualVocabEntry]:
        """Return a snapshot of all entries."""
        with self._lock:
            return list(self._entries.values())

    def get_all_for_state(self) -> list[dict]:
        """Return ``[{variant, term}]`` for JS-side state synchronization."""
        with self._lock:
            return [
                {"variant": e.variant, "term": e.term}
                for e in self._entries.values()
            ]

    def get_asr_hotwords(
        self,
        *,
        asr_model: Optional[str] = None,
        app_bundle_id: Optional[str] = None,
    ) -> list[str]:
        """Return *term* strings for ASR hotword injection.

        When *app_bundle_id* or *asr_model* is given, entries matching the
        filter are returned first, followed by non-matching entries.  This
        ensures context-specific hotwords have higher priority while still
        exposing the full manual vocabulary.
        """
        with self._lock:
            entries = list(self._entries.values())

        # Partition into matching vs non-matching
        matching: list[str] = []
        other: list[str] = []
        seen: set[str] = set()
        for e in entries:
            term_lower = e.term.lower()
            if term_lower in seen:
                continue
            seen.add(term_lower)
            is_match = True
            if app_bundle_id and e.app_bundle_id and e.app_bundle_id != app_bundle_id:
                is_match = False
            if asr_model and e.asr_model and e.asr_model != asr_model:
                is_match = False
            if is_match:
                matching.append(e.term)
            else:
                other.append(e.term)
        return matching + other

    def get_llm_vocab(
        self,
        *,
        app_bundle_id: Optional[str] = None,
    ) -> list[ManualVocabEntry]:
        """Return entries for LLM prompt injection.

        Entries matching *app_bundle_id* are sorted first.
        """
        with self._lock:
            entries = list(self._entries.values())

        if not app_bundle_id:
            return entries

        matching: list[ManualVocabEntry] = []
        other: list[ManualVocabEntry] = []
        for e in entries:
            if e.app_bundle_id and e.app_bundle_id == app_bundle_id:
                matching.append(e)
            else:
                other.append(e)
        return matching + other

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)
