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
        html: str,
        width: int = 900,
        height: int = 700,
        resizable: bool = True,
        allowed_read_paths: Optional[List[str]] = None,
    ):
        """Create and return a new WebView panel.

        The panel is not shown until ``panel.show()`` is called.

        Args:
            title: Window title.
            html: Initial HTML content.
            width: Default width in pixels.
            height: Default height in pixels.
            resizable: Whether the window can be resized.
            allowed_read_paths: Directories the WebView can read via file://.

        Returns:
            A :class:`WebViewPanel` instance.
        """
        from wenzi.scripting.ui.webview_panel import WebViewPanel

        return WebViewPanel(
            title=title,
            html=html,
            width=width,
            height=height,
            resizable=resizable,
            allowed_read_paths=allowed_read_paths,
        )
