"""Generate two-letter avatar icons for project names."""

from __future__ import annotations

import base64
import re
from functools import lru_cache
from html import escape

COLORS = [
    "#E05252", "#E07B39", "#D4A843", "#5AAE5A", "#43A5A5", "#4A90D9",
    "#6B7FD9", "#8B6FC0", "#C06BAA", "#7C8A6E", "#9E7B5B", "#5B8A9E",
]


def _djb2(s: str) -> int:
    h = 5381
    for ch in s:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return h


def _get_initials(name: str) -> str:
    """Extract two-letter initials from a project name.

    Rules:
    - Hyphen/underscore/space separated: first letter of first two parts
      e.g. "claude-code" -> "Cc", "api-server" -> "As"
    - CamelCase: first letter + next capital
      e.g. "VoiceText" -> "Vt", "WenZi" -> "Wz"
    - Fallback: first two characters
      e.g. "dotfiles" -> "Do", "blog" -> "Bl"
    - Single char or empty: return what's available
    """
    if not name:
        return "?"

    # Try separator-based splitting
    parts = re.split(r"[-_\s]+", name)
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0][0].upper() + parts[1][0].lower()

    # Try camelCase detection
    match = re.search(r"([a-zA-Z]).*?([A-Z])", name)
    if match:
        return match.group(1).upper() + match.group(2).lower()

    # Fallback: first two characters
    if len(name) >= 2:
        return name[0].upper() + name[1].lower()

    return name[0].upper()


@lru_cache(maxsize=128)
def generate(name: str, size: int = 32) -> str:
    """Generate a data URI for a two-letter avatar SVG from a project name."""
    h = _djb2(name)
    color = COLORS[h % len(COLORS)]
    initials = escape(_get_initials(name))

    rx = size * 0.1875
    font_size = size * 0.42
    y_pos = size * 0.62

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f'<rect width="{size}" height="{size}" rx="{rx}" fill="{color}"/>'
        f'<text x="{size / 2}" y="{y_pos}" text-anchor="middle" fill="white" '
        f'font-family="-apple-system,BlinkMacSystemFont,sans-serif" '
        f'font-weight="600" font-size="{font_size}">{initials}</text>'
        f"</svg>"
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"
