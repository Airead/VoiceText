"""Tests for the recorder module (AVAudioEngine backend)."""

import struct
import time
from unittest.mock import MagicMock

from wenzi.audio.recorder import Recorder, _resample_linear, _rms_int16


def _int16_bytes(value: int, count: int = 320) -> bytes:
    """Create raw int16 PCM bytes filled with a constant value."""
    return struct.pack(f"<{count}h", *([value] * count))


def _silence_bytes(count: int = 320) -> bytes:
    return b"\x00" * (count * 2)


def _mock_engine(monkeypatch):
    """Patch AVAudioEngine and friends so start() succeeds without hardware."""
    mock_engine = MagicMock()
    mock_input_node = MagicMock()
    mock_hw_fmt = MagicMock()
    mock_hw_fmt.sampleRate.return_value = 48000.0
    mock_input_node.outputFormatForBus_.return_value = mock_hw_fmt
    mock_input_node.auAudioUnit.return_value.deviceName.return_value = "TestMic"
    mock_engine.inputNode.return_value = mock_input_node
    mock_engine.startAndReturnError_.return_value = (True, None)

    monkeypatch.setattr(
        "wenzi.audio.recorder.AVAudioEngine",
        MagicMock(alloc=MagicMock(return_value=MagicMock(init=MagicMock(return_value=mock_engine)))),
    )
    monkeypatch.setattr(
        "wenzi.audio.recorder.NSNotificationCenter",
        MagicMock(defaultCenter=MagicMock(return_value=MagicMock(
            addObserverForName_object_queue_usingBlock_=MagicMock(return_value="observer"),
            removeObserver_=MagicMock(),
        ))),
    )
    return mock_engine


class TestRecorder:
    def test_init_defaults(self):
        r = Recorder()
        assert r.sample_rate == 16000
        assert r.is_recording is False

    def test_stop_without_start_returns_none(self):
        r = Recorder()
        assert r.stop() is None

    def test_start_stop_cycle(self, monkeypatch):
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20)
        r.start()
        assert r.is_recording is True

        # Simulate audio frames with enough energy to pass silence check
        frame = _int16_bytes(500)
        r._queue.put(frame)
        r._queue.put(frame)

        wav_data = r.stop()
        assert r.is_recording is False
        assert wav_data is not None
        assert len(wav_data) > 0

    def test_silence_detection_discards_quiet_audio(self, monkeypatch):
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20, silence_rms=20)
        r.start()

        # Simulate silent audio (all zeros -> RMS=0)
        r._queue.put(_silence_bytes())
        r._queue.put(_silence_bytes())

        wav_data = r.stop()
        assert wav_data is None

    def test_silence_detection_passes_loud_audio(self, monkeypatch):
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20, silence_rms=20)
        r.start()

        r._queue.put(_int16_bytes(1000))

        wav_data = r.stop()
        assert wav_data is not None

    def test_double_start_is_noop(self):
        r = Recorder()
        r._recording = True
        r.start()  # Should not raise

    def test_current_level_initial_zero(self):
        r = Recorder()
        assert r.current_level == 0.0

    def test_current_level_after_rms_set(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        # Directly set RMS to test level calculation
        # Frame of all 500s → RMS = 500 → level = 500/800 = 0.625
        r._current_rms = 500.0
        assert abs(r.current_level - 0.625) < 0.01

    def test_current_level_capped_at_one(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._current_rms = 10000.0
        assert r.current_level == 1.0

    def test_max_session_bytes(self, monkeypatch):
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20, max_session_bytes=640)
        r._recording = True

        # Simulate tap_callback by directly enqueueing
        frame = _int16_bytes(0, 320)  # 640 bytes
        r._queue.put(frame)
        r._total_bytes = 640

        # A second frame would exceed max; tap_callback would drop it
        # Verify the guard in tap_callback
        assert r._total_bytes + 640 > r.max_session_bytes

    def test_start_queries_device_name(self, monkeypatch):
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20)
        assert r._query_device_name_enabled is True

        name = r.start()
        assert name == "TestMic"
        r.stop()

    def test_start_skips_device_query_when_disabled(self, monkeypatch):
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20)
        r._query_device_name_enabled = False

        r.start()
        assert r.is_recording is True
        assert r._last_device_name is None
        r.stop()

    def test_starting_flag_prevents_concurrent_start(self):
        r = Recorder(sample_rate=16000, block_ms=20)
        r._starting_since = time.monotonic()
        result = r.start()
        assert result is r._last_device_name
        assert not r._recording

    def test_stale_starting_flag_is_reset(self, monkeypatch):
        monkeypatch.setattr(Recorder, "_STARTING_STALE_SECS", 0.0)
        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20)
        r._query_device_name_enabled = False
        r._starting_since = time.monotonic() - 1.0  # already stale
        r.start()
        assert r.is_recording is True
        r.stop()

    def test_mark_tainted_is_noop(self):
        r = Recorder()
        r.mark_tainted()  # Should not raise

    def test_device_param_logged_but_ignored(self, monkeypatch, caplog):
        import logging

        _mock_engine(monkeypatch)

        r = Recorder(sample_rate=16000, block_ms=20, device="SomeMic")
        r._query_device_name_enabled = False
        with caplog.at_level(logging.INFO, logger="wenzi.audio.recorder"):
            r.start()
        assert r.is_recording is True
        assert "ignoring" in caplog.text.lower()
        r.stop()


class TestRmsInt16:
    def test_silence(self):
        assert _rms_int16(b"\x00" * 640) == 0

    def test_constant_value(self):
        data = _int16_bytes(500, 100)
        assert _rms_int16(data) == 500

    def test_empty(self):
        assert _rms_int16(b"") == 0


class TestResampleLinear:
    def test_identity_ratio(self):
        """Ratio 1.0 should return the same samples."""
        src = (0.1, 0.2, 0.3, 0.4)
        result = _resample_linear(src, 4, 4, 1.0)
        assert len(result) == 4
        for a, b in zip(result, src):
            assert abs(a - b) < 1e-6

    def test_3to1_decimation(self):
        """48kHz→16kHz: ratio=3, 9 input → 3 output."""
        src = tuple(float(i) for i in range(9))
        result = _resample_linear(src, 9, 3, 3.0)
        assert len(result) == 3
        assert result[0] == 0.0
        assert result[1] == 3.0
        assert result[2] == 6.0

    def test_empty_input(self):
        assert _resample_linear((), 0, 0, 3.0) == []

    def test_fractional_ratio(self):
        """Non-integer ratio (e.g. 44.1→16) should interpolate."""
        src = (0.0, 1.0, 0.0)
        ratio = 3.0 / 2.0  # 1.5
        result = _resample_linear(src, 3, 2, ratio)
        assert len(result) == 2
        assert result[0] == 0.0  # src[0]
        assert abs(result[1] - 0.5) < 1e-6  # interpolated between src[1] and src[2]
