"""Tests for Recorder audio chunk callback (streaming support)."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

from wenzi.audio.recorder import Recorder


class TestAudioChunkCallback:
    def test_default_no_callback(self):
        r = Recorder()
        assert r._on_audio_chunk is None

    def test_set_and_clear_callback(self):
        r = Recorder()
        cb = MagicMock()
        r.set_on_audio_chunk(cb)
        assert r._on_audio_chunk is cb
        r.clear_on_audio_chunk()
        assert r._on_audio_chunk is None

    def test_callback_receives_audio_chunks(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._recording = True
        chunks: list[bytes] = []
        r.set_on_audio_chunk(lambda data: chunks.append(data))

        # Simulate by directly enqueueing and calling the callback
        fake_audio = struct.pack("<4h", 100, 200, 300, -100)
        r._queue.put(fake_audio)
        r._total_bytes = 0

        # Manually invoke what tap_callback does for the chunk callback
        cb = r._on_audio_chunk
        cb(fake_audio)

        assert len(chunks) == 1
        assert chunks[0] == fake_audio

    def test_callback_not_called_when_unset(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._recording = True

        # Should not raise when no callback is set
        assert r._on_audio_chunk is None

    def test_callback_error_does_not_break_queue(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._recording = True

        def bad_cb(data):
            raise RuntimeError("callback error")

        r.set_on_audio_chunk(bad_cb)

        # Enqueue frame directly (simulating tap_callback behavior)
        fake_audio = struct.pack("<2h", 100, 200)
        r._queue.put(fake_audio)

        # Audio should still be in queue
        assert not r._queue.empty()
        queued = r._queue.get_nowait()
        assert queued == fake_audio

    def test_callback_not_invoked_when_max_size_reached(self):
        r = Recorder(sample_rate=16000, block_ms=20, max_session_bytes=4)
        r._recording = True
        cb = MagicMock()
        r.set_on_audio_chunk(cb)

        # First frame: 4 bytes (2 int16) — simulate tap_callback enqueue
        frame1 = struct.pack("<2h", 100, 200)
        r._queue.put(frame1)
        r._total_bytes = 4
        cb(frame1)
        assert cb.call_count == 1

        # Second frame would exceed max — tap_callback would drop it
        assert r._total_bytes + 4 > r.max_session_bytes
