"""Tests for the vocabulary builder module."""

from __future__ import annotations

import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wenzi.enhance.vocabulary_builder import BuildCallbacks, VocabularyBuilder


def _make_config(**overrides):
    """Helper to create a valid builder config."""
    cfg = {
        "default_provider": "ollama",
        "default_model": "qwen2.5:7b",
        "providers": {
            "ollama": {
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",
                "models": ["qwen2.5:7b"],
            },
        },
    }
    cfg.update(overrides)
    return cfg


def _sample_corrections():
    return [
        {
            "timestamp": "2026-01-01T10:00:00+00:00",
            "asr_text": "派森编程语言",
            "enhanced_text": "Python编程语言",
            "final_text": "Python编程语言",
            "enhance_mode": "proofread",
            "user_corrected": True,
        },
        {
            "timestamp": "2026-01-01T11:00:00+00:00",
            "asr_text": "库伯尼特斯容器",
            "enhanced_text": "Kubernetes容器",
            "final_text": "Kubernetes容器",
            "enhance_mode": "proofread",
            "user_corrected": True,
        },
        {
            "timestamp": "2026-01-01T12:00:00+00:00",
            "asr_text": "VSCode编辑器",
            "enhanced_text": "VS Code编辑器",
            "final_text": "Visual Studio Code编辑器",
            "enhance_mode": "proofread",
            "user_corrected": True,
        },
    ]


_PIPE_RESPONSE_TWO = (
    "term|category|variants|context\n"
    "Python|tech|派森|编程语言\n"
    "Kubernetes|tech|库伯尼特斯|容器编排"
)

_PIPE_RESPONSE_ONE = (
    "term|category|variants|context\n"
    "Python|tech|派森|编程语言"
)

_PIPE_RESPONSE_K8S = (
    "term|category|variants|context\n"
    "Kubernetes|tech|库伯尼特斯|容器编排"
)

_PIPE_RESPONSE_TEST = (
    "term|category|variants|context\n"
    "TestTerm|tech||test"
)


class TestReadCorrections:
    def test_read_all(self, tmp_path):
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._read_corrections()
        assert len(result) == 3

    def test_read_since_timestamp(self, tmp_path):
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._read_corrections(since="2026-01-01T10:00:00+00:00")
        assert len(result) == 2
        assert result[0]["asr_text"] == "库伯尼特斯容器"

    def test_read_no_file(self, tmp_path):
        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._read_corrections()
        assert result == []

    def test_read_skips_invalid_json(self, tmp_path):
        corrections_path = tmp_path / "conversation_history.jsonl"
        with open(corrections_path, "w", encoding="utf-8") as f:
            f.write('{"timestamp": "2026-01-01T10:00:00", "asr_text": "hello", "user_corrected": true}\n')
            f.write("invalid json line\n")
            f.write('{"timestamp": "2026-01-01T11:00:00", "asr_text": "world", "user_corrected": true}\n')

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._read_corrections()
        assert len(result) == 2

    def test_read_skips_empty_lines(self, tmp_path):
        corrections_path = tmp_path / "conversation_history.jsonl"
        with open(corrections_path, "w", encoding="utf-8") as f:
            f.write('{"timestamp": "2026-01-01T10:00:00", "asr_text": "hello", "user_corrected": true}\n')
            f.write("\n")
            f.write("\n")
            f.write('{"timestamp": "2026-01-01T11:00:00", "asr_text": "world", "user_corrected": true}\n')

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._read_corrections()
        assert len(result) == 2

    def test_read_filters_non_corrections(self, tmp_path):
        corrections_path = tmp_path / "conversation_history.jsonl"
        with open(corrections_path, "w", encoding="utf-8") as f:
            f.write('{"timestamp": "2026-01-01T10:00:00", "asr_text": "a", "user_corrected": true}\n')
            f.write('{"timestamp": "2026-01-01T11:00:00", "asr_text": "b", "user_corrected": false}\n')
            f.write('{"timestamp": "2026-01-01T12:00:00", "asr_text": "c", "user_corrected": true}\n')

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._read_corrections()
        assert len(result) == 2
        assert result[0]["asr_text"] == "a"
        assert result[1]["asr_text"] == "c"


