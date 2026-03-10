"""py2app setup for building VoiceText.app."""

from setuptools import setup

APP = ["src/voicetext/app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "VoiceText",
        "CFBundleDisplayName": "VoiceText",
        "CFBundleIdentifier": "com.voicetext.app",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,  # Hide from Dock (menubar-only app)
        "NSMicrophoneUsageDescription": "VoiceText needs microphone access to record speech for transcription.",
        "NSAppleEventsUsageDescription": "VoiceText needs accessibility access to type transcribed text.",
    },
    "packages": ["voicetext", "funasr_onnx", "librosa", "sounddevice", "soundfile", "numpy"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
