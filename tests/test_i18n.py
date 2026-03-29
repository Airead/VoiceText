"""Tests for the i18n module."""

import json

import pytest


@pytest.fixture(autouse=True)
def _reset_i18n():
    """Reset i18n state between tests."""
    from wenzi import i18n

    orig_locale = i18n._current_locale
    orig_strings = i18n._strings.copy()
    orig_fallback = i18n._fallback_strings.copy()
    orig_dir = i18n._active_locales_dir
    yield
    i18n._current_locale = orig_locale
    i18n._strings = orig_strings
    i18n._fallback_strings = orig_fallback
    i18n._active_locales_dir = orig_dir


@pytest.fixture()
def locale_dir(tmp_path):
    """Create temporary locale files for testing."""
    en = {
        "app.name": "WenZi",
        "menu.quit": "Quit",
        "alert.update.title": "Update to v{version}",
        "only.in.en": "English only",
    }
    zh = {
        "app.name": "\u95fb\u5b57",
        "menu.quit": "\u9000\u51fa",
        "alert.update.title": "\u66f4\u65b0\u5230 v{version}",
    }
    (tmp_path / "en.json").write_text(json.dumps(en), encoding="utf-8")
    (tmp_path / "zh.json").write_text(json.dumps(zh), encoding="utf-8")
    return tmp_path


class TestTranslationLookup:
    def test_t_returns_english_value(self, locale_dir):
        from wenzi.i18n import init_i18n, t

        init_i18n(locale="en", locales_dir=locale_dir)
        assert t("app.name") == "WenZi"

    def test_t_returns_chinese_value(self, locale_dir):
        from wenzi.i18n import init_i18n, t

        init_i18n(locale="zh", locales_dir=locale_dir)
        assert t("app.name") == "\u95fb\u5b57"

    def test_t_fallback_to_english(self, locale_dir):
        from wenzi.i18n import init_i18n, t

        init_i18n(locale="zh", locales_dir=locale_dir)
        assert t("only.in.en") == "English only"

    def test_t_missing_key_returns_key(self, locale_dir):
        from wenzi.i18n import init_i18n, t

        init_i18n(locale="en", locales_dir=locale_dir)
        assert t("nonexistent.key") == "nonexistent.key"

    def test_t_interpolation(self, locale_dir):
        from wenzi.i18n import init_i18n, t

        init_i18n(locale="en", locales_dir=locale_dir)
        assert t("alert.update.title", version="1.2") == "Update to v1.2"

    def test_t_interpolation_missing_param_returns_template(self, locale_dir):
        from wenzi.i18n import init_i18n, t

        init_i18n(locale="en", locales_dir=locale_dir)
        result = t("alert.update.title")
        assert "{version}" in result


class TestLocaleManagement:
    def test_init_with_auto_detects_system(self, locale_dir, monkeypatch):
        from wenzi.i18n import get_locale, init_i18n

        mock_nslocale = type(
            "MockNSLocale",
            (),
            {"preferredLanguages": staticmethod(lambda: ["zh-Hans-CN", "en-US"])},
        )
        monkeypatch.setattr("wenzi.i18n.NSLocale", mock_nslocale)
        init_i18n(locale="auto", locales_dir=locale_dir)
        assert get_locale() == "zh"

    def test_init_with_auto_defaults_to_en(self, locale_dir, monkeypatch):
        from wenzi.i18n import get_locale, init_i18n

        mock_nslocale = type(
            "MockNSLocale",
            (),
            {"preferredLanguages": staticmethod(lambda: ["en-US"])},
        )
        monkeypatch.setattr("wenzi.i18n.NSLocale", mock_nslocale)
        init_i18n(locale="auto", locales_dir=locale_dir)
        assert get_locale() == "en"

    def test_init_with_none_treated_as_auto(self, locale_dir, monkeypatch):
        from wenzi.i18n import get_locale, init_i18n

        mock_nslocale = type(
            "MockNSLocale",
            (),
            {"preferredLanguages": staticmethod(lambda: ["ja-JP"])},
        )
        monkeypatch.setattr("wenzi.i18n.NSLocale", mock_nslocale)
        init_i18n(locale=None, locales_dir=locale_dir)
        assert get_locale() == "en"


class TestGetTranslationsForPrefix:
    def test_returns_matching_keys_with_prefix_stripped(self, locale_dir):
        from wenzi.i18n import get_translations_for_prefix, init_i18n

        init_i18n(locale="en", locales_dir=locale_dir)
        result = get_translations_for_prefix("alert.update.")
        assert result == {"title": "Update to v{version}"}

    def test_returns_empty_dict_for_no_match(self, locale_dir):
        from wenzi.i18n import get_translations_for_prefix, init_i18n

        init_i18n(locale="en", locales_dir=locale_dir)
        result = get_translations_for_prefix("nonexistent.")
        assert result == {}


class TestBuildDocUrl:
    def test_english_locale(self, locale_dir):
        from wenzi.i18n import build_doc_url, init_i18n

        init_i18n(locale="en", locales_dir=locale_dir)
        assert build_doc_url("user-guide.html#hotkeys") == (
            "https://airead.github.io/WenZi/docs/user-guide.html#hotkeys"
        )

    def test_chinese_locale(self, locale_dir):
        from wenzi.i18n import build_doc_url, init_i18n

        init_i18n(locale="zh", locales_dir=locale_dir)
        assert build_doc_url("enhance-modes.html#how-it-works") == (
            "https://airead.github.io/WenZi/zh/docs/enhance-modes.html#how-it-works"
        )
