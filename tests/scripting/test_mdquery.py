"""Tests for the MDQuery ctypes wrapper."""

from __future__ import annotations

from unittest.mock import patch


class TestEscapeQuery:
    def test_no_special_chars(self):
        from wenzi.scripting.sources._mdquery import _escape_query

        assert _escape_query("readme") == "readme"

    def test_escape_backslash(self):
        from wenzi.scripting.sources._mdquery import _escape_query

        assert _escape_query("a\\b") == "a\\\\b"

    def test_escape_double_quote(self):
        from wenzi.scripting.sources._mdquery import _escape_query

        assert _escape_query('a"b') == 'a\\"b'

    def test_escape_asterisk(self):
        from wenzi.scripting.sources._mdquery import _escape_query

        assert _escape_query("a*b") == "a\\*b"

    def test_escape_multiple_specials(self):
        from wenzi.scripting.sources._mdquery import _escape_query

        assert _escape_query('\\*"') == '\\\\\\*\\"'


class TestBuildQueryString:
    def test_simple(self):
        from wenzi.scripting.sources._mdquery import _build_query_string

        result = _build_query_string("readme")
        assert result == 'kMDItemFSName == "*readme*"cd'

    def test_with_special_chars(self):
        from wenzi.scripting.sources._mdquery import _build_query_string

        result = _build_query_string('te"st')
        assert result == 'kMDItemFSName == "*te\\"st*"cd'

    def test_content_type_folder(self):
        from wenzi.scripting.sources._mdquery import _build_query_string

        result = _build_query_string("docs", content_type="public.folder")
        assert 'kMDItemContentType == "public.folder"' in result
        assert 'kMDItemFSName == "*docs*"cd' in result

    def test_content_type_exclude_folder(self):
        from wenzi.scripting.sources._mdquery import _build_query_string

        result = _build_query_string("readme", content_type="!public.folder")
        assert 'kMDItemContentType != "public.folder"' in result
        assert 'kMDItemFSName == "*readme*"cd' in result

    def test_content_type_none(self):
        from wenzi.scripting.sources._mdquery import _build_query_string

        result = _build_query_string("file")
        assert "kMDItemContentType" not in result


