# 词库命中追踪设计

## 背景

当前词库系统使用单一的 `hit_count` / `last_hit` 来记录词条命中，语义不清：

- 无法区分是 ASR 热词生效还是 LLM 纠正的功劳
- ASR 热词真正生效的场景（ASR 直接输出正确形式）完全检测不到
- 无法为 ASR 和 LLM 的注入排序提供有效依据

## 四维追踪模型

将原有的单一 `hit_count` 拆分为四个独立维度：

| 维度 | 含义 | 检测条件 |
|------|------|---------|
| `asr_miss` | ASR 输出了错误形式（variant） | `variant in asr_text` |
| `asr_hit` | ASR 输出了正确形式（term） | `term in asr_text`（且 variant 不在 asr_text 中） |
| `llm_hit` | LLM 增强后包含正确形式 | `variant in asr_text AND term in enhanced_text` |
| `llm_miss` | LLM 增强后仍未纠正 | `variant in asr_text AND term NOT in enhanced_text` |

### 维度间关系

- `asr_miss` 与 `asr_hit` **互斥**：同一词条在单次识别中只计其一（忽略同时出现的罕见情况）
- `llm_hit` 与 `llm_miss` **互斥**，且**仅在 `asr_miss` 时才计数**（ASR 已正确则无需 LLM 纠正）
- 恒等式：`asr_miss_count = llm_hit_count + llm_miss_count`

## 全场景枚举

以词库中一个词条 `variant → term` 为例，列举所有可能情况：

| # | 注入ASR | 注入LLM | ASR含variant | ASR含term | 增强含term | asr_miss | asr_hit | llm_hit | llm_miss |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| 2 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 3 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 4 | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| 5 | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 6 | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 7 | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 8 | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 9 | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 10 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 11 | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| 12 | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| 13 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 场景说明

- **#1, #4**: ASR 热词生效，直接输出正确形式。当前系统检测不到此场景。
- **#2, #7**: 标准纠正路径——ASR 出错，LLM 兜底成功。
- **#3, #8**: ASR 和 LLM 都失败，该词最迫切需要 ASR 热词注入。
- **#5, #9**: LLM 没有从词库注入获得帮助，但凭自身能力纠正成功。仍记为 `llm_hit`，表示"该词条的纠正在最终结果中实现了"。
- **#11, #12**: 词未注入 ASR，但 ASR 自身就能正确识别。`asr_hit` 提供了"ASR 自身能力"的正向证据。

## 存储方案：SQLite 两张表

当前使用 JSON 文件存储，随着四维追踪 + 上下文分桶的引入，数据结构变复杂。迁移到 SQLite 的理由：

- 记录命中只需一条 UPSERT，无需全量重写文件
- 注入选词时通过索引直取 top-N，无需全表扫描
- 按上下文维度查询和聚合由 SQL 原生支持
- 项目中 ClipboardMonitor 已使用 SQLite，不引入新依赖

### 表结构

```sql
-- 词条主表
CREATE TABLE vocab_entry (
    id            INTEGER PRIMARY KEY,
    term          TEXT NOT NULL,
    variant       TEXT NOT NULL,
    source        TEXT NOT NULL,          -- 'asr' | 'llm' | 'user'
    frequency     INTEGER DEFAULT 1,
    first_seen    TEXT NOT NULL,
    last_updated  TEXT NOT NULL,
    app_bundle_id TEXT DEFAULT '',
    asr_model     TEXT DEFAULT '',
    llm_model     TEXT DEFAULT '',
    enhance_mode  TEXT DEFAULT '',
    UNIQUE(term, variant)
);

-- 分桶统计表
CREATE TABLE vocab_stats (
    entry_id    INTEGER NOT NULL REFERENCES vocab_entry(id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,            -- 'asr_miss' | 'asr_hit' | 'llm_hit' | 'llm_miss'
    context_key TEXT NOT NULL,            -- 'asr:whisper-large-v3' | 'app:com.apple.dt.Xcode' | ...
    count       INTEGER DEFAULT 0,
    last_time   TEXT DEFAULT '',
    PRIMARY KEY (entry_id, metric, context_key)
);

-- 注入排序索引（覆盖查询，按 count 降序直取 top-N）
CREATE INDEX idx_stats_rank ON vocab_stats(metric, context_key, count DESC);
```

### 上下文桶键格式

| 上下文维度 | 桶键格式 | 示例 |
|-----------|---------|------|
| ASR 模型 | `asr:<model_name>` | `asr:whisper-large-v3-turbo` |
| LLM 模型 | `llm:<model_name>` | `llm:gpt-4o` |
| 应用程序 | `app:<bundle_id>` | `app:com.apple.dt.Xcode` |

