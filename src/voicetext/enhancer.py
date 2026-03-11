"""AI text enhancement using OpenAI Agents SDK."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EnhanceMode(Enum):
    """Available enhancement modes."""

    OFF = "off"
    PROOFREAD = "proofread"
    FORMAT = "format"
    COMPLETE = "complete"
    ENHANCE = "enhance"


_MODE_PROMPTS: Dict[EnhanceMode, str] = {
    EnhanceMode.PROOFREAD: (
        "你是一个文本纠错润色助手。请修正用户输入中的错别字、语法错误和标点符号问题。"
        "保持原文的语义和风格不变，只做必要的修正。"
        "直接输出修正后的文本，不要添加任何解释或说明。"
    ),
    EnhanceMode.FORMAT: (
        "你是一个文本格式化助手。请将用户输入的口语化文本转换为书面语，"
        "并适当调整结构使其更加清晰易读。"
        "保持原文的核心语义不变。"
        "直接输出格式化后的文本，不要添加任何解释或说明。"
    ),
    EnhanceMode.COMPLETE: (
        "你是一个智能文本补全助手。请补全用户输入中不完整的句子，"
        "使其成为完整、通顺的表达。"
        "保持原文的语义和风格不变，只补全缺失的部分。"
        "直接输出补全后的文本，不要添加任何解释或说明。"
    ),
    EnhanceMode.ENHANCE: (
        "你是一个全面的文本增强助手。请对用户输入进行以下处理：\n"
        "1. 修正错别字和语法错误\n"
        "2. 修正标点符号\n"
        "3. 将口语化表达转换为书面语\n"
        "4. 补全不完整的句子\n"
        "5. 适当调整结构使其更加清晰\n"
        "保持原文的核心语义不变。"
        "直接输出增强后的文本，不要添加任何解释或说明。"
    ),
}


class TextEnhancer:
    """Enhance transcribed text using LLM via OpenAI Agents SDK."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._enabled = config.get("enabled", False)
        self._mode = EnhanceMode(config.get("mode", "proofread"))
        self._timeout = config.get("timeout", 30)

        provider_cfg = config.get("provider", {})
        self._base_url = provider_cfg.get("base_url", "http://localhost:11434/v1")
        self._api_key = provider_cfg.get("api_key", "ollama")
        self._model = provider_cfg.get("model", "qwen2.5:7b")

        self._provider = None
        self._init_provider()

    def _init_provider(self) -> None:
        """Initialize the custom model provider."""
        try:
            from agents import ModelProvider
            from agents.models.openai_chat_completions import (
                OpenAIChatCompletionsModel,
            )
            from openai import AsyncOpenAI

            client = AsyncOpenAI(base_url=self._base_url, api_key=self._api_key)
            model_name = self._model

            class _CustomModelProvider(ModelProvider):
                def get_model(self, model_name_override: str | None = None):
                    return OpenAIChatCompletionsModel(
                        model=model_name_override or model_name,
                        openai_client=client,
                    )

            self._provider = _CustomModelProvider()
            logger.info(
                "AI enhancer initialized: model=%s, base_url=%s",
                self._model,
                self._base_url,
            )
        except ImportError as e:
            logger.warning("Failed to initialize AI enhancer: %s", e)
            self._provider = None

    @property
    def mode(self) -> EnhanceMode:
        return self._mode

    @mode.setter
    def mode(self, value: EnhanceMode) -> None:
        self._mode = value
        logger.info("AI enhance mode changed to: %s", value.value)

    @property
    def is_active(self) -> bool:
        return self._enabled and self._mode != EnhanceMode.OFF

    async def enhance(self, text: str) -> str:
        """Enhance text using LLM. Returns original text on failure."""
        if not self.is_active or not text or not text.strip():
            return text

        if self._provider is None:
            logger.warning("AI enhancer not available, returning original text")
            return text

        prompt = _MODE_PROMPTS.get(self._mode)
        if not prompt:
            return text

        try:
            from agents import Agent, RunConfig, Runner

            agent = Agent(
                name="text_enhancer",
                instructions=prompt,
                model=self._model,
            )
            run_config = RunConfig(model_provider=self._provider)
            result = await asyncio.wait_for(
                Runner.run(agent, input=text.strip(), run_config=run_config),
                timeout=self._timeout,
            )
            enhanced = result.final_output
            if enhanced and enhanced.strip():
                logger.info(
                    "Text enhanced: '%s' -> '%s'",
                    text.strip()[:50],
                    enhanced.strip()[:50],
                )
                return enhanced.strip()
            else:
                logger.warning("LLM returned empty text, using original")
                return text
        except asyncio.TimeoutError:
            logger.error("AI enhancement timed out after %ds", self._timeout)
            return text
        except Exception as e:
            logger.error("AI enhancement failed: %s", e)
            return text


def create_enhancer(config: Dict[str, Any]) -> Optional[TextEnhancer]:
    """Factory function to create a TextEnhancer from app config.

    Returns None if ai_enhance is not configured.
    """
    ai_config = config.get("ai_enhance")
    if ai_config is None:
        return None
    return TextEnhancer(ai_config)
