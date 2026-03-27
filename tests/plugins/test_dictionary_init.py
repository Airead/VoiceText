"""Tests for dictionary plugin init and language detection."""


class TestDetectDirection:
    def test_english_defaults_to_en2zh(self):
        from dictionary import _detect_direction

        assert _detect_direction("hello") == "en2zh-CHS"

    def test_chinese_returns_zh2en(self):
        from dictionary import _detect_direction

        assert _detect_direction("你好") == "zh2en"

    def test_mixed_returns_zh2en(self):
        from dictionary import _detect_direction

        assert _detect_direction("hello你好") == "zh2en"

    def test_empty_defaults_to_en2zh(self):
        from dictionary import _detect_direction

        assert _detect_direction("") == "en2zh-CHS"

    def test_numbers_defaults_to_en2zh(self):
        from dictionary import _detect_direction

        assert _detect_direction("123") == "en2zh-CHS"
