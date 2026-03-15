"""Chooser data sources and core data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class ChooserItem:
    """A single item in the chooser result list."""

    title: str
    subtitle: str = ""
    icon: str = ""  # data: URI (base64 PNG) or empty
    action: Optional[Callable] = field(default=None, repr=False)
    secondary_action: Optional[Callable] = field(default=None, repr=False)  # Cmd+Enter
    reveal_path: Optional[str] = None  # For Cmd+Enter (reveal in Finder)


@dataclass
class ChooserSource:
    """A data source that provides items to the chooser.

    Sources with a prefix (e.g. ">cb") are only searched when the query
    starts with that prefix. Sources without a prefix participate in
    every search.
    """

    name: str
    prefix: Optional[str] = None
    search: Callable[[str], List[ChooserItem]] = field(default=None, repr=False)
    priority: int = 0  # Higher values appear first
