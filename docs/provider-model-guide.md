# Provider & Model Setup Guide

This guide explains how to configure ASR (speech recognition) models and AI enhancement providers in VoiceText. Both GUI (menubar) and config file approaches are covered.

## Table of Contents

- [ASR Model Selection](#asr-model-selection)
  - [Via GUI](#asr-via-gui)
  - [Via Config File](#asr-via-config-file)
  - [Available Models](#available-asr-models)
- [AI Provider Configuration](#ai-provider-configuration)
  - [Via GUI](#provider-via-gui)
  - [Via Config File](#provider-via-config-file)
  - [Provider Examples](#provider-examples)
- [Switching Provider & Model](#switching-provider--model)
  - [Via GUI](#switching-via-gui)
  - [Via Config File](#switching-via-config-file)
- [Removing a Provider](#removing-a-provider)

---

## ASR Model Selection

VoiceText supports two ASR backends:

| Backend | Best For | GPU | Offline |
|---------|----------|-----|---------|
| **FunASR Paraformer** (default) | Chinese speech | CPU (ONNX) | Yes (after first download) |
| **MLX-Whisper** | Multi-language, Apple Silicon | GPU (MLX) | Yes (after first download) |

### ASR Via GUI

Click the **Model** submenu in the menubar. Select any model — a checkmark indicates the active one:

```
Model
├── ✓ FunASR Paraformer (Chinese)
├──   Whisper tiny (MLX)
├──   Whisper base (MLX)
├──   Whisper small (MLX)
├──   Whisper medium (MLX)
└──   Whisper large-v3-turbo (MLX)
```

If the selected MLX-Whisper model hasn't been downloaded yet, VoiceText will download it automatically on first use.

### ASR Via Config File

Edit `~/.config/VoiceText/config.json`:

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
| `backend` | `"funasr"` or `"mlx-whisper"` |
| `preset` | Preset ID from the table below (recommended way to select a model) |
| `model` | Direct model path override (e.g. a custom HuggingFace model ID). Overrides `preset` |
| `language` | Language code for MLX-Whisper (`"zh"`, `"en"`, `"ja"`, etc.). Ignored by FunASR |
| `temperature` | Decoding temperature for MLX-Whisper. `0.0` = greedy |

After editing, restart VoiceText for changes to take effect.

### Available ASR Models

| Preset ID | Backend | Model | Size |
|-----------|---------|-------|------|
| `funasr-paraformer` | funasr | Paraformer-large (Chinese) | ~400 MB |
| `mlx-whisper-tiny` | mlx-whisper | `mlx-community/whisper-tiny` | ~75 MB |
| `mlx-whisper-base` | mlx-whisper | `mlx-community/whisper-base` | ~140 MB |
| `mlx-whisper-small` | mlx-whisper | `mlx-community/whisper-small` | ~460 MB |
| `mlx-whisper-medium` | mlx-whisper | `mlx-community/whisper-medium` | ~1.5 GB |
| `mlx-whisper-large-v3-turbo` | mlx-whisper | `mlx-community/whisper-large-v3-turbo` | ~1.6 GB |

---

## AI Provider Configuration

AI enhancement uses OpenAI-compatible LLM providers. You can configure multiple providers and switch between them at any time.

### Provider Via GUI

1. Open menubar → **AI Settings** → **Add Provider...**

2. A text editor dialog appears with a template:

   ```
   name: my-provider
   base_url: https://api.openai.com/v1
   api_key: sk-xxx
   models:
     gpt-4o
     gpt-4o-mini
   extra_body: {"chat_template_kwargs": {"enable_thinking": false}}
   ```

3. Fill in your provider details:
   - **name**: A unique identifier (e.g. `openai`, `deepseek`, `local-llama`)
   - **base_url**: The OpenAI-compatible API endpoint
   - **api_key**: Your API key
   - **models**: List your available models, one per line under `models:`
   - **extra_body** (optional): Additional JSON parameters sent with every request

4. Click **Verify** — VoiceText will test the connection using the first model in your list.

5. If verification passes, click **Save** to add the provider.

### Provider Via Config File

Edit `~/.config/VoiceText/config.json` and add entries under `ai_enhance.providers`:

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

After editing, restart VoiceText for changes to take effect.

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

**Switch provider:** Menubar → **AI Settings** → **Provider** → select one

```
AI Settings
├── Provider
│   ├── ✓ ollama
│   └──   openai
├── Model
│   ├── ✓ qwen2.5:7b
│   └──   llama3.1:8b
├── Thinking  ☐
├── ─────────────────
├── ...
```

The model list updates automatically when you switch providers, showing only models available for the selected provider.

**Switch model:** Menubar → **AI Settings** → **Model** → select one

**Toggle thinking mode:** Menubar → **AI Settings** → **Thinking** (checkbox)

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

### Via GUI

Menubar → **AI Settings** → **Remove Provider** → select the provider to remove → confirm in the dialog.

> The currently active provider cannot be removed. Switch to a different provider first.

### Via Config File

Delete the provider entry from `ai_enhance.providers` in `config.json`. If it was the active provider, update `default_provider` and `default_model` to point to a remaining provider.

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

Then select an enhancement mode from menubar → **AI Enhance** (e.g. "纠错润色") to activate.
