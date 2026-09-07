import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    """Standard LLM response model."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: float
    finish_reason: Optional[str] = None


class BaseLLM(ABC):
    """Abstract base for string-returning LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response string for the given prompt."""
        pass

    def _track_latency(self, func):
        start = time.perf_counter()
        try:
            return func()
        finally:
            elapsed = time.perf_counter() - start
            logger.debug("LLM call completed in %.3fs", elapsed)


class BaseLLMProvider(ABC):
    """Abstract base for structured LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate a structured response for the given prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is reachable."""
        pass
