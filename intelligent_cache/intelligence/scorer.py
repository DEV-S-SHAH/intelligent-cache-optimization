"""Intelligent cache policy scoring and TTL optimization."""

import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CachePolicyScorer:
    """Computes explainable caching decisions and adaptive TTL based on query and response utility."""

    def __init__(
        self,
        default_ttl: int = 3600,
        short_ttl: int = 300,
        long_ttl: int = 86400,
        cache_threshold: float = 0.30,
        long_ttl_threshold: float = 0.65,
    ):
        self.default_ttl = default_ttl
        self.short_ttl = short_ttl
        self.long_ttl = long_ttl
        self.cache_threshold = cache_threshold
        self.long_ttl_threshold = long_ttl_threshold

        # Weights
        self.weights = {
            "frequency": 0.25,
            "complexity_cost": 0.25,
            "latency": 0.20,
            "recency": 0.15,
            "similarity": 0.15,
            "size_penalty": 0.10,
        }

    def compute_decision(
        self,
        query: str,
        response: Any,
        frequency: int = 1,
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        similarity_score: Optional[float] = None,
        custom_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Compute an explainable cache decision.
        
        Returns:
            Dictionary containing score, decision, recommended_ttl, factors, and rationale.
        """
        if not query or not str(query).strip() or response is None:
            return {
                "score": 0.0,
                "decision": "DO_NOT_CACHE",
                "recommended_ttl": 0,
                "rationale": "Empty query or response. Do not cache.",
                "factors": {"frequency": 0.0, "cost": 0.0, "latency": 0.0, "similarity": 0.0, "size_penalty": 0.0},
            }

        # Frequency factor (saturates around 3-5 queries)
        freq_factor = min(1.0, frequency / 3.0)

        # Complexity / Cost factor based on tokens or length
        try:
            p_tokens = int(prompt_tokens)
        except (ValueError, TypeError):
            p_tokens = 0
        try:
            c_tokens = int(completion_tokens)
        except (ValueError, TypeError):
            c_tokens = 0
        total_tokens = p_tokens + c_tokens
        if total_tokens > 0:
            cost_factor = min(1.0, math.log(1 + total_tokens) / math.log(1000))
        else:
            resp_str = str(response)
            cost_factor = min(1.0, math.log(1 + len(resp_str)) / math.log(2000))

        # Latency factor (higher latency = higher incentive to cache)
        latency_factor = min(1.0, latency_ms / 1500.0) if latency_ms > 0 else 0.5

        # Recency / similarity factor
        sim_factor = similarity_score if similarity_score is not None else 0.5
        recency_factor = 0.8  # Newly generated result has fresh recency

        # Size penalty (penalize extremely large responses over 100KB)
        size_bytes = len(str(response).encode("utf-8"))
        size_penalty = 0.0
        if size_bytes > 50000:
            size_penalty = min(1.0, (size_bytes - 50000) / 200000.0)

        # Weighted score
        raw_score = (
            self.weights["frequency"] * freq_factor
            + self.weights["complexity_cost"] * cost_factor
            + self.weights["latency"] * latency_factor
            + self.weights["recency"] * recency_factor
            + self.weights["similarity"] * sim_factor
            - self.weights["size_penalty"] * size_penalty
        )
        score = max(0.0, min(1.0, raw_score))

        # Decision
        if score >= self.long_ttl_threshold:
            decision = "CACHE"
            recommended_ttl = self.long_ttl
            rationale = f"High utility score ({score:.2f}) due to high cost/latency/frequency. Cache with long TTL ({self.long_ttl}s)."
        elif score >= self.cache_threshold:
            decision = "CACHE"
            recommended_ttl = self.default_ttl
            rationale = f"Normal utility score ({score:.2f}). Cache with default TTL ({self.default_ttl}s)."
        else:
            decision = "DO_NOT_CACHE"
            recommended_ttl = 0
            rationale = f"Low utility score ({score:.2f}). Ephemeral or high storage penalty. Do not cache."

        return {
            "score": round(score, 4),
            "decision": decision,
            "recommended_ttl": recommended_ttl,
            "rationale": rationale,
            "factors": {
                "frequency": round(freq_factor, 3),
                "cost": round(cost_factor, 3),
                "latency": round(latency_factor, 3),
                "similarity": round(sim_factor, 3),
                "size_penalty": round(size_penalty, 3),
            },
        }
