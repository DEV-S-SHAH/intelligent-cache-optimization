"""Application configuration using pydantic-settings."""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    redis_url: str = Field(
        default=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"
    )
    database_url: str = Field(
        default=f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}"
        f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
        f"/{os.getenv('POSTGRES_DB', 'cache_db')}"
    )
    llm_provider: str = Field(default=os.getenv("LLM_PROVIDER", "mock"))
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    ollama_model: str = Field(default=os.getenv("OLLAMA_MODEL", "llama2"))
    embedding_model: str = Field(default=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    embedding_dimension: int = Field(default=int(os.getenv("EMBEDDING_DIMENSION", "384")))
    cache_exact_ttl: int = Field(default=int(os.getenv("CACHE_EXACT_TTL", "3600")))
    cache_semantic_ttl: int = Field(default=int(os.getenv("CACHE_SEMANTIC_TTL", "86400")))
    cache_context_ttl: int = Field(default=int(os.getenv("CACHE_CONTEXT_TTL", "1800")))
    cache_tool_ttl: int = Field(default=int(os.getenv("CACHE_TOOL_TTL", "7200")))
    cache_semantic_threshold: float = Field(default=float(os.getenv("CACHE_SEMANTIC_THRESHOLD", "0.85")))
    cache_max_size: int = Field(default=int(os.getenv("CACHE_MAX_SIZE", "10000")))
    cache_lru_eviction: bool = Field(default=os.getenv("CACHE_LRU_EVICTION", "true").lower() == "true")
    default_ttl: int = Field(default=3600)
    mock_llm_delay_ms: int = Field(default=int(os.getenv("MOCK_LLM_DELAY_MS", "1000")))
    cache_score_threshold: float = Field(default=float(os.getenv("CACHE_SCORE_THRESHOLD", "0.5")))
    cache_short_ttl: int = Field(default=int(os.getenv("CACHE_SHORT_TTL", "300")))
    cache_long_ttl: int = Field(default=int(os.getenv("CACHE_LONG_TTL", "86400")))
    api_port: int = Field(default=int(os.getenv("API_PORT", "8000")))
    dashboard_port: int = Field(default=int(os.getenv("DASHBOARD_PORT", "8501")))
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    metrics_enabled: bool = Field(default=os.getenv("METRICS_ENABLED", "true").lower() == "true")

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings = Settings()


def get_settings() -> Settings:
    return _settings
