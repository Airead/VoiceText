"""End-to-end test for vocabulary embedding retrieval.

Run: uv run python debug_scripts/test_embedding.py
"""

import logging
import sys
import time

sys.path.insert(0, "src")

from wenzi.vocabulary import VocabularyIndex

logging.basicConfig(level=logging.INFO, format="%(message)s")

config = {
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
}

print("=" * 60)
print("Vocabulary Embedding E2E Test")
print("=" * 60)

# 1. Load index
print("\n[1] Loading vocabulary index...")
t0 = time.time()
idx = VocabularyIndex(config)
ok = idx.load()
t1 = time.time()

if not ok:
    print("FAIL: Could not load vocabulary. Check ~/.config/WenZi/vocabulary.json")
    sys.exit(1)

print(f"  Loaded in {t1-t0:.2f}s")
print(f"  Entries: {len(idx._entries)}")
print(f"  Vectors: {idx._vectors.shape if idx._vectors is not None else 'None'}")

# 2. Test queries - mix of exact terms, variants, and semantic queries
test_queries = [
    "agent proxy",       # exact term
    "edient proxy",      # variant (ASR misrecognition)
    "果果",              # exact name
    "波郭",              # variant of 果果
    "编程开发软件",       # semantic: should match tech terms
    "公园里面的景点",     # semantic: should match place terms
    "木神迹这本书",       # variant of 牧神记
    "键盘快捷键操作",     # semantic: should match shift+回车
    "小朋友看的表演",     # semantic: should match 儿童剧场 or 葫芦兄弟
]

print("\n[2] Running retrieval queries...")
print("-" * 60)

for query in test_queries:
    t0 = time.time()
    results = idx.retrieve(query, top_k=3)
    elapsed = (time.time() - t0) * 1000

    print(f"\nQuery: \"{query}\"  ({elapsed:.1f}ms)")
    if results:
        for i, entry in enumerate(results, 1):
            print(f"  {i}. {entry.term} [{entry.category}] "
                  f"variants={entry.variants} context={entry.context}")
    else:
        print("  (no results)")

# 3. Test prompt formatting
print("\n" + "-" * 60)
print("\n[3] Prompt format example:")
results = idx.retrieve("开发软件", top_k=5)
prompt = idx.format_for_prompt(results)
print(prompt if prompt else "(empty)")

print("\n" + "=" * 60)
print("Done!")
