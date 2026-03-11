# VoiceText

A macOS menubar speech-to-text application. Hold a hotkey to record, release to transcribe and automatically type the result into the active application.

- **Offline-first**: Uses [FunASR](https://github.com/modelscope/FunASR) ONNX models by default — no cloud dependency
- **Multi-backend**: Supports FunASR (Chinese-optimized) and [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (99 languages, Apple Silicon GPU)
- **AI Enhancement**: Optional LLM-powered text proofreading, formatting, completion, and translation via OpenAI-compatible APIs
- **Vocabulary Retrieval**: Personal vocabulary index with embedding-based retrieval to improve correction of proper nouns and domain terms
- **Lightweight**: Runs as a menubar-only app (hidden from Dock)

## Requirements

- macOS (Apple Silicon recommended for MLX-Whisper)
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

## Installation

```bash
git clone <repo-url>
cd VoiceText

# Install dependencies
uv sync
```

ASR models will be downloaded automatically on first launch (FunASR ~500 MB cached in `~/.cache/modelscope/`, MLX-Whisper models cached in `~/.cache/huggingface/`).

## Usage

```bash
# Run from source
uv run python -m voicetext

# Run with a custom config file
uv run python -m voicetext path/to/config.json
```

1. The app starts with a **VT** icon in the menubar.
2. Hold the hotkey (default: `fn`) to record.
3. Release to transcribe — the recognized text is typed into the active window.

### Menubar Controls

- **ASR Model**: Switch between FunASR and MLX-Whisper models at runtime (models download on first use with progress display)
- **AI Enhance**: Toggle enhancement modes and select provider/model
- **Log Path**: Copy log file path to clipboard for debugging

### Permissions

On first launch the app will prompt for:

- **Microphone** — for audio recording
- **Accessibility** — for typing text into other applications

## ASR Backends

### FunASR (default)

Offline Chinese speech recognition using ONNX models. Includes voice activity detection (VAD) and automatic punctuation restoration.

### MLX-Whisper

OpenAI Whisper running on Apple Metal GPU via MLX. Supports 99 languages with multiple model sizes:

| Preset | Model | Size |
|--------|-------|------|
| Whisper tiny | `mlx-community/whisper-tiny` | ~75 MB |
| Whisper base | `mlx-community/whisper-base` | ~140 MB |
| Whisper small | `mlx-community/whisper-small` | ~460 MB |
| Whisper medium | `mlx-community/whisper-medium` | ~1.5 GB |
| Whisper large-v3-turbo | `mlx-community/whisper-large-v3-turbo` | ~1.6 GB |

## AI Text Enhancement

Optional post-processing of transcribed text using any OpenAI-compatible API (cloud or local like [Ollama](https://ollama.ai)).

### Enhancement Modes

| Mode | Description |
|------|-------------|
| Off | No enhancement |
| Proofread | Fix typos, grammar, and punctuation |
| Format | Convert spoken language to written form |
| Complete | Complete incomplete sentences |
| Enhance | Full enhancement (all of the above) |
| Translate to English | Translate Chinese text to English |

### Multi-Provider Support

Configure multiple LLM providers and switch between them at runtime from the menubar. Each provider supports:

- Custom base URL and API key
- Multiple models per provider
- Provider-specific `extra_body` parameters
- Optional extended thinking mode
- Configurable timeout

Providers can be added, removed, and verified directly from the menubar UI.

### Vocabulary Retrieval

VoiceText can build a personal vocabulary index from your correction history to improve recognition of proper nouns, technical terms, and domain-specific words. When enabled, relevant vocabulary entries are retrieved via embedding similarity and injected into the LLM prompt as context.

- **Build**: Click **AI Enhance > Build Vocabulary...** to extract terms from `corrections.jsonl` using LLM
- **Toggle**: Click **AI Enhance > Vocabulary** to enable/disable retrieval during enhancement
- Uses `fastembed` with a multilingual embedding model for local, offline semantic matching

See [docs/vocabulary-embedding-retrieval.md](docs/vocabulary-embedding-retrieval.md) for detailed design and motivation.

## Configuration

Default config path: `~/.config/VoiceText/config.json`. Pass a JSON config file as a command-line argument to override. Only the fields you want to change are needed; everything else uses defaults.

```json
{
  "hotkey": "fn",
  "audio": {
    "sample_rate": 16000,
    "block_ms": 20,
    "device": null,
    "max_session_bytes": 20971520,
    "silence_rms": 20
  },
  "asr": {
    "backend": "funasr",
    "use_vad": true,
    "use_punc": true,
    "language": "zh",
    "model": null,
    "preset": null,
    "temperature": 0.0
  },
  "output": {
    "method": "auto",
    "append_newline": false
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
    "vocabulary": {
      "enabled": false,
      "top_k": 5,
      "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
      "build_timeout": 600
    }
  },
  "logging": {
    "level": "INFO"
  }
}
```

### Options

| Key | Default | Description |
|-----|---------|-------------|
| `hotkey` | `"fn"` | Trigger key. Supported: `fn`, `f1`–`f12`, `esc`, `space`, `cmd`, `ctrl`, `alt`, `shift` |
| `audio.sample_rate` | `16000` | Audio sample rate in Hz |
| `audio.block_ms` | `20` | Recording block size in milliseconds |
| `audio.device` | `null` | Audio input device (null = system default) |
| `audio.max_session_bytes` | `20971520` | Max recording size (~20 MB) |
| `audio.silence_rms` | `20` | RMS threshold below which audio is considered silence |
| `asr.backend` | `"funasr"` | ASR backend: `funasr` or `mlx-whisper` |
| `asr.use_vad` | `true` | Enable voice activity detection (prevents hallucination on silence) |
| `asr.use_punc` | `true` | Enable automatic punctuation restoration |
| `asr.language` | `"zh"` | Language code (used by MLX-Whisper) |
| `asr.model` | `null` | Model identifier (e.g. `mlx-community/whisper-small`) |
| `asr.preset` | `null` | Preset ID from model registry (e.g. `mlx-whisper-small`) |
| `asr.temperature` | `0.0` | Decoding temperature (MLX-Whisper) |
| `output.method` | `"auto"` | Text injection method: `auto`, `clipboard`, or `applescript` |
| `output.append_newline` | `false` | Append a newline after typed text |
| `ai_enhance.enabled` | `false` | Enable AI text enhancement |
| `ai_enhance.mode` | `"proofread"` | Enhancement mode: `off`, `proofread`, `format`, `complete`, `enhance`, `translate_en` |
| `ai_enhance.default_provider` | `"ollama"` | Default LLM provider name |
| `ai_enhance.default_model` | `"qwen2.5:7b"` | Default LLM model |
| `ai_enhance.thinking` | `false` | Enable extended thinking for supported models |
| `ai_enhance.timeout` | `30` | LLM request timeout in seconds |
| `ai_enhance.vocabulary.enabled` | `false` | Enable vocabulary-based retrieval during enhancement |
| `ai_enhance.vocabulary.top_k` | `5` | Number of vocabulary entries to retrieve per query |
| `ai_enhance.vocabulary.embedding_model` | `"paraphrase-multilingual-MiniLM-L12-v2"` | Embedding model for vocabulary index |
| `ai_enhance.vocabulary.build_timeout` | `600` | Per-batch LLM timeout for vocabulary building (seconds) |
| `logging.level` | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FUNASR_ASR_MODEL` | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx` | ASR model ID |
| `FUNASR_VAD_MODEL` | `iic/speech_fsmn_vad_zh-cn-16k-common-onnx` | VAD model ID |
| `FUNASR_PUNC_MODEL` | `iic/punc_ct-transformer_zh-cn-common-vocab272727-onnx` | Punctuation model ID |
| `FUNASR_MODEL_REVISION` | `v2.0.5` | Model revision |
| `OMP_NUM_THREADS` | `8` | ONNX runtime thread count |

## Building

### macOS App Bundle (PyInstaller)

```bash
uv run pyinstaller VoiceText.spec
```

The built `VoiceText.app` will be in the `dist/` directory.

### macOS App Bundle (py2app)

```bash
uv run python setup.py py2app
```

## Testing

```bash
uv run pytest
```

## Logging

Logs are saved to `~/Library/Logs/VoiceText/voicetext.log` with rotation (5 MB per file, 3 backups). The log path can be copied from the menubar menu.

## Project Structure

```
src/voicetext/
├── app.py              # Menubar application (rumps)
├── config.py           # Configuration loading and defaults
├── hotkey.py           # Global hotkey listener (Quartz / pynput)
├── recorder.py         # Audio recording (sounddevice)
├── transcriber.py      # Abstract transcriber interface and factory
├── transcriber_funasr.py  # FunASR ONNX backend
├── transcriber_mlx.py     # MLX-Whisper backend
├── model_registry.py   # Model preset registry and cache management
├── enhancer.py         # AI text enhancement (OpenAI-compatible API)
├── vocabulary.py       # Vocabulary embedding index and retrieval
├── vocabulary_builder.py # Extract vocabulary from correction logs via LLM
├── vocab_build_window.py # Vocabulary build progress UI
├── punctuation.py      # Punctuation restoration (CT-Transformer)
└── input.py            # Text injection (clipboard / AppleScript)
```

## Documentation

- [AI Enhancement Modes Guide](docs/enhance-modes.md) — how to customize and create enhancement modes
- [Vocabulary Embedding Retrieval](docs/vocabulary-embedding-retrieval.md) — design and motivation of the vocabulary retrieval system

## License

MIT
