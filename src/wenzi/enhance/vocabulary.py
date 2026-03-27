"""Vocabulary hotword building for ASR injection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from wenzi.enhance.manual_vocabulary import ManualVocabularyStore

logger = logging.getLogger(__name__)

LAYER_MANUAL = "manual"


@dataclass
class HotwordDetail:
    """A hotword entry with full metadata for display in the preview panel."""

    term: str
    layer: str  # LAYER_MANUAL
    category: str = "other"
    variants: List[str] = field(default_factory=list)
    context: str = ""
    frequency: int = 1
    last_seen: str = ""
    score: float = 0.0
    recency_bonus: int = 0


def build_hotword_list_detailed(
    *,
    max_count: int = 10,
    asr_model: Optional[str] = None,
    app_bundle_id: Optional[str] = None,
    manual_vocab_store: "ManualVocabularyStore | None" = None,
) -> List[HotwordDetail]:
    """Build a hotword list from manual vocabulary for ASR injection.

    Returns up to *max_count* :class:`HotwordDetail` entries sourced from
    the user-curated manual vocabulary store.
    """
    result: List[HotwordDetail] = []
    if manual_vocab_store is not None:
        try:
            manual_terms = manual_vocab_store.get_asr_hotwords(
                asr_model=asr_model, app_bundle_id=app_bundle_id,
            )
            seen: set[str] = set()
            for term in manual_terms:
                if len(result) >= max_count:
                    break
                lower = term.lower()
                if lower in seen:
                    continue
                seen.add(lower)
                result.append(HotwordDetail(
                    term=term, layer=LAYER_MANUAL,
                ))
        except Exception as e:
            logger.warning("Failed to get manual vocab hotwords: %s", e)

    return result
