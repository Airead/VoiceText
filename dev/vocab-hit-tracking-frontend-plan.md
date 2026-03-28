# 词库命中追踪 — 前端 UI 实现计划

基于 `dev/vocab-hit-tracking-design.md` 设计文档的前端实现，依赖后端计划（`dev/vocab-hit-tracking-backend-plan.md`）完成后进行。

## 目标

1. 将表格中的 `Hit Count` 列替换为 `ASR` 和 `LLM` 两列紧凑展示
2. 新增词条展开详情面板，展示分桶统计
3. 筛选条件与统计数字联动

## 步骤

### 第 1 步：Controller 层数据适配

**文件**：修改 `src/wenzi/controllers/vocab_controller.py`

序列化变更（`_serialize_page()` 方法）：

- 移除 `hit_count` 和 `last_hit` 字段
- 新增汇总统计字段，从 `VocabDB` 查询后附加到每条记录：
  ```python
  d["asr_miss"] = ...   # 当前筛选上下文下的 asr_miss count
  d["asr_hit"] = ...    # 当前筛选上下文下的 asr_hit count
  d["llm_hit"] = ...    # 当前筛选上下文下的 llm_hit count
  d["llm_miss"] = ...   # 当前筛选上下文下的 llm_miss count
  ```
- 汇总逻辑：如果当前有 ASR Model / App 筛选条件，取对应桶的值；否则取全局汇总

排序变更（`_apply_filters()` 方法）：

- 支持新的排序列名：`asr_miss`、`llm_hit` 替代原有的 `hit_count`
- 排序时需要查询对应的统计值

新增详情查询方法：

- `get_entry_stats(variant, term) -> dict` — 返回某词条的完整分桶统计，供详情面板使用
- 格式：`{"asr": [{"context": "whisper-large-v3", "miss": 12, "hit": 3, "last": "..."}, ...], "llm": [...]}`

新增 JS 消息处理：

- `on_get_entry_stats(variant, term)` — 收到 JS 请求后查询并回传统计数据

**测试**：修改 `tests/controllers/test_vocab_controller.py`（如果存在）

- 测试新的序列化格式
- 测试筛选联动下的统计值
- 测试详情查询

### 第 2 步：Python-JS Bridge 新增消息

**文件**：修改 `src/wenzi/ui/vocab_manager_window.py`

新增 JS→Python 消息类型：

- `"getEntryStats"` → `on_get_entry_stats(variant, term)` — 请求词条详情统计

新增 Python→JS 调用：

- `setEntryStats(variant, term, stats)` — 将分桶统计推送到 JS 侧渲染详情面板

在 `VocabManagerMessageHandler` 中注册新消息类型的分发。

### 第 3 步：表格列替换

**文件**：修改 `src/wenzi/ui/templates/vocab_manager_web.html`

表头变更：

- 移除 `Hit Count`（`col-hits`）列
- 新增 `ASR` 列（`col-asr-stats`，sortable，`data-col="asr_miss"`）
- 新增 `LLM` 列（`col-llm-stats`，sortable，`data-col="llm_hit"`）

行渲染变更（`renderRows()` 函数）：

- 移除 `hit_count` 渲染
- 新增 ASR 列：显示 `miss/total` 格式
  ```javascript
  var asrMiss = r.asr_miss || 0;
  var asrHit = r.asr_hit || 0;
  var asrTotal = asrMiss + asrHit;
  // 显示: "3/15" 或 "0" (total 为 0 时)
  var asrText = asrTotal > 0 ? asrMiss + '/' + asrTotal : '0';
  ```
- 新增 LLM 列：显示 `hit/total` 格式
  ```javascript
  var llmHit = r.llm_hit || 0;
  var llmMiss = r.llm_miss || 0;
  var llmTotal = llmHit + llmMiss;
  var llmText = llmTotal > 0 ? llmHit + '/' + llmTotal : '0';
  ```

CSS 变更：

- 新增 `.col-asr-stats` 和 `.col-llm-stats` 样式（约 50px 宽，右对齐）
- 移除 `.col-hits` 样式

i18n 变更（`COLUMN_I18N` 和 `I18N` 对象）：

