"""vt.notify — macOS notification API."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify(title: str, message: str = "", sound: str | None = "default") -> None:
    """Send a macOS user notification.

    Args:
        sound: ``"default"`` for system sound, ``None`` for silent,
            or a macOS sound name (e.g. ``"Glass"``, ``"Ping"``).
    """
    from wenzi.statusbar import send_notification

    send_notification(title, "", message, sound=sound)
    logger.debug("Notification sent: %s", title)
