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
            "你是一个文本纠错润色助手。请修正用户输入中的错别字、语法错误和标点符号问题。"
            "保持原文的语义和风格不变，只做必要的修正。"
            "直接输出修正后的文本，不要添加任何解释或说明。"
        ),
        order=10,
    ),
    "format": ModeDefinition(
        mode_id="format",
        label="格式化",
        prompt=(
            "你是一个文本格式化助手。请将用户输入的口语化文本转换为书面语，"
            "并适当调整结构使其更加清晰易读。"
            "保持原文的核心语义不变。"
            "直接输出格式化后的文本，不要添加任何解释或说明。"
        ),
        order=20,
    ),
    "complete": ModeDefinition(
        mode_id="complete",
        label="智能补全",
        prompt=(
            "你是一个智能文本补全助手。请补全用户输入中不完整的句子，"
            "使其成为完整、通顺的表达。"
            "保持原文的语义和风格不变，只补全缺失的部分。"
            "直接输出补全后的文本，不要添加任何解释或说明。"
        ),
        order=30,
    ),
    "enhance": ModeDefinition(
        mode_id="enhance",
        label="全面增强",
        prompt=(
            "你是一个全面的文本增强助手。请对用户输入进行以下处理：\n"
            "1. 修正错别字和语法错误\n"
            "2. 修正标点符号\n"
            "3. 将口语化表达转换为书面语\n"
            "4. 补全不完整的句子\n"
            "5. 适当调整结构使其更加清晰\n"
            "保持原文的核心语义不变。"
            "直接输出增强后的文本，不要添加任何解释或说明。"
        ),
        order=40,
    ),
    "translate_en": ModeDefinition(
        mode_id="translate_en",
        label="翻译为英文",
        prompt=(
            "You are a Chinese-to-English translator. "
            "Translate the user's Chinese input into natural, fluent English. "
            "Preserve the original meaning and tone. "
            "Output only the translated text without any explanation."
        ),
        order=50,
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
