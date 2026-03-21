"""Tests for plugin metadata loading."""

from wenzi.scripting.plugin_meta import PluginMeta, load_plugin_meta


class TestPluginMeta:
    """Test PluginMeta dataclass defaults."""

    def test_defaults(self):
        meta = PluginMeta(name="test")
        assert meta.name == "test"
        assert meta.description == ""
        assert meta.version == ""
        assert meta.author == ""
        assert meta.url == ""
        assert meta.icon == ""
        assert meta.min_wenzi_version == ""


class TestLoadPluginMeta:
    """Test load_plugin_meta function."""

    def test_full_toml(self, tmp_path):
        """All fields are read from plugin.toml."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text(
            '[plugin]\n'
            'name = "My Plugin"\n'
            'description = "A test plugin"\n'
            'version = "1.2.3"\n'
            'author = "Alice"\n'
            'url = "https://example.com"\n'
            'icon = "icon.png"\n'
            'min_wenzi_version = "0.2.0"\n'
        )
        meta = load_plugin_meta(str(plugin_dir))
        assert meta.name == "My Plugin"
        assert meta.description == "A test plugin"
        assert meta.version == "1.2.3"
        assert meta.author == "Alice"
        assert meta.url == "https://example.com"
        assert meta.icon == "icon.png"
        assert meta.min_wenzi_version == "0.2.0"

    def test_missing_toml_fallback(self, tmp_path):
        """Missing plugin.toml falls back to directory name."""
        plugin_dir = tmp_path / "fallback_plugin"
        plugin_dir.mkdir()
        meta = load_plugin_meta(str(plugin_dir))
        assert meta.name == "fallback_plugin"
        assert meta.description == ""
        assert meta.version == ""

    def test_partial_fields(self, tmp_path):
        """Missing fields in TOML get default values."""
        plugin_dir = tmp_path / "partial"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text(
            '[plugin]\nname = "Partial"\n'
        )
        meta = load_plugin_meta(str(plugin_dir))
        assert meta.name == "Partial"
        assert meta.version == ""
        assert meta.author == ""

    def test_missing_plugin_section(self, tmp_path):
        """TOML without [plugin] section falls back to directory name."""
        plugin_dir = tmp_path / "bad_toml"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text('key = "value"\n')
        meta = load_plugin_meta(str(plugin_dir))
        assert meta.name == "bad_toml"

    def test_invalid_toml_fallback(self, tmp_path):
        """Malformed TOML falls back to directory name."""
        plugin_dir = tmp_path / "broken"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text("not valid [[[ toml")
        meta = load_plugin_meta(str(plugin_dir))
        assert meta.name == "broken"

    def test_wrong_type_fields(self, tmp_path):
        """Non-string field values are converted to str."""
        plugin_dir = tmp_path / "typed"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text(
            '[plugin]\nname = "Typed"\nversion = 123\n'
        )
        meta = load_plugin_meta(str(plugin_dir))
        assert meta.name == "Typed"
        assert meta.version == "123"
