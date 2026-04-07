# Configuration

Default config path: `~/.config/WenZi/config.json`. Only the fields you want to change are needed; everything else uses defaults.

## Config Directory Resolution

The config directory is resolved with the following priority:

1. **CLI argument** -- pass a directory path as the first positional argument: `wenzi /path/to/config-dir`
2. **NSUserDefaults** -- a custom directory saved via the Settings UI (stored under `io.github.airead.wenzi` / `config_dir`)
3. **Default** -- `~/.config/WenZi/`

The config file is always `config.json` inside the resolved directory.

## Full Default Configuration

```json
{
  "hotkeys": {"fn": true},
  "audio": {
    "sample_rate": 16000,
    "block_ms": 20,
    "device": null,
    "max_session_bytes": 20971520,
    "silence_rms": 20
  },
  "asr": {
    "backend": "apple",
    "use_vad": true,
    "use_punc": true,
    "language": "zh",
    "model": "on-device",
    "preset": null,
    "temperature": 0.0,
    "default_provider": null,
    "default_model": null,
    "providers": {}
  },
  "output": {
    "method": "auto",
    "append_newline": false,
    "preview": true,
    "preview_type": "web"
  },
  "ai_enhance": {
    "enabled": false,
    "mode": "proofread",
    "default_provider": "ollama",
    "default_model": "qwen2.5:7b",
    "providers": {
      "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "models": ["qwen2.5:7b"]
      }
    },
    "thinking": false,
    "timeout": 30,
    "connection_timeout": 10,
    "max_retries": 2,
    "vocabulary": {
      "enabled": false,
      "top_k": 5,
      "build_timeout": 600,
      "auto_build": true,
      "auto_build_threshold": 10
    },
    "conversation_history": {
      "enabled": false,
      "max_entries": 10,
      "refresh_threshold": 50,
      "max_history_chars": 6000
    }
  },
  "clipboard_enhance": {
    "hotkey": "ctrl+cmd+v"
  },
  "feedback": {
    "sound_enabled": true,
    "sound_volume": 0.4,
    "visual_indicator": true,
    "restart_key": "cmd",
    "cancel_key": "space"
  },
  "ui": {
    "settings_last_tab": "general"
  },
  "logging": {
    "level": "INFO"
  },
  "scripting": {
    "enabled": false,
    "script_dir": null
  }
}
```

## Options

### General

| Key | Default | Description |
|-----|---------|-------------|
| `hotkeys` | `{"fn": true}` | Hotkey map. Keys: `fn`, `f1`--`f12`, `esc`, `space`, `cmd`, `ctrl`, `alt`, `shift`. Values: `true` to enable |

### Audio

| Key | Default | Description |
|-----|---------|-------------|
| `audio.sample_rate` | `16000` | Audio sample rate in Hz |
| `audio.block_ms` | `20` | Recording block size in milliseconds |
| `audio.device` | `null` | Audio input device (null = system default) |
| `audio.max_session_bytes` | `20971520` | Max recording size (~20 MB) |
| `audio.silence_rms` | `20` | RMS threshold below which audio is considered silence |

### ASR

| Key | Default | Description |
|-----|---------|-------------|
| `asr.backend` | `"apple"` | ASR backend: `apple`, `funasr`, `mlx-whisper`, `whisper-api`, or `sherpa-onnx` |
| `asr.use_vad` | `true` | Enable voice activity detection (prevents hallucination on silence) |
| `asr.use_punc` | `true` | Enable automatic punctuation restoration |
| `asr.language` | `"zh"` | Language code (used by MLX-Whisper and Whisper API) |
| `asr.model` | `"on-device"` | Model identifier (e.g. `on-device` for Apple, `mlx-community/whisper-small` for MLX-Whisper) |
| `asr.preset` | `null` | Preset ID from model registry (e.g. `mlx-whisper-small`) |
| `asr.temperature` | `0.0` | Decoding temperature (MLX-Whisper and Whisper API) |
| `asr.default_provider` | `null` | Default remote ASR provider name (e.g. `"groq"`) |
| `asr.default_model` | `null` | Default remote ASR model (e.g. `"whisper-large-v3"`) |
| `asr.providers` | `{}` | Remote ASR providers (same format as `ai_enhance.providers`) |

### Output

| Key | Default | Description |
|-----|---------|-------------|
| `output.method` | `"auto"` | Text injection method: `auto`, `clipboard`, or `applescript` |
| `output.append_newline` | `false` | Append a newline after typed text |
| `output.preview` | `true` | Show floating preview panel for reviewing results before input |
| `output.preview_type` | `"web"` | Preview panel implementation: `web` (WebView-based) or `native` (AppKit-based) |

### AI Enhancement

