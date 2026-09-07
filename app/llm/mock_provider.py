import os
import logging
import time
import hashlib
import random
import string
from typing import Optional, Iterator

from .base import BaseLLM
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MockProvider(BaseLLM):
    def __init__(self, latency_ms: Optional[int] = None) -> None:
        self.latency_ms = latency_ms if latency_ms is not None else settings.mock_llm_delay_ms

    def generate(self, prompt: str, **kwargs) -> str:
        return self._track_latency(lambda: self._generate(prompt, **kwargs))

    def _generate(self, prompt: str, **kwargs) -> str:
        time.sleep(self.latency_ms / 1000.0)
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        seed = h % (10**8)
        rng = random.Random(seed)
        words = ["mock", "response", "for", "prompt", "hash", str(seed), "generated"]
        response = " ".join(rng.choices(words, k=rng.randint(5, 12)))
        logger.debug("Mock response generated for prompt hash %d", seed)
        return response

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        full = self.generate(prompt, **kwargs)
        for char in full:
            yield char
