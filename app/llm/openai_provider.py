import os
import logging
from typing import Optional

from .base import BaseLLM

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider")

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError as e:
            raise ImportError("openai package is required for OpenAIProvider") from e

    def generate(self, prompt: str, **kwargs) -> str:
        return self._track_latency(lambda: self._generate(prompt, **kwargs))

    def _generate(self, prompt: str, **kwargs) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            raise
