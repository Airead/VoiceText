"""Tests for cc_sessions.reader module."""

from __future__ import annotations

import json
from pathlib import Path

from cc_sessions.reader import read_session_detail


class TestReadSessionDetail:
    """Test read_session_detail function."""

    def _write_jsonl(self, path: Path, lines: list[dict]) -> Path:
        path.write_text("\n".join(json.dumps(item) for item in lines) + "\n")
        return path

    def test_extracts_conversation_turns(self, tmp_path: Path):
        """Reads first N user+assistant turn pairs."""
        jsonl = self._write_jsonl(tmp_path / "s1.jsonl", [
            {"type": "system", "timestamp": "2026-01-01T00:00:00Z", "cwd": "/tmp"},
            {"type": "user", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "user", "content": "Hello"}},
            {"type": "assistant", "timestamp": "2026-01-01T00:00:02Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}],
                         "usage": {"input_tokens": 100, "output_tokens": 50}}},
            {"type": "user", "timestamp": "2026-01-01T00:00:03Z",
             "message": {"role": "user", "content": "How are you?"}},
            {"type": "assistant", "timestamp": "2026-01-01T00:00:04Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "I'm good!"}],
                         "usage": {"input_tokens": 200, "output_tokens": 80}}},
        ])
        detail = read_session_detail(jsonl, max_turns=6)
        assert len(detail["turns"]) == 4  # 2 user + 2 assistant
        assert detail["turns"][0] == {"role": "user", "text": "Hello"}
        assert detail["turns"][1] == {"role": "assistant", "text": "Hi there!"}

    def test_limits_turns(self, tmp_path: Path):
        """Only returns up to max_turns messages."""
        lines = [{"type": "system", "timestamp": "2026-01-01T00:00:00Z"}]
        for i in range(10):
            lines.append({"type": "user", "timestamp": f"2026-01-01T00:0{i}:01Z",
                          "message": {"role": "user", "content": f"Q{i}"}})
            lines.append({"type": "assistant", "timestamp": f"2026-01-01T00:0{i}:02Z",
                          "message": {"role": "assistant", "content": [{"type": "text", "text": f"A{i}"}],
                                      "usage": {"input_tokens": 10, "output_tokens": 5}}})
        jsonl = self._write_jsonl(tmp_path / "long.jsonl", lines)
        detail = read_session_detail(jsonl, max_turns=4)
        assert len(detail["turns"]) == 4

    def test_sums_token_usage(self, tmp_path: Path):
        """Sums input_tokens and output_tokens across all assistant messages."""
        jsonl = self._write_jsonl(tmp_path / "tokens.jsonl", [
            {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "A"}],
                         "usage": {"input_tokens": 100, "output_tokens": 50}}},
            {"type": "assistant", "timestamp": "2026-01-01T00:00:02Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "B"}],
                         "usage": {"input_tokens": 200, "output_tokens": 80}}},
        ])
        detail = read_session_detail(jsonl)
        assert detail["total_input_tokens"] == 300
        assert detail["total_output_tokens"] == 130

    def test_truncates_long_messages(self, tmp_path: Path):
        """Assistant messages longer than 200 chars are truncated."""
        long_text = "A" * 500
        jsonl = self._write_jsonl(tmp_path / "long_msg.jsonl", [
            {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": long_text}],
                         "usage": {"input_tokens": 10, "output_tokens": 5}}},
        ])
        detail = read_session_detail(jsonl, max_turns=6)
        assert len(detail["turns"][0]["text"]) <= 203  # 200 + "..."

    def test_handles_missing_file(self, tmp_path: Path):
        """Returns empty detail for nonexistent file."""
        detail = read_session_detail(tmp_path / "nope.jsonl")
        assert detail["turns"] == []
        assert detail["total_input_tokens"] == 0
        assert detail["total_output_tokens"] == 0

    def test_handles_string_content(self, tmp_path: Path):
        """Handles assistant messages where content is a plain string."""
        jsonl = self._write_jsonl(tmp_path / "str.jsonl", [
            {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "assistant", "content": "Plain text response",
                         "usage": {"input_tokens": 10, "output_tokens": 5}}},
        ])
        detail = read_session_detail(jsonl, max_turns=6)
        assert detail["turns"][0]["text"] == "Plain text response"

    def test_skips_tool_use_and_thinking(self, tmp_path: Path):
        """Filters out tool_use and thinking content parts, keeps only text."""
        jsonl = self._write_jsonl(tmp_path / "tools.jsonl", [
            {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "assistant", "content": [
                 {"type": "thinking", "thinking": "Let me think..."},
                 {"type": "text", "text": "Here is the answer"},
                 {"type": "tool_use", "name": "Read", "input": {}},
             ], "usage": {"input_tokens": 10, "output_tokens": 5}}},
        ])
        detail = read_session_detail(jsonl, max_turns=6)
        assert detail["turns"][0]["text"] == "Here is the answer"

    def test_user_content_parts_list(self, tmp_path: Path):
        """Handles user messages where content is a list of parts."""
        jsonl = self._write_jsonl(tmp_path / "parts.jsonl", [
            {"type": "user", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "user", "content": [
                 {"type": "text", "text": "Part one"},
                 {"type": "text", "text": "Part two"},
             ]}},
        ])
        detail = read_session_detail(jsonl, max_turns=6)
        assert detail["turns"][0]["text"] == "Part one Part two"

    def test_skips_noise_user_messages(self, tmp_path: Path):
        """Skips system-injected noise messages in conversation turns."""
        jsonl = self._write_jsonl(tmp_path / "cleared.jsonl", [
            {"type": "user", "timestamp": "2026-01-01T00:00:00Z",
             "message": {"role": "user",
                         "content": "<local-command-caveat>Caveat: noise</local-command-caveat>"}},
            {"type": "user", "timestamp": "2026-01-01T00:00:01Z",
             "message": {"role": "user",
                         "content": "<command-name>/clear</command-name>"}},
            {"type": "user", "timestamp": "2026-01-01T00:00:02Z",
             "message": {"role": "user", "content": "The real question"}},
            {"type": "assistant", "timestamp": "2026-01-01T00:00:03Z",
             "message": {"role": "assistant",
                         "content": [{"type": "text", "text": "The answer"}],
                         "usage": {"input_tokens": 10, "output_tokens": 5}}},
        ])
        detail = read_session_detail(jsonl, max_turns=6)
        assert len(detail["turns"]) == 2
        assert detail["turns"][0] == {"role": "user", "text": "The real question"}
        assert detail["turns"][1] == {"role": "assistant", "text": "The answer"}
