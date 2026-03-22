"""HTML template loader for WKWebView-based UI panels."""

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent


def load_template(name: str, **replacements: str) -> str:
    """Load an HTML template and replace __KEY__ placeholders.

    Args:
        name: Template filename (e.g. "settings_window_web.html").
        **replacements: KEY=value pairs; each replaces __KEY__ in the template.

    Returns:
        The processed HTML string.
    """
    html = (_TEMPLATES_DIR / name).read_text("utf-8")
    for key, value in replacements.items():
        html = html.replace(f"__{key}__", value)
    return html