每次记录事件时，同时写入对应的模型桶和 App 桶。一次事件最多更新 2 个桶（阶段一：asr + app；阶段二：llm + app）。

### 典型查询

```sql
-- ASR 热词选词：按某模型的 asr_miss 排序取 top-N（走 idx_stats_rank 索引）
SELECT e.term, e.variant, s.count
FROM vocab_stats s
JOIN vocab_entry e ON e.id = s.entry_id
WHERE s.metric = 'asr_miss' AND s.context_key = 'asr:whisper-large-v3'
ORDER BY s.count DESC
LIMIT 10;

-- LLM 词库选词：按某模型的 llm_hit 排序取 top-N
SELECT e.term, e.variant, s.count
FROM vocab_stats s
JOIN vocab_entry e ON e.id = s.entry_id
WHERE s.metric = 'llm_hit' AND s.context_key = 'llm:gpt-4o'
ORDER BY s.count DESC
LIMIT 5;

-- 某词条的全部分桶统计（用于详情面板）
SELECT metric, context_key, count, last_time
FROM vocab_stats
WHERE entry_id = ?
ORDER BY metric, count DESC;

-- 某词条在某模型下的全局 asr_miss 汇总
SELECT SUM(count) FROM vocab_stats
WHERE entry_id = ? AND metric = 'asr_miss' AND context_key LIKE 'asr:%';

-- 记录一次命中（UPSERT）
INSERT INTO vocab_stats (entry_id, metric, context_key, count, last_time)
VALUES (?, 'asr_miss', 'asr:whisper-large-v3', 1, '2026-03-28T10:30:00')
ON CONFLICT(entry_id, metric, context_key)
DO UPDATE SET count = count + 1, last_time = excluded.last_time;
```


## 检测逻辑

检测分两个阶段执行。每次记录时携带当前上下文（asr_model, llm_model, app_bundle_id），通过 UPSERT 写入对应的桶。

### 阶段一：ASR 输出后（LLM 增强前）

对词库中**所有词条**扫描（不限于已注入的词条）：

```python
# 构建当前上下文桶键（跳过空值）
context_keys = []
if asr_model:
    context_keys.append(f"asr:{asr_model}")
if app_bundle_id:
    context_keys.append(f"app:{app_bundle_id}")

asr_miss_entries = []

for entry in all_entries:
    if entry.variant.lower() in asr_text_lower:
        # ASR 输出了错误形式
        for key in context_keys:
            UPSERT vocab_stats (entry.id, 'asr_miss', key)
        asr_miss_entries.append(entry)
    elif entry.term.lower() in asr_text_lower:
        # ASR 输出了正确形式
        for key in context_keys:
            UPSERT vocab_stats (entry.id, 'asr_hit', key)
```

将 asr_miss 检测提前到 LLM 增强前，确保即使词条未注入 LLM 词库，ASR 的失误也能被记录。

### 阶段二：LLM 增强后

对阶段一中标记为 asr_miss 的词条：

```python
# 构建当前上下文桶键（跳过空值）
context_keys = []
if llm_model:
    context_keys.append(f"llm:{llm_model}")
if app_bundle_id:
    context_keys.append(f"app:{app_bundle_id}")

for entry in asr_miss_entries:
    if entry.term.lower() in enhanced_text_lower:
        # LLM 成功纠正
        for key in context_keys:
            UPSERT vocab_stats (entry.id, 'llm_hit', key)
    else:
        # LLM 未能纠正
        for key in context_keys:
            UPSERT vocab_stats (entry.id, 'llm_miss', key)
```

### 上下文桶写入规则

- 阶段一（ASR 维度）：写入 `asr:<model>` 桶和 `app:<bundle_id>` 桶
- 阶段二（LLM 维度）：写入 `llm:<model>` 桶和 `app:<bundle_id>` 桶
- 如果某个上下文为空（如 app_bundle_id 未知），则跳过该桶，不写入
- 所有写入在一个 SQLite 事务中完成，保证原子性

## 驱动注入排序（预期用法）

| 计数 | 高值含义 | 驱动决策 |
|------|---------|---------|
| `asr_miss` 高 | ASR 经常在这个词上出错 | 优先注入 ASR 热词 |
| `asr_hit` 高 | ASR 自身就能正确识别 | 可降低 ASR 注入优先级，把名额让给更需要的词 |
| `llm_hit` 高 | LLM 经常能纠正这个词 | 优先注入 LLM 词库 |
| `llm_miss` 高 | LLM 经常纠正不了 | LLM 注入价值低，更依赖 ASR 热词 |