class TestBatchRecords:
    def test_batch_exact_size(self):
        builder = VocabularyBuilder(_make_config())
        records = [{"i": i} for i in range(20)]
        batches = builder._batch_records(records, batch_size=20)
        assert len(batches) == 1
        assert len(batches[0]) == 20

    def test_batch_remainder(self):
        builder = VocabularyBuilder(_make_config())
        records = [{"i": i} for i in range(25)]
        batches = builder._batch_records(records, batch_size=20)
        assert len(batches) == 2
        assert len(batches[0]) == 20
        assert len(batches[1]) == 5

    def test_batch_smaller_than_size(self):
        builder = VocabularyBuilder(_make_config())
        records = [{"i": i} for i in range(5)]
        batches = builder._batch_records(records, batch_size=20)
        assert len(batches) == 1
        assert len(batches[0]) == 5

    def test_batch_empty(self):
        builder = VocabularyBuilder(_make_config())
        batches = builder._batch_records([], batch_size=20)
        assert batches == []


def _mock_messages():
    """Helper to create a minimal session messages list."""
    return [{"role": "system", "content": "test system prompt"}]


def _mock_usage(prompt=10, completion=5, total=15, cached=0):
    """Helper to create a mock usage object with optional cached_tokens."""
    usage = MagicMock()
    usage.prompt_tokens = prompt
    usage.completion_tokens = completion
    usage.total_tokens = total
    details = MagicMock()
    details.cached_tokens = cached
    usage.prompt_tokens_details = details
    return usage


class TestExtractBatch:
    def test_successful_extraction(self):
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: 派森\nfinal_text: Python"
        messages = _mock_messages()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = _mock_usage()

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        entries, usage, text = asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client)
        )

        assert len(entries) == 1
        assert entries[0]["term"] == "Python"
        assert usage["total_tokens"] == 15
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 5
        assert text == _PIPE_RESPONSE_ONE

    def test_cached_tokens_tracked(self):
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: 派森\nfinal_text: Python"
        messages = _mock_messages()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = _mock_usage(prompt=100, completion=20, total=120, cached=80)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        entries, usage, text = asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client)
        )

        assert usage["input_tokens"] == 100
        assert usage["cached_tokens"] == 80
        assert usage["output_tokens"] == 20

    def test_cached_tokens_graceful_fallback(self):
        """Providers without cached token support should default to 0."""
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        mock_usage_obj = MagicMock()
        mock_usage_obj.prompt_tokens = 10
        mock_usage_obj.completion_tokens = 5
        mock_usage_obj.total_tokens = 15
        mock_usage_obj.prompt_tokens_details = None  # Provider doesn't support it

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = mock_usage_obj

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        _, usage, _ = asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client)
        )

        assert usage["cached_tokens"] == 0

    def test_empty_llm_response(self):
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        entries, usage, text = asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client)
        )

        assert entries == []
        assert text == ""

    def test_no_provider_config(self):
        builder = VocabularyBuilder({"providers": {}})
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        entries, usage, text = asyncio.run(
            builder._extract_batch(messages, user_prompt)
        )
        assert entries == []
        assert usage == {}
        assert text == ""

    def test_timeout(self):
        cfg = _make_config()
        cfg["vocabulary"] = {"build_timeout": 1}
        builder = VocabularyBuilder(cfg)
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        async def slow_create(**kwargs):
            await asyncio.sleep(10)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = slow_create

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                builder._extract_batch(messages, user_prompt, client=mock_client)
            )

    def test_messages_include_session_history(self):
        """Verify that session history is passed to the API call."""
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: 派森\nfinal_text: Python"
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "previous batch"},
            {"role": "assistant", "content": "previous response"},
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = _mock_usage()

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client)
        )

        # Verify 4 messages: system + prev user + prev assistant + new user
        call_kwargs = mock_client.chat.completions.create.call_args
        sent_messages = call_kwargs.kwargs.get("messages", call_kwargs[1].get("messages"))
        assert len(sent_messages) == 4
        assert sent_messages[0]["role"] == "system"
        assert sent_messages[1]["role"] == "user"
        assert sent_messages[2]["role"] == "assistant"
        assert sent_messages[3]["role"] == "user"


