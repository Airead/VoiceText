# AI 增强模式指南

闻字 使用 AI 增强模式对转录文本进行后处理。每个模式定义为一个独立的 Markdown 文件，存储在 `~/.config/WenZi/enhance_modes/` 目录中。你可以随意添加、编辑或删除模式，无需修改任何代码。

## 目录

- [工作原理](#工作原理)
- [文件格式](#文件格式)
- [链式模式](#链式模式)
- [内置模式](#内置模式)
- [添加新模式](#添加新模式)
- [编辑现有模式](#编辑现有模式)
- [删除模式](#删除模式)
- [使用技巧](#使用技巧)

## 工作原理

```
语音 -> ASR 转录 -> 增强模式 (LLM) -> 最终文本
```

1. 启动时，闻字 会确保内置模式文件存在于模式目录中。缺失的内置文件会自动重新创建；已有文件不会被覆盖。
2. 目录中所有 `.md` 文件会被加载并显示在 **AI Enhance** 菜单中。
3. 当增强模式处于激活状态时，转录文本会被发送到已配置的 LLM，模式的提示词作为系统消息。

## 文件格式

每个 `.md` 文件使用简单的 YAML front matter，后跟提示词正文：

```markdown
---
label: 显示名称
order: 50
---
系统提示词内容写在这里。
可以使用多行。
```

| 字段    | 必填 | 说明                                                     |
|---------|------|----------------------------------------------------------|
| `label` | 否   | 菜单中显示的名称。默认使用文件名                          |
| `order` | 否   | 菜单排序权重。默认为 `50`。数值越小，在菜单中位置越靠前    |
| `steps` | 否   | 逗号分隔的模式 ID 列表，用于链式执行（参见[链式模式](#链式模式)） |
| 正文    | 是   | 发送给 LLM 的系统提示词。第二个 `---` 之后的所有内容       |

**文件名**（不含 `.md`）作为模式 ID，必须与 `config.json` 中的 `mode` 值匹配。仅使用字母、数字、连字符和下划线。

> 保留模式 ID `off` 用于禁用增强功能，不对应任何文件。

## 链式模式

链式模式按顺序运行多个增强步骤，将每个步骤的输出作为下一个步骤的输入。这对于将现有模式组合成流水线非常有用，无需重复编写提示词。

要创建链式模式，添加 `steps` 字段，列出按顺序执行的模式 ID：

```markdown
---
label: Translate EN+ (Proofread → Translate)
order: 25
steps: proofread, translate_en
---
此模式先对文本进行纠错润色，然后翻译为英文。
```

**工作方式：**

1. 输入文本被发送到第一个步骤（`proofread`），使用该模式的提示词。
2. 步骤 1 的输出成为步骤 2（`translate_en`）的输入。
3. 最终输出是最后一个步骤的结果。

**在预览模式下**，每个步骤的输出会以分隔符显示，各步骤的思考文本会被累积。最终结果字段仅显示最后一个步骤的输出。

**在直接模式下**，流式覆盖层会显示步骤进度（例如 "Step 1/2: 纠错润色"）并实时更新。

> **注意：** 链式模式文件的提示词正文不会被发送给 LLM——每个步骤使用其自身模式的提示词。正文仅用于文档说明。

### 链式模式示例

```bash
cat > ~/.config/WenZi/enhance_modes/translate_en_plus.md << 'EOF'
---
label: Translate EN+ (纠错→翻译)
order: 25
steps: proofread, translate_en
---
Proofread first, then translate to English.
This prompt body is not used — each step uses its own mode's prompt.
EOF
```

## 内置模式

以下 4 个模式在首次启动时自动创建：

| 文件                   | 标签       | 排序 | 类型  | 说明                                     |
|------------------------|------------|------|-------|------------------------------------------|
| `proofread.md`         | 纠错润色   | 10   | 单步  | 修正错别字、语法和标点                     |
| `translate_en.md`      | 翻译为英文 | 20   | 单步  | 将中文翻译为英文                          |
| `translate_en_plus.md` | 润色+翻译EN | 25  | 链式 (proofread → translate_en) | 先纠错润色，再翻译为英文 |
| `commandline_master.md`| 命令行大神 | 30   | 单步  | 将自然语言转换为 shell 命令               |

## 添加新模式

### 方式 A：从菜单添加

1. 打开 **Settings...** → **AI** 标签页。
2. 点击 **Add Mode...**。
3. 在对话框中编辑模板并点击 **Save**。
4. 输入模式 ID（例如 `summarize`）并确认。
5. 新模式会立即出现在菜单中。

### 方式 B：手动创建文件

在模式目录中创建新的 `.md` 文件：

```bash
cat > ~/.config/WenZi/enhance_modes/summarize.md << 'EOF'
---
label: Summarize
order: 55
---
You are a text summarization assistant.
Condense the user's input into a brief summary of 1-3 sentences.
Preserve the key information and original meaning.
Output only the summary without any explanation.
EOF
```

重启应用以加载新模式。

### 示例：正式邮件模式

```bash
cat > ~/.config/WenZi/enhance_modes/formal_email.md << 'EOF'
---
label: Formal Email
order: 60
---
You are a professional email writing assistant.
Rewrite the user's input as a formal, polished email body.
Use appropriate greetings and closings if context suggests an email.
Maintain the original intent and key information.
Output only the email text without any explanation.
EOF
```

### 示例：翻译为日文

```bash
cat > ~/.config/WenZi/enhance_modes/translate_ja.md << 'EOF'
---
label: Translate to Japanese
order: 70
---
You are a Chinese-to-Japanese translator.
Translate the user's Chinese input into natural, fluent Japanese.
Preserve the original meaning and tone.
Output only the translated text without any explanation.
EOF
```

## 编辑现有模式

使用任意文本编辑器直接打开文件：

```bash
# 使用你偏好的编辑器
open -e ~/.config/WenZi/enhance_modes/proofread.md
# 或者
vim ~/.config/WenZi/enhance_modes/proofread.md
```

更改在重启应用后生效。

> 内置模式文件可以自由编辑。闻字 不会覆盖已存在的文件。

## 删除模式

删除对应的 `.md` 文件并重启：

```bash
rm ~/.config/WenZi/enhance_modes/summarize.md
```

**注意：** 如果删除内置模式文件（例如 `proofread.md`），它会在下次启动时以默认内容重新创建。要永久禁用内置模式，请将其提示词替换为直通指令：

```markdown
---
label: (Disabled) Proofread
order: 999
---
Output the user's input exactly as-is, without any changes.
```

## 使用技巧

- **排序**：使用有间隔的 `order` 值（10, 20, 30...），这样可以在现有模式之间插入新模式而无需重新编号。
- **提示词质量**：在提示词中要具体明确。告诉 LLM 该做什么以及不该做什么。始终以"仅输出处理后的文本，不要附加任何解释"结尾，以避免不必要的说明文字。
- **配置兼容性**：`~/.config/WenZi/config.json` 中的 `mode` 字段存储模式 ID（文件名）。如果模式文件被删除但配置仍引用它，应用会回退到第一个可用的模式。
- **非 `.md` 文件会被忽略**：你可以安全地在模式目录中保留笔记（`.txt`）或备份（`.bak`）。

更多灵感请参见 [增强模式示例](enhance-mode-examples.md) —— 一组即用型模板，涵盖写作、翻译、开发工具等场景。