### 冷启动回退策略

当指定桶查不到足够结果时（如使用新模型、新 App），按以下顺序回退补位：

```
1. 指定桶查询：WHERE context_key = 'asr:new-model' → 得到 N 条
2. 全局汇总补位（N < max_count 时）：
   SELECT entry_id, SUM(count) as total
   FROM vocab_stats
   WHERE metric = 'asr_miss' AND entry_id NOT IN (已选)
   GROUP BY entry_id
   ORDER BY total DESC
   LIMIT (max_count - N)
3. 兜底补位（全局也不够时）：
   从 vocab_entry 中按 last_updated DESC 补位，排除已选词条
```

三层保证任何情况下都能选满 top-N：指定上下文优先 → 全局统计次之 → 最近更新兜底。

LLM 词库选词同理，metric 从 `asr_miss` 换为 `llm_hit`。

### 组合判断示例

- **asr_miss 高 + llm_miss 高**：ASR 和 LLM 都搞不定，最迫切需要 ASR 热词注入
- **asr_miss 高 + llm_hit 高**：ASR 常出错但 LLM 能兜底，ASR 注入有价值但不最紧急
- **asr_hit 高 + asr_miss 低**：ASR 表现稳定，可降低注入优先级
- **asr_hit / (asr_hit + asr_miss) 比率**：衡量 ASR 对该词的自身识别能力

## UI 设计

采用**方案 A：表格总览 + 展开详情**，在表格主视图中保持简洁，详情面板展示完整分桶数据。

### 表格主视图

将现有的 `Hit Count` 列替换为两列紧凑展示：

| 列名 | 格式 | 含义 | 示例 |
|------|------|------|------|
| ASR | `miss/total` | ASR miss 次数 / 总出现次数 | `3/15` = miss 3 次，hit 12 次 |
| LLM | `hit/total` | LLM 纠正次数 / 需纠正总次数 | `2/3` = 纠正 2 次，未纠正 1 次 |

- 当选择了筛选条件（ASR Model / App 等）时，数字**联动切换**为对应桶的计数
- 未选筛选时显示全局汇总值
- 两列均可排序（按 miss count 或 hit count 排序）

### 展开详情面板

点击某个词条行展开，显示完整的分桶统计：

```
┌─ 详情：variant → term ─────────────────────────────┐
│                                                      │
│  ASR 识别统计                                         │
│  ┌──────────────────────┬───────┬───────┬──────────┐ │
│  │ 上下文               │ Miss  │ Hit   │ 最近     │ │
│  ├──────────────────────┼───────┼───────┼──────────┤ │
│  │ whisper-large-v3     │ 12    │ 3     │ 2h ago   │ │
│  │ sherpa-paraformer    │ 3     │ 18    │ 1d ago   │ │
│  │ Xcode                │ 8     │ 5     │ 2h ago   │ │
│  │ VS Code              │ 7     │ 16    │ 3d ago   │ │
│  └──────────────────────┴───────┴───────┴──────────┘ │
│                                                      │
│  LLM 纠正统计                                         │
│  ┌──────────────────────┬───────┬───────┬──────────┐ │
│  │ 上下文               │ Hit   │ Miss  │ 最近     │ │
│  ├──────────────────────┼───────┼───────┼──────────┤ │
│  │ gpt-4o               │ 10    │ 1     │ 2h ago   │ │
│  │ claude-3.5-sonnet    │ 4     │ 0     │ 5d ago   │ │
│  │ Xcode                │ 8     │ 0     │ 2h ago   │ │
│  │ VS Code              │ 6     │ 1     │ 3d ago   │ │
│  └──────────────────────┴───────┴───────┴──────────┘ │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 筛选联动

现有的标签筛选（Source / App / ASR Model）扩展行为：

- **选择 ASR Model 筛选**：表格中 ASR 列的数字切换为该模型桶的计数
- **选择 App 筛选**：ASR 列和 LLM 列的数字都切换为该 App 桶的计数
- **多个筛选同时选择**：取交集桶（如同时选了 whisper + Xcode，需要两个桶都有数据才显示）
- **无筛选**：显示全局汇总（所有桶求和）

## 注意事项

- 检测使用子串匹配（`variant.lower() in text.lower()`），短 variant 可能产生误匹配。应结合"过滤过短 variant"的优化一起实施。
- 切换增强模式时的 display-only 逻辑需同步调整，确保不重复计数。
- 四个维度的排序权重和具体算法待后续根据实际数据调优。
- 分桶粒度下单个桶内样本量可能较小，排序算法需考虑样本量不足时的处理（如回退到全局汇总）。
