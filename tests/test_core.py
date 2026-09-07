import pytest
import hashlib
from unittest.mock import MagicMock, patch
from app.cache.base import CacheEntry
from app.cache.exact_cache import ExactCache
from app.cache.tool_cache import ToolCache
from app.cache.policy import CachePolicy
from app.intelligence.scorer import CachePolicyScorer
from app.metrics.collector import MetricsCollector
from app.agent.tools import AgentTools
from app.config import get_settings


def test_metrics_collector():
    m = MetricsCollector()
    m.record_request()
    m.record_cache_hit("exact")
    m.record_cache_miss()
    m.record_latency(100.0)
    m.record_latency(200.0)

    data = m.get_metrics()
    assert data["total_requests"] == 1
    assert data["cache_hits"] == 1
    assert data["cache_misses"] == 1
    assert data["exact_hits"] == 1
    assert data["avg_latency_ms"] == 150.0


def test_metrics_hit_rate():
    m = MetricsCollector()
    m.record_request()
    for _ in range(9):
        m.record_cache_hit("semantic")
        m.record_llm_call_avoided()
    m.record_cache_miss()
    m.record_llm_call()
    data = m.get_metrics()
    assert abs(data["cache_hit_rate"] - 0.9) < 0.01


def test_tool_result_cache():
    with patch("redis.from_url") as mock_redis:
        client = MagicMock()
        mock_redis.return_value = client
        client.get.return_value = None

        cache = ToolCache("redis://localhost:6379/0")
        cache._client = client

        result = cache.get_tool("calculator", "2+2")
        assert result is None

        client.setex.return_value = True
        cache.set_tool("calculator", "2+2", "4", deterministic=True)
        client.setex.assert_called_once()


def test_cache_policy():
    policy = CachePolicy(enabled=True)
    assert policy.should_cache("What is Python?", 500, 0.01) is True
    assert policy.should_cache("hi", 5, 0.00001) is False
    assert policy.should_cache("", 0, 0.0) is False


def test_cache_scorer():
    scorer = CachePolicyScorer()
    policy = scorer.compute_score("test query", "response", {
        "frequency_score": 0.8,
        "similarity_score": 0.8,
        "recency_score": 0.8,
        "reuse_probability": 0.8,
        "estimated_cost": 0.8,
        "memory_penalty": 0.1,
    })
    assert policy["decision"] in ("CACHE", "CACHE_WITH_SHORT_TTL", "CACHE_WITH_LONG_TTL", "DO_NOT_CACHE")
    assert 0.0 <= policy["score"] <= 1.0


def test_calculator():
    tools = AgentTools()
    result = tools.calculator("2+2")
    assert "4" in result
    result = tools.calculator("25 * 4 + 10")
    assert "110" in result
    result = tools.calculator("2 ** 3")
    assert "8" in result
    result = tools.calculator("sqrt(16)")
    assert "4" in result


def test_document_lookup():
    tools = AgentTools()
    result = tools.document_lookup("Tell me about python")
    assert "Python" in result
    result = tools.document_lookup("random unknown topic xyz")
    assert "not found" in result.lower()
