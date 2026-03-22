"""Tests for cc-sessions identicon generation."""

import base64
import xml.etree.ElementTree as ET

from cc_sessions.identicon import (
    COLORS,
    generate,
    _djb2,
    _get_initials,
)


class TestDjb2:
    def test_deterministic(self):
        assert _djb2("VoiceText") == _djb2("VoiceText")

    def test_different_inputs_different_hashes(self):
        assert _djb2("VoiceText") != _djb2("claude-code")

    def test_empty_string(self):
        assert _djb2("") == 5381

    def test_unicode(self):
        h = _djb2("项目名")
        assert isinstance(h, int)
        assert h > 0


class TestGetInitials:
    def test_hyphen_separated(self):
        assert _get_initials("claude-code") == "Cc"
        assert _get_initials("api-server") == "As"
        assert _get_initials("ml-pipeline") == "Mp"

    def test_underscore_separated(self):
        assert _get_initials("my_project") == "Mp"

    def test_camel_case(self):
        assert _get_initials("VoiceText") == "Vt"
        assert _get_initials("WenZi") == "Wz"

    def test_plain_word(self):
        assert _get_initials("dotfiles") == "Do"
        assert _get_initials("blog") == "Bl"

    def test_single_char(self):
        assert _get_initials("x") == "X"

    def test_empty_string(self):
        assert _get_initials("") == "?"

    def test_multi_segment(self):
        assert _get_initials("infra-terraform") == "It"
        assert _get_initials("react-dashboard") == "Rd"

    def test_first_upper_second_lower(self):
        """First letter should be uppercase, second lowercase."""
        for name in ["VoiceText", "claude-code", "dotfiles", "WenZi"]:
            initials = _get_initials(name)
            assert initials[0].isupper(), f"{name} -> {initials}: first should be upper"
            if len(initials) > 1:
                assert initials[1].islower(), f"{name} -> {initials}: second should be lower"


class TestGenerate:
    def test_deterministic(self):
        assert generate("VoiceText") == generate("VoiceText")

    def test_different_projects_different_icons(self):
        names = ["VoiceText", "claude-code", "WenZi", "dotfiles",
                 "react-app", "api-server", "blog", "infra"]
        results = [generate(n) for n in names]
        assert len(set(results)) >= 6

    def test_data_uri_format(self):
        uri = generate("test-project")
        assert uri.startswith("data:image/svg+xml;base64,")

    def test_valid_svg(self):
        uri = generate("test-project")
        b64 = uri.split(",", 1)[1]
        svg_bytes = base64.b64decode(b64)
        root = ET.fromstring(svg_bytes)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"

    def test_svg_contains_text_element(self):
        uri = generate("VoiceText")
        b64 = uri.split(",", 1)[1]
        svg_str = base64.b64decode(b64).decode()
        assert "<text " in svg_str
        assert "Vt" in svg_str

    def test_empty_name(self):
        uri = generate("")
        assert uri.startswith("data:image/svg+xml;base64,")
        b64 = uri.split(",", 1)[1]
        svg_str = base64.b64decode(b64).decode()
        assert "?" in svg_str

    def test_long_name(self):
        uri = generate("a" * 1000)
        assert uri.startswith("data:image/svg+xml;base64,")

    def test_color_in_palette(self):
        for name in ["VoiceText", "claude-code", "WenZi"]:
            h = _djb2(name)
            color = COLORS[h % len(COLORS)]
            uri = generate(name)
            b64 = uri.split(",", 1)[1]
            svg_str = base64.b64decode(b64).decode()
            assert color in svg_str

    def test_initials_in_svg(self):
        """Verify the correct initials appear in the generated SVG."""
        cases = [
            ("claude-code", "Cc"),
            ("VoiceText", "Vt"),
            ("dotfiles", "Do"),
        ]
        for name, expected in cases:
            uri = generate(name)
            b64 = uri.split(",", 1)[1]
            svg_str = base64.b64decode(b64).decode()
            assert expected in svg_str, f"{name} should have '{expected}' in SVG"
