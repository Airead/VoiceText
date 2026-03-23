"""OCR text recognition using macOS Vision framework.

Provides a simple interface to extract text from images using
VNRecognizeTextRequest. Supports Chinese and English recognition.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# VNRequestTextRecognitionLevelFast = 0
# Accurate (1) only supports 6 Latin languages; Fast covers all 30+
# including zh-Hans/zh-Hant, and is sufficient for clipboard OCR.
_RECOGNITION_LEVEL_FAST = 0


def recognize_text(
    image_path: str,
    languages: list[str] | None = None,
) -> str:
    """Extract text from an image file using macOS Vision framework.

    Args:
        image_path: Absolute path to the image file.
        languages: Recognition languages. Defaults to zh-Hans, zh-Hant, en-US.

    Returns:
        Recognized text with lines joined by newline, or empty string on
        failure or if no text is found.
    """
    if languages is None:
        languages = ["zh-Hans", "zh-Hant", "en-US"]

    try:
        from Foundation import NSURL
        from Quartz import VNImageRequestHandler, VNRecognizeTextRequest

        image_url = NSURL.fileURLWithPath_(image_path)
        handler = VNImageRequestHandler.alloc().initWithURL_options_(
            image_url, None,
        )

        request = VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(_RECOGNITION_LEVEL_FAST)
        request.setRecognitionLanguages_(languages)

        success = handler.performRequests_error_([request], None)
        if not success:
            logger.debug("Vision request failed for %s", image_path)
            return ""

        results = request.results()
        if not results:
            return ""

        lines = []
        for observation in results:
            candidates = observation.topCandidates_(1)
            if candidates:
                text = str(candidates[0].string())
                if text:
                    lines.append(text)

        return "\n".join(lines)
    except Exception:
        logger.debug("OCR failed for %s", image_path, exc_info=True)
        return ""
