# 对话历史增强

## 背景

VoiceText 对每次语音输入会话进行独立处理——AI 增强步骤只能看到当前的 ASR 文本，对用户之前说过的内容一无所知。这种无状态的方式在处理孤立句子时效果尚可，但在以下场景中存在不足：

1. **反复出现的专有名词** — 用户在某句话中提到"萍萍"，但 ASR 将其识别为"平平"。没有先前上下文，LLM 没有依据判断哪个更正确。如果用户在之前的轮次中已确认了"萍萍"，这一信号就丢失了。
2. **话题连续性** — 对话天然地建立在之前的上下文之上。当用户说"她说今天很开心"时，LLM 无法在不知道之前提到过谁的情况下解析"她"的指代。
3. **用户表达习惯** — 有些用户会持续使用特定的措辞、标点风格或句式结构。无状态的增强器无法适应这些偏好。

## 动机

核心洞察：**用户近期确认的输出是反映其真实意图的最高质量信号**。

与原始 ASR 文本（包含错误）或 AI 增强文本（可能过度纠正）不同，最终确认的输出代表了用户的真实意图——他们已经审阅并批准了它。将这些确认的输出反馈到增强提示词中，我们给 LLM 提供了一个滚动的上下文窗口，使其能够：

- **一致的实体解析** — 一旦"平平 → 萍萍"被确认，后续出现的"平平"就能被正确解析。
- **话题感知增强** — LLM 理解当前的对话主题，能做出符合上下文的决策。
- **风格适配** — LLM 观察用户的实际写作方式，匹配其语气和格式偏好。

## 工作原理

### 记录

每次语音输入会话都会记录到 `~/.config/VoiceText/conversation_history.jsonl`，不区分模式：

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

| 字段 | 类型 | 说明 |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC 时间戳 |
| `asr_text` | string | 原始 ASR 识别文本 |
| `enhanced_text` | string | AI 增强后的文本（用户审阅前） |
| `final_text` | string | 最终确认的文本 |
| `enhance_mode` | string | 增强模式（`proofread`、`translate` 等） |
| `preview_enabled` | bool | 是否启用了预览模式 |
| `stt_model` | string | STT 模型标识 |
| `llm_model` | string | LLM 模型标识 |
| `user_corrected` | bool | 用户是否编辑了增强文本 |
| `audio_duration` | float | 录音时长（秒），精确到 0.1 秒 |

`audio_duration` 字段记录了每次会话中用户的语音时长。该值同时通过 `record_recording_duration()` 汇总到使用统计中。

直接模式（`preview_enabled: false`）和预览模式（`preview_enabled: true`）的会话都会被记录。这确保不会丢失任何数据，即使后续注入策略发生变化。

### 过滤：为何仅使用预览确认的记录

只有 `preview_enabled: true` 的记录会被注入到 AI 提示词中。原因如下：

- **预览模式** — 用户看到 AI 输出，可以编辑并明确确认最终文本。这个确认后的文本是可靠的。
- **直接模式** — 文本直接输入，未经审阅。用户从未验证过输出，因此可能包含未纠正的 ASR 错误或 AI 过度纠正。注入未经验证的文本会导致错误传播。

这是一个有意为之的数据质量决策：**一组较小的已验证数据比一组较大的未验证数据更有价值**。

### 上下文注入

当对话历史功能启用时，增强提示词会附加近期历史。格式设计旨在高效利用 token：

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

提示词格式的关键设计选择：

- **每条记录一行** — 最大程度减少 token 用量。
- **箭头标注纠正** — 仅在 ASR 文本和最终文本不同时显示，使纠正模式对 LLM 一目了然。
- **相同时不显示箭头** — 避免重复展示相同的文本。
- **仅包含 ASR + 最终文本** — AI 增强的中间文本不会被注入，以节省 token。LLM 只需看到用户实际说了什么（ASR）和实际想表达什么（最终文本）。

### 与其他上下文源的集成

对话历史在系统提示词中注入于词汇上下文**之后**，遵循相同的模式：

```
[Mode prompt]                    ← 基础增强指令
[Vocabulary context]             ← 来自用户词汇表的相关术语（如已启用）
[Conversation history context]   ← 近期确认的输出（如已启用）
```

每个上下文源都可独立开关，并能优雅降级——如果历史记录获取失败，增强过程将在没有它的情况下继续进行。

## 存储与归档

### 自动轮转

主历史文件（`conversation_history.jsonl`）通过自动轮转机制保持有界。每次 `log()` 调用后，系统会检查是否需要轮转：

1. **文件大小预检** — 如果文件小于 4 MB，则完全跳过轮转（廉价的前置检查，避免每次写入都计算行数）。
2. **记录数检查** — 如果文件超过 **20,000 条记录**（`_MAX_RECORDS`），超出限制的最旧记录将被归档。

### 按月归档

轮转出的记录按其 `timestamp` 字段中的月份分组，追加到按月命名的归档文件中：

