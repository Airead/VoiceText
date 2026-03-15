# Conversation History Enhancement

## Background

VoiceText processes each voice input session independently — the AI enhancement step sees only the current ASR text and has no knowledge of what the user said before. This stateless approach works for isolated sentences but falls short when:

1. **Recurring proper nouns** — The user mentions "萍萍" in one sentence, but ASR transcribes it as "平平". Without prior context, the LLM has no basis to prefer one over the other. If the user already confirmed "萍萍" in a previous turn, that signal is lost.
2. **Topic continuity** — Conversations naturally build on prior context. When the user says "她说今天很开心", the LLM cannot resolve "她" without knowing who was mentioned earlier.
3. **User expression patterns** — Some users consistently use specific phrasing, punctuation styles, or sentence structures. A stateless enhancer cannot adapt to these preferences.

## Motivation

The core insight: **the user's recent confirmed outputs are the highest-quality signal for what they actually mean**.

Unlike raw ASR text (which contains errors) or AI-enhanced text (which may over-correct), the final confirmed output represents the user's true intent — they have reviewed and approved it. By feeding these confirmed outputs back into the enhancement prompt, we give the LLM a running context window that enables:

- **Consistent entity resolution** — Once "平平 → 萍萍" is confirmed, subsequent mentions of "平平" can be correctly resolved.
- **Topic-aware enhancement** — The LLM understands the current conversation topic and can make contextually appropriate decisions.
- **Style adaptation** — The LLM observes how the user actually writes and can match their tone and formatting preferences.

## How It Works

### Recording

Every voice input session is recorded to `~/.config/VoiceText/conversation_history.jsonl`, regardless of mode:

```json
{
    "timestamp": "2026-03-12T10:30:00+00:00",
    "asr_text": "果果今天在公园里遇到了平平。",
    "enhanced_text": "果果今天在公园里遇到了平平。",
    "final_text": "果果今天在公园里遇到了萍萍。",
    "enhance_mode": "proofread",
    "preview_enabled": true,
    "stt_model": "funasr-paraformer",
    "llm_model": "qwen2.5:7b",
    "user_corrected": true,
    "audio_duration": 3.2
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC timestamp of the session |
| `asr_text` | string | Raw ASR transcription |
| `enhanced_text` | string | AI-enhanced text (before user review) |
| `final_text` | string | Final confirmed text |
| `enhance_mode` | string | Enhancement mode (`proofread`, `translate`, etc.) |
| `preview_enabled` | bool | Whether preview mode was active |
| `stt_model` | string | STT model identifier |
| `llm_model` | string | LLM model identifier |
| `user_corrected` | bool | Whether the user edited the enhanced text |
| `audio_duration` | float | Recording duration in seconds, rounded to 0.1s |

The `audio_duration` field tracks how long the user spoke for each session. This value is also aggregated in usage statistics via `record_recording_duration()`.

Both direct mode (`preview_enabled: false`) and preview mode (`preview_enabled: true`) sessions are recorded. This ensures no data is lost, even if the injection policy changes later.

### Filtering: Why Only Preview-Confirmed Records

Only records with `preview_enabled: true` are injected into the AI prompt. The reasoning:

- **Preview mode** — The user sees the AI output, can edit it, and explicitly confirms the final text. This confirmed text is reliable.
- **Direct mode** — Text is typed immediately without review. The user never validated the output, so it may contain uncorrected ASR errors or AI over-corrections. Injecting unverified text would propagate errors.

This is a deliberate data quality decision: **a smaller set of verified data is more valuable than a larger set of unverified data**.

### Context Injection

When conversation history is enabled, the enhancement prompt is augmented with recent history. The format is designed to be token-efficient:

```
---
以下是用户近期的对话记录，用于学习纠错偏好和话题上下文。
若 ASR 识别与最终确认不同则用→分隔（识别→确认），相同则表示无需纠错：

- 将是否开启对话历史注入的功能，做一个开关放在菜单栏里。
- 现在测试一下历史上下文注入的功能。
- 果果今天在公园里遇到了平平。 → 果果今天在公园里遇到了萍萍。
- 平平对果果说我今天吃了面条。 → 萍萍对果果说我今天吃了面条。
---
```

Key design choices for the prompt format:

- **One line per entry** — Minimizes token usage.
- **Arrow notation for corrections** — Only shown when ASR and final text differ, making correction patterns immediately visible to the LLM.
- **No arrow when identical** — Avoids redundant repetition of the same text.
- **Only ASR + final text** — The AI-enhanced intermediate text is omitted from injection to save tokens. The LLM only needs to see what the user actually said (ASR) and what they actually meant (final).

### Integration with Other Context Sources

Conversation history is injected into the system prompt **after** vocabulary context, following the same pattern:

```
[Mode prompt]                    ← base enhancement instructions
[Vocabulary context]             ← relevant terms from user's vocabulary (if enabled)
[Conversation history context]   ← recent confirmed outputs (if enabled)
```

Each context source is independently toggleable and gracefully degrades — if history retrieval fails, enhancement proceeds without it.

## Storage and Archiving

### Auto-Rotation

The main history file (`conversation_history.jsonl`) is kept bounded by an automatic rotation mechanism. After each `log()` call, the system checks whether rotation is needed:

1. **Size pre-check** -- If the file is smaller than 4 MB, rotation is skipped entirely (cheap guard to avoid counting lines on every write).
2. **Record count check** -- If the file exceeds **20,000 records** (`_MAX_RECORDS`), the oldest records beyond this limit are archived.

### Monthly Archives

Rotated records are grouped by the month in their `timestamp` field and appended to per-month archive files:

```
~/.config/VoiceText/
├── conversation_history.jsonl                  # Active file (up to 20,000 records)
└── conversation_history_archives/
    ├── 2025-11.jsonl
    ├── 2025-12.jsonl
    └── 2026-01.jsonl
