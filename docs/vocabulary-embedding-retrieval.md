# Vocabulary Embedding Retrieval

## Background

闻字 uses LLM to correct ASR (Automatic Speech Recognition) output. ASR engines frequently misrecognize proper nouns, technical terms, and domain-specific vocabulary — replacing them with phonetically similar but incorrect characters. For example, "Kubernetes" might be transcribed as "库伯尼特斯" or "酷伯", and "Python" as "派森".

A generic LLM has no knowledge of the user's personal vocabulary. Without additional context, it cannot reliably distinguish between a correct transcription and a misrecognized proper noun. This leads to two types of errors:

1. **Missed corrections** — the LLM leaves ASR errors in place because it doesn't recognize the intended term.
2. **Wrong corrections** — the LLM "corrects" a term to something plausible but incorrect, because it lacks domain context.

## Motivation

The core idea is: **if we can tell the LLM which specific terms the user frequently uses, it can make much better correction decisions**.

Rather than dumping an entire vocabulary list into every prompt (which would be noisy and waste tokens), we use **embedding-based semantic retrieval** to find only the vocabulary entries relevant to the current input text. This approach is essentially a lightweight, local RAG (Retrieval-Augmented Generation) pipeline.

## How It Works

The system consists of two stages: **vocabulary building** and **real-time retrieval**.

### Stage 1: Vocabulary Building

闻字 logs every user correction in `conversation_history.jsonl` — entries where the user edited the AI-enhanced text in the preview panel are marked with `user_corrected: true`. The vocabulary builder leverages these records:

1. Read corrected records from `conversation_history.jsonl` (supports incremental builds via timestamp filtering).
2. Batch records and send them to an LLM with a structured extraction prompt.
3. The LLM identifies proper nouns, technical terms, and frequently misrecognized words, returning structured entries with:
   - `term` — the correct form of the word
   - `category` — classification (tech, name, place, domain, other)
   - `variants` — common ASR misrecognitions (phonetic variants)
   - `context` — brief description for disambiguation
4. Merge new entries with existing vocabulary, deduplicating by term and accumulating frequency counts.
5. Save the result as `vocabulary.json`.

### Stage 2: Embedding Index Construction

Once `vocabulary.json` exists, the `VocabularyIndex` builds an embedding index:

1. Load vocabulary entries from `vocabulary.json`.
2. For each entry, generate embedding vectors for:
   - The term itself (e.g., "Kubernetes")
   - Each known variant (e.g., "库伯尼特斯", "酷伯")
   - A combined context string (e.g., "容器编排 Kubernetes")
3. Store all vectors in a numpy array, with a mapping from vector index back to vocabulary entry index.
4. Cache the index as `vocabulary_index.npz` for fast loading. Rebuild automatically when `vocabulary.json` is newer than the cached index.

The embedding model used is `paraphrase-multilingual-MiniLM-L12-v2` (via fastembed), chosen for:
- Multilingual support (Chinese + English in the same embedding space)
- Small size (~120MB), suitable for local execution
- Good quality for semantic similarity tasks

### Stage 3: Real-Time Retrieval During Enhancement

When the user triggers text enhancement:

1. Embed the input ASR text using the same model.
2. Compute cosine similarity between the query vector and all vocabulary vectors.
3. Rank results, deduplicate by entry (since each entry may have multiple vectors), and return the top-K entries (default: 5).
4. Format the matched entries into a structured prompt section and append it to the system prompt.

The injected prompt section looks like:

```
---
以下是用户词库中与本次输入相关的专有名词，ASR 常将其误写为同音近音词。
仅当输入中确实存在对应误写时才替换，不要强行套用：

- Kubernetes（容器编排）
- Python（编程语言）
---
```

This gives the LLM precise, relevant vocabulary context for each specific input, without overwhelming it with the entire vocabulary.

## Why Embedding Retrieval Instead of Alternatives

| Approach | Pros | Cons |
|---|---|---|
| **Full vocabulary in prompt** | Simple | Wastes tokens, noisy, hits context limits |
| **Keyword matching** | Fast, no model needed | Misses phonetic variants, no semantic understanding |
| **Embedding retrieval** | Semantic matching catches variants, scales well, token-efficient | Requires embedding model, initial build time |

The embedding approach is particularly effective for this use case because:

- ASR errors are often **phonetically similar** but **orthographically different** — embeddings in multilingual models capture phonetic/semantic proximity that keyword matching cannot.
- The vocabulary grows over time as the user makes more corrections, and retrieval naturally scales without increasing prompt size.
- Running the embedding model locally (via fastembed) avoids additional API costs and latency.

## Architecture Diagram

```
conversation_history.jsonl (user_corrected entries)
       │
       ▼
┌─────────────────┐     LLM extraction      ┌──────────────────┐
│ VocabularyBuilder│ ──────────────────────► │ vocabulary.json   │
└─────────────────┘                          └────────┬─────────┘
                                                      │
                                                      ▼
                                             ┌──────────────────┐
                                             │ VocabularyIndex   │
                                             │  (fastembed +     │
                                             │   numpy cosine)   │
                                             └────────┬─────────┘
                                                      │
                                                      ▼
                                             vocabulary_index.npz
                                                      │
                    ASR text ──► embed ──► retrieve ──┘
                                                      │
                                                      ▼
                                             matched entries
                                                      │
                                                      ▼
                                    ┌─────────────────────────────┐
                                    │ TextEnhancer                │
                                    │  system_prompt + vocab_ctx  │──► LLM ──► corrected text
                                    └─────────────────────────────┘
```

## Configuration

In `config.json` under `ai_enhance`:

```json
{
    "vocabulary": {
        "enabled": false,
        "top_k": 5,
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "build_timeout": 600,
        "auto_build": true,
        "auto_build_threshold": 10
    }
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Toggle vocabulary retrieval during enhancement |
| `top_k` | int | `5` | Number of entries to retrieve per query |
| `embedding_model` | string | `"paraphrase-multilingual-MiniLM-L12-v2"` | Embedding model for vocabulary index |
| `build_timeout` | int | `600` | Per-batch LLM timeout in seconds |
| `auto_build` | bool | `true` | Enable automatic vocabulary building after corrections accumulate |
| `auto_build_threshold` | int | `10` | Number of corrections to trigger an automatic build |

## Key Files

| File | Purpose |
|---|---|
| `src/wenzi/enhance/vocabulary_builder.py` | Extracts vocabulary from conversation history corrections via LLM |
| `src/wenzi/enhance/vocabulary.py` | Embedding index construction and retrieval |
| `src/wenzi/enhance/auto_vocab_builder.py` | Automatic vocabulary building triggered by correction count |
| `src/wenzi/enhance/enhancer.py` | Integrates vocabulary context into enhancement prompts |
| `src/wenzi/ui/vocab_build_window.py` | UI for vocabulary build progress |
| `src/wenzi/app.py` | Menu items for vocabulary toggle and build trigger |
| `src/wenzi/config.py` | Default configuration for vocabulary settings |
