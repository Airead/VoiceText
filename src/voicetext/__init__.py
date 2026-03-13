"""VoiceText - macOS menubar speech-to-text app."""

import sys

if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle — use the real version
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("voicetext")
    except PackageNotFoundError:
        __version__ = "0.0.0-dev"
else:
    # Running via uv run / python — always dev
    __version__ = "dev"
