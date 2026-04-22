#!/usr/bin/env python3
"""
MiniMax LLM 集成
使用 LangChain ChatOpenAI 兼容接口连接 MiniMax API
"""

import os
import json
import logging
from typing import Optional

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic"
MINIMAX_API_KEY=os.getenv("MINIMAX_API_KEY", "")
MODEL_NAME = "MiniMax-M2.7"  # MiniMax M2.7 模型


class MiniMaxLLM:
    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_NAME):
        self.api_key = api_key or MINIMAX_API_KEY
        self.model = model
        self._llm: Optional[ChatOpenAI] = None

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            if not self.api_key:
                raise ValueError(
                    "MINIMAX_API_KEY environment variable not set. "
                    "Set it in .env or export before running."
                )
            self._llm = ChatOpenAI(
                model=self.model,
                base_url=MINIMAX_BASE_URL,
                api_key=self.api_key,
                temperature=0.3,
                max_tokens=2048,
            )
            logger.info(f"[MiniMax] LLM initialized with model: {self.model}")
        return self._llm

    def chat(self, messages: list[dict], **kwargs):
        """发送对话请求，返回模型响应文本"""
        try:
            response = self.llm.invoke(messages, **kwargs)
            return response.content
        except Exception as e:
            logger.error(f"[MiniMax] Chat failed: {e}")
            raise


# 全局单例
_llm_instance: Optional[MiniMaxLLM] = None


def get_minimax_llm() -> MiniMaxLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = MiniMaxLLM()
    return _llm_instance


def init_minimax_llm(api_key: Optional[str] = None) -> MiniMaxLLM:
    global _llm_instance
    _llm_instance = MiniMaxLLM(api_key=api_key)
    return _llm_instance