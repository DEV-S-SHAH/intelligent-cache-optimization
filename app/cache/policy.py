from typing import Optional
from app.config import get_settings

settings = get_settings()


class CachePolicy:
    def __init__(self, enabled: bool = None):
        self.enabled = enabled if enabled is not None else settings.cache_policy_enabled

    def should_cache(self, query: str, response_length: int, estimated_cost: float, frequency: int = 1) -> bool:
        if not self.enabled:
            return True

        if len(query.strip()) < 3:
            return False

        if response_length < 5:
            return False

        if estimated_cost < 0.0001:
            return False

        score = self._score(query, response_length, estimated_cost, frequency)
        return score > 0.5

    def _score(self, query: str, response_length: int, estimated_cost: float, frequency: int) -> float:
        length_score = min(response_length / 500.0, 1.0)
        cost_score = min(estimated_cost / 0.01, 1.0)
        freq_score = min(frequency / 10.0, 1.0)
        reuse_score = 0.6 if "explain" in query.lower() or "what is" in query.lower() else 0.3

        return (0.25 * length_score) + (0.25 * cost_score) + (0.25 * freq_score) + (0.25 * reuse_score)
