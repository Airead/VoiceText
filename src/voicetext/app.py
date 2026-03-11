"""VoiceText macOS menubar application."""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Dict, Optional

import rumps
from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions
from CoreFoundation import kCFBooleanTrue

from .config import load_config, save_config
from .hotkey import HoldHotkeyListener
from .input import type_text
from .model_registry import (
    PRESET_BY_ID,
    PRESETS,
    ModelPreset,
    get_model_cache_dir,
    is_model_cached,
    resolve_preset_from_config,
)
from .recorder import Recorder
from .transcriber import create_transcriber


logger = logging.getLogger(__name__)

# Approximate FunASR total model size in bytes (ASR + VAD + PUNC)
_FUNASR_APPROX_SIZE = 502 * 1024 * 1024


class VoiceTextApp(rumps.App):
    """Menubar app: hold hotkey to record, release to transcribe and type."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        super().__init__("VoiceText", icon=None, title="VT")

        self._config_path = config_path
        self._config = load_config(config_path)
        self._setup_logging()

        audio_cfg = self._config["audio"]
        self._recorder = Recorder(
            sample_rate=audio_cfg["sample_rate"],
            block_ms=audio_cfg["block_ms"],
            device=audio_cfg.get("device"),
            max_session_bytes=audio_cfg["max_session_bytes"],
            silence_rms=audio_cfg.get("silence_rms", Recorder.DEFAULT_SILENCE_RMS),
        )

        asr_cfg = self._config["asr"]
        self._transcriber = create_transcriber(
            backend=asr_cfg.get("backend", "funasr"),
            use_vad=asr_cfg.get("use_vad", True),
            use_punc=asr_cfg.get("use_punc", True),
            language=asr_cfg.get("language"),
            model=asr_cfg.get("model"),
        )

        self._output_method = self._config["output"]["method"]
        self._append_newline = self._config["output"]["append_newline"]
        self._hotkey_listener: Optional[HoldHotkeyListener] = None
        self._busy = False

        # Resolve current preset
        self._current_preset_id = asr_cfg.get("preset")
        if not self._current_preset_id:
            self._current_preset_id = resolve_preset_from_config(
                asr_cfg.get("backend", "funasr"),
                asr_cfg.get("model"),
            )

        # Menu items
        self._status_item = rumps.MenuItem("Ready")
        self._status_item.set_callback(None)
        hotkey_name = self._config["hotkey"]
        self._hotkey_item = rumps.MenuItem(f"Hotkey: {hotkey_name}")
        self._hotkey_item.set_callback(None)

        # Model submenu
        self._model_menu = rumps.MenuItem("Model")
        self._model_menu_items: Dict[str, rumps.MenuItem] = {}
        for preset in PRESETS:
            item = rumps.MenuItem(preset.display_name)
            item.set_callback(self._on_model_select)
            # Tag the item with preset id
            item._preset_id = preset.id
            if preset.id == self._current_preset_id:
                item.state = 1
            # Show cached indicator
            if is_model_cached(preset):
                pass  # No extra decoration needed
            self._model_menu_items[preset.id] = item
            self._model_menu.add(item)

        self.menu = [
            self._status_item,
            self._hotkey_item,
            None,
            self._model_menu,
            None,
        ]
        self.quit_button.set_callback(self._on_quit_click)

    def _setup_logging(self) -> None:
        level = self._config["logging"]["level"]
        logging.basicConfig(
            level=getattr(logging, level, logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

    def _set_status(self, text: str) -> None:
        """Update menu bar title and status menu item."""
        self.title = text
        self._status_item.title = text

    def _on_hotkey_press(self) -> None:
        """Called when hotkey is pressed down - start recording."""
        if self._busy:
            return
        logger.info("Hotkey pressed, starting recording")
        self._set_status("Recording...")
        self._recorder.start()

    def _on_hotkey_release(self) -> None:
        """Called when hotkey is released - stop recording and transcribe."""
        if not self._recorder.is_recording:
            return
        logger.info("Hotkey released, stopping recording")
        wav_data = self._recorder.stop()
        if not wav_data:
            self._set_status("VT")
            return

        self._busy = True
        self._set_status("Transcribing...")

        # Run transcription in background to keep UI responsive
        def _do_transcribe():
            try:
                text = self._transcriber.transcribe(wav_data)
                if text and text.strip():
                    type_text(
                        text.strip(),
                        append_newline=self._append_newline,
                        method=self._output_method,
                    )
                    self._set_status("VT")
                else:
                    self._set_status("(empty)")
                    logger.warning("Transcription returned empty text")
            except Exception as e:
                logger.error("Transcription failed: %s", e)
                self._set_status("Error")
            finally:
                self._busy = False

        threading.Thread(target=_do_transcribe, daemon=True).start()

    def _on_model_select(self, sender) -> None:
        """Handle model menu item click."""
        preset_id = sender._preset_id

        # Ignore if already active
        if preset_id == self._current_preset_id:
            return

        # Reject if busy (transcribing or switching)
        if self._busy:
            rumps.notification(
                "VoiceText",
                "Cannot switch model",
                "Please wait for current operation to finish.",
            )
            return

        preset = PRESET_BY_ID[preset_id]
        self._busy = True

        # Disable all model menu callbacks during switch
        for item in self._model_menu_items.values():
            item.set_callback(None)

        old_preset_id = self._current_preset_id
        old_transcriber = self._transcriber

        def _do_switch():
            stop_event = threading.Event()
            monitor_thread = None

            try:
                # Cleanup current model
                self._set_status("Unloading...")
                old_transcriber.cleanup()

                # Check if model is cached; if not, start download monitor
                cached = is_model_cached(preset)
                if not cached:
                    monitor_thread = threading.Thread(
                        target=self._monitor_download_progress,
                        args=(preset, stop_event),
                        daemon=True,
                    )
                    monitor_thread.start()
                else:
                    self._set_status("Loading...")

                # Create and initialize new transcriber
                asr_cfg = self._config["asr"]
                new_transcriber = create_transcriber(
                    backend=preset.backend,
                    use_vad=asr_cfg.get("use_vad", True),
                    use_punc=asr_cfg.get("use_punc", True),
                    language=preset.language or asr_cfg.get("language"),
                    model=preset.model,
                )
                new_transcriber.initialize()

                # Stop download monitor
                stop_event.set()
                if monitor_thread:
                    monitor_thread.join(timeout=2)

                # Success: update state
                self._transcriber = new_transcriber
                self._current_preset_id = preset_id
                self._update_model_checkmark(preset_id)

                # Persist to config
                self._config["asr"]["preset"] = preset_id
                self._config["asr"]["backend"] = preset.backend
                self._config["asr"]["model"] = preset.model
                self._config["asr"]["language"] = preset.language
                save_config(self._config, self._config_path)

                self._set_status("VT")
                rumps.notification(
                    "VoiceText",
                    "Model switched",
                    f"Now using: {preset.display_name}",
                )
                logger.info("Switched to model: %s", preset.display_name)

            except Exception as e:
                stop_event.set()
                if monitor_thread:
                    monitor_thread.join(timeout=2)

                logger.error("Model switch failed: %s", e)
                self._set_status("Error")
                rumps.notification(
                    "VoiceText",
                    "Model switch failed",
                    str(e)[:100],
                )

                # Try to restore previous model
                self._try_restore_previous_model(old_preset_id)

            finally:
                # Re-enable model menu callbacks
                for item in self._model_menu_items.values():
                    item.set_callback(self._on_model_select)
                self._busy = False

        threading.Thread(target=_do_switch, daemon=True).start()

    def _monitor_download_progress(
        self, preset: ModelPreset, stop_event: threading.Event
    ) -> None:
        """Monitor download progress by checking cache directory size."""
        expected_size = self._get_expected_model_size(preset)
        if not expected_size:
            self._set_status("Downloading...")
            stop_event.wait()
            return

        cache_dir = get_model_cache_dir(preset)

        while not stop_event.is_set():
            current_size = _get_dir_size(cache_dir)
            pct = min(int(current_size / expected_size * 100), 99)
            self._set_status(f"DL {pct}%")
            stop_event.wait(1.0)

    def _get_expected_model_size(self, preset: ModelPreset) -> Optional[int]:
        """Get expected total download size for a preset."""
        if preset.backend == "funasr":
            return _FUNASR_APPROX_SIZE

        if preset.backend == "mlx-whisper" and preset.model:
            try:
                from huggingface_hub import model_info

                info = model_info(preset.model)
                total = sum(
                    s.size for s in (info.siblings or []) if s.size is not None
                )
                return total if total > 0 else None
            except Exception:
                logger.debug("Could not get model size for %s", preset.model)
                return None

        return None

    def _update_model_checkmark(self, preset_id: str) -> None:
        """Update checkmark state on model menu items."""
        for pid, item in self._model_menu_items.items():
            item.state = 1 if pid == preset_id else 0

    def _try_restore_previous_model(self, old_preset_id: Optional[str]) -> None:
        """Attempt to restore the previous model after a failed switch."""
        if not old_preset_id or old_preset_id not in PRESET_BY_ID:
            return

        old_preset = PRESET_BY_ID[old_preset_id]
        try:
            logger.info("Restoring previous model: %s", old_preset.display_name)
            self._set_status("Restoring...")
            asr_cfg = self._config["asr"]
            restored = create_transcriber(
                backend=old_preset.backend,
                use_vad=asr_cfg.get("use_vad", True),
                use_punc=asr_cfg.get("use_punc", True),
                language=old_preset.language or asr_cfg.get("language"),
                model=old_preset.model,
            )
            restored.initialize()
            self._transcriber = restored
            self._current_preset_id = old_preset_id
            self._update_model_checkmark(old_preset_id)
            self._set_status("VT")
            logger.info("Previous model restored")
        except Exception as e2:
            logger.error("Failed to restore previous model: %s", e2)
            self._set_status("Error")

    def _on_quit_click(self, _) -> None:
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        rumps.quit_application()

    @staticmethod
    def _ensure_accessibility() -> bool:
        """Check and prompt for accessibility permission if needed."""
        if AXIsProcessTrusted():
            logger.info("Accessibility permission granted")
            return True
        # Only prompt if not yet trusted
        options = {"AXTrustedCheckOptionPrompt": kCFBooleanTrue}
        AXIsProcessTrustedWithOptions(options)
        logger.warning("Accessibility permission not granted, prompting user")
        return False

    def run(self, **kwargs) -> None:
        """Initialize models and start the app."""
        self._ensure_accessibility()

        # Load models in background
        def _init_models():
            try:
                self._set_status("Loading...")
                self._transcriber.initialize()
                self._set_status("VT")
                logger.info("Models loaded, app ready")
            except Exception as e:
                logger.error("Model initialization failed: %s", e)
                self._set_status("Error")

        threading.Thread(target=_init_models, daemon=True).start()

        # Start hotkey listener
        hotkey_name = self._config["hotkey"]
        self._hotkey_listener = HoldHotkeyListener(
            key_name=hotkey_name,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        self._hotkey_listener.start()

        super().run(**kwargs)


def _get_dir_size(path) -> int:
    """Calculate total size of all files in a directory."""
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        return 0
    total = 0
    try:
        for f in target.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


def main() -> None:
    """Entry point."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = VoiceTextApp(config_path=config_path)  # None uses default path
    app.run()


if __name__ == "__main__":
    main()
