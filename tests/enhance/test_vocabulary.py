"""Tests for the vocabulary index and retrieval module."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from wenzi.enhance.vocabulary import (
    HotwordDetail,
    VocabularyEntry,
    VocabularyIndex,
    _parse_timestamp,
    _recency_bonus,
    build_hotword_list,
    build_hotword_list_detailed,
    get_vocab_entry_count,
    hotword_score,
    load_hotwords,
    load_hotwords_detailed,
)


# --- VocabularyEntry tests ---


class TestVocabularyEntry:
    def test_defaults(self):
        entry = VocabularyEntry(term="Python")
        assert entry.term == "Python"
        assert entry.category == "other"
        assert entry.variants == []
        assert entry.context == ""
        assert entry.frequency == 1

    def test_full_entry(self):
        entry = VocabularyEntry(
            term="Kubernetes",
            category="tech",
            variants=["库伯尼特斯", "K8S"],
            context="容器编排",
            frequency=5,
        )
        assert entry.term == "Kubernetes"
        assert entry.variants == ["库伯尼特斯", "K8S"]
        assert entry.frequency == 5

    def test_last_seen_defaults(self):
        entry = VocabularyEntry(term="Test")
        assert entry.last_seen == ""
        assert entry.last_seen_ts == 0.0

    def test_last_seen_custom(self):
        entry = VocabularyEntry(term="Test", last_seen="2026-03-20T10:00:00+00:00", last_seen_ts=1774011600.0)
        assert entry.last_seen == "2026-03-20T10:00:00+00:00"
        assert entry.last_seen_ts == 1774011600.0


# --- Recency bonus tests ---


class TestRecencyBonus:
    def test_within_24h(self):
        now = 1000000.0
        last_seen_ts = now - 3600  # 1 hour ago
        assert _recency_bonus(last_seen_ts, now) == 3

    def test_within_7d(self):
        now = 1000000.0
        last_seen_ts = now - 2 * 86400  # 2 days ago
        assert _recency_bonus(last_seen_ts, now) == 2

    def test_within_30d(self):
        now = 1000000.0
        last_seen_ts = now - 10 * 86400  # 10 days ago
        assert _recency_bonus(last_seen_ts, now) == 1

    def test_older_than_30d(self):
        now = 1000000.0
        last_seen_ts = now - 60 * 86400  # 60 days ago
        assert _recency_bonus(last_seen_ts, now) == 0

    def test_no_last_seen(self):
        assert _recency_bonus(0.0, 1000000.0) == 0

    def test_negative_last_seen(self):
        assert _recency_bonus(-1.0, 1000000.0) == 0

    def test_boundary_24h(self):
        now = 1000000.0
        # Exactly at 24h boundary → should NOT get +3 (age >= threshold)
        assert _recency_bonus(now - 86400.0, now) == 2
        # Just under 24h → should get +3
        assert _recency_bonus(now - 86399.0, now) == 3


class TestHotwordScore:
    def test_score_with_bonus(self):
        now = 1000000.0
        last_seen_ts = now - 3600  # 1 hour ago → +3
        assert hotword_score(5, last_seen_ts, now) == 8

    def test_score_no_bonus(self):
        assert hotword_score(5, 0.0, 1000000.0) == 5

    def test_score_frequency_only(self):
        now = 1000000.0
        last_seen_ts = now - 60 * 86400  # 60 days ago → +0
        assert hotword_score(3, last_seen_ts, now) == 3


# --- Helpers ---


def _make_vocab_json(entries):
    """Create a vocabulary.json-compatible dict."""
    return {
        "last_processed_timestamp": "2026-01-01T00:00:00+00:00",
        "entries": entries,
    }


def _sample_entries():
    return [
        {
            "term": "Python",
            "category": "tech",
            "variants": ["派森"],
            "context": "编程语言",
            "frequency": 3,
        },
        {
            "term": "Kubernetes",
            "category": "tech",
            "variants": ["库伯尼特斯"],
            "context": "容器编排",
            "frequency": 2,
        },
        {
            "term": "Visual Studio Code",
            "category": "tech",
            "variants": ["VSCode"],
            "context": "代码编辑器",
            "frequency": 1,
        },
    ]


def _write_vocab(tmp_path, entries):
    """Write vocabulary.json and return a loaded VocabularyIndex."""
    vocab_path = tmp_path / "vocabulary.json"
    vocab_path.write_text(
        json.dumps(_make_vocab_json(entries)), encoding="utf-8"
    )
    idx = VocabularyIndex({}, data_dir=str(tmp_path))
    idx.load()
    return idx


# --- VocabularyIndex load tests ---


class TestVocabularyIndexLoad:
    def test_load_success(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert idx.is_loaded
        assert idx.entry_count == 3

    def test_load_builds_index(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert len(idx._variants_by_length) > 0
        # "派森" is CJK so pinyin index should also be populated
        assert len(idx._pinyin_index) > 0

    def test_load_no_vocabulary_file(self, tmp_path):
        idx = VocabularyIndex({}, data_dir=str(tmp_path))
        result = idx.load()
        assert result is False
        assert not idx.is_loaded

    def test_load_empty_entries(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json([])), encoding="utf-8"
        )
        idx = VocabularyIndex({}, data_dir=str(tmp_path))
        result = idx.load()
        assert result is False


# --- Exact search tests ---


class TestExactSearch:
    def test_variant_in_text(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        results = idx.retrieve("我用派森写代码")
        terms = [r.term for r in results]
        assert "Python" in terms

    def test_term_only_in_text_not_matched(self, tmp_path):
        """Term-only match is filtered out — ASR already correct."""
        idx = _write_vocab(tmp_path, _sample_entries())
        results = idx.retrieve("I use Python for coding")
        terms = [r.term for r in results]
        assert "Python" not in terms

    def test_case_insensitive(self, tmp_path):
        """Case-insensitive variant matching still works."""
        entries = [
            {"term": "FunASR", "variants": ["fanASR", "FanASR"], "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.retrieve("I tried fanasr today")
        terms = [r.term for r in results]
        assert "FunASR" in terms

    def test_min_length_filtering(self, tmp_path):
        """Single-character variants are not indexed."""
        entries = [
            {"term": "AI", "variants": ["A", "人工智能"], "frequency": 1},
        ]
        idx = _write_vocab(tmp_path, entries)
        # "A" (1 char) should not be indexed; "AI" is term-only → filtered
        results = idx.retrieve("I like AI")
        assert results == []

        # Variant "人工智能" should match
        results2 = idx.retrieve("人工智能很厉害")
        terms2 = [r.term for r in results2]
        assert "AI" in terms2

    def test_no_match(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        results = idx.retrieve("今天天气很好")
        assert results == []

    def test_multiple_matches(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        results = idx.retrieve("我用派森和库伯尼特斯部署服务")
        terms = [r.term for r in results]
        assert "Python" in terms
        assert "Kubernetes" in terms


# --- Pinyin search tests ---


class TestPinyinSearch:
    def test_homophone_match(self, tmp_path):
        """Unseen variant with same pinyin should match via pinyin layer."""
        entries = [
            {"term": "Python", "variants": ["派森"], "context": "编程语言", "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        # "排森" has same pinyin as "派森" (pai sen) but different characters
        results = idx.retrieve("我用排森写代码")
        terms = [r.term for r in results]
        assert "Python" in terms

    def test_non_cjk_not_in_pinyin_index(self, tmp_path):
        """Pure ASCII terms/variants should NOT be in the pinyin index."""
        entries = [
            {"term": "Python", "variants": ["PyThon"], "frequency": 1},
        ]
        idx = _write_vocab(tmp_path, entries)
        # Pinyin index should be empty — no CJK strings
        assert len(idx._pinyin_index) == 0

    def test_pinyin_no_cross_boundary_match(self, tmp_path):
        """Pinyin matching should not match across character boundaries."""
        entries = [
            {"term": "Python", "variants": ["拍森"], "frequency": 1},
        ]
        idx = _write_vocab(tmp_path, entries)
        # "拍了一张森林的照片" — "拍" and "森" are not adjacent
        results = idx.retrieve("拍了一张森林的照片")
        terms = [r.term for r in results]
        assert "Python" not in terms


# --- Retrieve integration tests ---


class TestRetrieve:
    def test_frequency_ranking(self, tmp_path):
        entries = [
            {"term": "LowTerm", "variants": ["罗特"], "frequency": 1},
            {"term": "HighTerm", "variants": ["嗨特"], "frequency": 10},
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.retrieve("他说嗨特然后打了个电话给罗特", top_k=5)
        assert len(results) == 2
        # Higher frequency should come first (both are exact matches)
        assert results[0].term == "HighTerm"
        assert results[1].term == "LowTerm"

    def test_exact_before_pinyin(self, tmp_path):
        """Exact matches should rank before pinyin-only matches."""
        entries = [
            {"term": "A_Term", "variants": ["阿特"], "frequency": 1},
            {"term": "B_Term", "variants": ["贝特"], "frequency": 10},
        ]
        idx = _write_vocab(tmp_path, entries)
        # "阿特" is exact match, "倍特" is pinyin match for "贝特" (bei te)
        results = idx.retrieve("我找阿特和倍特", top_k=5)
        terms = [r.term for r in results]
        if "A_Term" in terms and "B_Term" in terms:
            assert terms.index("A_Term") < terms.index("B_Term")

    def test_top_k_limiting(self, tmp_path):
        entries = [
            {"term": f"Term{i}", "variants": [f"变体{i}号"], "frequency": i}
            for i in range(10)
        ]
        idx = _write_vocab(tmp_path, entries)
        text = "".join(f"变体{i}号" for i in range(10))
        results = idx.retrieve(text, top_k=3)
        assert len(results) == 3

    def test_empty_text(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert idx.retrieve("") == []
        assert idx.retrieve("   ") == []

    def test_not_loaded(self, tmp_path):
        idx = VocabularyIndex({}, data_dir=str(tmp_path))
        assert idx.retrieve("Python") == []

    def test_deduplication(self, tmp_path):
        """Same entry matched by both exact and pinyin should appear only once."""
        entries = [
            {"term": "Python", "variants": ["派森"], "context": "编程语言", "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.retrieve("我用派森写代码", top_k=5)
        terms = [r.term for r in results]
        assert terms.count("Python") == 1

    def test_early_termination_skips_pinyin(self, tmp_path):
        """When exact matches >= top_k, pinyin layer should be skipped."""
        entries = [
            {"term": f"Term{i}", "variants": [f"变体{i}号"], "frequency": i + 1}
            for i in range(5)
        ]
        idx = _write_vocab(tmp_path, entries)
        text = "".join(f"变体{i}号" for i in range(5))
        # top_k=3, and we have 5 exact matches, so pinyin should be skipped
        results = idx.retrieve(text, top_k=3)
        assert len(results) == 3
        # Should be sorted by frequency desc
        assert results[0].frequency >= results[1].frequency >= results[2].frequency

    def test_entries_without_variants_not_matched(self, tmp_path):
        """Entries with no variants are not returned by retrieve().

        Term-only matches indicate the ASR already produced the correct
        form, so no correction hint is needed.
        """
        entries = [
            {"term": "Docker", "variants": [], "context": "容器", "frequency": 2},
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.retrieve("I use Docker for deployment")
        assert results == []

    def test_term_match_filtered_variant_match_kept(self, tmp_path):
        """retrieve() returns only variant-matched entries, not term-matched."""
        entries = [
            {"term": "Kubernetes", "variants": ["库伯尼特斯"], "frequency": 5},
            {"term": "Docker", "variants": [], "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        # Text contains variant "库伯尼特斯" AND term "Docker"
        results = idx.retrieve("库伯尼特斯和Docker都很好用")
        terms = [r.term for r in results]
        assert "Kubernetes" in terms
        assert "Docker" not in terms


# --- Reload tests ---


class TestVocabularyIndexReload:
    def test_reload_resets_state(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert idx.is_loaded

        idx.reload()
        assert idx.is_loaded
        assert idx.entry_count == 3

    def test_reload_picks_up_new_entries(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert idx.entry_count == 3

        entries = _sample_entries() + [
            {"term": "Docker", "variants": [], "context": "", "frequency": 1}
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        idx.reload()
        assert idx.entry_count == 4


# --- Entry count tests ---


class TestEntryCount:
    def test_entry_count_after_load(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert idx.entry_count == 3

    def test_entry_count_zero_before_load(self, tmp_path):
        idx = VocabularyIndex({}, data_dir=str(tmp_path))
        assert idx.entry_count == 0


# --- Format tests ---


class TestVocabularyIndexFormatForPrompt:
    def test_format_with_context(self):
        entries = [
            VocabularyEntry(term="Python", context="编程语言"),
            VocabularyEntry(term="Kubernetes", context="容器编排"),
        ]
        idx = VocabularyIndex({})
        result = idx.format_for_prompt(entries)
        assert "用户词库" in result
        assert "不要强行套用" in result
        assert "- Python（编程语言）" in result
        assert "- Kubernetes（容器编排）" in result

    def test_format_without_context(self):
        entries = [VocabularyEntry(term="Python")]
        idx = VocabularyIndex({})
        result = idx.format_for_prompt(entries)
        assert "- Python" in result
        assert "- Python（" not in result

    def test_format_empty(self):
        idx = VocabularyIndex({})
        result = idx.format_for_prompt([])
        assert result == ""

    def test_format_mixed(self):
        entries = [
            VocabularyEntry(term="Python", context="编程语言"),
            VocabularyEntry(term="FastAPI"),
        ]
        idx = VocabularyIndex({})
        result = idx.format_for_prompt(entries)
        assert "- Python（编程语言）" in result
        assert "- FastAPI" in result


class TestVocabularyFormatEntryLines:
    def test_entries_with_context(self):
        entries = [
            VocabularyEntry(term="Python", context="编程语言"),
            VocabularyEntry(term="Kubernetes", context="容器编排"),
        ]
        result = VocabularyIndex.format_entry_lines(entries)
        assert result == "- Python（编程语言）\n- Kubernetes（容器编排）"

    def test_entries_without_context(self):
        entries = [VocabularyEntry(term="Python")]
        result = VocabularyIndex.format_entry_lines(entries)
        assert result == "- Python"

    def test_empty_entries(self):
        assert VocabularyIndex.format_entry_lines([]) == ""

    def test_mixed_entries(self):
        entries = [
            VocabularyEntry(term="Python", context="编程语言"),
            VocabularyEntry(term="FastAPI"),
        ]
        result = VocabularyIndex.format_entry_lines(entries)
        assert "- Python（编程语言）" in result
        assert "- FastAPI" in result
        assert "- FastAPI（" not in result

    def test_consistency_with_format_for_prompt(self):
        """format_entry_lines output should appear in format_for_prompt output."""
        entries = [
            VocabularyEntry(term="API", context="接口"),
            VocabularyEntry(term="SDK"),
        ]
        idx = VocabularyIndex({})
        entry_lines = VocabularyIndex.format_entry_lines(entries)
        full_prompt = idx.format_for_prompt(entries)
        assert entry_lines in full_prompt


# --- get_vocab_entry_count tests ---


class TestGetVocabEntryCount:
    def test_count_with_entries(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(_sample_entries())),
            encoding="utf-8",
        )
        assert get_vocab_entry_count(str(tmp_path)) == 3

    def test_count_no_file(self, tmp_path):
        assert get_vocab_entry_count(str(tmp_path)) == 0

    def test_count_empty_entries(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json([])),
            encoding="utf-8",
        )
        assert get_vocab_entry_count(str(tmp_path)) == 0

    def test_count_invalid_json(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text("not json", encoding="utf-8")
        assert get_vocab_entry_count(str(tmp_path)) == 0


# --- load_hotwords tests ---


class TestLoadHotwords:
    def test_filters_by_frequency(self, tmp_path):
        entries = [
            {"term": "HighFreq", "frequency": 5},
            {"term": "LowFreq", "frequency": 1},
            {"term": "MidFreq", "frequency": 2},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=2)
        assert "HighFreq" in result
        assert "MidFreq" in result
        assert "LowFreq" not in result

    def test_sorts_by_frequency_desc(self, tmp_path):
        entries = [
            {"term": "Low", "frequency": 2},
            {"term": "High", "frequency": 10},
            {"term": "Mid", "frequency": 5},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=1)
        assert result == ["High", "Mid", "Low"]

    def test_respects_max_count(self, tmp_path):
        entries = [
            {"term": f"Term{i}", "frequency": 10 - i}
            for i in range(10)
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=1, max_count=3)
        assert len(result) == 3
        assert result[0] == "Term0"

    def test_max_count_none_returns_all(self, tmp_path):
        """max_count=None means unlimited — all entries are returned."""
        entries = [
            {"term": f"Term{i}", "frequency": 20 - i}
            for i in range(20)
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=1, max_count=None)
        assert len(result) == 20

    def test_default_max_count_is_unlimited(self, tmp_path):
        """Default max_count should return all entries (unlimited)."""
        entries = [
            {"term": f"Term{i}", "frequency": 15 - i}
            for i in range(15)
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=1)
        assert len(result) == 15

    def test_no_file_returns_empty(self, tmp_path):
        result = load_hotwords(data_dir=str(tmp_path))
        assert result == []

    def test_all_low_frequency_returns_empty(self, tmp_path):
        entries = [
            {"term": "A", "frequency": 1},
            {"term": "B", "frequency": 1},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=2)
        assert result == []

    def test_sorts_by_score_with_recency(self, tmp_path):
        """Recency bonus should affect hotword ordering."""
        now = datetime.now(timezone.utc)
        recent_ts = (now - timedelta(hours=1)).isoformat()  # +3 bonus
        entries = [
            {"term": "Stale", "frequency": 5},  # score=5
            {"term": "Recent", "frequency": 3, "last_seen": recent_ts},  # score=6
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords(data_dir=str(tmp_path), min_frequency=1)
        assert result == ["Recent", "Stale"]


# --- find_terms_in_text tests ---


class TestFindTermsInText:
    def test_exact_term_match(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        results = idx.find_terms_in_text("I use Python for coding")
        terms = [r.term for r in results]
        assert "Python" in terms

    def test_variant_match(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        results = idx.find_terms_in_text("我用派森写代码")
        terms = [r.term for r in results]
        assert "Python" in terms

    def test_no_pinyin_layer(self, tmp_path):
        """find_terms_in_text should NOT use pinyin matching."""
        entries = [
            {"term": "Python", "variants": ["派森"], "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        # "排森" has same pinyin but different characters — should NOT match
        results = idx.find_terms_in_text("我用排森写代码")
        terms = [r.term for r in results]
        assert "Python" not in terms

    def test_not_loaded_returns_empty(self, tmp_path):
        idx = VocabularyIndex({}, data_dir=str(tmp_path))
        assert idx.find_terms_in_text("Python") == []

    def test_empty_text_returns_empty(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        assert idx.find_terms_in_text("") == []
        assert idx.find_terms_in_text("   ") == []

    def test_sorted_by_frequency_desc(self, tmp_path):
        entries = [
            {"term": "LowTerm", "variants": ["罗特"], "frequency": 1},
            {"term": "HighTerm", "variants": ["嗨特"], "frequency": 10},
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.find_terms_in_text("我说嗨特然后打了个电话给罗特")
        assert len(results) == 2
        assert results[0].term == "HighTerm"
        assert results[1].term == "LowTerm"

    def test_recency_can_override_frequency(self, tmp_path):
        """A recently-seen lower-frequency term can outrank a stale higher-frequency term."""
        now = datetime.now(timezone.utc)
        recent_ts = (now - timedelta(hours=1)).isoformat()  # +3 bonus
        entries = [
            {"term": "StaleTerm", "variants": ["陈旧"], "frequency": 5},  # score=5
            {"term": "RecentTerm", "variants": ["新鲜"], "frequency": 3, "last_seen": recent_ts},  # score=6
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.find_terms_in_text("陈旧和新鲜都在这里")
        assert len(results) == 2
        assert results[0].term == "RecentTerm"
        assert results[1].term == "StaleTerm"

    def test_same_frequency_recent_first(self, tmp_path):
        """Same frequency: recently-seen term should rank higher."""
        now = datetime.now(timezone.utc)
        recent_ts = (now - timedelta(days=2)).isoformat()  # +2 bonus
        entries = [
            {"term": "OldTerm", "variants": ["老的"], "frequency": 3},  # score=3
            {"term": "NewTerm", "variants": ["新的"], "frequency": 3, "last_seen": recent_ts},  # score=5
        ]
        idx = _write_vocab(tmp_path, entries)
        results = idx.find_terms_in_text("老的和新的")
        assert len(results) == 2
        assert results[0].term == "NewTerm"
        assert results[1].term == "OldTerm"


# --- _parse_timestamp tests ---


class TestParseTimestamp:
    def test_iso_with_timezone(self):
        dt = _parse_timestamp("2026-03-20T10:30:00+08:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_iso_without_timezone(self):
        dt = _parse_timestamp("2026-03-20T10:30:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc

    def test_invalid_string(self):
        assert _parse_timestamp("not-a-date") is None

    def test_none_input(self):
        assert _parse_timestamp(None) is None

    def test_empty_string(self):
        assert _parse_timestamp("") is None


# --- build_hotword_list tests ---


def _make_mock_history(records):
    """Create a mock ConversationHistory that returns given records."""

    class MockHistory:
        def get_recent(self, n=10):
            return records[:n]

    return MockHistory()


class TestBuildHotwordList:
    def test_context_layer_priority(self, tmp_path):
        """Context-layer terms should come before base-layer terms."""
        entries = [
            {"term": "Python", "variants": ["派森"], "frequency": 5},
            {"term": "Docker", "variants": ["多克"], "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        now = datetime.now(timezone.utc)
        records = [
            {
                "timestamp": now.isoformat(),
                "final_text": "我在用派森写代码",
                "preview_enabled": True,
            },
        ]
        history = _make_mock_history(records)
        base = ["Kubernetes", "Terraform"]
        result = build_hotword_list(idx, history, base)
        assert result is not None
        # Python should be first (from context), then base terms
        assert result[0] == "Python"
        assert "Kubernetes" in result
        assert "Terraform" in result

    def test_deduplication(self, tmp_path):
        """Terms appearing in both layers should not be duplicated."""
        entries = [
            {"term": "Python", "variants": ["派森"], "frequency": 5},
        ]
        idx = _write_vocab(tmp_path, entries)
        now = datetime.now(timezone.utc)
        records = [
            {
                "timestamp": now.isoformat(),
                "final_text": "我用派森",
                "preview_enabled": True,
            },
        ]
        history = _make_mock_history(records)
        base = ["Python", "Docker"]
        result = build_hotword_list(idx, history, base)
        assert result is not None
        assert result.count("Python") == 1

    def test_max_count_limit(self, tmp_path):
        entries = [
            {"term": f"Term{i}", "variants": [f"变体{i}号"], "frequency": i + 1}
            for i in range(10)
        ]
        idx = _write_vocab(tmp_path, entries)
        now = datetime.now(timezone.utc)
        combined_text = " ".join(f"变体{i}号" for i in range(10))
        records = [
            {
                "timestamp": now.isoformat(),
                "final_text": combined_text,
                "preview_enabled": True,
            },
        ]
        history = _make_mock_history(records)
        base = [f"Base{i}" for i in range(10)]
        result = build_hotword_list(idx, history, base, max_count=5)
        assert result is not None
        assert len(result) == 5

    def test_age_filtering(self, tmp_path):
        """Records older than max_age_hours should be skipped."""
        entries = [
            {"term": "Python", "variants": ["派森"], "frequency": 5},
        ]
        idx = _write_vocab(tmp_path, entries)
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        records = [
            {
                "timestamp": old_time.isoformat(),
                "final_text": "我用派森",
                "preview_enabled": True,
            },
        ]
        history = _make_mock_history(records)
        # With max_age_hours=2, the old record should be filtered out
        result = build_hotword_list(idx, history, None, max_age_hours=2.0)
        assert result is None  # No context, no base

    def test_vocab_index_none_uses_base(self):
        """When vocab_index is None, only base hotwords are used."""
        base = ["Python", "Docker"]
        result = build_hotword_list(None, None, base)
        assert result == ["Python", "Docker"]

    def test_history_none_uses_base(self, tmp_path):
        """When history is None, only base hotwords are used."""
        idx = _write_vocab(tmp_path, _sample_entries())
        base = ["Python", "Docker"]
        result = build_hotword_list(idx, None, base)
        assert result == ["Python", "Docker"]

    def test_all_none_returns_none(self):
        """When everything is None/empty, return None."""
        result = build_hotword_list(None, None, None)
        assert result is None

    def test_empty_base_with_no_context_returns_none(self, tmp_path):
        idx = _write_vocab(tmp_path, _sample_entries())
        history = _make_mock_history([])
        result = build_hotword_list(idx, history, None)
        assert result is None

    def test_base_only_when_no_context(self, tmp_path):
        """When history is empty, only base hotwords are returned."""
        idx = _write_vocab(tmp_path, _sample_entries())
        history = _make_mock_history([])
        base = ["Python", "Docker"]
        result = build_hotword_list(idx, history, base)
        assert result == ["Python", "Docker"]


# --- HotwordDetail tests ---


class TestHotwordDetail:
    def test_defaults(self):
        d = HotwordDetail(term="API", layer="base")
        assert d.term == "API"
        assert d.layer == "base"
        assert d.category == "other"
        assert d.variants == []
        assert d.context == ""
        assert d.frequency == 1
        assert d.last_seen == ""
        assert d.score == 0.0
        assert d.recency_bonus == 0

    def test_full_fields(self):
        d = HotwordDetail(
            term="Kubernetes",
            layer="context",
            category="tech",
            variants=["k8s"],
            context="container orchestration",
            frequency=12,
            last_seen="2026-03-20T10:00:00+00:00",
            score=15.0,
            recency_bonus=3,
        )
        assert d.term == "Kubernetes"
        assert d.layer == "context"
        assert d.score == 15.0
        assert d.recency_bonus == 3
        assert d.variants == ["k8s"]


# --- load_hotwords_detailed tests ---


class TestLoadHotwordsDetailed:
    def test_returns_hotword_detail_objects(self, tmp_path):
        entries = [
            {"term": "API", "frequency": 5, "category": "tech",
             "variants": ["api"], "context": "interface"},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords_detailed(data_dir=str(tmp_path), min_frequency=1)
        assert len(result) == 1
        assert isinstance(result[0], HotwordDetail)
        assert result[0].term == "API"
        assert result[0].layer == "base"
        assert result[0].category == "tech"
        assert result[0].variants == ["api"]
        assert result[0].context == "interface"
        assert result[0].frequency == 5

    def test_filters_by_frequency(self, tmp_path):
        entries = [
            {"term": "High", "frequency": 5},
            {"term": "Low", "frequency": 1},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords_detailed(data_dir=str(tmp_path), min_frequency=2)
        assert len(result) == 1
        assert result[0].term == "High"

    def test_sorts_by_score_desc(self, tmp_path):
        entries = [
            {"term": "Low", "frequency": 2},
            {"term": "High", "frequency": 10},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords_detailed(data_dir=str(tmp_path), min_frequency=1)
        assert result[0].term == "High"
        assert result[1].term == "Low"

    def test_recency_bonus_computed(self, tmp_path):
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(hours=1)).isoformat()
        entries = [
            {"term": "Recent", "frequency": 2, "last_seen": recent},
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords_detailed(data_dir=str(tmp_path), min_frequency=1)
        assert result[0].recency_bonus == 3  # < 24h
        assert result[0].score == 5.0  # freq 2 + bonus 3

    def test_max_count(self, tmp_path):
        entries = [
            {"term": f"T{i}", "frequency": 10 - i} for i in range(10)
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords_detailed(
            data_dir=str(tmp_path), min_frequency=1, max_count=3,
        )
        assert len(result) == 3

    def test_max_count_none_returns_all(self, tmp_path):
        """max_count=None means unlimited — all entries are returned."""
        entries = [
            {"term": f"T{i}", "frequency": 20 - i} for i in range(20)
        ]
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(
            json.dumps(_make_vocab_json(entries)), encoding="utf-8"
        )
        result = load_hotwords_detailed(
            data_dir=str(tmp_path), min_frequency=1, max_count=None,
        )
        assert len(result) == 20

    def test_no_file_returns_empty(self, tmp_path):
        result = load_hotwords_detailed(data_dir=str(tmp_path))
        assert result == []


# --- build_hotword_list_detailed tests ---


class TestBuildHotwordListDetailed:
    def test_context_layer_marked(self, tmp_path):
        now = datetime.now(timezone.utc)
        entries = [
            {"term": "Python", "category": "tech", "variants": ["派森"],
             "context": "language", "frequency": 3},
        ]
        idx = _write_vocab(tmp_path, entries)
        history = _make_mock_history([
            {"final_text": "I use Python for data analysis",
             "timestamp": now.isoformat()},
        ])
        result = build_hotword_list_detailed(idx, history, None)
        assert len(result) == 1
        assert result[0].layer == "context"
        assert result[0].term == "Python"
        assert result[0].category == "tech"
        assert result[0].frequency == 3

    def test_base_layer_marked(self):
        base = [
            HotwordDetail(term="Docker", layer="base", frequency=5, score=5.0),
        ]
        result = build_hotword_list_detailed(None, None, base)
        assert len(result) == 1
        assert result[0].layer == "base"
        assert result[0].term == "Docker"

    def test_context_before_base(self, tmp_path):
        now = datetime.now(timezone.utc)
        entries = [
            {"term": "Python", "category": "tech", "variants": ["派森"],
             "context": "", "frequency": 2},
        ]
        idx = _write_vocab(tmp_path, entries)
        history = _make_mock_history([
            {"final_text": "Python is great",
             "timestamp": now.isoformat()},
        ])
        base = [
            HotwordDetail(term="Docker", layer="base", frequency=10, score=10.0),
        ]
        result = build_hotword_list_detailed(idx, history, base)
        terms = [d.term for d in result]
        assert terms.index("Python") < terms.index("Docker")

    def test_deduplication(self, tmp_path):
        now = datetime.now(timezone.utc)
        entries = [
            {"term": "Python", "frequency": 3, "variants": ["派森"]},
        ]
        idx = _write_vocab(tmp_path, entries)
        history = _make_mock_history([
            {"final_text": "Python rocks",
             "timestamp": now.isoformat()},
        ])
        base = [
            HotwordDetail(term="Python", layer="base", frequency=3, score=3.0),
        ]
        result = build_hotword_list_detailed(idx, history, base)
        assert sum(1 for d in result if d.term == "Python") == 1
        assert result[0].layer == "context"  # context wins

    def test_all_none_returns_empty(self):
        result = build_hotword_list_detailed(None, None, None)
        assert result == []

    def test_max_count(self, tmp_path):
        now = datetime.now(timezone.utc)
        entries = [
            {"term": f"Term{i}", "frequency": 2, "variants": [f"term{i}"]}
            for i in range(10)
        ]
        idx = _write_vocab(tmp_path, entries)
        history = _make_mock_history([
            {"final_text": " ".join(f"term{i}" for i in range(10)),
             "timestamp": now.isoformat()},
        ])
        result = build_hotword_list_detailed(idx, history, None, max_count=3)
        assert len(result) == 3