class TestParseLLMResponse:
    def test_parse_pipe_text(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\nPython|tech|派森|编程语言"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["term"] == "Python"
        assert result[0]["category"] == "tech"
        assert result[0]["variants"] == ["派森"]
        assert result[0]["context"] == "编程语言"

    def test_parse_multiple_entries(self):
        builder = VocabularyBuilder(_make_config())
        content = (
            "term|category|variants|context\n"
            "Python|tech|派森|编程语言\n"
            "Kubernetes|tech|库伯尼特斯|容器编排"
        )
        result = builder._parse_llm_response(content)
        assert len(result) == 2
        assert result[0]["term"] == "Python"
        assert result[1]["term"] == "Kubernetes"

    def test_parse_with_markdown_fences(self):
        builder = VocabularyBuilder(_make_config())
        content = "```\nterm|category|variants|context\nPython|tech|派森|编程语言\n```"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["term"] == "Python"

    def test_parse_empty_variants(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\nPython|tech||编程语言"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["variants"] == []

    def test_parse_multiple_variants(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\nKubernetes|tech|库伯尼特斯,酷伯,K8S|容器编排"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["variants"] == ["库伯尼特斯", "酷伯", "K8S"]

    def test_parse_skips_short_lines(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\nPython|tech|派森|编程语言\nbadline|tech|only three"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["term"] == "Python"

    def test_parse_empty_content(self):
        builder = VocabularyBuilder(_make_config())
        result = builder._parse_llm_response("")
        assert result == []

    def test_parse_header_only(self):
        builder = VocabularyBuilder(_make_config())
        result = builder._parse_llm_response("term|category|variants|context")
        assert result == []

    def test_parse_default_category(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\nPython||派森|编程语言"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["category"] == "other"

    def test_parse_skips_empty_term(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\n|tech|派森|编程语言\nPython|tech||编程语言"
        result = builder._parse_llm_response(content)
        assert len(result) == 1
        assert result[0]["term"] == "Python"

    def test_parse_skips_blank_lines(self):
        builder = VocabularyBuilder(_make_config())
        content = "term|category|variants|context\nPython|tech|派森|编程语言\n\nJava|tech|加瓦|编程语言"
        result = builder._parse_llm_response(content)
        assert len(result) == 2


class TestMergeEntries:
    def test_merge_new_entries(self):
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "Python", "category": "tech", "variants": ["派森"], "context": "编程语言", "frequency": 1}
        ]
        new = [
            {"term": "Java", "category": "tech", "variants": ["加瓦"], "context": "编程语言"}
        ]
        result = builder._merge_entries(existing, new)
        assert len(result) == 2
        terms = {e["term"] for e in result}
        assert terms == {"Python", "Java"}

    def test_merge_deduplicates_by_term(self):
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "Python", "variants": ["派森"], "frequency": 2}
        ]
        new = [
            {"term": "Python", "variants": ["拍森"], "context": ""}
        ]
        result = builder._merge_entries(existing, new)
        assert len(result) == 1
        entry = result[0]
        assert entry["term"] == "Python"
        assert set(entry["variants"]) == {"派森", "拍森"}
        assert entry["frequency"] == 3

    def test_merge_accumulates_frequency(self):
        builder = VocabularyBuilder(_make_config())
        existing = [{"term": "Python", "frequency": 5}]
        new = [{"term": "Python"}]
        result = builder._merge_entries(existing, new)
        assert result[0]["frequency"] == 6

    def test_merge_updates_empty_context(self):
        builder = VocabularyBuilder(_make_config())
        existing = [{"term": "Python", "context": "", "frequency": 1}]
        new = [{"term": "Python", "context": "编程语言"}]
        result = builder._merge_entries(existing, new)
        assert result[0]["context"] == "编程语言"

    def test_merge_keeps_existing_context(self):
        builder = VocabularyBuilder(_make_config())
        existing = [{"term": "Python", "context": "编程语言", "frequency": 1}]
        new = [{"term": "Python", "context": "脚本语言"}]
        result = builder._merge_entries(existing, new)
        assert result[0]["context"] == "编程语言"

    def test_merge_empty_existing(self):
        builder = VocabularyBuilder(_make_config())
        new = [{"term": "Python", "variants": ["派森"]}]
        result = builder._merge_entries([], new)
        assert len(result) == 1
        assert result[0]["frequency"] == 1

    def test_merge_empty_new(self):
        builder = VocabularyBuilder(_make_config())
        existing = [{"term": "Python", "frequency": 1}]
        result = builder._merge_entries(existing, [])
        assert len(result) == 1

    def test_merge_skips_empty_term(self):
        builder = VocabularyBuilder(_make_config())
        new = [{"term": "", "category": "tech"}, {"term": "Python"}]
        result = builder._merge_entries([], new)
        assert len(result) == 1
        assert result[0]["term"] == "Python"

    def test_merge_case_insensitive(self):
        """Entries differing only in case should be merged into one."""
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "python", "category": "tech", "variants": ["派森"], "context": "", "frequency": 2}
        ]
        new = [
            {"term": "Python", "category": "tech", "variants": ["拍森"], "context": "编程语言"}
        ]
        result = builder._merge_entries(existing, new)
        assert len(result) == 1
        entry = result[0]
        # Term form upgraded from all-lowercase to mixed-case
        assert entry["term"] == "Python"
        assert set(entry["variants"]) == {"派森", "拍森"}
        assert entry["frequency"] == 3
        # Context filled in from new entry since existing was empty
        assert entry["context"] == "编程语言"

    def test_merge_case_insensitive_keeps_existing_non_lowercase(self):
        """When existing term is already non-all-lowercase, keep it."""
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "GitHub", "variants": [], "frequency": 3}
        ]
        new = [
            {"term": "Github", "variants": ["git hub"]}
        ]
        result = builder._merge_entries(existing, new)
        assert len(result) == 1
        assert result[0]["term"] == "GitHub"
        assert result[0]["variants"] == ["git hub"]

    def test_merge_existing_internal_dedup(self):
        """Duplicate entries within existing list should be merged."""
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "python", "variants": ["派森"], "frequency": 2},
            {"term": "Python", "variants": ["拍森"], "context": "编程语言", "frequency": 3},
        ]
        result = builder._merge_entries(existing, [])
        assert len(result) == 1
        entry = result[0]
        assert entry["term"] == "Python"
        assert set(entry["variants"]) == {"派森", "拍森"}
        assert entry["frequency"] == 5
        assert entry["context"] == "编程语言"

    def test_merge_removes_self_referencing_variant(self):
        """Variants matching the term (case-insensitive) should be removed."""
        builder = VocabularyBuilder(_make_config())
        new = [
            {"term": "build", "variants": ["build", "Build", "bio"], "context": "开发操作"}
        ]
        result = builder._merge_entries([], new)
        assert len(result) == 1
        assert result[0]["variants"] == ["bio"]

    def test_merge_variant_case_insensitive_dedup(self):
        """Variants differing only in case should be deduplicated."""
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "Claude", "variants": ["Cloud", "cloud pipe"], "frequency": 1}
        ]
        new = [
            {"term": "claude", "variants": ["cloud", "CLOUD", "克劳德"]}
        ]
        result = builder._merge_entries(existing, new)
        assert len(result) == 1
        entry = result[0]
        assert entry["term"] == "Claude"
        # "Cloud" kept (first-seen), "cloud" and "CLOUD" deduped away
        assert "Cloud" in entry["variants"]
        assert "cloud pipe" in entry["variants"]
        assert "克劳德" in entry["variants"]
        assert len(entry["variants"]) == 3

    def test_merge_strips_variant_whitespace(self):
        """Variants with leading/trailing whitespace should be stripped."""
        builder = VocabularyBuilder(_make_config())
        new = [
            {"term": "Python", "variants": [" 派森 ", "  拍森"], "context": "编程语言"}
        ]
        result = builder._merge_entries([], new)
        assert set(result[0]["variants"]) == {"派森", "拍森"}

    def test_merge_skips_whitespace_only_term(self):
        """Terms that become empty after strip should be skipped."""
        builder = VocabularyBuilder(_make_config())
        new = [{"term": "  ", "category": "tech"}, {"term": "Python"}]
        result = builder._merge_entries([], new)
        assert len(result) == 1
        assert result[0]["term"] == "Python"

    def test_merge_filters_empty_variants_in_merge_path(self):
        """Empty/whitespace-only variants should be filtered during merge."""
        builder = VocabularyBuilder(_make_config())
        existing = [
            {"term": "Python", "variants": [" ", "派森", ""], "frequency": 1}
        ]
        new = [
            {"term": "python", "variants": ["  ", "拍森"]}
        ]
        result = builder._merge_entries(existing, new)
        assert len(result) == 1
        assert "" not in result[0]["variants"]
        assert " " not in result[0]["variants"]
        assert set(result[0]["variants"]) == {"派森", "拍森"}


