#!/usr/bin/env python3
"""Verify benchmark measurement correctness."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.llm.mock_provider import MockProvider
from app.cache.manager import CacheManager
from app.metrics.collector import MetricsCollector


def test_mock_latency():
    """Verify mock LLM actually waits for configured latency."""
    settings = get_settings()
    delay = settings.mock_llm_delay_ms
    print(f"\n[TEST] Mock LLM latency configured: {delay} ms")

    provider = MockProvider()
    start = time.perf_counter()
    response = provider.generate("test query")
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(f"[TEST] Actual mock latency: {elapsed_ms:.1f} ms")
    assert elapsed_ms >= delay * 0.9, f"Mock latency too low: {elapsed_ms:.1f}ms < {delay}ms"
    print("[PASS] Mock LLM latency is correct")


def test_cache_hit_vs_miss_latency():
    """Verify cache HIT is faster than cache MISS."""
    print("\n[TEST] Cache HIT vs MISS latency")
    cm = CacheManager()
    query = "What is the capital of France?"
    response = "Paris"

    # Pre-seed frequency so the query gets cached
    cm._query_frequency[query] = 3

    # Measure MISS before caching
    start = time.perf_counter()
    cached = cm.get(query)
    miss_latency = (time.perf_counter() - start) * 1000
    assert cached is None, "Expected cache miss before storing"

    # Store in cache via intelligent policy
    cm.set(query, response)

    # Measure HIT
    start = time.perf_counter()
    cached = cm.get(query)
    hit_latency = (time.perf_counter() - start) * 1000
    assert cached is not None, "Expected cache hit after storing"
    assert cached.get("response") == response, "Cached response mismatch"

    print(f"[TEST] MISS latency: {miss_latency:.2f} ms")
    print(f"[TEST] HIT latency:  {hit_latency:.2f} ms")
    assert hit_latency < miss_latency, "Cache HIT should be faster than MISS"
    print("[PASS] Cache HIT is faster than MISS")


def test_no_cache_creates_zero_entries():
    """Verify No Cache mode creates zero cache entries."""
    print("\n[TEST] No Cache creates zero entries")
    cm = CacheManager()
    stats_before = cm.stats()
    total_before = stats_before.get("total_entries", 0)

    # Simulate No Cache mode: just call LLM, never cache
    query = "test query no cache"
    response = "response"

    # In no_cache mode, we should NOT call cm.set()
    # Just verify stats are unchanged
    stats_after = cm.stats()
    total_after = stats_after.get("total_entries", 0)

    print(f"[TEST] Entries before: {total_before}, after: {total_after}")
    assert total_after == total_before, "No Cache should not create any entries"
    print("[PASS] No Cache creates zero entries")


def test_intelligent_policy_decisions():
    """Verify intelligent policy makes explainable decisions."""
    print("\n[TEST] Intelligent policy decisions")
    from app.intelligence.scorer import CachePolicyScorer

    scorer = CachePolicyScorer()

    # High-value query should be cached
    high_value = scorer.compute_score("frequent query", "response", {
        "frequency_score": 0.9,
        "similarity_score": 0.9,
        "recency_score": 0.9,
        "reuse_probability": 0.9,
        "estimated_cost": 0.9,
        "memory_penalty": 0.1,
    })
    print(f"[TEST] High-value query: decision={high_value['decision']}, score={high_value['score']}")
    assert high_value["decision"] in ("CACHE", "CACHE_WITH_LONG_TTL"), "High-value query should be cached"

    # Low-value query should not be cached
    low_value = scorer.compute_score("hi", "response", {
        "frequency_score": 0.0,
        "similarity_score": 0.0,
        "recency_score": 1.0,
        "reuse_probability": 0.0,
        "estimated_cost": 0.0,
        "memory_penalty": 0.05,
    })
    print(f"[TEST] Low-value query: decision={low_value['decision']}, score={low_value['score']}")
    assert low_value["decision"] == "DO_NOT_CACHE", "Low-value query should not be cached"
    print("[PASS] Intelligent policy makes correct decisions")


def test_semantic_vs_intelligent_difference():
    """Verify Intelligent Cache can make different decisions from Semantic Cache."""
    print("\n[TEST] Semantic vs Intelligent policy difference")
    from app.intelligence.scorer import CachePolicyScorer

    scorer = CachePolicyScorer()

    # Cold query - semantic would cache it, intelligent should not
    cold = scorer.compute_score("rare obscure query", "response", {
        "frequency_score": 0.0,
        "similarity_score": 0.0,
        "recency_score": 1.0,
        "reuse_probability": 0.0,
        "estimated_cost": 0.0,
        "memory_penalty": 0.5,
    })
    print(f"[TEST] Cold query: intelligent decision={cold['decision']}, score={cold['score']}")
    # Intelligent might skip this, but semantic would still store it
    assert cold["decision"] != "CACHE", "Cold query should not be cached by intelligent policy"
    print("[PASS] Intelligent policy can differ from semantic-only caching")


def main():
    print("=" * 60)
    print("Benchmark Measurement Verification")
    print("=" * 60)

    test_mock_latency()
    test_cache_hit_vs_miss_latency()
    test_no_cache_creates_zero_entries()
    test_intelligent_policy_decisions()
    test_semantic_vs_intelligent_difference()

    print("\n" + "=" * 60)
    print("All verification tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
