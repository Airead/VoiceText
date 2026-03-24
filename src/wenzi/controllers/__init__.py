"""Controllers subpackage — business logic controllers for the app."""

import logging

_logger = logging.getLogger(__name__)


def fire_scripting_event(app, event_name: str, **kwargs) -> None:
    """Fire a scripting event if the script engine is available."""
    engine = getattr(app, "_script_engine", None)
    if engine is None:
        return
    try:
        engine.wz._registry.fire_event(event_name, **kwargs)
    except Exception:
        _logger.debug("Failed to fire scripting event %s", event_name)


from .config_controller import ConfigController
from .enhance_controller import EnhanceCacheEntry, EnhanceController
from .enhance_mode_controller import EnhanceModeController
from .menu_builder import MenuBuilder
from .model_controller import ModelController, migrate_asr_config
from .preview_controller import PreviewController
from .recording_controller import RecordingController
from .recording_flow import Action, RecordingFlow
from .settings_controller import SettingsController
from .update_controller import UpdateController

__all__ = [
    "ConfigController",
    "EnhanceCacheEntry",
    "EnhanceController",
    "EnhanceModeController",
    "MenuBuilder",
    "ModelController",
    "PreviewController",
    "Action",
    "RecordingController",
    "RecordingFlow",
    "SettingsController",
    "UpdateController",
    "migrate_asr_config",
]
