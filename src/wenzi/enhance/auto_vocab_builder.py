"""Automatic vocabulary building triggered by correction count threshold."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

from wenzi.statusbar import send_notification

logger = logging.getLogger(__name__)


class AutoVocabBuilder:
    """Silently builds vocabulary in the background when enough corrections accumulate."""

    def __init__(
        self,
        config: Dict[str, Any],
        enabled: bool = True,
        threshold: int = 50,
        on_build_done: Optional[Callable[[], None]] = None,
        on_status_update: Optional[Callable[[str], None]] = None,
        conversation_history: Any = None,
        data_dir: str | None = None,
    ) -> None:
        self._config = config
        self._enabled = enabled
        self._threshold = threshold
        self._counter = 0
        self._building = False
        self._lock = threading.Lock()
        self._enhancer = None
        self._on_build_done = on_build_done
        self._on_status_update = on_status_update
        self._conversation_history = conversation_history
        self._data_dir = data_dir
        self._init_counter_from_disk()

    def _init_counter_from_disk(self) -> None:
        """Initialize counter from unprocessed corrections on disk.

        Reads the last_processed_timestamp from vocabulary.json and counts
        corrections that occurred after it, so the counter survives app restarts.
        """
        if not self._enabled or not self._conversation_history or not self._data_dir:
            return

        try:
            vocab_path = os.path.join(
                os.path.expanduser(self._data_dir), "vocabulary.json"
            )
            since = None
            if os.path.exists(vocab_path):
                with open(vocab_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                since = data.get("last_processed_timestamp")

            pending = len(self._conversation_history.get_corrections(since=since))
            if pending > 0:
                self._counter = pending
                logger.info(
                    "Auto vocab builder: %d unprocessed corrections from disk",
                    pending,
                )
        except Exception as e:
            logger.debug("Failed to init counter from disk: %s", e)

    def set_enhancer(self, enhancer: Any) -> None:
        """Bind the TextEnhancer instance (needed for vocab_index reload)."""
        self._enhancer = enhancer

    def on_correction_logged(self) -> None:
        """Increment counter and trigger build if threshold is reached."""
        if not self._enabled:
            return

        with self._lock:
            self._counter += 1
            if self._counter < self._threshold:
                return
            if self._building:
                return
            self._counter = 0
            self._building = True

        self._run_silent_build()

    def is_building(self) -> bool:
        """Return True if a background build is in progress."""
        return self._building

    def _run_silent_build(self) -> None:
        """Start a background thread to build vocabulary silently."""
        t = threading.Thread(target=self._build, daemon=True)
        t.start()

    def _build(self) -> None:
        """Execute incremental vocabulary build, reload index, and notify."""
        if self._on_status_update:
            self._on_status_update("VB ...")
        try:
            from .vocabulary_builder import BuildCallbacks, VocabularyBuilder
            ai_cfg = self._config.get("ai_enhance", {})
            kwargs = {}
            if self._data_dir:
                kwargs["data_dir"] = self._data_dir
            builder = VocabularyBuilder(
                ai_cfg, conversation_history=self._conversation_history,
                **kwargs,
            )

            # Track progress: use total correction records as denominator,
            # streaming entry count as real-time numerator within each batch,
            # snapping to actual records processed after each batch completes.
            total_records = 0
            batch_size = 60
            records_completed = 0  # records from fully completed batches
            batch_entry_count = 0  # entries extracted in current batch (streaming)
            got_header = False

            def _update_status() -> None:
                if self._on_status_update and total_records > 0:
                    current = min(records_completed + batch_entry_count, total_records)
                    self._on_status_update(f"VB {current}/{total_records}")

            def _on_progress_init(rec_count: int, b_size: int) -> None:
                nonlocal total_records, batch_size
                total_records = rec_count
                batch_size = b_size
                _update_status()

            def _on_stream_chunk(chunk: str) -> None:
                nonlocal batch_entry_count, got_header
                for ch in chunk:
                    if ch == "\n":
                        if not got_header:
                            got_header = True  # skip header line
                        else:
                            batch_entry_count += 1
                            _update_status()

            def _on_batch_start(batch_idx: int, total: int) -> None:
                nonlocal got_header, batch_entry_count
                got_header = False
                batch_entry_count = 0

            def _on_batch_retry(batch_idx: int, total: int) -> None:
                nonlocal batch_entry_count, got_header
                got_header = False
                batch_entry_count = 0  # discard partial count

            def _on_batch_done(batch_idx: int, total: int, entries: int) -> None:
                nonlocal records_completed, batch_entry_count
                records_completed = min(batch_idx * batch_size, total_records)
                batch_entry_count = 0
                _update_status()

            callbacks = BuildCallbacks(
                on_progress_init=_on_progress_init,
                on_batch_start=_on_batch_start,
                on_stream_chunk=_on_stream_chunk if self._on_status_update else None,
                on_batch_done=_on_batch_done,
                on_batch_retry=_on_batch_retry,
            )

            loop = asyncio.new_event_loop()
            summary = loop.run_until_complete(builder.build(callbacks=callbacks))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

            # Reload vocabulary index
            if self._enhancer and self._enhancer.vocab_index is not None:
                self._enhancer.vocab_index.reload()

            new_entries = summary.get("new_entries", 0)
            total_entries = summary.get("total_entries", 0)
            logger.info(
                "Auto vocabulary build completed: %d new, %d total",
                new_entries,
                total_entries,
            )

            if self._on_build_done:
                try:
                    self._on_build_done()
                except Exception:
                    logger.debug("on_build_done callback failed", exc_info=True)

            if new_entries > 0:
                try:
                    send_notification(
                        "WenZi",
                        "Vocabulary Auto-Built",
                        f"{new_entries} new entries ({total_entries} total)",
                    )
                except Exception:
                    logger.debug("Notification center unavailable")
        except Exception as e:
            logger.error("Auto vocabulary build failed: %s", e)
        finally:
            with self._lock:
                self._building = False
            if self._on_status_update:
                self._on_status_update("")
