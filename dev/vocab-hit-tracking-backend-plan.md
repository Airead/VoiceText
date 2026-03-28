# 词库命中追踪 — 后端实现计划

基于 `dev/vocab-hit-tracking-design.md` 设计文档的后端实现。

## 目标

1. 将词库存储从 JSON 文件迁移到 SQLite
2. 实现四维命中追踪（asr_miss / asr_hit / llm_hit / llm_miss）+ 按上下文分桶
3. 改造注入选词逻辑，基于分桶统计排序
4. 改造命中检测逻辑，分两阶段记录

## 步骤

### 第 1 步：创建 SQLite 存储层

**文件**：新建 `src/wenzi/enhance/vocab_db.py`

创建 `VocabDB` 类，封装 SQLite 操作：

- `__init__(path: str)` — 打开数据库连接，启用 WAL 模式和外键约束，调用 `_ensure_tables()`
- `_ensure_tables()` — 创建 `vocab_entry` 和 `vocab_stats` 表及索引（`CREATE TABLE IF NOT EXISTS`）
- `close()` — 关闭连接

CRUD 方法（对应现有 `ManualVocabularyStore` 的接口）：

- `add(variant, term, source, **kwargs) -> dict` — INSERT OR 更新 frequency
- `remove(variant, term) -> bool` — DELETE，CASCADE 自动清理 stats
- `remove_batch(pairs) -> int` — 批量删除
- `get(variant, term) -> Optional[dict]`
- `contains(variant, term) -> bool`
- `get_all() -> list[dict]`
- `entry_count -> int`

统计方法：

- `record_stats(entries: list[tuple[int, str, str]])` — 批量 UPSERT vocab_stats，参数为 `[(entry_id, metric, context_key), ...]`
- `get_stats(entry_id: int) -> list[dict]` — 取某词条全部分桶统计
- `get_stats_summary(entry_id: int, metric: str) -> int` — 某词条某维度全局汇总

排序查询方法：

- `top_by_metric(metric, context_key, limit) -> list[dict]` — 按某桶某维度取 top-N（走 idx_stats_rank 索引），支持冷启动回退（见下方）

**测试**：新建 `tests/enhance/test_vocab_db.py`

- 测试建表、CRUD、UPSERT stats、top_by_metric 排序、CASCADE 删除、并发写入
- 所有测试使用 `tmp_path` 下的 SQLite 文件

### 第 2 步：改造 ManualVocabularyStore

**文件**：修改 `src/wenzi/enhance/manual_vocabulary.py`

将内部存储从 `dict[tuple, ManualVocabEntry]` + JSON 文件改为委托给 `VocabDB`：

- `__init__(path)` — path 改为 `.db` 后缀，内部创建 `VocabDB` 实例
- 移除 `self._entries` dict 和 `self._lock`（并发安全由 SQLite 保证）
- 移除 `load()` / `save()` 方法（SQLite 自动持久化）
- `add()` / `remove()` / `get()` 等方法委托给 `VocabDB`
- `ManualVocabEntry` dataclass 保留作为接口层数据结构，从 DB dict 转换

字段变更：

- 移除 `hit_count: int` 和 `last_hit: str`
- 不在 dataclass 中新增字段（统计数据从 `vocab_stats` 表按需查询）

新增方法：

- `record_asr_phase(asr_text, entries, asr_model, app_bundle_id) -> list[ManualVocabEntry]` — 阶段一检测，返回 asr_miss 列表
- `record_llm_phase(asr_miss_entries, enhanced_text, llm_model, app_bundle_id)` — 阶段二检测
- `get_asr_hotwords(*, asr_model, app_bundle_id, max_count) -> list[str]` — 调用 `top_by_metric` 排序选词，含冷启动回退
- `get_llm_vocab(*, llm_model, app_bundle_id, max_entries) -> list[ManualVocabEntry]` — 调用 `top_by_metric` 排序选词，含冷启动回退
- `get_entry_stats(variant, term) -> dict` — 返回某词条的全部分桶统计（供 UI 详情面板）

**测试**：修改 `tests/enhance/test_manual_vocabulary.py`

- 更新现有测试适配新的初始化方式（path 从 `.json` → `.db`）
- 移除 `load()` / `save()` 相关测试
- 新增 `record_asr_phase` / `record_llm_phase` 测试
- 新增排序选词测试（验证 asr_miss 高的词排在前面）
- 新增冷启动回退测试（新模型无桶数据时回退到全局汇总，全局也无数据时回退到 last_updated）
- 新增 `get_entry_stats` 测试

