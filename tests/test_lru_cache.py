"""Tests for LRU cache module."""

import pytest

from wenzi.lru_cache import LRUCache


class TestLRUCacheBasic:
    def test_set_and_get(self):
        cache = LRUCache(maxsize=10)
        cache["a"] = 1
        assert cache["a"] == 1

    def test_get_missing_returns_default(self):
        cache = LRUCache(maxsize=10)
        assert cache.get("missing") is None
        assert cache.get("missing", 42) == 42

    def test_contains(self):
        cache = LRUCache(maxsize=10)
        cache["a"] = 1
        assert "a" in cache
        assert "b" not in cache

    def test_clear(self):
        cache = LRUCache(maxsize=10)
        cache["a"] = 1
        cache["b"] = 2
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None

    def test_len(self):
        cache = LRUCache(maxsize=10)
        cache["a"] = 1
        cache["b"] = 2
        assert len(cache) == 2

    def test_update_existing_key(self):
        cache = LRUCache(maxsize=10)
        cache["a"] = 1
        cache["a"] = 2
        assert cache["a"] == 2
        assert len(cache) == 1

    def test_delete(self):
        cache = LRUCache(maxsize=10)
        cache["a"] = 1
        del cache["a"]
        assert "a" not in cache


class TestLRUCacheEviction:
    def test_evicts_oldest_when_full(self):
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        cache["d"] = 4  # should evict "a"
        assert "a" not in cache
        assert len(cache) == 3
        assert cache["b"] == 2
        assert cache["d"] == 4

    def test_get_promotes_to_mru(self):
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        # Access "a" to promote it
        _ = cache["a"]
        cache["d"] = 4  # should evict "b" (now the LRU)
        assert "a" in cache
        assert "b" not in cache
        assert "c" in cache
        assert "d" in cache

    def test_set_existing_promotes_to_mru(self):
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        # Update "a" to promote it
        cache["a"] = 10
        cache["d"] = 4  # should evict "b"
        assert "a" in cache
        assert cache["a"] == 10
        assert "b" not in cache

    def test_eviction_order(self):
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        cache["d"] = 4  # evicts a
        cache["e"] = 5  # evicts b
        cache["f"] = 6  # evicts c
        assert list(cache.keys()) == ["d", "e", "f"]

    def test_maxsize_one(self):
        cache = LRUCache(maxsize=1)
        cache["a"] = 1
        cache["b"] = 2
        assert len(cache) == 1
        assert "a" not in cache
        assert cache["b"] == 2

    def test_get_default_does_not_promote(self):
        """Getting a missing key should not affect cache order."""
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        cache.get("missing", None)
        cache["d"] = 4  # should evict "a"
        assert "a" not in cache
        assert "b" in cache


class TestLRUCacheValidation:
    def test_maxsize_zero_raises(self):
        with pytest.raises(ValueError, match="maxsize must be >= 1"):
            LRUCache(maxsize=0)

    def test_maxsize_negative_raises(self):
        with pytest.raises(ValueError, match="maxsize must be >= 1"):
            LRUCache(maxsize=-1)

    def test_maxsize_property(self):
        cache = LRUCache(maxsize=42)
        assert cache.maxsize == 42


class TestLRUCacheWithTupleKeys:
    """Test with tuple keys to match enhance cache usage pattern."""

    def test_tuple_keys(self):
        cache = LRUCache(maxsize=5)
        key1 = ("proofread", "ollama", "qwen2.5:7b", False)
        key2 = ("translate", "ollama", "qwen2.5:7b", False)
        cache[key1] = "result1"
        cache[key2] = "result2"
        assert cache[key1] == "result1"
        assert cache[key2] == "result2"

    def test_tuple_key_eviction(self):
        cache = LRUCache(maxsize=2)
        k1 = ("mode1", "p1", "m1", False)
        k2 = ("mode2", "p1", "m1", False)
        k3 = ("mode3", "p1", "m1", False)
        cache[k1] = "r1"
        cache[k2] = "r2"
        cache[k3] = "r3"  # evicts k1
        assert k1 not in cache
        assert cache.get(k2) == "r2"
        assert cache.get(k3) == "r3"