```

Each archive file is named `YYYY-MM.jsonl` and contains all records from that month. Records whose timestamp cannot be parsed are placed in `unknown.jsonl`. Archives are append-only -- subsequent rotations add to existing month files rather than overwriting them.

After archiving, the main file is atomically replaced (via a temp file + `os.replace()`) with only the most recent 20,000 records, and all in-memory caches are invalidated.

### Browsing Archived Records

The History Browser provides an **"Include archived"** toggle. When enabled, `get_all()` and `search()` load records from all archive files (sorted chronologically by filename) and prepend them to the active records. This allows users to search and browse their full history without the active file growing unbounded.

## In-Memory Cache

To avoid repeated disk reads, `ConversationHistory` maintains a two-tier cache:

| Cache | Size | Purpose | Populated |
|---|---|---|---|
| Hot-path (`_cache`) | Last 200 records | Serves `get_recent()` for context injection | Lazily on first `get_recent()` call |
| Full (`_full_cache`) | All records in the active file | Serves `get_all()` and `search()` for the History Browser | Lazily on first `get_all()`/`search()` call |

**Hot-path cache** -- Stores the most recent 200 raw (unfiltered) records. Updated in-place by `log()`, `update_record()`, and `delete_record()`. Since context injection typically needs only 10 entries filtered from the tail, 200 cached records provide ample headroom without loading the entire file.

**Full cache** -- Stores all parsed records from the active JSONL file. Staleness is detected by comparing the file's `mtime` -- if the file has been modified externally, the cache is reloaded on the next access. Callers should call `release_full_cache()` when the data is no longer needed (e.g., when the History Browser window is closed) to free memory promptly.

Both caches are fully invalidated after a rotation event.

## History Browser Pagination

The web-based History Browser (`history_browser_window_web.py`) displays records in pages of **100 entries** (`PAGE_SIZE = 100`). The Python backend computes total pages from the filtered record count and sends only the current page's records to the WKWebView frontend. The frontend renders a pager with previous/next navigation and a "Page X / Y" indicator.

Pagination is reset to page 0 whenever the search query, time filter, or archive toggle changes.

## Architecture

```
Voice Input
     │
     ▼
┌──────────┐     ┌───────────────────────────────────┐
│ ASR      │────►│ conversation_history.jsonl         │
└──────────┘     │  (up to 20,000 records)            │
     │           └────────┬──────────────┬────────────┘
     │                    │              │ _maybe_rotate()
     │                    │              ▼
     │                    │   ┌──────────────────────────┐
     │                    │   │ archives/YYYY-MM.jsonl    │
     │                    │   │ (monthly, append-only)    │
     │                    │   └──────────────────────────┘
     ▼                    │
┌──────────┐              │ get_recent(n=10)
│ Enhancer │◄─────────────┘ filter: preview_enabled=true
│          │                via hot-path cache (200 records)
│ system_prompt = base_prompt      │
│            + vocab_context       │
│            + history_context ◄───┘
│          │
│          │──► LLM ──► enhanced text
└──────────┘
     │
     ▼
┌──────────────────┐
│ Preview Panel    │──► user confirms ──► type_text
│ (preview mode)   │                        │
└──────────────────┘                        ▼
                                   log(preview_enabled=true,
                                        audio_duration=N.Ns)
```

## Configuration

In `config.json` under `ai_enhance`:

```json
{
    "conversation_history": {
        "enabled": false,
        "max_entries": 10
    }
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Toggle conversation history injection |
| `max_entries` | int | `10` | Maximum number of recent entries to inject |

The toggle is also available in the **Settings** panel (AI tab).

## Key Files

| File | Purpose |
|---|---|
| `src/voicetext/enhance/conversation_history.py` | JSONL recording, reading, caching, rotation, archiving, and prompt formatting |
| `src/voicetext/enhance/enhancer.py` | Integrates history context into enhancement prompts |
| `src/voicetext/ui/history_browser_window_web.py` | Web-based History Browser with pagination and archive toggle |
| `src/voicetext/usage_stats.py` | Aggregates `audio_duration` via `record_recording_duration()` |
| `src/voicetext/app.py` | Records sessions in both output paths; menu toggle |
| `src/voicetext/config.py` | Default configuration for conversation history |
