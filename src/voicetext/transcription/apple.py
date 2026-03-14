"""Apple Speech (SFSpeechRecognizer) transcriber for macOS."""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from typing import Callable, Optional

import numpy as np

from .base import BaseTranscriber

logger = logging.getLogger(__name__)

_LANG_TO_LOCALE = {
    "zh": "zh-CN",
    "en": "en-US",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "it": "it-IT",
    "pt": "pt-BR",
    "ru": "ru-RU",
}

RECOGNITION_TIMEOUT = 30  # seconds
STREAMING_FINAL_TIMEOUT = 10  # seconds to wait for final result after endAudio


_audio_fmt = None  # Cached AVAudioFormat (created once per sample rate)
_audio_fmt_sr = None


def _int16_to_avaudiopcmbuffer(samples: np.ndarray, sample_rate: int = 16000):
    """Convert int16 numpy array to AVAudioPCMBuffer for Speech framework."""
    global _audio_fmt, _audio_fmt_sr
    from AVFoundation import AVAudioFormat, AVAudioPCMBuffer

    if _audio_fmt is None or _audio_fmt_sr != sample_rate:
        _audio_fmt = AVAudioFormat.alloc().initStandardFormatWithSampleRate_channels_(
            float(sample_rate), 1
        )
        _audio_fmt_sr = sample_rate

    frame_count = len(samples)
    buf = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(_audio_fmt, frame_count)
    buf.setFrameLength_(frame_count)

    float_samples = samples.astype(np.float32) / 32768.0
    channel0 = buf.floatChannelData()[0]
    raw_buf = channel0.as_buffer(frame_count)
    raw_buf[:] = float_samples.tobytes()

    return buf


def _resolve_locale(language: str) -> str:
    """Convert short language code to BCP-47 locale."""
    if "-" in language or "_" in language:
        return language
    return _LANG_TO_LOCALE.get(language, language)


