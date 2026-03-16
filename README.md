# 闻字 (WenZi)

A macOS menubar speech-to-text application. Hold a hotkey to record, release to transcribe and automatically type the result into the active application.

- **Offline-first**: Uses [FunASR](https://github.com/modelscope/FunASR) Chinese-optimized ONNX by default — fully offline, no cloud dependency
- **Multi-backend**: Supports FunASR (Chinese-optimized ONNX, default), Apple Speech (macOS built-in), [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (99 languages, Apple Silicon GPU), and remote Whisper API (OpenAI-compatible, e.g. Groq)
- **Live Transcription**: Real-time streaming overlay shows partial transcription results while you are still recording
- **AI Enhancement**: Optional LLM-powered text proofreading, formatting, completion, and translation via OpenAI-compatible APIs — with session-level caching to avoid redundant API calls
- **Chain Modes**: Multi-step enhancement pipelines (e.g., proofread then translate) defined via simple Markdown files
- **Direct Mode Streaming**: Real-time streaming overlay shows AI enhancement progress without preview panel
- **Clipboard Enhancement**: AI-enhance selected text in any app with a hotkey — copies selection, enhances via LLM, and outputs the result
- **Vocabulary Retrieval**: Personal vocabulary index with embedding-based retrieval to improve correction of proper nouns and domain terms, with automatic background building
- **Conversation History**: Injects recent confirmed outputs into the AI prompt for topic continuity and consistent entity resolution
- **Scripting**: Python-based scripting system with leader keys, global hotkeys, alerts, timers, and pasteboard access for custom automation
- **Dark Mode**: Full dark mode support across all UI panels, adapting automatically to macOS appearance
- **Lightweight**: Runs as a menubar-only app (hidden from Dock)

## Quick Start

### Option 1: Download Release (Recommended)

Download the latest `WenZi.app` from the [Releases](https://github.com/Airead/WenZi/releases) page, drag it to `/Applications`, and double-click to launch.

> **First launch note:** Since 闻字 is not signed with an Apple Developer certificate, macOS will block the first launch. Go to **System Settings → Privacy & Security**, scroll down to find the 闻字 blocked message, and click **Open Anyway**.

### Option 2: Build from Source

If you prefer to build the app yourself, the project provides build scripts:

```bash
git clone https://github.com/Airead/WenZi
cd WenZi
uv sync

# Build WenZi.app only
./scripts/build.sh

# Or build WenZi.app + DMG installer
./scripts/build-dmg.sh
```

The built `WenZi.app` will be in the `dist/` directory. The DMG build also produces a `WenZi-<version>-arm64.dmg` with an Applications shortcut for drag-and-drop installation.

### Option 3: Run from Source (Development)

If you want to modify the code or debug, run directly from the terminal:

```bash
git clone https://github.com/Airead/WenZi
cd WenZi
uv sync

# Run
uv run python -m wenzi

# Run with a custom config file
uv run python -m wenzi path/to/config.json
```

### Requirements

- macOS (Apple Silicon recommended for MLX-Whisper)
- Option 1: no additional requirements
- Options 2 & 3: Python 3.13+ and [uv](https://github.com/astral-sh/uv)

The default backend (FunASR) downloads models automatically on first use (~500 MB cached in `~/.cache/modelscope/`). The menubar icon shows download progress (`DL X%`) — please wait for the download to complete before trying to transcribe. If you switch to Apple Speech, no download is needed. MLX-Whisper models are cached in `~/.cache/huggingface/`.

### Permissions

On first launch the app will prompt for:

- **Microphone** — for audio recording
- **Accessibility** — for typing text into other applications
- **Speech Recognition** — required only when using the Apple Speech backend

## Usage

1. The app starts with a **microphone icon** (🎙) in the menubar. On first launch, the default FunASR backend downloads models automatically (~500 MB). The menubar icon shows progress — subsequent launches are instant.
2. Hold the hotkey (default: `fn`) to record — a floating indicator with audio level bars shows recording status. If the ASR backend supports streaming, a live transcription overlay shows partial results in real time.
3. Release to transcribe — the recognized text is typed into the active window.

While recording (holding the hotkey), additional keys are available:

| Key | Action |
|-----|--------|
| `Cmd` (default) | Restart recording — discard current audio and start over |
| `Space` (default) | Cancel recording — discard audio without transcribing |
| `Z` (default) | Cancel and show the most recent preview history record |

The restart and cancel keys are configurable in the Settings panel (General tab).

### Preview Mode (Default)

When **Preview** is enabled (the default), a WKWebView-based floating panel shows the result for review before input. In the preview panel you can:

- Edit the text before confirming
- Press `Enter` to confirm and type, or `⌘+Enter` to copy to clipboard
- Use `⌘1` ~ `⌘9` to quickly switch AI enhancement modes and re-enhance with the selected mode
- Toggle the **Punc** checkbox to enable/disable punctuation restoration and re-transcribe
- Switch STT or LLM model via dropdown popups
- Play back or save the recorded audio
- Open Google Translate for the current text

Switching between modes or settings reuses cached results when available, avoiding redundant API calls. Cached results are marked with `[cached]`.

### Direct Mode

When **Preview** is disabled, results are typed directly. If AI enhancement is active, a streaming overlay shows real-time enhancement progress with token usage. Press `Esc` to cancel.

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
├── About 闻字          Version info
└── Quit
```

The **Settings** panel (4 tabs) centralizes all configuration. The last active tab is remembered across sessions.

| Tab | Controls |
|-----|----------|
| **General** | Recording hotkeys, restart/cancel key selection, sound feedback, visual indicator, preview toggle, custom config directory, scripting toggle |
| **STT** | Local ASR model selection (Apple Speech, FunASR, MLX-Whisper), remote ASR provider management |
| **LLM** | LLM provider/model selection, add/remove providers |
| **AI** | Enhancement mode (sorted by display order), thinking mode, vocabulary, conversation history, auto build |

## ASR Backends

### Apple Speech (default)

macOS built-in speech recognition using the SFSpeechRecognizer framework. Uses on-device recognition by default — no model download required, ready to use immediately. Supports on-device and server-based recognition for multiple languages (Chinese, English, Japanese, Korean, and more). Requires Speech Recognition permission in System Settings. Supports real-time streaming transcription during recording.

### FunASR

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

闻字 can build a personal vocabulary index from your correction history to improve recognition of proper nouns, technical terms, and domain-specific words. When enabled, relevant vocabulary entries are retrieved via embedding similarity and injected into the LLM prompt as context.

The vocabulary supports both automatic and manual building:

- **Accumulate corrections**: Edit AI-enhanced text in the preview window; each edit is logged to `conversation_history.jsonl` with a `user_corrected` flag
- **Auto build**: By default, vocabulary is automatically rebuilt in the background after every 10 corrections. A macOS notification shows the result. Toggle via Settings → AI tab → **Auto Build Vocabulary**
- **Manual build**: Click Settings → AI tab → **Build Vocabulary...** to trigger a build on demand. Supports incremental builds — only new corrections since the last build are processed
- **Toggle**: Enable/disable in the Settings panel (AI tab). The entry count is shown next to the toggle
- Uses `fastembed` with a multilingual embedding model for local, offline semantic matching

See [docs/vocabulary-embedding-retrieval.md](docs/vocabulary-embedding-retrieval.md) for detailed design and motivation.

### Conversation History

闻字 can inject recent conversation history into the AI enhancement prompt, enabling the LLM to understand the current topic and resolve recurring entities consistently. For example, if the user confirmed "萍萍" in a previous turn, subsequent ASR errors like "平平" can be correctly resolved.

- **Toggle**: Enable/disable in the Settings panel (AI tab)
- Only preview-confirmed records (where the user reviewed and approved the output) are injected — ensuring data quality
- Token-efficient format: identical ASR/output shown once, corrections shown with arrow notation (e.g., `平平 → 萍萍`)

See [docs/conversation-history-enhancement.md](docs/conversation-history-enhancement.md) for detailed design and motivation.

## History Browser

Access via menubar → **Browse History...** to search and browse past transcriptions. Features include:

- **Full-text search** across ASR and enhanced text
- **Tag filters** — filter by enhancement mode, STT/LLM model, or correction status
- **Time range** — filter by today, last 7 days, last 30 days, or all time
- **Record deletion** — delete individual records from the history
- **Archived history** — toggle the "Archived" checkbox to include records from monthly archive files. Conversation history is automatically rotated: when the main file grows too large, older records are archived into monthly JSONL files under `conversation_history_archives/`

## Usage Statistics

Access via menubar → **Usage Stats** to view interactive charts and counters. The statistics panel uses WKWebView with Chart.js and includes:

- **Interactive stacked bar charts** — daily transcription counts (direct vs. preview mode), token usage breakdown
- **Recording duration tracking** — cumulative and daily recording time
- **Token usage** — prompt, completion, total, and cached tokens with cost-awareness
- **Per-mode breakdown** — usage counts for each enhancement mode

Statistics are stored with both cumulative totals and per-day breakdowns.

## Scripting

闻字 includes a Python-based scripting system for custom automation. Enable it in Settings → General → **Scripting**, then create scripts at `~/.config/WenZi/scripts/init.py`.

The scripting API (`vt` namespace) provides:

- **Leader keys** — hold a trigger key (e.g., right Command) to see a floating panel of mappings, then press a second key to launch apps or run commands
- **Global hotkeys** — bind arbitrary key combinations to Python callbacks
- **Alerts and notifications** — show floating alerts or macOS notifications
- **Timers** — schedule one-shot or repeating callbacks
- **Pasteboard** — read and write the system clipboard
- **Execute** — run shell commands

See [docs/scripting.md](docs/scripting.md) for the full API reference and examples.

## Configuration

Default config path: `~/.config/WenZi/config.json`. Pass a JSON config file as a command-line argument to override. Only the fields you want to change are needed; everything else uses defaults.

The config directory can be changed via Settings → General → **Config Directory** (stored in macOS `NSUserDefaults` so it persists independently of the config file itself). Use the **Reset** button to revert to the default location.

See [docs/configuration.md](docs/configuration.md) for the full default configuration, all available options, and environment variables.

## Testing

```bash
uv run pytest
```

## Logging

Logs are saved to `~/Library/Logs/WenZi/wenzi.log` with rotation (5 MB per file, 3 backups). View logs in-app via menubar → **View Logs...**.

## Project Structure

```
src/wenzi/
├── app.py                       # Menubar application with enhancement caching
├── config.py                    # Configuration loading and defaults
├── hotkey.py                    # Global hotkey listener (Quartz)
├── input.py                     # Text injection (clipboard / AppleScript)
├── usage_stats.py               # Usage statistics with cumulative and daily breakdown
├── audio/                       # Recording, sound feedback, recording indicator
│   ├── recorder.py              # Audio recording (sounddevice)
│   ├── sound_manager.py         # Sound feedback for recording start/stop
│   └── recording_indicator.py   # Floating recording indicator with audio level bars
├── transcription/               # ASR backends
│   ├── base.py                  # Abstract transcriber interface and factory
│   ├── funasr.py                # FunASR ONNX backend
│   ├── mlx.py                   # MLX-Whisper backend
│   ├── apple.py                 # Apple Speech backend (SFSpeechRecognizer)
│   ├── whisper_api.py           # Remote Whisper API backend (OpenAI-compatible)
│   ├── model_registry.py        # Model preset registry and cache management
│   └── punctuation.py           # Punctuation restoration (CT-Transformer)
├── enhance/                     # AI text enhancement and vocabulary
│   ├── enhancer.py              # AI text enhancement (OpenAI-compatible API)
│   ├── mode_loader.py           # Enhancement mode definitions, chain steps, and file loading
│   ├── conversation_history.py  # Conversation history with monthly archiving
│   ├── preview_history.py       # In-memory preview history store
│   ├── vocabulary.py            # Vocabulary embedding index and retrieval
│   ├── vocabulary_builder.py    # Extract vocabulary from conversation history via LLM
│   └── auto_vocab_builder.py    # Automatic vocabulary building triggered by correction count
├── ui/                          # UI panels and windows
│   ├── result_window_web.py     # WKWebView-based preview panel (default)
│   ├── result_window.py         # AppKit-based preview panel (native fallback)
│   ├── streaming_overlay.py     # Floating overlay for direct mode AI streaming
│   ├── live_transcription_overlay.py  # Real-time transcription overlay during recording
│   ├── settings_window.py       # Tabbed settings panel (General, STT, LLM, AI)
│   ├── history_browser_window_web.py  # WKWebView history browser with tag filters
│   ├── stats_panel.py           # Statistics charts panel (Chart.js via WKWebView)
│   ├── log_viewer_window.py     # Log viewer panel
│   ├── translate_webview.py     # Google Translate webview
│   └── vocab_build_window.py    # Vocabulary build progress UI
├── controllers/                 # Business logic controllers
│   ├── recording_controller.py  # Hotkey → recording → transcription flow
│   ├── preview_controller.py    # Preview panel lifecycle and history
│   ├── enhance_controller.py    # AI enhancement orchestration
│   ├── settings_controller.py   # Settings panel state management
│   └── ...
└── scripting/                   # Python-based scripting/plugin system
    ├── engine.py                # Script loading and lifecycle
    ├── registry.py              # Plugin registry
    └── api/                     # Scripting API (hotkey, alert, timer, pasteboard, ...)
```

## Documentation

- **[User Guide](docs/user-guide.md) — progressive guide from first launch to advanced usage (start here!)**
- [Configuration](docs/configuration.md) — full default config, all options, and environment variables
- [Provider & Model Setup Guide](docs/provider-model-guide.md) — step-by-step setup for ASR and LLM providers
- [AI Enhancement Modes Guide](docs/enhance-modes.md) — how to customize and create enhancement modes
- [Enhancement Mode Examples](docs/enhance-mode-examples.md) — ready-to-use mode templates for inspiration
- [Prompt Optimization Workflow](docs/prompt-optimization-workflow.md) — how to use the Preview panel to systematically improve prompts
- [Vocabulary Embedding Retrieval](docs/vocabulary-embedding-retrieval.md) — design and motivation of the vocabulary retrieval system
- [Conversation History Enhancement](docs/conversation-history-enhancement.md) — how conversation history improves AI enhancement accuracy
- [Scripting](docs/scripting.md) — Python-based scripting system with leader keys, hotkeys, and automation APIs

## License

MIT
