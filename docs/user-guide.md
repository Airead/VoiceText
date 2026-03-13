# VoiceText User Guide

A progressive guide from first launch to advanced usage. Follow the levels in order — each builds on the previous one.

## Table of Contents

- [Level 1: Getting Started](#level-1-getting-started) — Install, launch, and transcribe your first sentence
- [Level 2: Daily Use Basics](#level-2-daily-use-basics) — Preview mode, hotkeys, and output control
- [Level 3: Choosing the Right ASR Backend](#level-3-choosing-the-right-asr-backend) — Pick the best speech engine for your language and hardware
- [Level 4: AI Enhancement](#level-4-ai-enhancement) — Let an LLM proofread, translate, or reformat your text
- [Level 5: Preview Power Features](#level-5-preview-power-features) — Edit, switch modes, cache, and translate inside the preview panel
- [Level 6: Direct Mode & Streaming](#level-6-direct-mode--streaming) — Type results instantly with real-time AI overlay
- [Level 7: Clipboard Enhancement](#level-7-clipboard-enhancement) — AI-enhance any selected text in any app
- [Level 8: Custom Enhancement Modes](#level-8-custom-enhancement-modes) — Create your own modes and chain pipelines
- [Level 9: Multi-Provider Setup](#level-9-multi-provider-setup) — Configure multiple ASR and LLM providers
- [Level 10: Vocabulary & Conversation History](#level-10-vocabulary--conversation-history) — Teach VoiceText your personal terms and keep topic context
- [Level 11: Fine-Tuning & Troubleshooting](#level-11-fine-tuning--troubleshooting) — Advanced config, logging, and common issues

---

## Level 1: Getting Started

**Goal:** Install VoiceText and transcribe your first sentence.

### Install

**Option A — Download Release (easiest):**

1. Download `VoiceText.app` from the [Releases](https://github.com/Airead/VoiceText/releases) page.
2. Drag it to `/Applications`.
3. Double-click to launch.

> **First launch:** macOS blocks unsigned apps. Go to **System Settings → Privacy & Security**, find the VoiceText blocked message, and click **Open Anyway**.

**Option B — Build from Source:**

```bash
git clone https://github.com/Airead/VoiceText
cd VoiceText
uv sync
./scripts/build.sh        # builds VoiceText.app in dist/
```

**Option C — Run from Source (for developers):**

```bash
git clone https://github.com/Airead/VoiceText
cd VoiceText
uv sync
uv run python -m voicetext
```

### Grant Permissions

On first launch, macOS will ask for:

| Permission | Why |
|---|---|
| **Microphone** | Record your voice |
| **Accessibility** | Type text into other apps |
| **Speech Recognition** | Only needed for Apple Speech backend |

Grant all requested permissions in **System Settings → Privacy & Security**.

### First Launch: Model Download

**Important:** On first launch, VoiceText needs to download the default FunASR speech recognition model (~500 MB). During download:

- The menubar icon changes to a **download icon** (⬇) with a percentage like `DL 45%`
- **Please wait for the download to complete** before trying to transcribe — this may take a few minutes depending on your network speed
- Click menubar → **View Logs...** to open the built-in log viewer and monitor download progress in real time
- Once loading finishes, the icon changes back to a **microphone icon** (🎙) and the status shows "Ready"

> **Tip:** If the download fails or is interrupted, delete `~/.cache/modelscope/` and restart VoiceText to retry.

### Your First Transcription

1. Look for the **microphone icon** (🎙) in the menubar — that means VoiceText is ready.
2. Open any text input (Notes, browser, editor, terminal…).
3. **Hold** the `fn` key and speak.
4. **Release** `fn` — the transcribed text appears.

That's it! You've completed the basic workflow.

### Understanding the Menubar Icon

The menubar icon changes to reflect the current status:

| Icon | Status | Meaning |
|---|---|---|
| 🎙 (mic.fill) | Ready | Idle, ready to record |
| 〰 (waveform) | Recording... | Capturing audio |
| 💬 (text.bubble) | Transcribing... | Processing speech to text |
| ✨ (sparkles) | Enhancing... | AI enhancement in progress |
| 👁 (eye) | Preview... | Preview panel is open |
| ⬇ (arrow.down.circle) + DL X% | Downloading... | Model download in progress |
| ⚙ (cpu) | Loading... | Loading model into memory |
| ⚠ (triangle) | Error | Something went wrong |

---

## Level 2: Daily Use Basics

**Goal:** Understand the two output modes and basic menubar controls.

### Preview Mode vs Direct Mode

VoiceText has two ways to deliver results:

| Mode | Behavior | When to use |
|---|---|---|
| **Preview** (default) | Shows a floating panel — review and edit before confirming | When accuracy matters, or you want to check before typing |
| **Direct** | Types text immediately into the active app | When speed matters and you trust the transcription |

Toggle via: menubar → **Settings...** → General tab → **Preview** checkbox.

### Preview Panel Basics

When Preview is on, after recording you'll see a floating panel:

- **Confirm** (`Enter`) — types the text and closes the panel
- **Copy to clipboard** (`⌘+Enter`) — copies the text to clipboard instead of typing
- **Cancel** (`Esc`) — discards the text
- **Edit** — click the text area to modify before confirming

### Menubar Overview

Click the **microphone icon** in the menubar to see the menu:

```
🎙
├── Ready                    (status indicator)
├── ─────────────────────
├── Enhance Clipboard        AI-enhance selected text (Ctrl+Cmd+V)
├── Browse History...        Search and browse past transcriptions
├── Settings...              Open the settings panel (4 tabs)
├── ─────────────────────
├── View Logs...             Open log viewer
├── Usage Stats              View usage statistics
├── About VoiceText          Version info
└── Quit
```

All model selection, AI enhancement configuration, and hotkey management are done through the **Settings** panel — not the menubar menu directly.

### Recording Feedback

While holding `fn`, a floating indicator with audio level bars shows you're recording. A sound plays on start and stop (configurable in Settings → General).

---

## Level 3: Choosing the Right ASR Backend

**Goal:** Pick the best speech engine for your needs.

### Backend Comparison

| Backend | Language | Speed | Accuracy | Download Size |
|---|---|---|---|---|
| **FunASR** (default) | Chinese | Fast | High (Chinese) | ~500 MB |
| **MLX-Whisper** | 99 languages | Medium | High | 75 MB – 1.6 GB |
| **Apple Speech** | Multiple | Fast | Good | None (built-in) |
| **Whisper API** | Multiple | Depends on network | High | None (cloud) |

### How to Switch

Open **Settings...** → **STT** tab. You'll see:

- **Local** section: Radio buttons for all available local ASR presets (FunASR, MLX-Whisper variants, Apple Speech)
- **Remote** section: Cloud-based ASR providers you've configured

Click a radio button to switch. The model will start loading (or downloading if not yet cached).

> **First download reminder:** When switching to a new MLX-Whisper model for the first time, the model needs to download. Watch the menubar icon for `DL X%` progress. Model sizes range from ~75 MB (tiny) to ~1.6 GB (large-v3-turbo).

### Recommendations

- **Chinese only** → FunASR (best accuracy, fully offline)
- **English or multilingual** → MLX-Whisper small or large-v3-turbo
- **Quick test, no download** → Apple Speech
- **Best accuracy, don't mind latency** → Whisper API via Groq (free tier available)

---

## Level 4: AI Enhancement

**Goal:** Use an LLM to proofread, translate, or reformat transcribed text.

AI enhancement is **optional** — by default it's off. When enabled, your transcribed text is sent to an LLM for post-processing before output.

### Step 1: Set Up an LLM Provider

You need an LLM backend. Two easy options:

**Option A — Local with Ollama (free, private):**

1. Install [Ollama](https://ollama.ai) and run `ollama pull qwen2.5:7b`
2. That's it — VoiceText's default config points to Ollama

**Option B — Cloud API (e.g., DeepSeek, OpenAI):**

1. Open **Settings...** → **LLM** tab → **Add Provider...**
2. Fill in provider details:
   ```
   name: deepseek
   base_url: https://api.deepseek.com/v1
   api_key: sk-your-key
   models:
     deepseek-chat
   ```
3. Click **Verify** → **Save**

### Step 2: Select an Enhancement Mode

Open **Settings...** → **AI** tab. Select a mode:

| Mode | What it does |
|---|---|
| **Off** | No enhancement (raw transcription) |
| **纠错润色** (Proofread) | Fix typos, grammar, punctuation |
| **翻译为英文** (Translate EN) | Translate to English |
| **命令行大神** (Commandline) | Convert speech to shell commands |

### Step 3: Try It

1. Make sure an LLM provider is configured and a mode is selected.
2. Hold `fn`, say something, release.
3. The result now goes through the LLM before appearing.

> **Tip:** Start with "纠错润色" (Proofread) — it's the most universally useful mode.

---

## Level 5: Preview Power Features

**Goal:** Master the preview panel's editing and switching capabilities.

With Preview mode on and AI enhancement active, the preview panel becomes a powerful editor.

### Quick Mode Switching

Press `⌘1` through `⌘9` to instantly switch enhancement modes and re-process the same audio:

- `⌘1` = first mode in list (e.g., Proofread)
- `⌘2` = second mode (e.g., Translate EN)
- `⌘3` = third mode (e.g., Commandline)
- …and so on for custom modes

### Result Caching

When you switch modes in the preview panel, VoiceText **caches** completed results. Switching back to a previously used mode shows the cached result instantly (marked `[cached]`) — no API call needed.

The cache is cleared when new audio is recorded.

### Other Preview Features

| Feature | How |
|---|---|
| **Edit text** | Click the text area and type |
| **Copy to clipboard** | `⌘+Enter` — copies instead of typing into the active app |
| **Toggle punctuation** | Check/uncheck the **Punc** checkbox to re-transcribe with/without punctuation |
| **Switch STT model** | Use the STT dropdown in the panel |
| **Switch LLM model** | Use the LLM dropdown in the panel |
| **Play audio** | Click the play button to hear the recording |
| **Save audio** | Click save to export the recording as a file |
| **Google Translate** | Click the translate button to open Google Translate with current text |

---

## Level 6: Direct Mode & Streaming

**Goal:** Use VoiceText for fast, hands-free input with real-time AI feedback.

### Enable Direct Mode

Turn off Preview: **Settings...** → General tab → uncheck **Preview**.

Now when you release the hotkey, text is typed directly into the active app — no panel, no confirmation needed.

### Streaming Overlay

With AI enhancement active in direct mode, a **streaming overlay** appears showing the LLM processing your text in real-time. You can see tokens appear as they're generated.

- Press **Esc** to cancel enhancement and discard the result
- The overlay shows token count and processing status
- Once complete, the final text is typed automatically

### When to Use Direct Mode

- Chat apps where speed matters
- Terminal / command line input
- Any workflow where you trust the AI output and don't need to review

---

## Level 7: Clipboard Enhancement

**Goal:** AI-enhance any text in any app, not just speech transcriptions.

### How It Works

1. **Select** text in any application.
2. Press `Ctrl+Cmd+V` (default hotkey).
3. VoiceText copies the selection, sends it to the LLM with the current enhancement mode, and outputs the result.

You can also trigger it from the menubar: click **Enhance Clipboard**.

### Use Cases

- Select a rough draft → enhance with Proofread mode
- Select Chinese text → translate to English
- Select a task description → convert to shell command

### Output Behavior

- **Preview on:** Result appears in the preview panel for review
- **Preview off:** Result replaces via clipboard

### Customize the Hotkey

Edit `~/.config/VoiceText/config.json`:

```json
{
  "clipboard_enhance": {
    "hotkey": "ctrl+cmd+v"
  }
}
```

The hotkey format is `modifier+modifier+key`. See [Level 11](#hotkey-configuration) for format details and examples.

---

## Level 8: Custom Enhancement Modes

**Goal:** Create your own AI modes and chain pipelines.

### Create a Custom Mode

**Via Settings (easy):**

1. Open **Settings...** → **AI** tab → **Add Mode...**
2. Edit the template, click **Save**, enter a mode ID.

**Via file (flexible):**

Create a `.md` file in `~/.config/VoiceText/enhance_modes/`:

```markdown
---
label: Formal Email
order: 60
---
You are a professional email writing assistant.
Rewrite the user's input as a formal, polished email body.
Use appropriate greetings and closings if context suggests an email.
Maintain the original intent and key information.
Output only the email text without any explanation.
```

The filename (without `.md`) becomes the mode ID. Restart to load.

### Create a Chain Mode

Chain modes run multiple steps sequentially:

```markdown
---
label: 润色+翻译EN
order: 25
steps: proofread, translate_en
---
First proofreads the text, then translates to English.
(This body is documentation only — each step uses its own prompt.)
```

### Tips for Good Prompts

- Be specific about what to do AND what NOT to do
- End with "Output only the processed text without any explanation"
- Use `order` values with gaps (10, 20, 30…) so you can insert modes between them

See [Enhancement Mode Examples](enhance-mode-examples.md) for ready-to-use templates covering email, meeting notes, translation, developer tools, and more.

---

## Level 9: Multi-Provider Setup

**Goal:** Configure multiple ASR and LLM providers and switch between them.

### Why Multiple Providers?

- Use a fast local model (Ollama) for simple tasks, cloud API for complex ones
- Have a backup when one provider is down
- Compare results across different models

### Add Providers via Settings

**LLM providers:** Settings → **LLM** tab → **Add Provider...**

**ASR providers:** Settings → **STT** tab → **Add Provider...**

Both use the same dialog format:

```
name: provider-name
base_url: https://api.example.com/v1
api_key: your-key
models:
  model-1
  model-2
```

### Switch at Runtime

In the **Settings** panel, all configured models appear as radio buttons. Click to switch — no restart needed.

### In Preview Panel

You can also switch LLM and STT models directly from the preview panel's dropdowns, making it easy to compare results from different models on the same audio.

See [Provider & Model Setup Guide](provider-model-guide.md) for detailed examples covering Ollama, OpenAI, DeepSeek, Groq, OpenRouter, Qwen, and more.

---

## Level 10: Vocabulary & Conversation History

**Goal:** Teach VoiceText your personal terms and maintain topic context across turns.

### Vocabulary Retrieval

**Problem:** ASR often misrecognizes proper nouns, technical terms, and names (e.g., "萍萍" → "平平").

**Solution:** VoiceText builds a personal vocabulary from your correction history and uses it to improve future results.

#### How to Build Vocabulary

1. **Use Preview mode with AI enhancement** — edit the result when the AI gets a term wrong.
2. Each edit is logged to `~/.config/VoiceText/conversation_history.jsonl` with a `user_corrected` flag.
3. **Auto build** (default): After every 10 corrections, vocabulary is rebuilt automatically in the background.
4. **Manual build:** Settings → **AI** tab → **Build Vocabulary...**

#### Enable Vocabulary

Settings → **AI** tab → toggle **Vocabulary (N)**. The number shows how many entries are indexed.

When enabled, relevant vocabulary entries are retrieved via embedding similarity and injected into the LLM prompt, helping it correct domain-specific terms.

### Conversation History

**Problem:** Each transcription is independent — the LLM doesn't know what you just said.

**Solution:** VoiceText injects recent confirmed outputs into the AI prompt, so the LLM understands the current topic.

#### Enable

Settings → **AI** tab → toggle **Conversation History**.

#### How It Works

- Only **preview-confirmed** records are used (ensuring quality)
- Recent entries are formatted efficiently with arrow notation for corrections
- The LLM uses this context to maintain consistency (e.g., always using the correct name spelling)

#### Browse History

Menubar → **Browse History...** opens a searchable, filterable view of all past transcriptions. You can filter by mode, model, and whether corrections were made.

See [Vocabulary Embedding Retrieval](vocabulary-embedding-retrieval.md) and [Conversation History Enhancement](conversation-history-enhancement.md) for technical details.

---

## Level 11: Fine-Tuning & Troubleshooting

**Goal:** Optimize your setup and solve common problems.

### Settings Panel

Menubar → **Settings...** opens a panel with 4 tabs:

| Tab | What you can configure |
|---|---|
| **General** | Recording hotkeys, sound feedback, visual indicator, preview toggle |
| **STT** | Local ASR model selection, remote ASR provider management |
| **LLM** | LLM provider and model selection, provider management |
| **AI** | Enhancement mode, thinking mode, vocabulary, conversation history, auto build |

At the bottom, toolbar buttons provide quick access to **Show Config**, **Edit Config**, and **Reload Config**.

### Hotkey Configuration

VoiceText supports flexible hotkey configuration. The recording hotkey is configured in the **Settings** panel (General tab), while the clipboard enhance hotkey is set in the config file.

#### Hotkey Format

Hotkeys use the format `modifier+modifier+key`, where:

- **Modifiers:** `cmd` (or `command`), `ctrl`, `alt` (or `option`), `shift`
- **Regular keys:** `a`–`z`, `0`–`9`
- **Special keys:** `fn`, `f1`–`f12`, `esc`, `space`
- **Right-side modifiers:** `cmd_r`, `ctrl_r`, `alt_r`, `shift_r`

#### Examples

| Hotkey | Config value | Description |
|---|---|---|
| Fn key (hold to record) | `"fn"` | Default recording hotkey — single special key |
| F5 key | `"f5"` | Use a function key to record |
| Ctrl+Cmd+V | `"ctrl+cmd+v"` | Default clipboard enhance hotkey |
| Shift+Cmd+Space | `"shift+cmd+space"` | Alternative with Space key |
| Alt+D | `"alt+d"` | Option+D combination |
| Ctrl+Shift+R | `"ctrl+shift+r"` | Triple modifier example |
| Ctrl+Cmd+1 | `"ctrl+cmd+1"` | Number key combination |

#### Config File Examples

```json
{
  "hotkeys": {
    "fn": true,
    "f5": true
  },
  "clipboard_enhance": {
    "hotkey": "shift+cmd+space"
  }
}
```

Multiple recording hotkeys can be enabled simultaneously by adding entries to the `hotkeys` map with `true` values. Set to `false` to disable a hotkey without removing it.

### Configuration File

Location: `~/.config/VoiceText/config.json`

You only need to include fields you want to change — everything else uses defaults. After editing, click **Reload Config** in the Settings toolbar to apply without restarting.

See [Configuration Reference](configuration.md) for all options.

### Logging

Logs are saved to `~/Library/Logs/VoiceText/voicetext.log` (5 MB rotation, 3 backups).

**View logs (recommended):** Menubar → **View Logs...** opens the built-in log viewer — the easiest way to check logs, monitor model download/loading progress, and diagnose issues in real time.

Log files are also available on disk at the path above if you prefer an external editor.

### Usage Statistics

Menubar → **Usage Stats** shows:
- Total and today's transcription count
- Enhancement usage by mode
- Stored data counts (conversations, vocabulary entries)

### Common Issues

#### Text doesn't type into the app
- Check **Accessibility** permission in System Settings
- Try switching output method in config: `"output": {"method": "clipboard"}`

#### Model download takes too long
- The menubar shows `DL X%` during download — this is normal for first launch
- FunASR: ~500 MB, MLX-Whisper large-v3-turbo: ~1.6 GB
- Check the log viewer for detailed progress
- If partially downloaded, delete the cache directory (`~/.cache/modelscope/` for FunASR, `~/.cache/huggingface/` for MLX-Whisper) and restart

#### LLM enhancement times out
- Increase timeout: edit `config.json` → `ai_enhance.timeout` (default: 30s)
- Check if your LLM provider is reachable
- For Ollama, ensure it's running: `ollama serve`

#### Preview panel doesn't appear
- Make sure **Preview** is enabled in Settings → General
- Try clicking the menubar icon to bring the app to focus

#### Notifications don't work during development
- Expected when running via `uv run` without app bundling
- Notifications work normally in the packaged `.app` version

### Keyboard Shortcuts Summary

| Shortcut | Context | Action |
|---|---|---|
| `fn` (hold/release) | Global | Record / stop and transcribe |
| `Ctrl+Cmd+V` | Global | Clipboard enhancement |
| `Enter` | Preview panel | Confirm and type text |
| `⌘+Enter` | Preview panel | Copy to clipboard |
| `Esc` | Preview panel / Streaming overlay | Cancel |
| `⌘1` – `⌘9` | Preview panel | Switch enhancement mode |
| `⌘A/C/V/X` | Preview panel | Standard edit shortcuts |
| `⌘Z` / `⌘⇧Z` | Preview panel | Undo / Redo |

---

## What's Next?

You now know everything VoiceText offers. Here are some ideas to get the most out of it:

- **Create modes for your workflow** — meeting notes, code review comments, Slack messages
- **Build chain modes** — proofread → translate, or summarize → format
- **Accumulate vocabulary** — the more you correct, the smarter it gets
- **Try different models** — compare Groq's speed vs local Ollama's privacy vs OpenAI's accuracy
- **Browse [Enhancement Mode Examples](enhance-mode-examples.md)** for inspiration

For technical details on any feature, see the [documentation index](../README.md#documentation).