class AppleSpeechTranscriber(BaseTranscriber):
    """Speech-to-text using macOS built-in SFSpeechRecognizer."""

    skip_punc = True  # Apple Speech produces punctuated output

    def __init__(
        self,
        language: str = "zh",
        on_device: bool = True,
    ) -> None:
        self._language = language
        self._locale_id = _resolve_locale(language)
        self._on_device = on_device
        self._initialized = False
        self._recognizer = None

        # Streaming state
        self._stream_request = None
        self._stream_task = None
        self._stream_runloop_thread: Optional[threading.Thread] = None
        self._stream_runloop_stop = threading.Event()
        self._stream_final_event = threading.Event()
        self._stream_final_text: str = ""
        self._stream_on_partial: Optional[Callable[[str, bool], None]] = None

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def model_display_name(self) -> str:
        mode = "On-Device" if self._on_device else "Server"
        return f"Apple Speech ({mode})"

    def initialize(self) -> None:
        """Request authorization and create the recognizer."""
        if self._initialized:
            return

        logger.info(
            "Initializing Apple Speech recognizer (locale=%s, on_device=%s)",
            self._locale_id,
            self._on_device,
        )

        import Speech
        from Foundation import NSLocale

        # Request authorization (blocking via threading.Event)
        auth_event = threading.Event()
        auth_status = [None]

        def _on_auth(status):
            auth_status[0] = status
            auth_event.set()

        Speech.SFSpeechRecognizer.requestAuthorization_(_on_auth)

        # Drive the RunLoop so the callback fires on this thread
        from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode

        deadline = time.monotonic() + 10
        while not auth_event.is_set() and time.monotonic() < deadline:
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.1, False)

        if not auth_event.is_set():
            raise PermissionError(
                "Apple Speech authorization timed out. "
                "Grant access in System Settings > Privacy & Security > Speech Recognition."
            )

        if auth_status[0] != Speech.SFSpeechRecognizerAuthorizationStatusAuthorized:
            raise PermissionError(
                "Apple Speech recognition not authorized. "
                "Grant access in System Settings > Privacy & Security > Speech Recognition."
            )

        locale = NSLocale.alloc().initWithLocaleIdentifier_(self._locale_id)
        recognizer = Speech.SFSpeechRecognizer.alloc().initWithLocale_(locale)

        if recognizer is None or not recognizer.isAvailable():
            raise RuntimeError(
                f"SFSpeechRecognizer is not available for locale {self._locale_id!r}."
            )

        # Check on-device support
        if self._on_device and not recognizer.supportsOnDeviceRecognition():
            logger.warning(
                "On-device recognition not supported for %s, falling back to server mode.",
                self._locale_id,
            )
            self._on_device = False

        self._recognizer = recognizer
        self._initialized = True
        logger.info("Apple Speech recognizer ready (locale=%s)", self._locale_id)

    def transcribe(self, wav_data: bytes) -> str:
        """Transcribe WAV audio bytes using SFSpeechRecognizer."""
        if not self._initialized:
            self.initialize()

        import Speech
        from Foundation import NSURL
        from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode

        # Write WAV to a temporary file for SFSpeechURLRecognitionRequest
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_data)
            tmp_path = tmp.name

        try:
            url = NSURL.fileURLWithPath_(tmp_path)
            request = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(url)

            if self._on_device:
                request.setRequiresOnDeviceRecognition_(True)

            result_holder = [None]
            error_holder = [None]
            done_event = threading.Event()

            def _handler(result, error):
                if error is not None:
                    error_holder[0] = error
                if result is not None and result.isFinal():
                    result_holder[0] = result
                    done_event.set()
                elif error is not None:
                    done_event.set()

            self._recognizer.recognitionTaskWithRequest_resultHandler_(
                request, _handler
            )

            # Drive RunLoop until recognition completes or times out
            deadline = time.monotonic() + RECOGNITION_TIMEOUT
            while not done_event.is_set() and time.monotonic() < deadline:
                CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.1, False)

            if not done_event.is_set():
                logger.warning("Apple Speech recognition timed out after %ds", RECOGNITION_TIMEOUT)
                return ""

            if error_holder[0] is not None and result_holder[0] is None:
                logger.error("Apple Speech recognition error: %s", error_holder[0])
                return ""

            if result_holder[0] is not None:
                text = result_holder[0].bestTranscription().formattedString()
                logger.info("Transcription result: %s", text[:100])
                return text

            return ""
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── Streaming interface ───────────────────────────────────────────

    @property
    def supports_streaming(self) -> bool:
        return True

    def start_streaming(self, on_partial: Callable[[str, bool], None]) -> None:
        """Begin a streaming recognition session using SFSpeechAudioBufferRecognitionRequest."""
        if not self._initialized:
            self.initialize()

        import Speech

        self._stream_final_event.clear()
        self._stream_runloop_stop.clear()
        self._stream_final_text = ""
        self._stream_on_partial = on_partial

        request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)
        if self._on_device:
            request.setRequiresOnDeviceRecognition_(True)
        self._stream_request = request

        # Result handler — will be invoked on the RunLoop thread
        def _result_handler(result, error):
            if error is not None:
                err_desc = (
                    str(error.localizedDescription())
                    if hasattr(error, "localizedDescription")
                    else str(error)
                )
                logger.warning("Streaming recognition error: %s", err_desc)
                if result is None:
                    self._stream_final_event.set()
                    return

            if result is None:
                return

            text = result.bestTranscription().formattedString()
            is_final = result.isFinal()

            if is_final:
                self._stream_final_text = text
                self._stream_final_event.set()

            cb = self._stream_on_partial
            if cb is not None:
                try:
                    cb(text, is_final)
                except Exception:
                    logger.warning("on_partial callback error", exc_info=True)

        # Start recognition task on a dedicated RunLoop thread
        recognizer = self._recognizer

        def _runloop_thread():
            from CoreFoundation import (
                CFRunLoopRunInMode,
                kCFRunLoopDefaultMode,
            )

            # Create the task on this thread so callbacks fire on its RunLoop
            task = recognizer.recognitionTaskWithRequest_resultHandler_(
                request, _result_handler
            )
            self._stream_task = task

            while not self._stream_runloop_stop.is_set():
                CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.05, False)

        t = threading.Thread(target=_runloop_thread, daemon=True)
        t.start()
        self._stream_runloop_thread = t
        logger.info("Streaming recognition started")

    def feed_audio(self, samples: np.ndarray) -> None:
        """Feed an int16 audio chunk to the active streaming session."""
        request = self._stream_request
        if request is None:
            return
        pcm_buf = _int16_to_avaudiopcmbuffer(samples, self.sample_rate)
        request.appendAudioPCMBuffer_(pcm_buf)

    @property
    def sample_rate(self) -> int:
        """Return the expected sample rate (matches Recorder default)."""
        return 16000

    def stop_streaming(self) -> str:
        """End audio and wait for the final transcription result."""
        request = self._stream_request
        if request is not None:
            request.endAudio()
            logger.info("Streaming endAudio sent, waiting for final result...")

        if not self._stream_final_event.wait(timeout=STREAMING_FINAL_TIMEOUT):
            logger.warning(
                "Streaming final result timed out after %ds", STREAMING_FINAL_TIMEOUT
            )
            if self._stream_task is not None:
                self._stream_task.cancel()

        self._stop_runloop_thread()
        text = self._stream_final_text
        self._reset_streaming_state()
        logger.info("Streaming recognition stopped, final text: %s", text[:100] if text else "(empty)")
        return text

    def cancel_streaming(self) -> None:
        """Cancel the active streaming session."""
        if self._stream_task is not None:
            self._stream_task.cancel()
        self._stop_runloop_thread()
        self._reset_streaming_state()
        logger.info("Streaming recognition cancelled")

    def _stop_runloop_thread(self) -> None:
        """Signal the RunLoop thread to stop and wait for it."""
        self._stream_runloop_stop.set()
        t = self._stream_runloop_thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)

    def _reset_streaming_state(self) -> None:
        """Clear all streaming state."""
        self._stream_request = None
        self._stream_task = None
        self._stream_runloop_thread = None
        self._stream_on_partial = None
        self._stream_final_text = ""

    def cleanup(self) -> None:
        """Release the recognizer."""
        self.cancel_streaming()
        self._recognizer = None
        self._initialized = False
        logger.info("Apple Speech recognizer cleaned up")
