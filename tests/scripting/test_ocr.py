"""Tests for OCR text recognition module."""

import sys
from unittest.mock import MagicMock, patch


def _make_mock_quartz(observations=None, success=True):
    """Set up mock Quartz and Foundation modules in sys.modules.

    Returns (mock_quartz, mock_foundation, mock_handler, mock_request).
    """
    mock_quartz = MagicMock()

    mock_request = MagicMock()
    mock_request.results.return_value = observations or []

    mock_quartz.VNRecognizeTextRequest.alloc.return_value.init.return_value = mock_request

    mock_handler = MagicMock()
    mock_handler.performRequests_error_.return_value = success
    mock_quartz.VNImageRequestHandler.alloc.return_value.initWithURL_options_.return_value = mock_handler

    mock_foundation = MagicMock()

    return mock_quartz, mock_foundation, mock_handler, mock_request


def _make_observation(text: str):
    """Create a mock VNRecognizedTextObservation."""
    candidate = MagicMock()
    candidate.string.return_value = text

    obs = MagicMock()
    obs.topCandidates_.return_value = [candidate]
    return obs


class TestRecognizeText:
    def test_basic_recognition(self):
        """Mock Vision framework and verify text extraction."""
        obs = _make_observation("Hello World")
        mock_quartz, mock_foundation, _, _ = _make_mock_quartz(
            observations=[obs],
        )

        with patch.dict(sys.modules, {
            "Quartz": mock_quartz, "Foundation": mock_foundation,
        }):
            from wenzi.scripting.ocr import recognize_text
            result = recognize_text("/fake/image.png")

        assert result == "Hello World"

    def test_multiple_lines(self):
        """Multiple observations should be joined by newlines."""
        observations = [
            _make_observation("Line 1"),
            _make_observation("Line 2"),
            _make_observation("Line 3"),
        ]
        mock_quartz, mock_foundation, _, _ = _make_mock_quartz(
            observations=observations,
        )

        with patch.dict(sys.modules, {
            "Quartz": mock_quartz, "Foundation": mock_foundation,
        }):
            from wenzi.scripting.ocr import recognize_text
            result = recognize_text("/fake/image.png")

        assert result == "Line 1\nLine 2\nLine 3"

    def test_no_text_found(self):
        """Empty observations should return empty string."""
        mock_quartz, mock_foundation, _, _ = _make_mock_quartz(
            observations=[],
        )

        with patch.dict(sys.modules, {
            "Quartz": mock_quartz, "Foundation": mock_foundation,
        }):
            from wenzi.scripting.ocr import recognize_text
            result = recognize_text("/fake/image.png")

        assert result == ""

    def test_vision_request_failure(self):
        """When Vision request fails, return empty string."""
        mock_quartz, mock_foundation, _, _ = _make_mock_quartz(
            success=False,
        )

        with patch.dict(sys.modules, {
            "Quartz": mock_quartz, "Foundation": mock_foundation,
        }):
            from wenzi.scripting.ocr import recognize_text
            result = recognize_text("/fake/image.png")

        assert result == ""

    def test_exception_returns_empty(self):
        """Any exception during OCR should return empty string."""
        mock_foundation = MagicMock()
        mock_foundation.NSURL.fileURLWithPath_.side_effect = RuntimeError("boom")

        mock_quartz = MagicMock()

        with patch.dict(sys.modules, {
            "Quartz": mock_quartz, "Foundation": mock_foundation,
        }):
            from wenzi.scripting.ocr import recognize_text
            result = recognize_text("/fake/image.png")

        assert result == ""

    def test_custom_languages(self):
        """Custom languages should be passed to the request."""
        obs = _make_observation("Test")
        mock_quartz, mock_foundation, _, mock_request = _make_mock_quartz(
            observations=[obs],
        )

        with patch.dict(sys.modules, {
            "Quartz": mock_quartz, "Foundation": mock_foundation,
        }):
            from wenzi.scripting.ocr import recognize_text
            recognize_text("/fake/image.png", languages=["en-US"])

        mock_request.setRecognitionLanguages_.assert_called_with(["en-US"])
