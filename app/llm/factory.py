import os
import logging
from typing import Optional

from .base import BaseLLM
from .openai_provider import OpenAIProvider
from .mock_provider import MockProvider

logger = logging.getLogger(__name__)


def get_llm(provider: Optional[str] = None) -> BaseLLM:
    provider = provider or os.getenv("LLM_PROVIDER", "mock").lower()

    if provider == "openai":
        logger.debug("Initializing OpenAI provider")
        return OpenAIProvider()
    elif provider == "mock":
        logger.debug("Initializing Mock provider")
        return MockProvider()
    elif provider == "ollama":
        logger.debug("Initializing Ollama provider (using OpenAI-compatible client)")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model = os.getenv("OLLAMA_MODEL", "llama2")
        return OpenAIProvider(base_url=base_url, model=model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
