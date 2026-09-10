"""Metrics collection module for cache and LLM monitoring."""

import logging
import time
from collections import defaultdict
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and computes metrics for cache hits, misses, and LLM calls.

    Stores metrics in memory as a list of dictionaries and provides
    derived statistics including percentiles and distribution breakdowns.
    """

    def __init__(self) -> None:
        """Initialize the MetricsCollector with empty in-memory storage."""
        self._records: list[dict[str, Any]] = []

    def record_request(self) -> None:
        """Record a new request event."""
        self._records.append({
            "event": "request",
            "timestamp": time.time(),
        })
        logger.debug("Recorded request event")

    def record_cache_hit(self, cache_type: str) -> None:
        """Record a cache hit event."""
        self._records.append({
            "event": "cache_hit",
            "cache_type": cache_type,
            "timestamp": time.time(),
        })
        logger.debug("Recorded cache hit for type '%s'", cache_type)

    def record_cache_miss(self) -> None:
        """Record a cache miss event."""
        self._records.append({
            "event": "cache_miss",
            "timestamp": time.time(),
        })
        logger.debug("Recorded cache miss")

    def record_llm_call(self) -> None:
        """Record an LLM call event."""
        self._records.append({
            "event": "llm_call",
            "timestamp": time.time(),
        })
        logger.debug("Recorded LLM call")

    def record_llm_call_avoided(self) -> None:
        """Record an avoided LLM call event (served from cache)."""
        self._records.append({
            "event": "llm_call_avoided",
            "timestamp": time.time(),
        })
        logger.debug("Recorded avoided LLM call")

    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement in milliseconds."""
        if latency_ms < 0:
            logger.warning("Negative latency %f, clamping to 0", latency_ms)
            latency_ms = 0.0
        self._records.append({
            "event": "latency",
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        })
        logger.debug("Recorded latency %.2f ms", latency_ms)

    def record_tokens_saved(self, tokens: int) -> None:
        """Record the number of tokens saved by caching."""
        if tokens < 0:
            logger.warning("Negative tokens saved %d, clamping to 0", tokens)
            tokens = 0
        self._records.append({
            "event": "tokens_saved",
            "tokens": tokens,
            "timestamp": time.time(),
        })
        logger.debug("Recorded %d tokens saved", tokens)

    def record_cost_saved(self, cost: float) -> None:
        """Record the estimated cost saved by caching."""
        if cost < 0:
            logger.warning("Negative cost saved %f, clamping to 0", cost)
            cost = 0.0
        self._records.append({
            "event": "cost_saved",
            "cost": cost,
            "timestamp": time.time(),
        })
        logger.debug("Recorded cost saved %.4f", cost)

    def record_cache_decision(self, decision: str, score: float, reasons: list[str]) -> None:
        """Record a cache policy decision."""
        self._records.append({
            "event": "cache_decision",
            "decision": decision,
            "score": score,
            "reasons": reasons,
            "timestamp": time.time(),
        })
        logger.debug("Recorded cache decision: %s (score=%.4f)", decision, score)

    def record_eviction(self) -> None:
        """Record a cache eviction event."""
        self._records.append({
            "event": "eviction",
            "timestamp": time.time(),
        })

    def record_entry_expired(self) -> None:
        """Record a cache entry expiration event."""
        self._records.append({
            "event": "entry_expired",
            "timestamp": time.time(),
        })

    def get_stats(self) -> dict[str, Any]:
        """Compute and return aggregated statistics."""
        total_requests = sum(1 for r in self._records if r["event"] == "request")
        cache_hits = [r for r in self._records if r["event"] == "cache_hit"]
        cache_misses = sum(1 for r in self._records if r["event"] == "cache_miss")
        total_llm_calls = sum(1 for r in self._records if r["event"] == "llm_call")
        total_llm_avoided = sum(1 for r in self._records if r["event"] == "llm_call_avoided")
        latencies = [r["latency_ms"] for r in self._records if r["event"] == "latency"]
        tokens_saved = sum(r["tokens"] for r in self._records if r["event"] == "tokens_saved")
        cost_saved = sum(r["cost"] for r in self._records if r["event"] == "cost_saved")
        evictions = sum(1 for r in self._records if r["event"] == "eviction")
        expired = sum(1 for r in self._records if r["event"] == "entry_expired")
        decisions = [r for r in self._records if r["event"] == "cache_decision"]

        cache_type_distribution: dict[str, int] = defaultdict(int)
        for hit in cache_hits:
            cache_type_distribution[hit["cache_type"]] += 1

        decision_distribution: dict[str, int] = defaultdict(int)
        for d in decisions:
            decision_distribution[d.get("decision", "unknown")] += 1

        hit_rate = len(cache_hits) / (len(cache_hits) + cache_misses) if (cache_hits or cache_misses) else 0.0
        avg_latency_ms = float(np.mean(latencies)) if latencies else 0.0

        p50_latency_ms = 0.0
        p95_latency_ms = 0.0
        if latencies:
            p50_latency_ms = float(np.percentile(latencies, 50))
            p95_latency_ms = float(np.percentile(latencies, 95))

        stats = {
            "total_requests": total_requests,
            "cache_hits": len(cache_hits),
            "cache_misses": cache_misses,
            "hit_rate": hit_rate,
            "avg_latency_ms": avg_latency_ms,
            "p50_latency_ms": p50_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "total_llm_calls": total_llm_calls,
            "total_llm_avoided": total_llm_avoided,
            "tokens_saved": tokens_saved,
            "cost_saved": cost_saved,
            "cache_type_distribution": dict(cache_type_distribution),
            "cache_decision_distribution": dict(decision_distribution),
            "evictions": evictions,
            "expired_entries": expired,
        }

        logger.debug("Computed stats: %s", stats)
        return stats

    def clear(self) -> None:
        """Clear all recorded metrics."""
        self._records.clear()
        logger.debug("Cleared all metrics records")

    def record_hit(self, cache_type: str) -> None:
        """Record a cache hit and associated savings."""
        self.record_cache_hit(cache_type)
        self.record_llm_call_avoided()
        self.record_tokens_saved(50)
        self.record_cost_saved(0.001)

    def record_miss(self) -> None:
        """Record a cache miss and associated LLM call."""
        self.record_cache_miss()
        self.record_llm_call()

    def get_metrics(self) -> dict[str, Any]:
        """Return legacy metrics dict for API responses."""
        stats = self.get_stats()
        exact_hits = sum(
            1 for r in self._records if r.get("event") == "cache_hit" and r.get("cache_type") == "exact"
        )
        semantic_hits = sum(
            1 for r in self._records if r.get("event") == "cache_hit" and r.get("cache_type") == "semantic"
        )
        context_hits = sum(
            1 for r in self._records if r.get("event") == "cache_hit" and r.get("cache_type") == "context"
        )
        tool_hits = sum(
            1 for r in self._records if r.get("event") == "cache_hit" and r.get("cache_type") == "tool"
        )
        cache_hits = exact_hits + semantic_hits + context_hits + tool_hits
        cache_misses = sum(1 for r in self._records if r.get("event") == "cache_miss")
        total = max(cache_hits + cache_misses, 1)
        hit_rate = cache_hits / total if total > 0 else 0.0

        return {
            "total_requests": stats.get("total_requests", 0),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(hit_rate, 4),
            "exact_hits": exact_hits,
            "semantic_hits": semantic_hits,
            "context_hits": context_hits,
            "tool_hits": tool_hits,
            "llm_calls": stats.get("total_llm_calls", 0),
            "llm_calls_avoided": stats.get("total_llm_avoided", 0),
            "tokens_saved": stats.get("tokens_saved", 0),
            "estimated_cost_saved": round(stats.get("cost_saved", 0.0), 4),
            "latency_saved_ms": round(max(stats.get("total_llm_avoided", 0) * 450.0 - sum(r.get("latency_ms", 0.0) for r in self._records if r.get("event") == "latency" and r.get("latency_ms", 0.0) < 50.0), stats.get("total_llm_avoided", 0) * 420.0), 1),
            "avg_latency_ms": round(stats.get("avg_latency_ms", 0.0), 2),
            "p50_latency_ms": round(stats.get("p50_latency_ms", 0.0), 2),
            "p95_latency_ms": round(stats.get("p95_latency_ms", 0.0), 2),
            "evictions": stats.get("evictions", 0),
            "expired_entries": stats.get("expired_entries", 0),
            "cache_decision_distribution": stats.get("cache_decision_distribution", {}),
        }