class TestBuild:
    def test_build_no_records(self, tmp_path):
        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = asyncio.run(builder.build())
        assert result["new_records"] == 0

    def test_build_end_to_end(self, tmp_path):
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_TWO
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build())

        assert result["new_records"] == 3
        assert result["total_entries"] == 2

        # Verify vocabulary.json was written with built_at
        vocab_path = tmp_path / "vocabulary.json"
        assert vocab_path.exists()
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        assert len(data["entries"]) == 2
        assert "built_at" in data

    def test_build_incremental(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        existing = {
            "last_processed_timestamp": "2026-01-01T10:00:00+00:00",
            "entries": [
                {"term": "Python", "category": "tech", "variants": ["派森"], "context": "编程语言", "frequency": 1}
            ],
        }
        vocab_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")

        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_K8S
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build())

        assert result["new_records"] == 2
        assert result["total_entries"] == 2  # Python + Kubernetes

        # Verify built_at is present
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        assert "built_at" in data

    def test_build_full_rebuild(self, tmp_path):
        vocab_path = tmp_path / "vocabulary.json"
        existing = {
            "last_processed_timestamp": "2026-01-01T10:00:00+00:00",
            "entries": [
                {"term": "OldTerm", "category": "other", "variants": [], "context": "", "frequency": 1}
            ],
        }
        vocab_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")

        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(
                builder.build(full_rebuild=True)
            )

        assert result["new_records"] == 3
        assert result["total_entries"] == 2  # OldTerm + Python

        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        assert "built_at" in data