class TestMdquerySearch:
    """Test mdquery_search with mocked ctypes calls."""

    def test_empty_query_returns_empty(self):
        from wenzi.scripting.sources._mdquery import mdquery_search

        assert mdquery_search("") == []
        assert mdquery_search("   ") == []

    @patch("wenzi.scripting.sources._mdquery._cfstr")
    @patch("wenzi.scripting.sources._mdquery._cs")
    @patch("wenzi.scripting.sources._mdquery._cf")
    def test_mdquery_create_null_returns_empty(self, mock_cf, mock_cs, mock_cfstr):
        from wenzi.scripting.sources._mdquery import mdquery_search

        mock_cfstr.return_value = 12345  # fake CFStringRef
        mock_cs.MDQueryCreate.return_value = None  # NULL

        result = mdquery_search("test")
        assert result == []
        mock_cf.CFRelease.assert_called_with(12345)

    @patch("wenzi.scripting.sources._mdquery._cfstr")
    @patch("wenzi.scripting.sources._mdquery._cs")
    @patch("wenzi.scripting.sources._mdquery._cf")
    def test_mdquery_execute_fails_returns_empty(self, mock_cf, mock_cs, mock_cfstr):
        from wenzi.scripting.sources._mdquery import mdquery_search

        mock_cfstr.return_value = 12345
        mock_cs.MDQueryCreate.return_value = 99999  # fake query ref
        mock_cs.MDQueryExecute.return_value = False

        result = mdquery_search("test")
        assert result == []
        # Query should be stopped and released
        mock_cs.MDQueryStop.assert_called_with(99999)
        mock_cf.CFRelease.assert_any_call(99999)

    @patch("wenzi.scripting.sources._mdquery._cfstr_to_py")
    @patch("wenzi.scripting.sources._mdquery._cfstr")
    @patch("wenzi.scripting.sources._mdquery._cs")
    @patch("wenzi.scripting.sources._mdquery._cf")
    def test_successful_search(self, mock_cf, mock_cs, mock_cfstr, mock_cfstr_to_py):
        from wenzi.scripting.sources._mdquery import mdquery_search

        mock_cfstr.return_value = 12345
        query_ref = 99999
        mock_cs.MDQueryCreate.return_value = query_ref
        mock_cs.MDQueryExecute.return_value = True
        mock_cs.MDQueryGetResultCount.return_value = 2
        mock_cs.MDQueryGetResultAtIndex.side_effect = [1001, 1002]
        mock_cs.MDItemCopyAttribute.side_effect = [2001, 2002]
        mock_cfstr_to_py.side_effect = ["/path/a.txt", "/path/b.txt"]

        result = mdquery_search("test", max_results=30)

        assert result == ["/path/a.txt", "/path/b.txt"]
        mock_cs.MDQuerySetMaxCount.assert_called_with(query_ref, 30)
        # Attribute refs should be released
        mock_cf.CFRelease.assert_any_call(2001)
        mock_cf.CFRelease.assert_any_call(2002)

    @patch("wenzi.scripting.sources._mdquery._cfstr_to_py")
    @patch("wenzi.scripting.sources._mdquery._cfstr")
    @patch("wenzi.scripting.sources._mdquery._cs")
    @patch("wenzi.scripting.sources._mdquery._cf")
    def test_null_item_skipped(self, mock_cf, mock_cs, mock_cfstr, mock_cfstr_to_py):
        from wenzi.scripting.sources._mdquery import mdquery_search

        mock_cfstr.return_value = 12345
        mock_cs.MDQueryCreate.return_value = 99999
        mock_cs.MDQueryExecute.return_value = True
        mock_cs.MDQueryGetResultCount.return_value = 2
        mock_cs.MDQueryGetResultAtIndex.side_effect = [None, 1002]
        mock_cs.MDItemCopyAttribute.return_value = 2002
        mock_cfstr_to_py.return_value = "/path/b.txt"

        result = mdquery_search("test")
        assert result == ["/path/b.txt"]

    @patch("wenzi.scripting.sources._mdquery._cfstr_to_py")
    @patch("wenzi.scripting.sources._mdquery._cs")
    @patch("wenzi.scripting.sources._mdquery._cf")
    @patch("wenzi.scripting.sources._mdquery._cfstr")
    def test_null_attribute_skipped(self, mock_cfstr, mock_cf, mock_cs, mock_cfstr_to_py):
        from wenzi.scripting.sources._mdquery import mdquery_search

        mock_cfstr.return_value = 12345
        mock_cs.MDQueryCreate.return_value = 99999
        mock_cs.MDQueryExecute.return_value = True
        mock_cs.MDQueryGetResultCount.return_value = 1
        mock_cs.MDQueryGetResultAtIndex.return_value = 1001
        mock_cs.MDItemCopyAttribute.return_value = None  # NULL attr

        result = mdquery_search("test")
        assert result == []

    @patch("wenzi.scripting.sources._mdquery._cfstr")
    @patch("wenzi.scripting.sources._mdquery._cs")
    @patch("wenzi.scripting.sources._mdquery._cf")
    def test_cleanup_on_success(self, mock_cf, mock_cs, mock_cfstr):
        from wenzi.scripting.sources._mdquery import mdquery_search

        mock_cfstr.return_value = 12345
        query_ref = 99999
        mock_cs.MDQueryCreate.return_value = query_ref
        mock_cs.MDQueryExecute.return_value = True
        mock_cs.MDQueryGetResultCount.return_value = 0

        mdquery_search("test")

        mock_cs.MDQueryStop.assert_called_with(query_ref)
        mock_cf.CFRelease.assert_any_call(query_ref)
        mock_cf.CFRelease.assert_any_call(12345)  # qs_ref
