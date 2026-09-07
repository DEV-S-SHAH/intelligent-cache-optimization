"""Cache policy scoring module with explainable decisions."""

import math
import logging
import os
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class CachePolicyScorer:
    """Computes an explainable cache score and makes caching decisions.

    Decision types:
        CACHE
        DO_NOT_CACHE
        CACHE_WITH_SHORT_TTL
        CACHE_WITH_LONG_TTL

    Factors (all normalized to 0.0-1.0):
        frequency_score
        similarity_score
        recency_score
        reuse_probability
        estimated_cost
        memory_penalty

    Weights are configurable via environment variables.
    """

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        threshold: Optional[float] = None,
        short_ttl: Optional[int] = None,
        long_ttl: Optional[int] = None,
    ):
        self.weights = weights or {
            "frequency_score": float(os.getenv("WEIGHT_FREQUENCY", "0.20")),
            "similarity_score": float(os.getenv("WEIGHT_SIMILARITY", "0.25")),
            "recency_score": float(os.getenv("WEIGHT_RECENCY", "0.15")),
            "reuse_probability": float(os.getenv("WEIGHT_REUSE", "0.20")),
            "estimated_cost": float(os.getenv("WEIGHT_COST", "0.10")),
            "memory_penalty": float(os.getenv("WEIGHT_MEMORY", "0.10")),
        }
        self.threshold = threshold if threshold is not None else settings.cache_score_threshold
        self.short_ttl = short_ttl or settings.cache_short_ttl
        self.long_ttl = long_ttl or settings.cache_long_ttl
        self._normalize_weights()

    def _normalize_weights(self) -> None:
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def compute_score(
        self,
        query_text: str,
        response: Any,
        cache_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute the cache score and decision for a given query and response.

        Args:
            query_text: The input query text.
            response: The response object to be cached.
            cache_metadata: Dictionary containing metadata such as:
                - frequency_score (float): 0.0-1.0
                - similarity_score (float): 0.0-1.0
                - recency_score (float): 0.0-1.0 (1.0 = most recent)
                - reuse_probability (float): 0.0-1.0
                - estimated_cost (float): 0.0-1.0
                - memory_penalty (float): 0.0-1.0 (higher = more expensive to cache)

        Returns:
            Dictionary containing score, decision, reasons, and factor scores.
        """
        factors = {
            "frequency_score": self._score_frequency(cache_metadata.get("frequency_score", 0.0)),
            "similarity_score": self._score_similarity(cache_metadata.get("similarity_score", 0.0)),
            "recency_score": self._score_recency(cache_metadata.get("recency_score", 0.0)),
            "reuse_probability": self._score_reuse(cache_metadata.get("reuse_probability", 0.0)),
            "estimated_cost": self._score_cost(cache_metadata.get("estimated_cost", 0.0)),
            "memory_penalty": self._score_memory(cache_metadata.get("memory_penalty", 0.0)),
        }

        total_score = sum(self.weights.get(k, 0.0) * v for k, v in factors.items())
        total_score = max(0.0, min(1.0, total_score))

        decision, reasons = self._make_decision(total_score, factors)

        result = {
            "score": round(total_score, 4),
            "decision": decision,
            "reasons": reasons,
            "factors": {k: round(v, 4) for k, v in factors.items()},
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "threshold": self.threshold,
        }

        logger.info(
            "Cache policy decision=%s score=%.4f query=%s reasons=%s",
            decision,
            total_score,
            query_text[:100],
            reasons,
        )

        return result

    def _make_decision(self, score: float, factors: dict[str, float]) -> tuple[str, list[str]]:
        """Make a caching decision based on score and factors."""
        reasons: list[str] = []

        if score >= 0.85:
            decision = "CACHE"
        elif score >= 0.70:
            decision = "CACHE_WITH_SHORT_TTL"
        elif score >= 0.50:
            decision = "CACHE_WITH_LONG_TTL"
        else:
            decision = "DO_NOT_CACHE"

        if factors.get("frequency_score", 0) > 0.7:
            reasons.append("high frequency")
        if factors.get("similarity_score", 0) > 0.8:
            reasons.append("high similarity")
        if factors.get("recency_score", 0) > 0.7:
            reasons.append("recent query")
        if factors.get("reuse_probability", 0) > 0.6:
            reasons.append("high reuse probability")
        if factors.get("estimated_cost", 0) > 0.6:
            reasons.append("high estimated cost")
        if factors.get("memory_penalty", 0) < 0.3:
            reasons.append("low memory cost")

        if not reasons:
            if score < 0.5:
                reasons.append("low overall score")
            elif score < 0.7:
                reasons.append("moderate score")

        return decision, reasons

    def _score_frequency(self, frequency: float) -> float:
        return max(0.0, min(1.0, frequency))

    def _score_similarity(self, similarity: float) -> float:
        return max(0.0, min(1.0, similarity))

    def _score_recency(self, recency: float) -> float:
        return max(0.0, min(1.0, recency))

    def _score_reuse(self, reuse: float) -> float:
        return max(0.0, min(1.0, reuse))

    def _score_cost(self, cost: float) -> float:
        return max(0.0, min(1.0, cost))

    def _score_memory(self, memory: float) -> float:
        return 1.0 - max(0.0, min(1.0, memory))

    def get_ttl_for_decision(self, decision: str) -> Optional[int]:
        """Get the TTL for a given cache decision."""
        if decision == "CACHE":
            return self.long_ttl
        elif decision == "CACHE_WITH_SHORT_TTL":
            return self.short_ttl
        elif decision == "CACHE_WITH_LONG_TTL":
            return self.long_ttl
        return None
