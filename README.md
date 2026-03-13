# VoiceText

A macOS menubar speech-to-text application. Hold a hotkey to record, release to transcribe and automatically type the result into the active application.

- **Offline-first**: Uses [FunASR](https://github.com/modelscope/FunASR) ONNX models by default — no cloud dependency
- **Multi-backend**: Supports FunASR (Chinese-optimized), [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (99 languages, Apple Silicon GPU), Apple Speech (macOS built-in), and remote Whisper API (OpenAI-compatible, e.g. Groq)
- **AI Enhancement**: Optional LLM-powered text proofreading, formatting, completion, and translation via OpenAI-compatible APIs — with session-level caching to avoid redundant API calls
- **Chain Modes**: Multi-step enhancement pipelines (e.g., proofread then translate) defined via simple Markdown files
- **Direct Mode Streaming**: Real-time streaming overlay shows AI enhancement progress without preview panel
- **Clipboard Enhancement**: AI-enhance selected text in any app with a hotkey — copies selection, enhances via LLM, and outputs the result
- **Vocabulary Retrieval**: Personal vocabulary index with embedding-based retrieval to improve correction of proper nouns and domain terms, with automatic background building
- **Conversation History**: Injects recent confirmed outputs into the AI prompt for topic continuity and consistent entity resolution
- **Lightweight**: Runs as a menubar-only app (hidden from Dock)

## Quick Start

### Option 1: Download Release (Recommended)

Download the latest `VoiceText.app` from the [Releases](https://github.com/Airead/VoiceText/releases) page, drag it to `/Applications`, and double-click to launch.

> **First launch note:** Since VoiceText is not signed with an Apple Developer certificate, macOS will block the first launch. Go to **System Settings → Privacy & Security**, scroll down to find the VoiceText blocked message, and click **Open Anyway**.

### Option 2: Build from Source

If you prefer to build the app yourself, the project provides build scripts:

```bash
git clone https://github.com/Airead/VoiceText
cd VoiceText
uv sync

# Build VoiceText.app only
./scripts/build.sh

# Or build VoiceText.app + DMG installer
./scripts/build-dmg.sh
```

The built `VoiceText.app` will be in the `dist/` directory. The DMG build also produces a `VoiceText-<version>-arm64.dmg` with an Applications shortcut for drag-and-drop installation.

### Option 3: Run from Source (Development)

If you want to modify the code or debug, run directly from the terminal:

```bash
git clone https://github.com/Airead/VoiceText
cd VoiceText
uv sync

# Run
uv run python -m voicetext

# Run with a custom config file
uv run python -m voicetext path/to/config.json
```

### Requirements

- macOS (Apple Silicon recommended for MLX-Whisper)
- Option 1: no additional requirements
- Options 2 & 3: Python 3.13+ and [uv](https://github.com/astral-sh/uv)

ASR models will be downloaded automatically on first launch (FunASR ~500 MB cached in `~/.cache/modelscope/`, MLX-Whisper models cached in `~/.cache/huggingface/`). The menubar icon shows download progress (`DL X%`) — please wait for the download to complete before trying to transcribe.

### Permissions

On first launch the app will prompt for:

- **Microphone** — for audio recording
- **Accessibility** — for typing text into other applications
- **Speech Recognition** — required only if using the Apple Speech backend

## Usage

1. The app starts with a **microphone icon** (🎙) in the menubar. On first launch, it downloads the default ASR model (~500 MB) — the icon shows a download indicator with progress percentage. Wait for the icon to return to the microphone and the status to show "Ready".
2. Hold the hotkey (default: `fn`) to record — a floating indicator with audio level bars shows recording status.
3. Release to transcribe — the recognized text is typed into the active window.

### Direct Mode (Default)

When **Preview** is disabled, results are typed directly. If AI enhancement is active, a streaming overlay shows real-time enhancement progress with token usage. Press `Esc` to cancel.

### Preview Mode

When **Preview** is enabled, a floating panel shows the result for review before input. In the preview panel you can:

- Edit the text before confirming
- Press `Enter` to confirm and type, or `⌘+Enter` to copy to clipboard
- Use `⌘1` ~ `⌘9` to quickly switch AI enhancement modes and re-enhance with the selected mode
- Toggle the **Punc** checkbox to enable/disable punctuation restoration and re-transcribe
- Switch STT or LLM model via dropdown popups
- Play back or save the recorded audio
- Open Google Translate for the current text

Switching between modes or settings reuses cached results when available, avoiding redundant API calls. Cached results are marked with `[cached]`.

### Clipboard Enhancement

Press the clipboard enhance hotkey (default: `Ctrl+Cmd+V`) to AI-enhance selected text in any application:

1. The current selection is automatically copied via `Cmd+C`
2. The text is sent to the configured LLM for enhancement
3. The result is placed on the clipboard (or shown in the preview panel if enabled)

Configure the hotkey and output method in `config.json` under `clipboard_enhance`.

### Menubar & Settings

Click the menubar icon to access:

```
🎙
├── Ready                    (status indicator)
├── ─────────────────────
├── Enhance Clipboard        AI-enhance selected text (Ctrl+Cmd+V)
├── Browse History...        Search and browse past transcriptions
├── Settings...              Open the settings panel
├── ─────────────────────
├── View Logs...             Open log viewer
├── Usage Stats              View usage statistics
├── About VoiceText          Version info
└── Quit
```

The **Settings** panel (4 tabs) centralizes all configuration:

| Tab | Controls |
|-----|----------|
| **General** | Recording hotkeys, sound feedback, visual indicator, preview toggle |
| **STT** | Local ASR model selection (FunASR, MLX-Whisper, Apple Speech), remote ASR provider management |
| **LLM** | LLM provider/model selection, add/remove providers |
| **AI** | Enhancement mode, thinking mode, vocabulary, conversation history, auto build |

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

### Apple Speech

macOS built-in speech recognition using the SFSpeechRecognizer framework. Supports on-device and server-based recognition for multiple languages (Chinese, English, Japanese, Korean, and more). Requires Speech Recognition permission in System Settings. No model download needed.

### Whisper API (Remote)

OpenAI-compatible audio transcription API. Works with cloud providers like Groq, OpenAI, and any compatible endpoint. Configure remote ASR providers from the **Settings** panel (STT tab) or in `config.json` under `asr.providers`. See [docs/provider-model-guide.md](docs/provider-model-guide.md) for setup details.

## AI Text Enhancement

Optional post-processing of transcribed text using any OpenAI-compatible API (cloud or local like [Ollama](https://ollama.ai)).

### Enhancement Modes

| Mode | Description |
|------|-------------|
| Off | No enhancement |
| Proofread (纠错润色) | Fix typos, grammar, and punctuation |
| Translate to English (翻译为英文) | Translate Chinese text to English |
| Translate EN+ (润色+翻译EN) | Chain mode: proofread then translate to English |
| Commandline Master (命令行大神) | Convert natural language to shell commands |

Additional modes can be added via Markdown files or the Settings panel (AI tab → **Add Mode...**) — see [docs/enhance-modes.md](docs/enhance-modes.md).

### Chain Modes

Chain modes run multiple enhancement steps sequentially, passing the output of each step as input to the next. For example, a "Translate EN+" chain first proofreads the text, then translates it to English. Define chains by adding a `steps` field to the mode's Markdown front matter. See [docs/enhance-modes.md](docs/enhance-modes.md) for details.

### Enhancement Result Caching

Within a preview panel session, completed enhancement results are cached. Switching between modes, LLM models, or thinking settings reuses cached results instantly instead of making new API calls. Cached results are marked with `[cached]` in the token label. The cache is automatically cleared when the ASR input text changes.

### Multi-Provider Support

Configure multiple LLM providers and switch between them at runtime. Each provider supports:

- Custom base URL and API key
- Multiple models per provider
- Provider-specific `extra_body` parameters
- Optional extended thinking mode
- Configurable timeout

Providers can be added, removed, and verified from the **Settings** panel (LLM tab). See [docs/provider-model-guide.md](docs/provider-model-guide.md) for step-by-step setup instructions covering both GUI and config file approaches.

### Vocabulary Retrieval

VoiceText can build a personal vocabulary index from your correction history to improve recognition of proper nouns, technical terms, and domain-specific words. When enabled, relevant vocabulary entries are retrieved via embedding similarity and injected into the LLM prompt as context.

The vocabulary supports both automatic and manual building:

- **Accumulate corrections**: Edit AI-enhanced text in the preview window; each edit is logged to `conversation_history.jsonl` with a `user_corrected` flag
- **Auto build**: By default, vocabulary is automatically rebuilt in the background after every 10 corrections. A macOS notification shows the result. Toggle via Settings → AI tab → **Auto Build Vocabulary**
- **Manual build**: Click Settings → AI tab → **Build Vocabulary...** to trigger a build on demand. Supports incremental builds — only new corrections since the last build are processed
- **Toggle**: Enable/disable in the Settings panel (AI tab). The entry count is shown next to the toggle
- Uses `fastembed` with a multilingual embedding model for local, offline semantic matching

See [docs/vocabulary-embedding-retrieval.md](docs/vocabulary-embedding-retrieval.md) for detailed design and motivation.

### Conversation History

VoiceText can inject recent conversation history into the AI enhancement prompt, enabling the LLM to understand the current topic and resolve recurring entities consistently. For example, if the user confirmed "萍萍" in a previous turn, subsequent ASR errors like "平平" can be correctly resolved.

- **Toggle**: Enable/disable in the Settings panel (AI tab)
- Only preview-confirmed records (where the user reviewed and approved the output) are injected — ensuring data quality
- Token-efficient format: identical ASR/output shown once, corrections shown with arrow notation (e.g., `平平 → 萍萍`)

See [docs/conversation-history-enhancement.md](docs/conversation-history-enhancement.md) for detailed design and motivation.

## Configuration

Default config path: `~/.config/VoiceText/config.json`. Pass a JSON config file as a command-line argument to override. Only the fields you want to change are needed; everything else uses defaults.

See [docs/configuration.md](docs/configuration.md) for the full default configuration, all available options, and environment variables.

## Testing

```bash
uv run pytest
```

## Logging

Logs are saved to `~/Library/Logs/VoiceText/voicetext.log` with rotation (5 MB per file, 3 backups). View logs in-app via menubar → **View Logs...**.

## Project Structure

```
src/voicetext/
├── app.py                    # Menubar application with enhancement caching
├── config.py                 # Configuration loading and defaults
├── hotkey.py                 # Global hotkey listener (Quartz)
├── recorder.py               # Audio recording (sounddevice)
├── sound_manager.py          # Sound feedback for recording start/stop
├── recording_indicator.py    # Floating recording indicator with audio level bars
├── transcriber.py            # Abstract transcriber interface and factory
├── transcriber_funasr.py     # FunASR ONNX backend
├── transcriber_mlx.py        # MLX-Whisper backend
├── transcriber_apple.py      # Apple Speech Recognition backend (SFSpeechRecognizer)
├── transcriber_whisper_api.py # Remote Whisper API backend (OpenAI-compatible)
├── model_registry.py         # Model preset registry and cache management
├── enhancer.py               # AI text enhancement (OpenAI-compatible API)
├── mode_loader.py            # Enhancement mode definitions, chain steps, and file loading
├── auto_vocab_builder.py     # Automatic vocabulary building triggered by correction count
├── result_window.py          # Floating preview panel with cached result replay
├── streaming_overlay.py      # Floating overlay for direct mode AI streaming
├── settings_window.py        # Tabbed settings panel (General, STT, LLM, AI)
├── history_browser_window.py # Conversation history browser with search and filters
├── log_viewer_window.py      # Log viewer panel
├── translate_webview.py      # Google Translate webview for quick translation
├── vocabulary.py             # Vocabulary embedding index and retrieval
├── vocabulary_builder.py     # Extract vocabulary from conversation history via LLM
├── vocab_build_window.py     # Vocabulary build progress UI
├── conversation_history.py   # Conversation history recording and context injection
├── usage_stats.py            # Usage statistics with cumulative and daily breakdown
├── punctuation.py            # Punctuation restoration (CT-Transformer)
└── input.py                  # Text injection (clipboard / AppleScript)
```

## Documentation

- **[User Guide](docs/user-guide.md) — progressive guide from first launch to advanced usage (start here!)**
- [Configuration](docs/configuration.md) — full default config, all options, and environment variables
- [Provider & Model Setup Guide](docs/provider-model-guide.md) — step-by-step setup for ASR and LLM providers
- [AI Enhancement Modes Guide](docs/enhance-modes.md) — how to customize and create enhancement modes
- [Enhancement Mode Examples](docs/enhance-mode-examples.md) — ready-to-use mode templates for inspiration
- [Vocabulary Embedding Retrieval](docs/vocabulary-embedding-retrieval.md) — design and motivation of the vocabulary retrieval system
- [Conversation History Enhancement](docs/conversation-history-enhancement.md) — how conversation history improves AI enhancement accuracy

## License

MIT
