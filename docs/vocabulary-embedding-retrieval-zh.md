# 词库嵌入检索

## 背景

闻字 使用 LLM 对 ASR（自动语音识别）的输出进行纠错。ASR 引擎经常会将专有名词、技术术语和领域特定词汇识别错误——将其替换为发音相似但不正确的字符。例如，"Kubernetes" 可能被转录为"库伯尼特斯"或"酷伯"，"Python" 可能被转录为"派森"。

通用 LLM 并不了解用户的个人词库。如果没有额外的上下文信息，它无法可靠地区分正确的转录和被误识别的专有名词。这会导致两类错误：

1. **漏纠** — LLM 没有纠正 ASR 错误，因为它无法识别用户实际想表达的术语。
2. **误纠** — LLM 将术语"纠正"为看似合理但实际错误的内容，因为它缺乏领域上下文。

## 动机

核心思路是：**如果我们能告诉 LLM 用户常用的具体术语，它就能做出更好的纠正决策**。

与其将整个词库列表塞入每次提示词中（这样既嘈杂又浪费 token），我们使用**基于嵌入的语义检索**来找到与当前输入文本相关的词库条目。这种方法本质上是一个轻量级的本地 RAG（检索增强生成）管线。

## 工作原理

系统由两个阶段组成：**词库构建**和**实时检索**。

### 阶段一：词库构建

闻字 在 `conversation_history.jsonl` 中记录用户的每次修改——当用户在预览面板中编辑了 AI 增强后的文本时，对应的记录会被标记为 `user_corrected: true`。词库构建器利用这些记录：

1. 从 `conversation_history.jsonl` 中读取已修改的记录（支持通过时间戳过滤进行增量构建）。
2. 将记录分批发送给 LLM，附带结构化提取提示词。
3. LLM 识别专有名词、技术术语和常被误识别的词汇，返回包含以下字段的结构化条目：
   - `term` — 词汇的正确形式
   - `category` — 分类（tech、name、place、domain、other）
   - `variants` — 常见的 ASR 误识别形式（同音/近音变体）
   - `context` — 用于消歧的简短描述
4. 将新条目与现有词库合并，按 term 去重并累计频次。
5. 将结果保存为 `vocabulary.json`。

### 阶段二：嵌入索引构建

`vocabulary.json` 准备就绪后，`VocabularyIndex` 会构建嵌入索引：

1. 从 `vocabulary.json` 加载词库条目。
2. 为每个条目生成嵌入向量，包括：
   - 术语本身（例如 "Kubernetes"）
   - 每个已知变体（例如 "库伯尼特斯"、"酷伯"）
   - 组合上下文字符串（例如 "容器编排 Kubernetes"）
3. 将所有向量存储在 numpy 数组中，并维护从向量索引到词库条目索引的映射。
4. 将索引缓存为 `vocabulary_index.npz` 以便快速加载。当 `vocabulary.json` 比缓存索引更新时，自动重建索引。

使用的嵌入模型是 `paraphrase-multilingual-MiniLM-L12-v2`（通过 fastembed），选择该模型的原因：
- 多语言支持（中文和英文在同一嵌入空间）
- 体积小（约 120MB），适合本地运行
- 在语义相似度任务上表现良好

### 阶段三：增强过程中的实时检索

当用户触发文本增强时：

1. 使用相同的模型对输入的 ASR 文本进行嵌入。
2. 计算查询向量与所有词库向量之间的余弦相似度。
3. 对结果排序，按条目去重（因为每个条目可能有多个向量），返回 top-K 条目（默认：5）。
4. 将匹配的条目格式化为结构化提示词片段，附加到系统提示词中。

注入的提示词片段如下：

```
---
以下是用户词库中与本次输入相关的专有名词，ASR 常将其误写为同音近音词。
仅当输入中确实存在对应误写时才替换，不要强行套用：

- Kubernetes（容器编排）
- Python（编程语言）
---
```

这样可以为每次具体的输入提供精确且相关的词库上下文，而不会用整个词库去干扰 LLM。

## 为什么选择嵌入检索而非其他方案

| 方案 | 优点 | 缺点 |
|---|---|---|
| **完整词库放入提示词** | 实现简单 | 浪费 token，噪声大，容易超出上下文限制 |
| **关键词匹配** | 速度快，无需模型 | 无法捕获同音变体，缺乏语义理解 |
| **嵌入检索** | 语义匹配能捕获变体，扩展性好，token 高效 | 需要嵌入模型，有初始构建时间 |

嵌入检索方案对此场景特别有效，原因如下：

- ASR 错误通常是**发音相似**但**书写不同**的——多语言模型中的嵌入能够捕捉到关键词匹配无法识别的语音/语义相近性。
- 随着用户做出更多修改，词库会持续增长，而检索方式可以自然扩展，不会增加提示词长度。
- 在本地运行嵌入模型（通过 fastembed）可以避免额外的 API 成本和延迟。

## 架构图

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

## 配置

在 `config.json` 的 `ai_enhance` 下：

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

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 在增强过程中是否启用词库检索 |
| `top_k` | int | `5` | 每次查询检索的条目数 |
| `embedding_model` | string | `"paraphrase-multilingual-MiniLM-L12-v2"` | 词库索引使用的嵌入模型 |
| `build_timeout` | int | `600` | 每批次 LLM 超时时间（秒） |
| `auto_build` | bool | `true` | 当修改次数累积到阈值时，是否自动构建词库 |
| `auto_build_threshold` | int | `10` | 触发自动构建的修改次数 |

## 关键文件

| 文件 | 用途 |
|---|---|
| `src/wenzi/enhance/vocabulary_builder.py` | 通过 LLM 从对话历史修改记录中提取词库 |
| `src/wenzi/enhance/vocabulary.py` | 嵌入索引的构建与检索 |
| `src/wenzi/enhance/auto_vocab_builder.py` | 基于修改计数触发的自动词库构建 |
| `src/wenzi/enhance/enhancer.py` | 将词库上下文集成到增强提示词中 |
| `src/wenzi/ui/vocab_build_window.py` | 词库构建进度的 UI 界面 |
| `src/wenzi/app.py` | 词库开关和构建触发的菜单项 |
| `src/wenzi/config.py` | 词库设置的默认配置 |
