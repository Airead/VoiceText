"""Tests for CorrectionTracker: SQLite schema and word-level diff extraction."""

import sqlite3

from wenzi.enhance.correction_tracker import CorrectionTracker, extract_word_pairs


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


def test_init_creates_tables(tmp_path):
    db_path = str(tmp_path / "tracker.db")
    tracker = CorrectionTracker(db_path=db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "correction_sessions" in tables
    assert "correction_pairs" in tables
    conn.close()


def test_init_sets_schema_version(tmp_path):
    db_path = str(tmp_path / "tracker.db")
    CorrectionTracker(db_path=db_path)
    conn = sqlite3.connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    conn.close()


def test_init_enables_foreign_keys(tmp_path):
    db_path = str(tmp_path / "tracker.db")
    tracker = CorrectionTracker(db_path=db_path)
    conn = tracker._get_conn()
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


# ---------------------------------------------------------------------------
# extract_word_pairs
# ---------------------------------------------------------------------------


def test_extract_simple_replace():
    pairs = extract_word_pairs("我在用cloud做开发", "我在用claude做开发")
    assert ("cloud", "claude") in pairs


def test_extract_cjk_grouped():
    pairs = extract_word_pairs("我在用库伯尼特斯做编排", "我在用Kubernetes做编排")
    assert ("库伯尼特斯", "Kubernetes") in pairs


def test_extract_latin_space_restored():
    pairs = extract_word_pairs("use boys test app", "use VoiceText app")
    assert any("VoiceText" in p[1] for p in pairs)


def test_extract_skip_large_replace():
    a = "一二三四五六七八九十壹贰"
    b = "ABCDEFGHIJKLMN"
    pairs = extract_word_pairs(a, b, max_replace_tokens=8)
    assert len(pairs) == 0


def test_extract_identical_texts():
    pairs = extract_word_pairs("hello world", "hello world")
    assert pairs == []
