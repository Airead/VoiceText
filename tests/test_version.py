"""Tests for version and build info consistency."""


class TestVersion:
    def test_version_importable(self):
        from wenzi import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_is_dev_when_not_frozen(self):
        """When running outside PyInstaller (e.g. uv run), version should be 'dev'."""
        from wenzi import __version__

        assert __version__ == "dev"
