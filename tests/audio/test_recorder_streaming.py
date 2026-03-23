"""Tests for Recorder audio chunk callback (streaming support)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

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
        r._recording = True  # callback guard requires recording state
        chunks = []
        r.set_on_audio_chunk(lambda data: chunks.append(data))

        # Simulate the sounddevice callback
        fake_audio = np.array([100, 200, 300, -100], dtype=np.int16)
        r._callback(fake_audio.tobytes(), len(fake_audio), None, None)

        assert len(chunks) == 1
        np.testing.assert_array_equal(chunks[0], fake_audio)

    def test_callback_not_called_when_unset(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._recording = True

        fake_audio = np.array([100, 200], dtype=np.int16)
        # Should not raise when no callback is set
        r._callback(fake_audio.tobytes(), len(fake_audio), None, None)

    def test_callback_error_does_not_break_recording(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._recording = True

        def bad_cb(data):
            raise RuntimeError("callback error")

        r.set_on_audio_chunk(bad_cb)

        fake_audio = np.array([100, 200], dtype=np.int16)
        # Should not raise
        r._callback(fake_audio.tobytes(), len(fake_audio), None, None)

        # Audio should still be queued
        assert not r._queue.empty()
        queued = r._queue.get_nowait()
        np.testing.assert_array_equal(queued, fake_audio)

    def test_callback_receives_copy_not_original(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._recording = True
        received = []
        r.set_on_audio_chunk(lambda data: received.append(data))

        fake_audio = np.array([100, 200, 300], dtype=np.int16)
        r._callback(fake_audio.tobytes(), len(fake_audio), None, None)

        # The callback should receive a copy, not a view of the buffer
        assert len(received) == 1
        assert received[0] is not fake_audio

    def test_callback_not_invoked_when_max_size_reached(self):
        r = Recorder(sample_rate=16000, block_ms=20, max_session_bytes=4)
        r._recording = True
        cb = MagicMock()
        r.set_on_audio_chunk(cb)

        # First frame: 4 bytes (2 int16) fits
        frame1 = np.array([100, 200], dtype=np.int16)
        r._callback(frame1.tobytes(), len(frame1), None, None)
        assert cb.call_count == 1

        # Second frame: would exceed max, should be dropped
        frame2 = np.array([300, 400], dtype=np.int16)
        r._callback(frame2.tobytes(), len(frame2), None, None)
        assert cb.call_count == 1  # Not called again
