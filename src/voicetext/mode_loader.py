"""Load AI enhancement mode definitions from external Markdown files."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MODE_OFF = "off"

DEFAULT_MODES_DIR = os.path.join("~", ".config", "VoiceText", "enhance_modes")


@dataclass
class ModeDefinition:
    """A single enhancement mode definition."""

    mode_id: str
    label: str
    prompt: str
    order: int = 50


_BUILTIN_MODES: Dict[str, ModeDefinition] = {
    "proofread": ModeDefinition(
        mode_id="proofread",
        label="纠错润色",
        prompt=(
            "你是一个文本纠错润色助手。用户输入来自语音识别（ASR），"
            "可能包含谐音字、同音字替换、吞字漏字等语音识别特有的错误，请结合上下文语义推断正确用词。"
            "请修正错别字、语法错误和标点符号问题，保持原文的语义和风格不变，只做必要的修正。"
            "直接输出修正后的文本，不要添加任何解释或说明。"
        ),
        order=10,
    ),
    "translate_en": ModeDefinition(
        mode_id="translate_en",
        label="翻译为英文",
        prompt=(
            "You are a Chinese-to-English translator. "
            "The user's input comes from speech recognition (ASR) and may contain "
            "homophone errors or misrecognized characters — infer the intended meaning from context. "
            "Translate the input into natural, fluent English. "
            "Preserve the original meaning and tone. "
            "Output only the translated text without any explanation."
        ),
        order=20,
    ),
    "commandline_master": ModeDefinition(
        mode_id="commandline_master",
        label="命令行大神",
        prompt=(
            "你是一个精通 Linux、FFmpeg、OpenSSL、Curl 等工具的命令行终端专家。\n"
            "\n"
            "【注意】用户输入来自语音识别（ASR），可能包含谐音字、同音字替换等错误，"
            "请结合上下文语义推断用户的真实意图。\n"
            "\n"
            "【指令说明】\n"
            "用户会输入一句【自然语言描述的需求】，请将其\u201c编译\u201d为\u201c最简洁、高效、可直接执行\u201d的 Command Line 命令。\n"
            "\n"
            "【改写公式】\n"
            "1. 第一步（工具锁定）： 迅速分析需求，定位核心工具（如 awk, sed, ffmpeg, openssl, docker 等）。\n"
            "2. 第二步（参数构建）： 组合参数以实现功能。优先使用管道符 `|` 组合命令，追求单行解决问题。\n"
            "3. 第三步（绝对静默）： 禁止输出任何解释、注释或Markdown格式（除非代码换行需要）。**只输出代码本身**。\n"
            "\n"
            "【Few-Shot 转换示范】\n"
            "\n"
            '- 输入（需求）： "显示当前所有python进程的进程号"\n'
            "  - 输出： ps aux | grep python | grep -v grep | awk '{print $2}'\n"
            "\n"
            '- 输入（需求）： "把当前目录下的视频全部转成mp3"\n'
            '  - 输出： for i in *.mp4; do ffmpeg -i \\"$i\\" -vn \\".mp3\\"; done\n'
            "\n"
            '- 输入（需求）： "查一下本机公网IP"\n'
            "  - 输出： curl ifconfig.me\n"
            "\n"
            '- 输入（需求）： "生成一个32位的随机十六进制字符串"\n'
            "  - 输出： openssl rand -hex 16\n"
            "\n"
            "【开始执行】\n"
            "请输入你的需求（自然语言）。"
        ),
        order=30,
    ),
}


def parse_mode_file(file_path: str) -> Optional[ModeDefinition]:
    """Parse a Markdown mode file with optional YAML front matter.

    Returns None if the file is empty or unreadable.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logger.warning("Failed to read mode file %s: %s", file_path, e)
        return None

    if not content.strip():
        return None

    basename = os.path.splitext(os.path.basename(file_path))[0]
    label = basename
    order = 50
    prompt = content.strip()

    # Try to parse front matter delimited by ---
    parts = content.split("---", 2)
    if len(parts) >= 3 and not parts[0].strip():
        front_matter = parts[1]
        body = parts[2].strip()

        # Extract label
        label_match = re.search(r"^label:\s*(.+)$", front_matter, re.MULTILINE)
        if label_match:
            label = label_match.group(1).strip()

        # Extract order
        order_match = re.search(r"^order:\s*(\d+)$", front_matter, re.MULTILINE)
        if order_match:
            order = int(order_match.group(1))

        if body:
            prompt = body

    return ModeDefinition(mode_id=basename, label=label, prompt=prompt, order=order)


def load_modes(modes_dir: Optional[str] = None) -> Dict[str, ModeDefinition]:
    """Load enhancement modes from a directory of Markdown files.

    Falls back to builtin defaults if the directory does not exist or
    contains no valid .md files.
    """
    if modes_dir is None:
        modes_dir = DEFAULT_MODES_DIR
    expanded = os.path.expanduser(modes_dir)

    modes: Dict[str, ModeDefinition] = {}

    if os.path.isdir(expanded):
        for name in os.listdir(expanded):
            if not name.endswith(".md"):
                continue
            path = os.path.join(expanded, name)
            mode_def = parse_mode_file(path)
            if mode_def is not None:
                modes[mode_def.mode_id] = mode_def

    if not modes:
        return dict(_BUILTIN_MODES)

    return modes


def ensure_default_modes(modes_dir: Optional[str] = None) -> str:
    """Ensure each builtin default mode has a corresponding Markdown file.

    Missing builtin mode files are created; existing ones are never overwritten.
    Returns the expanded directory path.
    """
    if modes_dir is None:
        modes_dir = DEFAULT_MODES_DIR
    expanded = os.path.expanduser(modes_dir)

    os.makedirs(expanded, exist_ok=True)

    for mode_id, mode_def in _BUILTIN_MODES.items():
        file_path = os.path.join(expanded, f"{mode_id}.md")
        if os.path.exists(file_path):
            continue
        content = (
            f"---\n"
            f"label: {mode_def.label}\n"
            f"order: {mode_def.order}\n"
            f"---\n"
            f"{mode_def.prompt}\n"
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Created default mode file: %s", file_path)

    return expanded


def get_sorted_modes(modes: Dict[str, ModeDefinition]) -> List[Tuple[str, str]]:
    """Return (mode_id, label) pairs sorted by order."""
    sorted_modes = sorted(modes.values(), key=lambda m: (m.order, m.mode_id))
    return [(m.mode_id, m.label) for m in sorted_modes]
