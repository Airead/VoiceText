"""Tests for the browser bookmark data source."""

import json
import os

from voicetext.scripting.sources.bookmark_source import (
    Bookmark,
    BookmarkSource,
    _collect_chromium_nodes,
    _collect_safari_nodes,
    _firefox_folder_path,
    _read_chromium_bookmarks,
)


class TestBookmark:
    def test_domain(self):
        bm = Bookmark(name="GitHub", url="https://github.com/user/repo")
        assert bm.domain() == "github.com"

    def test_domain_no_scheme(self):
        bm = Bookmark(name="Test", url="not-a-url")
        assert bm.domain() == ""

    def test_domain_empty(self):
        bm = Bookmark(name="Test", url="")
        assert bm.domain() == ""


class TestChromiumParser:
    def _make_bookmarks_json(self, tmp_path, browser_dir, bookmarks):
        """Write a Chromium Bookmarks JSON file."""
        profile_dir = os.path.join(tmp_path, browser_dir, "Default")
        os.makedirs(profile_dir, exist_ok=True)
        path = os.path.join(profile_dir, "Bookmarks")
        with open(path, "w") as f:
            json.dump(bookmarks, f)
        return str(tmp_path / browser_dir)

    def test_read_simple_bookmarks(self, tmp_path):
        data = {
            "roots": {
                "bookmark_bar": {
                    "type": "folder",
                    "name": "Bookmark Bar",
                    "children": [
                        {
                            "type": "url",
                            "name": "GitHub",
                            "url": "https://github.com",
                        },
                        {
                            "type": "url",
                            "name": "Google",
                            "url": "https://google.com",
                        },
                    ],
                },
                "other": {"type": "folder", "name": "Other", "children": []},
                "synced": {"type": "folder", "name": "Synced", "children": []},
            }
        }
        base = self._make_bookmarks_json(tmp_path, "Chrome", data)
        result = _read_chromium_bookmarks(base, "chrome")
        assert len(result) == 2
        assert result[0].name == "GitHub"
        assert result[0].url == "https://github.com"
        assert result[0].browser == "chrome"
        assert result[0].profile == "Default"

    def test_nested_folders(self, tmp_path):
        data = {
            "roots": {
                "bookmark_bar": {
                    "type": "folder",
                    "name": "Bookmark Bar",
                    "children": [
                        {
                            "type": "folder",
                            "name": "Dev",
                            "children": [
                                {
                                    "type": "url",
                                    "name": "Stack Overflow",
                                    "url": "https://stackoverflow.com",
                                },
                            ],
                        },
                    ],
                },
                "other": {"type": "folder", "name": "Other", "children": []},
            }
        }
        base = self._make_bookmarks_json(tmp_path, "Chrome", data)
        result = _read_chromium_bookmarks(base, "chrome")
        assert len(result) == 1
        assert "Dev" in result[0].folder_path

    def test_deduplication(self, tmp_path):
        data = {
            "roots": {
                "bookmark_bar": {
                    "type": "folder",
                    "name": "Bookmark Bar",
                    "children": [
                        {"type": "url", "name": "A", "url": "https://a.com"},
                        {"type": "url", "name": "A dup", "url": "https://a.com"},
                    ],
                },
            }
        }
        base = self._make_bookmarks_json(tmp_path, "Chrome", data)
        result = _read_chromium_bookmarks(base, "chrome")
        assert len(result) == 1

    def test_nonexistent_dir(self):
        result = _read_chromium_bookmarks("/nonexistent/path", "chrome")
        assert result == []

    def test_collect_nodes(self):
        node = {
            "type": "folder",
            "name": "Root",
            "children": [
                {"type": "url", "name": "A", "url": "https://a.com"},
                {
                    "type": "folder",
                    "name": "Sub",
                    "children": [
                        {"type": "url", "name": "B", "url": "https://b.com"},
                    ],
                },
            ],
        }
        out: list = []
        seen: set = set()
        _collect_chromium_nodes(node, "", "chrome", "Default", out, seen)
        assert len(out) == 2
        assert out[0].name == "A"
        assert out[1].name == "B"
        assert "Sub" in out[1].folder_path