class TestBuildWithCancel:
    def test_cancel_after_first_batch(self, tmp_path):
        """Cancel event set after first batch - should save partial results."""
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = []
        for i in range(80):
            day = 1 + i // 24
            hour = i % 24
            records.append({
                "timestamp": f"2026-01-{day:02d}T{hour:02d}:00:00+00:00",
                "asr_text": f"test{i}",
                "final_text": f"test{i}",
                "user_corrected": True,
            })
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_TEST
        mock_response.usage = None

        cancel_event = threading.Event()
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                cancel_event.set()
            return mock_response

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(
                builder.build(cancel_event=cancel_event)
            )

        assert result.get("cancelled") is True
        assert result["new_entries"] == 1
        assert result["total_entries"] == 1
        assert (tmp_path / "vocabulary.json").exists()

    def test_cancel_before_any_batch(self, tmp_path):
        """Cancel event set before processing starts."""
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        cancel_event = threading.Event()
        cancel_event.set()

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = asyncio.run(
            builder.build(cancel_event=cancel_event)
        )

        assert result.get("cancelled") is True
        assert result["new_entries"] == 0


class _AsyncStreamMock:
    """Mock for OpenAI AsyncStream that supports async with and async for."""

    def __init__(self, items):
        self._items = iter(items)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


