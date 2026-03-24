"""wz.ui — UI API for user scripts."""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class UIAPI:
    """API for creating UI panels, exposed as wz.ui."""

    def webview_panel(
        self,
        title: str,
        html: str = "",
        html_file: str = "",
        width: int = 900,
        height: int = 700,
        resizable: bool = True,
        allowed_read_paths: Optional[List[str]] = None,
        titlebar_hidden: bool = False,
        floating: bool = True,
    ):
        """Create and return a new WebView panel.

        The panel is not shown until ``panel.show()`` is called.

        Provide either *html* (a string) or *html_file* (a path to an HTML
        file on disk).  When *html_file* is used, the file is loaded directly
        via ``loadFileURL`` — no temp file is created, and the file's
        directory is automatically granted read access.

        Args:
            title: Window title.
            html: Initial HTML content string.
            html_file: Path to an HTML file to load directly.
            width: Default width in pixels.
            height: Default height in pixels.
            resizable: Whether the window can be resized.
            allowed_read_paths: Directories the WebView can read via file://.
            titlebar_hidden: Hide the native title bar and traffic light
                buttons so the web content fills the entire window.
            floating: Keep the panel above all other windows. Default True.

        Returns:
            A :class:`WebViewPanel` instance.
        """
        from wenzi.scripting.ui.webview_panel import WebViewPanel

        return WebViewPanel(
            title=title,
            html=html,
            html_file=html_file,
            width=width,
            height=height,
            resizable=resizable,
            allowed_read_paths=allowed_read_paths,
            titlebar_hidden=titlebar_hidden,
            floating=floating,
        )