### 第 3 步：改造命中检测流程

**文件**：修改 `src/wenzi/controllers/enhance_controller.py`

当前流程：`_push_diffs_and_hits()` → `_find_vocab_hits()` → `record_hits()`，全部在 LLM 增强后执行。

改为两阶段：

**阶段一**（ASR 输出后、LLM 增强前）：

- 在 `_run_single_async()` 和 `_run_chain_async()` 中，拿到 `asr_text` 后立即调用：
  ```python
  asr_miss_entries = self._manual_vocab_store.record_asr_phase(
      asr_text, asr_model=..., app_bundle_id=...
  )
  ```
- 需要从 `EnhanceController` 获取当前 asr_model 和 app_bundle_id 上下文

**阶段二**（LLM 增强后）：

- 改造 `_push_vocab_hits()` 接收 `asr_miss_entries` 参数：
  ```python
  def _push_vocab_hits(self, asr_miss_entries, enhanced_text, llm_model, app_bundle_id):
      self._manual_vocab_store.record_llm_phase(
          asr_miss_entries, enhanced_text, llm_model, app_bundle_id
      )
  ```

- `_push_vocab_hits_display_only()` 同步调整，只检测不记录

上下文传递：

- `EnhanceController` 需要接收 `asr_model` 和 `app_bundle_id` 参数
- 这些信息从 `recording_flow.py` 的 `InputContext` 中获取，已有现成数据

**测试**：修改 `tests/controllers/test_enhance_controller.py`

- 更新现有命中检测测试
- 新增两阶段检测测试：验证 asr_miss 在 LLM 增强前记录
- 新增上下文桶写入测试：验证 stats 写入正确的桶键
- 验证 display-only 模式不记录统计

### 第 4 步：改造注入选词逻辑

**文件**：修改 `src/wenzi/enhance/vocabulary.py`

`build_hotword_list_detailed()` 改造：

- 调用改造后的 `get_asr_hotwords()` 获取按 asr_miss 排序的热词列表
- `HotwordDetail` dataclass 更新：移除 `hit_count` / `last_hit`，新增 `asr_miss_count` / `llm_hit_count`

**文件**：修改 `src/wenzi/enhance/enhancer.py`

`_build_context_section()` 中的词库注入：

- 调用改造后的 `get_llm_vocab()` 获取按 llm_hit 排序的词条
- 格式化逻辑不变（`"variant" → "term"`）

**文件**：修改 `src/wenzi/app.py`

- `_load_hotwords()` 和 `_build_dynamic_hotwords()` 适配新接口
- `ManualVocabularyStore` 初始化路径从 `.json` 改为 `.db`

**测试**：修改 `tests/enhance/test_vocabulary.py`

- 更新 `HotwordDetail` 相关测试
- 新增排序验证测试（asr_miss 高的词排在前面）

### 第 5 步：更新 `__init__.py` 导出

**文件**：修改 `src/wenzi/enhance/__init__.py`

- 新增 `VocabDB` 导出（如果需要外部直接访问）
- 更新已变更的公开接口

### 第 6 步：清理

- 确认所有测试通过：`uv run pytest tests/ -v --cov=wenzi`
- 确认 lint 通过：`uv run ruff check`
- 清理不再使用的 JSON 持久化相关代码

## 涉及文件汇总

| 文件 | 操作 |
|------|------|
| `src/wenzi/enhance/vocab_db.py` | **新建** — SQLite 存储层 |
| `src/wenzi/enhance/manual_vocabulary.py` | **改造** — 委托 VocabDB，新增两阶段检测 |
| `src/wenzi/enhance/vocabulary.py` | **改造** — HotwordDetail 字段更新 |
| `src/wenzi/enhance/enhancer.py` | **小改** — 适配新的 get_llm_vocab 接口 |
| `src/wenzi/controllers/enhance_controller.py` | **改造** — 两阶段命中检测 |
| `src/wenzi/controllers/recording_flow.py` | **小改** — 传递上下文到 enhance_controller |
| `src/wenzi/app.py` | **小改** — 初始化路径和接口适配 |
| `src/wenzi/enhance/__init__.py` | **小改** — 更新导出 |
| `tests/enhance/test_vocab_db.py` | **新建** — VocabDB 测试 |
| `tests/enhance/test_manual_vocabulary.py` | **改造** — 适配新接口 |
| `tests/enhance/test_vocabulary.py` | **改造** — HotwordDetail 测试更新 |
| `tests/controllers/test_enhance_controller.py` | **改造** — 两阶段检测测试 |