class TestExtractBatchStreaming:
    def test_streaming_collects_chunks(self):
        """on_stream_chunk should be called for each streamed chunk."""
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        pipe_parts = ["term|categ", "ory|variants|context\n", "Python|tech|派森|", "编程语言"]
        "".join(pipe_parts)

        chunks = []
        for part in pipe_parts:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = part
            chunk.usage = None
            chunks.append(chunk)

        async def mock_create(**kwargs):
            assert kwargs.get("stream") is True
            return _AsyncStreamMock(chunks)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        collected_chunks = []
        def on_chunk(c):
            return collected_chunks.append(c)

        entries, usage, text = asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client, on_stream_chunk=on_chunk)
        )

        assert collected_chunks == pipe_parts
        assert len(entries) == 1
        assert entries[0]["term"] == "Python"

    def test_cancel_interrupts_streaming(self):
        """cancel_event should interrupt streaming and return empty results."""
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        pipe_parts = ["term|categ", "ory|variants|context\n", "Python|tech|派森|", "编程语言"]

        cancel_event = threading.Event()
        chunks_received = []

        chunks = []
        for part in pipe_parts:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = part
            chunk.usage = None
            chunks.append(chunk)

        async def mock_create(**kwargs):
            return _AsyncStreamMock(chunks)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        def on_chunk(c):
            chunks_received.append(c)
            # Cancel after receiving the first chunk
            if len(chunks_received) == 1:
                cancel_event.set()

        entries, usage, text = asyncio.run(
            builder._extract_batch(
                messages, user_prompt, client=mock_client,
                on_stream_chunk=on_chunk, cancel_event=cancel_event,
            )
        )

        # Should have stopped early — got 1 chunk, then cancel was detected
        assert len(chunks_received) == 1
        assert entries == []
        assert text == ""

    def test_no_callback_uses_non_streaming(self):
        """Without on_stream_chunk, the non-streaming path is used."""
        builder = VocabularyBuilder(_make_config())
        user_prompt = "asr_text: test\nfinal_text: test"
        messages = _mock_messages()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        entries, usage, text = asyncio.run(
            builder._extract_batch(messages, user_prompt, client=mock_client)
        )

        create_call = mock_client.chat.completions.create
        create_call.assert_called_once()
        call_kwargs = create_call.call_args[1]
        assert "stream" not in call_kwargs

        assert len(entries) == 1
        assert entries[0]["term"] == "Python"


class TestBuildWithCallbacks:
    def test_callbacks_called_correctly(self, tmp_path):
        """Verify on_batch_start and on_batch_done are called for each batch."""
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = _sample_corrections()
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        pipe_content = _PIPE_RESPONSE_ONE

        stream_chunk = MagicMock()
        stream_chunk.choices = [MagicMock()]
        stream_chunk.choices[0].delta.content = pipe_content
        stream_chunk.usage = None

        async def mock_create(**kwargs):
            return _AsyncStreamMock([stream_chunk])

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        on_batch_start = MagicMock()
        on_batch_done = MagicMock()
        on_stream_chunk = MagicMock()

        callbacks = BuildCallbacks(
            on_batch_start=on_batch_start,
            on_batch_done=on_batch_done,
            on_stream_chunk=on_stream_chunk,
        )

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(
                builder.build(callbacks=callbacks)
            )

        on_batch_start.assert_called_once_with(1, 1)
        on_batch_done.assert_called_once_with(1, 1, 1)
        on_stream_chunk.assert_called_once_with(pipe_content)
        assert result["new_entries"] == 1


class TestBuildPrompts:
    def test_system_prompt_contains_instructions(self):
        builder = VocabularyBuilder(_make_config())
        prompt = builder._build_system_prompt([])
        assert "term|category|variants|context" in prompt
        assert "管道" in prompt
        assert "已存在" not in prompt  # No existing terms section when empty

    def test_system_prompt_includes_existing_terms(self):
        builder = VocabularyBuilder(_make_config())
        prompt = builder._build_system_prompt(["Python", "Kubernetes"])
        assert "已存在" in prompt
        assert "Python" in prompt
        assert "Kubernetes" in prompt

    def test_user_prompt_contains_records(self):
        batch = [
            {"asr_text": "派森", "final_text": "Python"},
            {"asr_text": "加瓦", "final_text": "Java"},
        ]
        prompt = VocabularyBuilder._build_user_prompt(batch)
        assert "派森" in prompt
        assert "Python" in prompt
        assert "加瓦" in prompt
        assert "Java" in prompt

    def test_user_prompt_replaces_newlines(self):
        """Newlines in text should be replaced with ⏎ to keep one record per line."""
        batch = [
            {"asr_text": "第一行\n第二行", "final_text": "first\nsecond"},
        ]
        prompt = VocabularyBuilder._build_user_prompt(batch)
        # Should be a single line with ⏎ instead of newlines
        assert "\n" not in prompt.split("→")[0].replace("\n", "")  # no raw newline in asr part
        assert "⏎" in prompt
        assert prompt == "第一行⏎第二行 → first⏎second"


