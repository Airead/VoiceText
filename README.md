# VoiceText

A macOS menubar speech-to-text application. Hold a hotkey to record, release to transcribe and automatically type the result into the active application.

- **Offline**: Uses [FunASR](https://github.com/modelscope/FunASR) ONNX models — no cloud dependency
- **Chinese**: Optimized for Mandarin Chinese with automatic punctuation
- **Lightweight**: Runs as a menubar-only app (hidden from Dock)

## Requirements

- macOS
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

## Installation

```bash
git clone <repo-url>
cd VoiceText

# Install dependencies
uv sync
```

ASR models will be downloaded automatically on first launch (~1 GB, cached in `~/.cache/modelscope/`).

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

### Permissions

On first launch the app will prompt for:

- **Microphone** — for audio recording
- **Accessibility** — for typing text into other applications

## Configuration

Pass a JSON config file as a command-line argument. Only the fields you want to override are needed; everything else uses defaults.

```json
{
  "hotkey": "fn",
  "audio": {
    "sample_rate": 16000,
    "block_ms": 20,
    "device": null,
    "max_session_bytes": 20000000,
    "silence_rms": 20
  },
  "asr": {
    "use_vad": true,
    "use_punc": true
  },
  "output": {
    "method": "auto",
    "append_newline": false
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
| `audio.max_session_bytes` | `20000000` | Max recording size (~20 MB) |
| `audio.silence_rms` | `20` | RMS threshold below which audio is considered silence |
| `asr.use_vad` | `true` | Enable voice activity detection (prevents hallucination on silence) |
| `asr.use_punc` | `true` | Enable automatic punctuation restoration |
| `output.method` | `"auto"` | Text injection method: `auto`, `clipboard`, or `applescript` |
| `output.append_newline` | `false` | Append a newline after typed text |
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

## Project Structure

```
src/voicetext/
├── app.py          # Menubar application (rumps)
├── config.py       # Configuration loading and defaults
├── hotkey.py       # Global hotkey listener (Quartz / pynput)
├── recorder.py     # Audio recording (sounddevice)
├── transcriber.py  # FunASR ONNX speech-to-text
└── input.py        # Text injection (clipboard / AppleScript)
```

## License

MIT
