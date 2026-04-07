# 配置说明

默认配置文件路径：`~/.config/WenZi/config.json`。只需包含你想修改的字段，其余字段将使用默认值。

## 配置目录解析

配置目录按以下优先级解析：

1. **命令行参数** -- 将目录路径作为第一个位置参数传入：`wenzi /path/to/config-dir`
2. **NSUserDefaults** -- 通过设置界面保存的自定义目录（存储在 `io.github.airead.wenzi` / `config_dir` 下）
3. **默认路径** -- `~/.config/WenZi/`

配置文件始终是解析后目录中的 `config.json`。

## 完整默认配置

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

## 配置项说明

### 通用设置

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `hotkeys` | `{"fn": true}` | 热键映射。可用键名：`fn`、`f1`--`f12`、`esc`、`space`、`cmd`、`ctrl`、`alt`、`shift`。值设为 `true` 表示启用 |

### 音频设置

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `audio.sample_rate` | `16000` | 音频采样率（Hz） |
| `audio.block_ms` | `20` | 录音块大小（毫秒） |
| `audio.device` | `null` | 音频输入设备（null 表示使用系统默认设备） |
| `audio.max_session_bytes` | `20971520` | 单次录音最大字节数（约 20 MB） |
| `audio.silence_rms` | `20` | 静音判定的 RMS 阈值，低于此值视为静音 |

### 语音识别（ASR）

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `asr.backend` | `"apple"` | ASR 后端引擎：`apple`、`funasr`、`mlx-whisper`、`whisper-api` 或 `sherpa-onnx` |
| `asr.use_vad` | `true` | 启用语音活动检测（可防止静音时产生幻觉输出） |
| `asr.use_punc` | `true` | 启用自动标点恢复 |
| `asr.language` | `"zh"` | 语言代码（用于 MLX-Whisper 和 Whisper API） |
| `asr.model` | `"on-device"` | 模型标识符（例如 Apple 使用 `on-device`，MLX-Whisper 使用 `mlx-community/whisper-small`） |
| `asr.preset` | `null` | 模型注册表中的预设 ID（例如 `mlx-whisper-small`） |
| `asr.temperature` | `0.0` | 解码温度（用于 MLX-Whisper 和 Whisper API） |
| `asr.default_provider` | `null` | 默认远程 ASR 提供商名称（例如 `"groq"`） |
| `asr.default_model` | `null` | 默认远程 ASR 模型（例如 `"whisper-large-v3"`） |
| `asr.providers` | `{}` | 远程 ASR 提供商配置（格式与 `ai_enhance.providers` 相同） |

### 输出设置

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `output.method` | `"auto"` | 文本注入方式：`auto`（自动）、`clipboard`（剪贴板）或 `applescript` |
| `output.append_newline` | `false` | 在输出文本后追加换行符 |
| `output.preview` | `true` | 显示浮动预览面板，在输入前查看和确认识别结果 |
| `output.preview_type` | `"web"` | 预览面板实现方式：`web`（基于 WebView）或 `native`（基于 AppKit） |

### AI 增强

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `ai_enhance.enabled` | `false` | 启用 AI 文本增强 |
| `ai_enhance.mode` | `"proofread"` | 增强模式：`off`（关闭）、`proofread`（校对）、`translate_en`（翻译为英文）、`translate_en_plus`（高级英文翻译）、`commandline_master`（命令行大师）或自定义模式 ID |
| `ai_enhance.default_provider` | `"ollama"` | 默认 LLM 提供商名称 |
| `ai_enhance.default_model` | `"qwen2.5:7b"` | 默认 LLM 模型 |
| `ai_enhance.thinking` | `false` | 为支持的模型启用扩展思考功能 |
| `ai_enhance.timeout` | `30` | LLM 请求超时时间（秒） |
| `ai_enhance.connection_timeout` | `10` | LLM 连接超时时间（秒） |
| `ai_enhance.max_retries` | `2` | 连接失败时的最大重试次数 |

