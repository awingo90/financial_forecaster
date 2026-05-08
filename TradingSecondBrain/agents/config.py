"""Centralized configuration loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Paths
    vault_path: Path = Path.home() / "TradingSecondBrain" / "obsidian-vault"

    # LLMs
    ollama_base_url: str = "http://localhost:11434"
    ollama_reasoning_model: str = "qwen3:32b"          # or "deepseek-r1:32b"
    ollama_embedding_model: str = "nomic-embed-text"

    # Optional cloud fallback (off by default — VAULT.md §2.5 requires opt-in)
    allow_cloud_llm: bool = False
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Vector DB
    vector_backend: str = "qdrant"                     # "qdrant" | "chroma"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "trading_vault"
    chroma_path: str = "./chroma_storage"

    # Obsidian Local REST API
    obsidian_api_url: str = "http://127.0.0.1:27124"   # http port; use 27123 for https
    obsidian_api_key: str = ""

    # Market data
    polygon_api_key: str | None = None

    # API server
    api_host: str = "127.0.0.1"
    api_port: int = 8088
    api_token: str = "changeme-local-token"

    # Risk caps (mirrors TRADING_SYSTEM.md — hard-coded so an LLM can't override)
    max_single_name_pct: float = 2.0
    max_basket_pct: float = 5.0
    max_drawdown_pct: float = 15.0
    min_reward_risk: float = 2.0


settings = Settings()