class TestSaveLoadVocabulary:
    def test_save_and_load(self, tmp_path):
        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        vocab = {
            "last_processed_timestamp": "2026-01-01T00:00:00",
            "entries": [{"term": "Python", "category": "tech"}],
        }
        builder._save_vocabulary(vocab)

        loaded = builder._load_existing_vocabulary()
        assert loaded["entries"][0]["term"] == "Python"

    def test_load_nonexistent(self, tmp_path):
        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        result = builder._load_existing_vocabulary()
        assert result == {}


class TestBuildRetryAndAbort:
    def _write_corrections(self, tmp_path, count=80):
        corrections_path = tmp_path / "conversation_history.jsonl"
        records = []
        for i in range(count):
            day = 1 + i // 24
            hour = i % 24
            records.append({
                "timestamp": f"2026-01-{day:02d}T{hour:02d}:00:00+00:00",
                "asr_text": f"test{i}",
                "final_text": f"test{i}",
                "user_corrected": True,
            })
        with open(corrections_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return records

    def test_retry_succeeds_on_second_attempt(self, tmp_path):
        """First attempt fails, retry succeeds — batch results are kept."""
        self._write_corrections(tmp_path, count=5)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = None

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("server down")
            return mock_response

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build())

        assert result["new_entries"] == 1
        assert result.get("aborted") is None
        assert call_count == 2

    def test_abort_after_two_failures(self, tmp_path):
        """Both attempts fail — build aborts, no entries saved."""
        self._write_corrections(tmp_path, count=5)

        async def mock_create(**kwargs):
            raise ConnectionError("server down")

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build())

        assert result.get("aborted") is True
        assert result["new_entries"] == 0
        assert result["new_records"] == 0
        # vocabulary.json should NOT be created (no successful batch)
        assert not (tmp_path / "vocabulary.json").exists()

    def test_timestamp_not_advanced_on_abort(self, tmp_path):
        """Verify last_processed_timestamp is not advanced when build aborts."""
        self._write_corrections(tmp_path, count=5)

        # Pre-existing vocabulary with old timestamp
        vocab_path = tmp_path / "vocabulary.json"
        vocab_path.write_text(json.dumps({
            "last_processed_timestamp": "2025-01-01T00:00:00+00:00",
            "entries": [{"term": "OldTerm", "category": "other", "variants": [], "context": "", "frequency": 1}],
        }), encoding="utf-8")

        async def mock_create(**kwargs):
            raise ConnectionError("server down")

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build())

        assert result.get("aborted") is True
        # Timestamp should NOT have advanced
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        assert data["last_processed_timestamp"] == "2025-01-01T00:00:00+00:00"
        assert len(data["entries"]) == 1  # OldTerm still there

    def test_partial_progress_saved_on_abort(self, tmp_path):
        """First batch succeeds, second batch aborts — first batch is saved."""
        self._write_corrections(tmp_path, count=80)  # 2 batches of 60+20

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = None

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return mock_response
            # Fail on all subsequent attempts (batch 2 + retry)
            raise ConnectionError("server down")

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build())

        assert result.get("aborted") is True
        assert result["new_entries"] == 1  # from first batch
        assert result["new_records"] == 60  # first batch only

        # vocabulary.json should have first batch's results
        data = json.loads((tmp_path / "vocabulary.json").read_text(encoding="utf-8"))
        assert len(data["entries"]) == 1
        # Timestamp advanced to first batch's last record (index 59), not beyond
        assert data["last_processed_timestamp"] == "2026-01-03T11:00:00+00:00"

    def test_per_batch_save(self, tmp_path):
        """Each successful batch saves immediately to vocabulary.json."""
        self._write_corrections(tmp_path, count=80)  # 2 batches

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = None

        save_timestamps = []
        original_save = VocabularyBuilder._save_vocabulary

        def tracking_save(self_inner, vocab):
            save_timestamps.append(vocab["last_processed_timestamp"])
            original_save(self_inner, vocab)

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client), \
             patch.object(VocabularyBuilder, "_save_vocabulary", tracking_save):
            asyncio.run(builder.build())

        # Should have saved twice (once per batch)
        assert len(save_timestamps) == 2
        # First save covers batch 1 (records 0-59), second covers batch 2 (records 60-79)
        assert save_timestamps[0] == "2026-01-03T11:00:00+00:00"
        assert save_timestamps[1] == "2026-01-04T07:00:00+00:00"

    def test_batch_retry_callback(self, tmp_path):
        """on_batch_retry callback is called before retry."""
        self._write_corrections(tmp_path, count=5)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _PIPE_RESPONSE_ONE
        mock_response.usage = None

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("transient error")
            return mock_response

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = mock_create

        retry_calls = []
        callbacks = BuildCallbacks(
            on_batch_retry=lambda i, t: retry_calls.append((i, t)),
        )

        builder = VocabularyBuilder(_make_config(), data_dir=str(tmp_path))
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(builder.build(callbacks=callbacks))

        assert len(retry_calls) == 1
        assert retry_calls[0] == (1, 1)
        assert result["new_entries"] == 1