### 词汇检索

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `ai_enhance.vocabulary.enabled` | `false` | 在增强过程中启用基于词汇表的检索 |
| `ai_enhance.vocabulary.top_k` | `5` | 每次查询检索的词汇条目数 |
| `ai_enhance.vocabulary.build_timeout` | `600` | 词汇构建时每批次的 LLM 超时时间（秒） |
| `ai_enhance.vocabulary.auto_build` | `true` | 当纠正累积到一定数量时自动构建词汇表 |
| `ai_enhance.vocabulary.auto_build_threshold` | `10` | 触发自动构建的纠正次数 |

### 对话历史

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `ai_enhance.conversation_history.enabled` | `false` | 启用对话历史上下文注入 |
| `ai_enhance.conversation_history.max_entries` | `10` | 重建后的基础条目数（也是初始条目数） |
| `ai_enhance.conversation_history.refresh_threshold` | `50` | 触发重建的最大条目数 |
| `ai_enhance.conversation_history.max_history_chars` | `6000` | 触发重建的最大总字符数 |

> **注意：** 对话历史超过 20,000 条记录时会自动轮转归档。旧记录按月归档到 `conversation_history_archives/` 目录下的 JSONL 文件中。此上限不可配置。

> **提示词缓存优化：** 对话历史采用追加式构建，保持系统提示词前缀稳定不变，从而让大模型 API 的提示词缓存（OpenAI、DeepSeek 等）可以复用已缓存的 KV 状态。当条目数达到 `refresh_threshold` 或总字符数达到 `max_history_chars` 时，会以最近 `max_entries` 条为基础重建。大多数 API 提供商要求缓存前缀至少达到 **1024 tokens**（约 500-700 个中文字符）。如果你使用的增强模式提示词较短，建议适当增大 `max_entries`（如改为 20），以确保重建后系统提示词能超过此阈值。
>
> `max_entries`（基础条目数）和 `refresh_threshold`（最大条目数）均可在 **Settings > AI** 的 Conversation History 开关下方配置。

### 剪贴板增强

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `clipboard_enhance.hotkey` | `"ctrl+cmd+v"` | 触发剪贴板 AI 增强的热键（修饰键+按键格式） |

### 反馈设置

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `feedback.sound_enabled` | `true` | 启用录音开始/停止的声音反馈 |
| `feedback.sound_volume` | `0.4` | 声音音量（0.0 -- 1.0） |
| `feedback.visual_indicator` | `true` | 显示浮动录音指示器及音频电平条 |
| `feedback.restart_key` | `"cmd"` | 按住触发热键时重新开始录音的按键。可选值：`space`、`cmd`、`ctrl`、`alt`、`shift`、`esc` |
| `feedback.cancel_key` | `"space"` | 按住触发热键时取消录音的按键。可选值：`space`、`cmd`、`ctrl`、`alt`、`shift`、`esc` |

### 界面

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `ui.settings_last_tab` | `"general"` | 设置窗口中上次激活的标签页（自动持久化）。可选值：`general`、`stt`、`llm`、`ai` |

### 脚本

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `scripting.enabled` | `false` | 启用 Python 脚本系统 |
| `scripting.script_dir` | `null` | Python 脚本的自定义目录（null 表示使用 `<配置目录>/scripts`） |

### 日志设置

| 键名 | 默认值 | 说明 |
|-----|---------|-------------|
| `logging.level` | `"INFO"` | 日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR` |

## 环境变量

| 变量名 | 默认值 | 说明 |
|----------|---------|-------------|
| `FUNASR_ASR_MODEL` | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx` | ASR 模型 ID |
| `FUNASR_VAD_MODEL` | `iic/speech_fsmn_vad_zh-cn-16k-common-onnx` | VAD 模型 ID |
| `FUNASR_PUNC_MODEL` | `iic/punc_ct-transformer_zh-cn-common-vocab272727-onnx` | 标点模型 ID |
| `FUNASR_MODEL_REVISION` | `v2.0.5` | 模型版本 |
| `OMP_NUM_THREADS` | `8` | ONNX 运行时线程数 |
