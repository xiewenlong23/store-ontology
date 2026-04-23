#!/usr/bin/env python3
"""
MiniMax LLM 集成
使用原生 Anthropic 客户端连接 MiniMax API
"""

import os
import json
import logging
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic"
# Load .env early so the module-level constant picks up the key
from dotenv import load_dotenv
load_dotenv()
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MODEL_NAME = os.environ.get("MINIMAX_MODEL_NAME", "MiniMax-M2.7-highspeed")  # MiniMax M2 模型


class MiniMaxLLM:
    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_NAME):
        self.api_key = api_key or MINIMAX_API_KEY
        self.model = model
        self._client: Optional[anthropic.Anthropic] = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "MINIMAX_API_KEY environment variable not set. "
                    "Set it in .env or export before running."
                )
            self._client = anthropic.Anthropic(
                base_url=MINIMAX_BASE_URL,
                api_key=self.api_key,
            )
            logger.info(f"[MiniMax] LLM initialized with model: {self.model}")
        return self._client

    def chat(self, messages: list[dict], tools: Optional[list] = None, **kwargs):
        """发送对话请求，返回模型响应文本和工具调用（如果有）"""
        try:
            # Convert messages format: {"role": "system|user|assistant", "content": "..."}
            # to Anthropic format
            anthropic_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                if role == "system":
                    # Anthropic uses user role for system-level instructions in messages array
                    role = "user"
                anthropic_messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })

            # 构建请求参数
            request_kwargs = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", 2048),
                "messages": anthropic_messages,
                "temperature": kwargs.get("temperature", 0.3),
            }

            # 如果提供了工具定义，添加到请求中
            if tools:
                request_kwargs["tools"] = tools

            response = self.client.messages.create(**request_kwargs)

            # 提取 text 和 tool_use 块
            text_parts = []
            tool_use = None
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_use = {
                        "name": block.name,
                        "input": block.input,
                    }

            text = "\n".join(text_parts) if text_parts else ""

            # 如果有工具调用，返回结构化数据
            if tool_use:
                return {
                    "type": "tool_call",
                    "text": text,
                    "tool_name": tool_use["name"],
                    "tool_args": tool_use["input"],
                }

            return text
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