"""
Store Ontology Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    store_id: str = "STORE_001"
    feishu_bot_token: Optional[str] = None
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    nebula_graph_host: str = "localhost"
    nebula_graph_port: int = 9669
    sparql_endpoint: str = "http://localhost:7200"
    langsmith_api_key: Optional[str] = None
    # Deep Agent 模型配置
    default_model: str = "minimax:MiniMax-M2.7-flash"
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    dashscope_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