| Key | Default | Description |
|-----|---------|-------------|
| `ai_enhance.enabled` | `false` | Enable AI text enhancement |
| `ai_enhance.mode` | `"proofread"` | Enhancement mode: `off`, `proofread`, `translate_en`, `translate_en_plus`, `commandline_master`, or custom mode IDs |
| `ai_enhance.default_provider` | `"ollama"` | Default LLM provider name |
| `ai_enhance.default_model` | `"qwen2.5:7b"` | Default LLM model |
| `ai_enhance.thinking` | `false` | Enable extended thinking for supported models |
| `ai_enhance.timeout` | `30` | LLM request timeout in seconds |
| `ai_enhance.connection_timeout` | `10` | LLM connection timeout in seconds |
| `ai_enhance.max_retries` | `2` | Maximum retry attempts on connection failure |

### Vocabulary Retrieval

| Key | Default | Description |
|-----|---------|-------------|
| `ai_enhance.vocabulary.enabled` | `false` | Enable vocabulary-based retrieval during enhancement |
| `ai_enhance.vocabulary.top_k` | `5` | Number of vocabulary entries to retrieve per query |
| `ai_enhance.vocabulary.build_timeout` | `600` | Per-batch LLM timeout for vocabulary building (seconds) |
| `ai_enhance.vocabulary.auto_build` | `true` | Enable automatic vocabulary building after corrections accumulate |
| `ai_enhance.vocabulary.auto_build_threshold` | `10` | Number of corrections to trigger an automatic build |

### Conversation History

| Key | Default | Description |
|-----|---------|-------------|
| `ai_enhance.conversation_history.enabled` | `false` | Enable conversation history context injection |
| `ai_enhance.conversation_history.max_entries` | `10` | Base number of entries after a rebuild (also the initial count) |
| `ai_enhance.conversation_history.refresh_threshold` | `50` | Max entry count before triggering a rebuild |
| `ai_enhance.conversation_history.max_history_chars` | `6000` | Max total characters before triggering a rebuild |

> **Note:** Conversation history is automatically rotated when it exceeds 20,000 records. Older records are archived into monthly JSONL files under `conversation_history_archives/`. This limit is not configurable.

> **Prompt caching:** History entries are appended incrementally to keep the system prompt prefix stable, which allows LLM API-level prompt caching (OpenAI, DeepSeek, etc.) to reuse cached KV state. When the entry count reaches `refresh_threshold` or total characters reach `max_history_chars`, the history is rebuilt with the most recent `max_entries` as a new base. Most API providers require the cached prefix to be at least **1024 tokens** (~500–700 Chinese characters). If your enhancement mode prompt is short, consider increasing `max_entries` (e.g., to 20) so the system prompt exceeds this threshold right after a rebuild.
>
> Both `max_entries` (Base entries) and `refresh_threshold` (Max entries) can be configured in **Settings > AI** under the Conversation History toggle.

### Clipboard Enhancement

| Key | Default | Description |
|-----|---------|-------------|
| `clipboard_enhance.hotkey` | `"ctrl+cmd+v"` | Hotkey to trigger clipboard AI enhancement (modifier+key format) |

### Feedback

| Key | Default | Description |
|-----|---------|-------------|
| `feedback.sound_enabled` | `true` | Enable sound feedback for recording start/stop |
| `feedback.sound_volume` | `0.4` | Sound volume (0.0 -- 1.0) |
| `feedback.visual_indicator` | `true` | Show floating recording indicator with audio level bars |
| `feedback.restart_key` | `"cmd"` | Key to restart recording while the trigger hotkey is held. Options: `space`, `cmd`, `ctrl`, `alt`, `shift`, `esc` |
| `feedback.cancel_key` | `"space"` | Key to cancel recording while the trigger hotkey is held. Options: `space`, `cmd`, `ctrl`, `alt`, `shift`, `esc` |

### UI

| Key | Default | Description |
|-----|---------|-------------|
| `ui.settings_last_tab` | `"general"` | Last active tab in the Settings window (persisted automatically). Values: `general`, `stt`, `llm`, `ai` |

### Scripting

| Key | Default | Description |
|-----|---------|-------------|
| `scripting.enabled` | `false` | Enable the Python scripting system |
| `scripting.script_dir` | `null` | Custom directory for Python scripts (null = `<config_dir>/scripts`) |

### Logging

| Key | Default | Description |
|-----|---------|-------------|
| `logging.level` | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FUNASR_ASR_MODEL` | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx` | ASR model ID |
| `FUNASR_VAD_MODEL` | `iic/speech_fsmn_vad_zh-cn-16k-common-onnx` | VAD model ID |
| `FUNASR_PUNC_MODEL` | `iic/punc_ct-transformer_zh-cn-common-vocab272727-onnx` | Punctuation model ID |
| `FUNASR_MODEL_REVISION` | `v2.0.5` | Model revision |
| `OMP_NUM_THREADS` | `8` | ONNX runtime thread count |