- 移除 `hit_count` 相关翻译
- 新增 `asr_miss: 'column_asr'` 和 `llm_hit: 'column_llm'` 翻译

**测试**：无独立前端测试，通过后端集成测试覆盖数据格式

### 第 4 步：展开详情面板

**文件**：修改 `src/wenzi/ui/templates/vocab_manager_web.html`

交互逻辑：

- 点击表格行 → 展开/收起详情（toggle）
- 再次点击同一行或点击其他行 → 收起当前详情
- 展开时发送 `getEntryStats` 消息请求数据

详情面板 HTML 结构：

```html
<tr class="detail-row">
  <td colspan="全部列数">
    <div class="detail-panel">
      <div class="detail-section">
        <h4>ASR Recognition</h4>
        <table class="detail-table">
          <tr><th>Context</th><th>Miss</th><th>Hit</th><th>Last</th></tr>
          <!-- 动态填充 -->
        </table>
      </div>
      <div class="detail-section">
        <h4>LLM Correction</h4>
        <table class="detail-table">
          <tr><th>Context</th><th>Hit</th><th>Miss</th><th>Last</th></tr>
          <!-- 动态填充 -->
        </table>
      </div>
    </div>
  </td>
</tr>
```

JS 实现：

- `toggleDetail(variant, term, rowElement)` — 展开/收起逻辑
- `renderDetailPanel(stats)` — 收到 `setEntryStats` 回调后渲染分桶数据表格
- 上下文名称显示：`asr:whisper-large-v3` → `whisper-large-v3`，`app:com.apple.dt.Xcode` → `Xcode`
- 时间显示：复用现有的 `fmtRelative()` 函数

CSS：

- `.detail-row` — 展开行样式，背景色区分
- `.detail-panel` — 两列布局（ASR 和 LLM 并排）
- `.detail-table` — 紧凑表格样式
- 暗色模式适配（使用系统语义色变量）

### 第 5 步：筛选联动

**文件**：修改 `src/wenzi/ui/templates/vocab_manager_web.html` + `src/wenzi/controllers/vocab_controller.py`

联动逻辑：

当用户选择了筛选标签（如 ASR Model: "whisper-large-v3"），Controller 需要：

1. 识别当前活跃的 ASR Model / App 筛选
2. 序列化记录时，统计值从对应桶取值而非全局汇总
3. 推送到 JS 后，表格中 ASR / LLM 列的数字自动反映筛选上下文

Controller 端：

- `_serialize_page()` 接收当前筛选上下文参数
- 从 `_active_tags` 中提取 asr_model / app 筛选条件
- 调用 `VocabDB.top_by_metric()` 时传入对应 context_key

JS 端：

- 无额外变更，数字由 Controller 计算后直接推送

### 第 6 步：Preview Panel 中的命中展示适配

**文件**：修改相关 preview panel 模板

当前 `set_vocab_hits()` 推送的数据格式包含 `hitCount`，需要适配：

- 将 `hitCount` 替换为 `asrMissCount` / `llmHitCount`（或移除，按需调整）
- Preview panel 中的命中展示改为显示"ASR miss → LLM corrected"的语义

### 第 7 步：清理与验证

- 移除所有 `hit_count` / `last_hit` 相关的前端代码
- 确认排序功能正常（点击 ASR / LLM 列头）
- 确认筛选联动正常
- 确认暗色模式下展开详情面板显示正常
- 运行全量测试：`uv run pytest tests/ -v --cov=wenzi`
- 运行 lint：`uv run ruff check`

## 涉及文件汇总

| 文件 | 操作 |
|------|------|
| `src/wenzi/controllers/vocab_controller.py` | **改造** — 序列化、排序、筛选联动、详情查询 |
| `src/wenzi/ui/vocab_manager_window.py` | **小改** — 新增消息类型 |
| `src/wenzi/ui/templates/vocab_manager_web.html` | **改造** — 列替换、展开详情、样式 |
| preview panel 相关模板 | **小改** — 命中展示适配 |
| `tests/controllers/test_vocab_controller.py` | **改造** — 新数据格式测试 |
