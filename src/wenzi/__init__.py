"""WenZi (闻字) - macOS menubar speech-to-text app."""

import os
import sys

if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle — use the real version
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("wenzi")
    except PackageNotFoundError:
        __version__ = "0.0.0-dev"
else:
    # Running via uv run / python — always dev
    __version__ = "dev"


def get_version() -> str:
    """Return the current app version, honoring WENZI_DEV_VERSION env var."""
    return os.environ.get("WENZI_DEV_VERSION") or __version__


def is_version_compatible(min_version: str) -> bool:
    """Return True if the running WenZi version meets *min_version*.

    Returns True for ``"dev"`` builds and unparseable versions.
    """
    current = get_version()
    if current == "dev":
        return True
    try:
        cur = tuple(int(x) for x in current.split("."))
        req = tuple(int(x) for x in min_version.split("."))
    except (ValueError, AttributeError):
        return True
    return cur >= req