```
~/.config/VoiceText/
├── conversation_history.jsonl                  # 活跃文件（最多 20,000 条记录）
└── conversation_history_archives/
    ├── 2025-11.jsonl
    ├── 2025-12.jsonl
    └── 2026-01.jsonl
```

每个归档文件命名为 `YYYY-MM.jsonl`，包含该月的所有记录。无法解析时间戳的记录会被放入 `unknown.jsonl`。归档文件仅追加——后续轮转会向已有的月份文件追加内容，而非覆盖。

归档完成后，主文件通过临时文件 + `os.replace()` 原子替换，仅保留最近的 20,000 条记录，同时所有内存缓存被清除。

### 浏览归档记录

历史浏览器提供了**"包含归档"**开关。启用后，`get_all()` 和 `search()` 会加载所有归档文件中的记录（按文件名时间排序），并将其置于活跃记录之前。这使用户能够搜索和浏览完整历史，同时保持活跃文件不会无限增长。

## 内存缓存

为避免重复的磁盘读取，`ConversationHistory` 维护两级缓存：

| 缓存 | 大小 | 用途 | 填充时机 |
|---|---|---|---|
| 热路径（`_cache`） | 最近 200 条记录 | 为 `get_recent()` 提供上下文注入服务 | 首次 `get_recent()` 调用时惰性加载 |
| 完整缓存（`_full_cache`） | 活跃文件全部记录 | 为历史浏览器的 `get_all()` 和 `search()` 服务 | 首次 `get_all()`/`search()` 调用时惰性加载 |

**热路径缓存** — 存储最近 200 条原始（未过滤）记录。由 `log()`、`update_record()` 和 `delete_record()` 就地更新。由于上下文注入通常只需从尾部过滤出 10 条记录，200 条缓存提供了充足的余量，无需加载整个文件。

**完整缓存** — 存储活跃 JSONL 文件中所有已解析的记录。通过比较文件的 `mtime` 检测过期——如果文件被外部修改，下次访问时会重新加载。调用方应在不再需要数据时调用 `release_full_cache()`（例如关闭历史浏览器窗口时）以及时释放内存。

轮转事件后，两级缓存均被完全清除。

## 历史浏览器分页

基于 Web 的历史浏览器（`history_browser_window_web.py`）以每页 **100 条记录**（`PAGE_SIZE = 100`）的方式显示。Python 后端根据过滤后的记录总数计算总页数，仅将当前页的记录发送给 WKWebView 前端。前端渲染分页器，提供上一页/下一页导航和"第 X / Y 页"指示器。

当搜索关键词、时间过滤器或归档开关发生变化时，分页会重置到第 0 页。

## 架构

```
Voice Input
     │
     ▼
┌──────────┐     ┌───────────────────────────────────┐
│ ASR      │────►│ conversation_history.jsonl         │
└──────────┘     │  （最多 20,000 条记录）               │
     │           └────────┬──────────────┬────────────┘
     │                    │              │ _maybe_rotate()
     │                    │              ▼
     │                    │   ┌──────────────────────────┐
     │                    │   │ archives/YYYY-MM.jsonl    │
     │                    │   │ （按月归档，仅追加）         │
     │                    │   └──────────────────────────┘
     ▼                    │
┌──────────┐              │ get_recent(n=10)
│ Enhancer │◄─────────────┘ filter: preview_enabled=true
│          │                经由热路径缓存（200 条记录）
│ system_prompt = base_prompt      │
│            + vocab_context       │
│            + history_context ◄───┘
│          │
│          │──► LLM ──► enhanced text
└──────────┘
     │
     ▼
┌──────────────────┐
│ Preview Panel    │──► 用户确认 ──► type_text
│ (预览模式)        │                  │
└──────────────────┘                  ▼
                                 log(preview_enabled=true,
                                      audio_duration=N.Ns)
```

## 配置

在 `config.json` 的 `ai_enhance` 下：

```json
{
    "conversation_history": {
        "enabled": false,
        "max_entries": 10
    }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 开关对话历史注入功能 |
| `max_entries` | int | `10` | 注入的最大近期记录数 |

该开关也可在 **Settings** 面板（AI 标签页）中使用。

## 关键文件

| 文件 | 用途 |
|---|---|
| `src/voicetext/enhance/conversation_history.py` | JSONL 记录、读取、缓存、轮转、归档及提示词格式化 |
| `src/voicetext/enhance/enhancer.py` | 将历史上下文集成到增强提示词中 |
| `src/voicetext/ui/history_browser_window_web.py` | 基于 Web 的历史浏览器，支持分页和归档开关 |
| `src/voicetext/usage_stats.py` | 通过 `record_recording_duration()` 汇总 `audio_duration` |
| `src/voicetext/app.py` | 在两个输出路径中记录会话；菜单开关 |
| `src/voicetext/config.py` | 对话历史的默认配置 |
