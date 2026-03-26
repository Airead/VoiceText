# 服务商与模型配置指南

本指南说明如何在 闻字 中配置 ASR（语音识别）模型和 AI 增强服务商。涵盖 GUI（设置面板）和配置文件两种方式。

## 目录

- [ASR 模型选择](#asr-模型选择)
  - [通过 GUI](#通过-gui-配置-asr)
  - [通过配置文件](#通过配置文件配置-asr)
  - [可用模型](#可用-asr-模型)
- [远程 ASR 服务商](#远程-asr-服务商)
  - [通过 GUI](#通过-gui-配置远程-asr)
  - [通过配置文件](#通过配置文件配置远程-asr)
  - [远程 ASR 示例](#远程-asr-示例)
- [AI (LLM) 服务商配置](#ai-llm-服务商配置)
  - [通过 GUI](#通过-gui-配置服务商)
  - [通过配置文件](#通过配置文件配置服务商)
  - [服务商示例](#服务商示例)
- [切换服务商与模型](#切换服务商与模型)
  - [通过 GUI](#通过-gui-切换)
  - [通过配置文件](#通过配置文件切换)
- [移除服务商](#移除服务商)

---

## ASR 模型选择

闻字 支持五种 ASR 后端：

| 后端 | 最适用场景 | GPU | 离线 |
|------|-----------|-----|------|
| **Apple Speech**（默认） | 多语言，无需下载 | CPU/Neural Engine | 设备端或服务器端 |
| **FunASR Paraformer** | 中文语音 | CPU (ONNX) | 是（首次下载后） |
| **Sherpa-ONNX** | 流式识别，轻量中文模型 | CPU (ONNX) | 是（首次下载后） |
| **MLX-Whisper** | 多语言，Apple Silicon | GPU (MLX) | 是（首次下载后） |
| **Whisper API**（远程） | 云端，任意硬件 | 不适用 | 否（需要 API） |

### 通过 GUI 配置 ASR

打开 **Settings...** → **STT** 标签页。所有可用的本地和远程 ASR 模型以单选按钮形式列出。选择其中一个即可切换——当前激活的模型会高亮显示。

如果所选的 MLX-Whisper 模型尚未下载，闻字 会在首次使用时自动下载（菜单栏图标显示 `DL X%` 下载进度）。已配置服务商的远程 ASR 模型也会显示在此标签页中。

### 通过配置文件配置 ASR

编辑 `~/.config/WenZi/config.json`：

```json
{
  "asr": {
    "backend": "mlx-whisper",
    "preset": "mlx-whisper-small",
    "model": null,
    "language": "zh",
    "temperature": 0.0
  }
}
```

关键字段：

| 字段 | 说明 |
|------|------|
| `backend` | `"apple"`、`"funasr"`、`"sherpa-onnx"`、`"mlx-whisper"` 或 `"whisper-api"` |
| `preset` | 下表中的预设 ID（推荐的模型选择方式） |
| `model` | 直接指定模型路径（例如自定义 HuggingFace 模型 ID），会覆盖 `preset` |
| `language` | 语言代码（`"zh"`、`"en"`、`"ja"` 等）。MLX-Whisper 和 Apple Speech 使用此字段。FunASR 和 Sherpa-ONNX 忽略此字段（语言由模型决定） |
| `temperature` | MLX-Whisper 的解码温度。`0.0` = 贪心解码 |

编辑后需重启 闻字 使更改生效。

### 可用 ASR 模型

| 预设 ID | 后端 | 模型 | 大小 |
|---------|------|------|------|
| `apple-speech-ondevice` | apple | Apple Speech（设备端） | 内置 |
| `apple-speech-server` | apple | Apple Speech（服务器端） | 内置 |
| `funasr-paraformer` | funasr | Paraformer-large（中文） | ~400 MB |
| `sherpa-zipformer-zh` | sherpa-onnx | Zipformer Chinese 14M | ~28 MB |
| `sherpa-paraformer-zh` | sherpa-onnx | Paraformer 双语（中英） | ~220 MB |
| `mlx-whisper-medium` | mlx-whisper | `mlx-community/whisper-medium` | ~1.5 GB |
| `mlx-whisper-large-v3-turbo` | mlx-whisper | `mlx-community/whisper-large-v3-turbo` | ~1.6 GB |

> **注意：** MLX-Whisper 的 tiny/base/small 模型没有预设，但可以通过直接设置 `asr.model` 来使用（例如 `"model": "mlx-community/whisper-small"`）。Sherpa-ONNX 模型会在首次使用时自动从 HuggingFace 下载。

---

## 远程 ASR 服务商

除本地 ASR 后端外，闻字 还支持通过 OpenAI 兼容的音频转录 API（例如 Groq、OpenAI）进行远程 ASR。远程服务商的配置与 LLM 服务商分开管理。

### 通过 GUI 配置远程 ASR

1. 打开 **Settings...** → **STT** 标签页 → **Add Provider...**

2. 填写服务商详情（对话框格式与 LLM 服务商相同）：

   ```
   name: groq
   base_url: https://api.groq.com/openai/v1
   api_key: gsk-xxx
   models:
     whisper-large-v3
   ```

3. 点击 **Verify** — 闻字 会发送一段短暂的静音音频片段来测试连接。

4. 验证通过后，点击 **Save**。新模型将出现在 **STT** 标签页中。

### 通过配置文件配置远程 ASR

编辑 `~/.config/WenZi/config.json`，在 `asr` 下添加条目：

```json
{
  "asr": {
    "default_provider": "groq",
    "default_model": "whisper-large-v3",
    "providers": {
      "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "gsk-xxx",
        "models": ["whisper-large-v3"]
      }
    }
  }
}
```

设置 `default_provider` 和 `default_model` 后，闻字 启动时将使用远程 ASR 模型。将两者都设为 `null` 可切换回本地后端。

### 远程 ASR 示例

**Groq**
```json
"groq": {
  "base_url": "https://api.groq.com/openai/v1",
  "api_key": "gsk-xxx",
  "models": ["whisper-large-v3"]
}
```

**OpenAI**
```json
"openai": {
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-xxx",
  "models": ["whisper-1"]
}
```

---

## AI (LLM) 服务商配置

AI 增强功能使用 OpenAI 兼容的 LLM 服务商。您可以配置多个服务商，并随时在它们之间切换。

### 通过 GUI 配置服务商

1. 打开 **Settings...** → **LLM** 标签页 → **Add Provider...**

2. 从 **Preset Provider** 下拉框中选择预设服务商（可选）：
   - 选择预设会自动填充 **Name** 和 **Base URL**
   - 同时会显示该服务商的**模型下拉列表**，方便选择可用模型
   - 如需自定义配置，选择 **Custom** 即可手动填写

3. 填写服务商详情：
   - **Name**：唯一标识符（例如 `openai`、`deepseek`、`local-llama`）
   - **Base URL**：OpenAI 兼容的 API 端点
   - **API Key**：您的 API 密钥
   - **Models**：可用模型列表，可从下拉框选择或手动输入（每行一个）
   - **Extra Body**（可选）：随每个请求一起发送的额外 JSON 参数

4. 点击 **Verify** — 闻字 会使用列表中的第一个模型测试连接。

5. 验证通过后，点击 **Save** 添加服务商。

#### 支持的预设服务商

| 预设 | 服务商 | 常用模型 |
|------|--------|----------|
| OpenAI | OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo |
| Qwen | 通义千问 (阿里云) | qwen-max, qwen-plus, qwen-turbo, qwen-coder-plus |
| Doubao | 豆包 (字节跳动) | doubao-1-5-pro-32k, doubao-1-5-lite-32k |
| DeepSeek | DeepSeek | deepseek-chat, deepseek-reasoner |
| MiniMax | MiniMax | MiniMax-Text-01, abab6.5s-chat |
| Zhipu | 智谱AI | glm-4-plus, glm-4-9b, glm-4-flash |
| Moonshot | 月之暗面 (Kimi) | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k |
| SiliconFlow | SiliconFlow | DeepSeek-V3, DeepSeek-R1, Qwen2.5-72B |
| Ollama | Ollama (本地) | qwen2.5:7b, deepseek-r1:7b, llama3.2:3b |

### 通过配置文件配置服务商

编辑 `~/.config/WenZi/config.json`，在 `ai_enhance.providers` 下添加条目：

```json
{
  "ai_enhance": {
    "default_provider": "openai",
    "default_model": "gpt-4o",
    "providers": {
      "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-your-key-here",
        "models": ["gpt-4o", "gpt-4o-mini"]
      }
    }
  }
}
```

每个服务商条目需要以下字段：

| 字段 | 必填 | 说明 |
|------|------|------|
| `base_url` | 是 | OpenAI 兼容的 API 端点 URL |
| `api_key` | 是 | 认证密钥 |
| `models` | 是 | 该服务商可用的模型名称数组 |
| `extra_body` | 否 | 包含额外请求参数的 JSON 对象 |

编辑后需重启 闻字 使更改生效。

### 服务商示例

**Ollama（本地）**
```json
"ollama": {
  "base_url": "http://localhost:11434/v1",
  "api_key": "ollama",
  "models": ["qwen2.5:7b", "llama3.1:8b"]
}
```

**OpenAI**
```json
"openai": {
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-xxx",
  "models": ["gpt-4o", "gpt-4o-mini"]
}
```

**DeepSeek**
```json
"deepseek": {
  "base_url": "https://api.deepseek.com/v1",
  "api_key": "sk-xxx",
  "models": ["deepseek-chat", "deepseek-reasoner"]
}
```

**OpenRouter**
```json
"openrouter": {
  "base_url": "https://openrouter.ai/api/v1",
  "api_key": "sk-or-xxx",
  "models": ["anthropic/claude-sonnet-4", "google/gemini-2.5-flash"]
}
```

**Qwen（支持扩展思考）**
```json
"qwen": {
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "api_key": "sk-xxx",
  "models": ["qwen3-235b-a22b", "qwen3-32b"],
  "extra_body": {"chat_template_kwargs": {"enable_thinking": false}}
}
```

> **关于 `extra_body` 的说明：** 部分服务商需要额外参数。例如，Qwen 模型需要 `enable_thinking` 来控制思考模式。此字段会与标准 OpenAI 字段一起直接传递在请求体中。

---

## 切换服务商与模型

### 通过 GUI 切换

**切换 LLM 服务商/模型：** 打开 **Settings...** → **LLM** 标签页 → 从可用模型列表中选择。

所有已配置服务商的模型以单选按钮形式显示，当前激活的模型会高亮。

**切换 STT 模型：** 打开 **Settings...** → **STT** 标签页 → 选择一个（本地或远程）。

**切换思考模式：** 打开 **Settings...** → **AI** 标签页 → **Thinking** 复选框。

您也可以直接在**预览面板**的下拉菜单中切换 STT 和 LLM 模型，无需打开设置面板。

### 通过配置文件切换

更新 `config.json` 中的 `default_provider` 和 `default_model`：

```json
{
  "ai_enhance": {
    "default_provider": "deepseek",
    "default_model": "deepseek-chat",
    "thinking": false
  }
}
```

> **重要：** `default_model` 必须是所选服务商 `models` 数组中列出的模型之一。

---

## 移除服务商

### LLM 服务商

**通过 GUI：** 打开 **Settings...** → **LLM** 标签页 → **Remove...** → 选择要移除的服务商 → 在对话框中确认。

**通过配置文件：** 从 `config.json` 的 `ai_enhance.providers` 中删除该服务商条目。如果它是当前激活的服务商，需将 `default_provider` 和 `default_model` 更新为其他可用服务商。

### ASR 服务商

**通过 GUI：** 打开 **Settings...** → **STT** 标签页 → **Remove...** → 选择要移除的服务商 → 在对话框中确认。

**通过配置文件：** 从 `config.json` 的 `asr.providers` 中删除该服务商条目。如果它是当前激活的服务商，需将 `asr.default_provider` 和 `asr.default_model` 设为 `null`。

> 无法移除当前激活的服务商。请先切换到其他服务商/模型。

---

## 快速开始示例

使用 OpenAI 增强的最简配置：

```json
{
  "ai_enhance": {
    "enabled": true,
    "mode": "proofread",
    "default_provider": "openai",
    "default_model": "gpt-4o-mini",
    "providers": {
      "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-your-key-here",
        "models": ["gpt-4o", "gpt-4o-mini"]
      }
    }
  }
}
```

或使用本地 Ollama（无需 API 密钥）：

```json
{
  "ai_enhance": {
    "enabled": true,
    "mode": "proofread",
    "default_provider": "ollama",
    "default_model": "qwen2.5:7b",
    "providers": {
      "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "models": ["qwen2.5:7b"]
      }
    }
  }
}
```

然后在 **Settings...** → **AI** 标签页中选择增强模式（例如"纠错润色"）即可激活。
