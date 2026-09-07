import httpx
import time
from typing import Optional
from app.llm.base import BaseLLMProvider, LLMResponse
from app.config import get_settings

settings = get_settings()


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        start = time.perf_counter()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        latency = (time.perf_counter() - start) * 1000
        content = data.get("response", "")
        tokens_used = data.get("eval_count", None)

        return LLMResponse(
            content=content,
            model=self.model,
            tokens_used=tokens_used,
            latency_ms=latency,
            finish_reason="stop",
        )

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