class TestSafariParser:
    def test_collect_nodes(self):
        data = {
            "WebBookmarkType": "WebBookmarkTypeList",
            "Title": "",
            "Children": [
                {
                    "WebBookmarkType": "WebBookmarkTypeList",
                    "Title": "BookmarksBar",
                    "Children": [
                        {
                            "WebBookmarkType": "WebBookmarkTypeLeaf",
                            "URLString": "https://apple.com",
                            "URIDictionary": {"title": "Apple"},
                        },
                    ],
                },
                {
                    "WebBookmarkType": "WebBookmarkTypeList",
                    "Title": "com.apple.ReadingList",
                    "Children": [
                        {
                            "WebBookmarkType": "WebBookmarkTypeLeaf",
                            "URLString": "https://reading.com",
                            "URIDictionary": {"title": "Reading"},
                        },
                    ],
                },
            ],
        }
        out: list = []
        _collect_safari_nodes(data, "", out)
        # Reading list should be skipped
        assert len(out) == 1
        assert out[0].name == "Apple"
        assert out[0].url == "https://apple.com"
        assert out[0].browser == "safari"

    def test_leaf_without_title_uses_url(self):
        data = {
            "WebBookmarkType": "WebBookmarkTypeLeaf",
            "URLString": "https://example.com",
            "URIDictionary": {},
        }
        out: list = []
        _collect_safari_nodes(data, "", out)
        assert len(out) == 1
        assert out[0].name == "https://example.com"


class TestFirefoxFolderPath:
    def test_simple_hierarchy(self):
        folders = {
            1: ("root________", 0),
            2: ("Bookmarks Menu", 1),
            3: ("Dev", 2),
        }
        path = _firefox_folder_path(3, folders)
        assert path == "Bookmarks Menu > Dev"

    def test_no_parent(self):
        folders = {}
        path = _firefox_folder_path(999, folders)
        assert path == ""

    def test_circular_reference(self):
        """Should not infinite loop on circular references."""
        folders = {
            1: ("A", 2),
            2: ("B", 1),
        }
        path = _firefox_folder_path(1, folders)
        assert "A" in path or "B" in path


class TestBookmarkSource:
    def test_empty_query_returns_items(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("GitHub", "https://github.com", browser="chrome"),
            Bookmark("Google", "https://google.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("")
        assert len(results) == 2

    def test_search_by_name(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("GitHub", "https://github.com", browser="chrome"),
            Bookmark("Google", "https://google.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("git")
        assert len(results) == 1
        assert results[0].title == "GitHub"

    def test_search_by_domain(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("My Page", "https://example.com/page", browser="chrome"),
            Bookmark("Other", "https://other.org", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("example")
        assert len(results) == 1
        assert results[0].title == "My Page"

    def test_search_by_folder(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("Page", "https://a.com", folder_path="Dev > Python", browser="chrome"),
            Bookmark("Other", "https://b.com", folder_path="News", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("python")
        assert len(results) == 1

    def test_item_has_action(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("Test", "https://test.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("test")
        assert results[0].action is not None

    def test_item_has_item_id(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("Test", "https://test.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("test")
        assert results[0].item_id.startswith("bm:")

    def test_as_chooser_source(self):
        source = BookmarkSource()
        cs = source.as_chooser_source()
        assert cs.name == "bookmarks"
        assert cs.prefix == "bm"
        assert cs.priority == 5
        assert cs.search is not None

    def test_subtitle_with_folder(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark(
                "GitHub", "https://github.com",
                folder_path="Dev", browser="chrome", profile="Default",
            ),
        ]
        source._last_refresh = float("inf")
        results = source.search("github")
        assert "Dev" in results[0].subtitle
        assert "Chrome" in results[0].subtitle

    def test_multi_term_and_matching(self):
        """Multiple terms should all match (AND logic)."""
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("AWS Console", "https://aws.amazon.com", browser="safari"),
            Bookmark("aws secrets manager", "https://aws.amazon.com/sm",
                     folder_path="Bookmarks Bar > f2pool", browser="chrome",
                     profile="Profile 1"),
            Bookmark("Google Docs", "https://docs.google.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")

        # Both "sa" and "aws" must match
        results = source.search("sa aws")
        # "sa" matches "safari" (browser label) for AWS Console
        # "aws" matches name for both AWS items
        titles = [r.title for r in results]
        assert "AWS Console" in titles
        assert "Google Docs" not in titles

    def test_multi_term_no_match_if_one_missing(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("GitHub", "https://github.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("git xyz")
        assert len(results) == 0

    def test_search_by_browser_label(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark("Apple", "https://apple.com", browser="safari"),
            Bookmark("Google", "https://google.com", browser="chrome"),
        ]
        source._last_refresh = float("inf")
        results = source.search("safari")
        assert len(results) == 1
        assert results[0].title == "Apple"

    def test_max_results_capped(self):
        source = BookmarkSource()
        source._bookmarks = [
            Bookmark(f"Item {i}", f"https://example{i}.com", browser="chrome")
            for i in range(100)
        ]
        source._last_refresh = float("inf")
        results = source.search("example")
        assert len(results) <= 50
