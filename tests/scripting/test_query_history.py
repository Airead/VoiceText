"""Tests for QueryHistory — chooser query recall."""

import json
import os

from wenzi.scripting.sources.query_history import QueryHistory


class TestBasicRecordAndEntries:
    def test_record_and_entries(self, tmp_path):
        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)
        h.record("safari")
        h.record("chrome")
        h.record("firefox")
        assert h.entries() == ["firefox", "chrome", "safari"]

    def test_dedup_moves_to_front(self, tmp_path):
        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)
        h.record("safari")
        h.record("chrome")
        h.record("safari")
        # safari re-recorded → newest
        assert h.entries() == ["safari", "chrome"]

    def test_max_entries(self, tmp_path):
        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)
        for i in range(120):
            h.record(f"query{i}")
        entries = h.entries()
        assert len(entries) == 100
        # Most recent should be first
        assert entries[0] == "query119"
        # Oldest kept should be query20
        assert entries[-1] == "query20"

    def test_empty_query_ignored(self, tmp_path):
        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)
        h.record("")
        h.record("   ")
        h.record(None)  # type: ignore[arg-type]
        assert h.entries() == []

    def test_entries_empty_initially(self, tmp_path):
        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)
        assert h.entries() == []


class TestPersistence:
    def test_flush_and_reload(self, tmp_path):
        path = str(tmp_path / "history.json")
        h1 = QueryHistory(path=path)
        h1.record("alpha")
        h1.record("beta")
        h1.flush_sync()

        h2 = QueryHistory(path=path)
        assert h2.entries() == ["beta", "alpha"]

    def test_file_not_exists(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        h = QueryHistory(path=path)
        assert h.entries() == []

    def test_corrupt_file(self, tmp_path):
        path = str(tmp_path / "history.json")
        with open(path, "w") as f:
            f.write("not valid json{{{")
        h = QueryHistory(path=path)
        # Should not crash, just return empty
        assert h.entries() == []

    def test_wrong_type_in_file(self, tmp_path):
        path = str(tmp_path / "history.json")
        with open(path, "w") as f:
            json.dump({"not": "a list"}, f)
        h = QueryHistory(path=path)
        assert h.entries() == []

    def test_filters_non_string_entries(self, tmp_path):
        path = str(tmp_path / "history.json")
        with open(path, "w") as f:
            json.dump(["valid", 123, None, "", "also valid"], f)
        h = QueryHistory(path=path)
        assert h.entries() == ["also valid", "valid"]

    def test_creates_parent_directory(self, tmp_path):
        path = str(tmp_path / "sub" / "dir" / "history.json")
        h = QueryHistory(path=path)
        h.record("test")
        h.flush_sync()
        assert os.path.isfile(path)


class TestClear:
    def test_clear(self, tmp_path):
        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)
        h.record("a")
        h.record("b")
        h.clear()
        assert h.entries() == []

    def test_clear_persists(self, tmp_path):
        path = str(tmp_path / "history.json")
        h1 = QueryHistory(path=path)
        h1.record("a")
        h1.flush_sync()
        h1.clear()
        h1.flush_sync()

        h2 = QueryHistory(path=path)
        assert h2.entries() == []


class TestThreadSafety:
    def test_concurrent_records(self, tmp_path):
        import threading

        path = str(tmp_path / "history.json")
        h = QueryHistory(path=path)

        def writer(start):
            for i in range(50):
                h.record(f"t{start}-q{i}")

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = h.entries()
        # Should have at most 100 entries
        assert len(entries) <= 100
        # All entries should be valid strings
        assert all(isinstance(e, str) for e in entries)