class TestBuildModelSelection:
    def _make_multi_provider_config(self, **vocab_overrides):
        cfg = {
            "default_provider": "ollama",
            "default_model": "qwen2.5:7b",
            "providers": {
                "ollama": {
                    "base_url": "http://localhost:11434/v1",
                    "api_key": "ollama",
                    "models": ["qwen2.5:7b"],
                },
                "openai": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-test",
                    "models": ["gpt-4o", "gpt-4o-mini"],
                },
            },
            "vocabulary": vocab_overrides,
        }
        return cfg

    def test_default_uses_enhance_model(self):
        """Without build_provider/model, uses default_provider/model."""
        cfg = self._make_multi_provider_config()
        builder = VocabularyBuilder(cfg)
        pcfg = builder._get_provider_config()
        assert pcfg["model"] == "qwen2.5:7b"
        assert pcfg["base_url"] == "http://localhost:11434/v1"
        assert builder._get_active_provider_name() == "ollama"

    def test_build_model_overrides_default(self):
        """build_provider/model overrides the default."""
        cfg = self._make_multi_provider_config(
            build_provider="openai", build_model="gpt-4o",
        )
        builder = VocabularyBuilder(cfg)
        pcfg = builder._get_provider_config()
        assert pcfg["model"] == "gpt-4o"
        assert pcfg["base_url"] == "https://api.openai.com/v1"
        assert pcfg["api_key"] == "sk-test"
        assert builder._get_active_provider_name() == "openai"

    def test_empty_build_model_falls_back(self):
        """Empty build_provider/model falls back to default."""
        cfg = self._make_multi_provider_config(
            build_provider="", build_model="",
        )
        builder = VocabularyBuilder(cfg)
        pcfg = builder._get_provider_config()
        assert pcfg["model"] == "qwen2.5:7b"
        assert builder._get_active_provider_name() == "ollama"

    def test_partial_build_config_falls_back(self):
        """Only build_provider set (no build_model) falls back to default."""
        cfg = self._make_multi_provider_config(
            build_provider="openai", build_model="",
        )
        builder = VocabularyBuilder(cfg)
        pcfg = builder._get_provider_config()
        # Should fall back to default, not use openai with wrong model
        assert pcfg["model"] == "qwen2.5:7b"
        assert builder._get_active_provider_name() == "ollama"

    def test_removed_provider_falls_back(self):
        """build_provider pointing to non-existent provider falls back."""
        cfg = self._make_multi_provider_config(
            build_provider="removed", build_model="some-model",
        )
        builder = VocabularyBuilder(cfg)
        pcfg = builder._get_provider_config()
        assert pcfg["model"] == "qwen2.5:7b"
        assert builder._get_active_provider_name() == "ollama"

    def test_build_model_not_in_provider_list(self):
        """build_model not in provider's model list falls back to first model."""
        cfg = self._make_multi_provider_config(
            build_provider="openai", build_model="nonexistent-model",
        )
        builder = VocabularyBuilder(cfg)
        pcfg = builder._get_provider_config()
        # Provider is openai (valid), but model falls back to first in list
        assert pcfg["base_url"] == "https://api.openai.com/v1"
        assert pcfg["model"] == "gpt-4o"
