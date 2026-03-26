# Provider & Model Setup Guide

This guide explains how to configure ASR (speech recognition) models and AI enhancement providers in 闻字. Both GUI (Settings panel) and config file approaches are covered.

## Table of Contents

- [ASR Model Selection](#asr-model-selection)
  - [Via GUI](#asr-via-gui)
  - [Via Config File](#asr-via-config-file)
  - [Available Models](#available-asr-models)
- [Remote ASR Providers](#remote-asr-providers)
  - [Via GUI](#remote-asr-via-gui)
  - [Via Config File](#remote-asr-via-config-file)
  - [Remote ASR Examples](#remote-asr-examples)
- [AI (LLM) Provider Configuration](#ai-llm-provider-configuration)
  - [Via GUI](#provider-via-gui)
  - [Via Config File](#provider-via-config-file)
  - [Provider Examples](#provider-examples)
- [Switching Provider & Model](#switching-provider--model)
  - [Via GUI](#switching-via-gui)
  - [Via Config File](#switching-via-config-file)
- [Removing a Provider](#removing-a-provider)

---

## ASR Model Selection

闻字 supports five ASR backends:

| Backend | Best For | GPU | Offline |
|---------|----------|-----|---------|
| **Apple Speech** (default) | Multi-language, no download needed | CPU/Neural Engine | On-device or server-based |
| **FunASR Paraformer** | Chinese speech | CPU (ONNX) | Yes (after first download) |
| **Sherpa-ONNX** | Streaming, lightweight Chinese models | CPU (ONNX) | Yes (after first download) |
| **MLX-Whisper** | Multi-language, Apple Silicon | GPU (MLX) | Yes (after first download) |
| **Whisper API** (remote) | Cloud-based, any hardware | N/A | No (requires API) |

### ASR Via GUI

Open **Settings...** → **STT** tab. All available local and remote ASR models are listed as radio buttons. Select one to switch — the active model is highlighted.

If the selected MLX-Whisper model hasn't been downloaded yet, 闻字 will download it automatically on first use (the menubar icon shows `DL X%` progress). Remote ASR models from configured providers also appear in this tab.

### ASR Via Config File

Edit `~/.config/WenZi/config.json`:

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

Key fields:

| Field | Description |
|-------|-------------|
| `backend` | `"apple"`, `"funasr"`, `"sherpa-onnx"`, `"mlx-whisper"`, or `"whisper-api"` |
| `preset` | Preset ID from the table below (recommended way to select a model) |
| `model` | Direct model path override (e.g. a custom HuggingFace model ID). Overrides `preset` |
| `language` | Language code (`"zh"`, `"en"`, `"ja"`, etc.). Used by MLX-Whisper and Apple Speech. Ignored by FunASR and Sherpa-ONNX (language is determined by the model) |
| `temperature` | Decoding temperature for MLX-Whisper. `0.0` = greedy |

After editing, restart 闻字 for changes to take effect.

### Available ASR Models

| Preset ID | Backend | Model | Size |
|-----------|---------|-------|------|
| `apple-speech-ondevice` | apple | Apple Speech (On-Device) | Built-in |
| `apple-speech-server` | apple | Apple Speech (Server) | Built-in |
| `funasr-paraformer` | funasr | Paraformer-large (Chinese) | ~400 MB |
| `sherpa-zipformer-zh` | sherpa-onnx | Zipformer Chinese 14M | ~28 MB |
| `sherpa-paraformer-zh` | sherpa-onnx | Paraformer Bilingual (Chinese-English) | ~220 MB |
| `mlx-whisper-medium` | mlx-whisper | `mlx-community/whisper-medium` | ~1.5 GB |
| `mlx-whisper-large-v3-turbo` | mlx-whisper | `mlx-community/whisper-large-v3-turbo` | ~1.6 GB |

> **Note:** MLX-Whisper tiny/base/small models are not available as presets but can be used by setting `asr.model` directly (e.g., `"model": "mlx-community/whisper-small"`). Sherpa-ONNX models are downloaded automatically from HuggingFace on first use.

---

## Remote ASR Providers

In addition to local ASR backends, 闻字 supports remote ASR via OpenAI-compatible audio transcription APIs (e.g. Groq, OpenAI). Remote providers are configured separately from LLM providers.

### Remote ASR Via GUI

1. Open **Settings...** → **STT** tab → **Add Provider...**

2. Fill in the provider details (same dialog format as LLM providers):

   ```
   name: groq
   base_url: https://api.groq.com/openai/v1
   api_key: gsk-xxx
   models:
     whisper-large-v3
   ```

3. Click **Verify** — 闻字 will test the connection by sending a short silent audio clip.

4. If verification passes, click **Save**. The new models appear in the **STT** tab.

### Remote ASR Via Config File

Edit `~/.config/WenZi/config.json` and add entries under `asr`:

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

When `default_provider` and `default_model` are set, 闻字 starts with the remote ASR model. Set both to `null` to use a local backend.

### Remote ASR Examples

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

## AI (LLM) Provider Configuration

AI enhancement uses OpenAI-compatible LLM providers. You can configure multiple providers and switch between them at any time.

### Provider Via GUI

1. Open **Settings...** → **LLM** tab → **Add Provider...**

2. Select a **Preset Provider** from the dropdown (optional):
   - Selecting a preset auto-fills **Name** and **Base URL**
   - A **model dropdown** appears with available models for easy selection
   - Choose **Custom** for manual configuration

3. Fill in your provider details:
   - **Name**: A unique identifier (e.g. `openai`, `deepseek`, `local-llama`)
   - **Base URL**: The OpenAI-compatible API endpoint
   - **API Key**: Your API key
   - **Models**: Available models, select from dropdown or type manually (one per line)
   - **Extra Body** (optional): Additional JSON parameters sent with every request

4. Click **Verify** — 闻字 will test the connection using the first model in your list.

5. If verification passes, click **Save** to add the provider.

#### Supported Preset Providers

| Preset | Provider | Common Models |
|--------|----------|---------------|
| OpenAI | OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo |
| Qwen | Alibaba DashScope | qwen-max, qwen-plus, qwen-turbo, qwen-coder-plus |
| Doubao | ByteDance Volcano | doubao-1-5-pro-32k, doubao-1-5-lite-32k |
| DeepSeek | DeepSeek | deepseek-chat, deepseek-reasoner |
| MiniMax | MiniMax | MiniMax-Text-01, abab6.5s-chat |
| Zhipu | Zhipu AI | glm-4-plus, glm-4-9b, glm-4-flash |
| Moonshot | Moonshot AI (Kimi) | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k |
| SiliconFlow | SiliconFlow | DeepSeek-V3, DeepSeek-R1, Qwen2.5-72B |
| Ollama | Ollama (Local) | qwen2.5:7b, deepseek-r1:7b, llama3.2:3b |

### Provider Via Config File

Edit `~/.config/WenZi/config.json` and add entries under `ai_enhance.providers`:

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

Each provider entry requires:

| Field | Required | Description |
|-------|----------|-------------|
| `base_url` | Yes | OpenAI-compatible API endpoint URL |
| `api_key` | Yes | Authentication key |
| `models` | Yes | Array of model names available from this provider |
| `extra_body` | No | JSON object with extra request parameters |

After editing, restart 闻字 for changes to take effect.

### Provider Examples

**Ollama (local)**
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

**Qwen (with extended thinking)**
```json
"qwen": {
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "api_key": "sk-xxx",
  "models": ["qwen3-235b-a22b", "qwen3-32b"],
  "extra_body": {"chat_template_kwargs": {"enable_thinking": false}}
}
```

> **Note on `extra_body`:** Some providers require additional parameters. For example, Qwen models need `enable_thinking` to control the thinking mode. This field is passed directly in the request body alongside the standard OpenAI fields.

---

## Switching Provider & Model

### Switching Via GUI

**Switch LLM provider/model:** Open **Settings...** → **LLM** tab → select from the list of available models.

All models from all configured providers are shown as radio buttons. The active model is highlighted.

**Switch STT model:** Open **Settings...** → **STT** tab → select one (local or remote).

**Toggle thinking mode:** Open **Settings...** → **AI** tab → **Thinking** checkbox.

You can also switch STT and LLM models directly from the **preview panel** dropdowns without opening the Settings panel.

### Switching Via Config File

Update `default_provider` and `default_model` in `config.json`:

```json
{
  "ai_enhance": {
    "default_provider": "deepseek",
    "default_model": "deepseek-chat",
    "thinking": false
  }
}
```

> **Important:** The `default_model` must be one of the models listed in the selected provider's `models` array.

---

## Removing a Provider

### LLM Provider

**Via GUI:** Open **Settings...** → **LLM** tab → **Remove...** → select the provider to remove → confirm in the dialog.

**Via Config File:** Delete the provider entry from `ai_enhance.providers` in `config.json`. If it was the active provider, update `default_provider` and `default_model` to point to a remaining provider.

### ASR Provider

**Via GUI:** Open **Settings...** → **STT** tab → **Remove...** → select the provider to remove → confirm in the dialog.

**Via Config File:** Delete the provider entry from `asr.providers` in `config.json`. If it was the active provider, update `asr.default_provider` and `asr.default_model` to `null`.

> The currently active provider cannot be removed. Switch to a different provider/model first.

---

## Quick Start Example

A minimal config to get started with OpenAI enhancement:

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

Or with local Ollama (no API key needed):

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

Then select an enhancement mode from **Settings...** → **AI** tab (e.g. "纠错润色") to activate.
