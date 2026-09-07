"""Tests for the intelligent caching middleware."""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cache.base import BaseCache
from app.cache.exact_cache import ExactCache
from app.cache.semantic_cache import SemanticCache
from app.cache.context_cache import ContextCache
from app.cache.tool_cache import ToolCache
from app.cache.manager import CacheManager
from app.llm.base import BaseLLM
from app.llm.mock_provider import MockProvider
from app.embeddings.encoder import EmbeddingEncoder
from app.intelligence.scorer import CachePolicyScorer
from app.intelligence.eviction import LRUEvictionPolicy
from app.metrics.collector import MetricsCollector
from app.agent.tools import AgentTools


class TestBaseCache:
    def test_generate_key(self):
        class ConcreteCache(BaseCache):
            def get(self, key: str):
                return None
            def set(self, key: str, value, ttl=None):
                return False
            def delete(self, key: str):
                return False
            def clear(self):
                pass
            def _generate_key(self, *parts):
                return "|".join(str(p) for p in parts)
        cache = ConcreteCache()
        assert cache._generate_key("hello") == cache._generate_key("hello")
        assert cache._generate_key("hello") != cache._generate_key("world")


class TestExactCache:
    @patch('redis.Redis')
    def test_set_and_get(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.scan_iter.return_value = []

        backend = {}
        def mock_set(*args, **kwargs):
            if len(args) >= 3:
                backend[args[0]] = args[2]
            else:
                backend[kwargs.get('key', '')] = kwargs.get('value')
            return True
        def mock_setex(*args, **kwargs):
            if len(args) >= 3:
                backend[args[0]] = args[2]
            return True
        def mock_get(key):
            return backend.get(key)

        mock_client.set.side_effect = mock_set
        mock_client.setex.side_effect = mock_setex
        mock_client.get.side_effect = mock_get

        cache = ExactCache("redis://localhost:6379/0")
        cache._client = mock_client

        cache.set("test_query", "test_response", ttl=3600)
        result = cache.get("test_query")

        assert result == "test_response"
        mock_client.setex.assert_called_once()

    @patch('redis.Redis')
    def test_miss(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = None

        cache = ExactCache("redis://localhost:6379/0")
        cache._client = mock_client

        result = cache.get("nonexistent_query")
        assert result is None

    @patch('redis.Redis')
    def test_delete(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client

        cache = ExactCache("redis://localhost:6379/0")
        cache._client = mock_client

        cache.delete("test_query")
        mock_client.delete.assert_called_once_with("test_query")

    @patch('app.cache.exact_cache.redis.from_url')
    @patch('app.cache.exact_cache.redis.Redis')
    def test_redis_failure_graceful(self, mock_redis_cls, mock_from_url):
        mock_from_url.side_effect = Exception("Redis connection failed")

        cache = ExactCache("redis://localhost:6379/0")
        # Force client to None to simulate Redis unavailable
        cache._client = None

        result = cache.get("test_query")
        assert result is None

        cache.set("test_query", "response")
        result = cache.get("test_query")
        assert result is None


class TestSemanticCache:
    @patch('app.cache.semantic_cache.create_engine')
    def test_store_and_search(self, mock_engine):
        mock_session = Mock()
        mock_engine.return_value.connect.return_value.__enter__ = Mock(return_value=Mock())
        mock_engine.return_value.connect.return_value.__exit__ = Mock(return_value=False)

        cache = SemanticCache()
        cache._engine = mock_engine
        cache._SessionLocal = lambda: mock_session
        cache._pgvector_available = True

        mock_session.execute.return_value.fetchone.return_value = Mock(
            id="test-id",
            query_text="test query",
            embedding=[0.1]*384,
            response='{"text": "test response"}',
            ttl_seconds=3600,
            similarity_threshold=0.85,
            hit_count=0,
            created_at=None,
            distance=0.1,
        )

        cache.store("test query", [0.1]*384, {"text": "test response"})
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()


class TestContextCache:
    @patch('app.cache.context_cache.create_engine')
    def test_set_and_get(self, mock_engine):
        mock_session = Mock()
        mock_engine.return_value.connect.return_value.__enter__ = Mock(return_value=Mock())
        mock_engine.return_value.connect.return_value.__exit__ = Mock(return_value=False)

        cache = ContextCache()
        cache._engine = mock_engine
        cache._SessionLocal = lambda: mock_session

        mock_session.execute.return_value.fetchone.return_value = Mock(
            id="test-id",
            session_id="session-1",
            context_data='{"history": []}',
            messages="[]",
            ttl_seconds=1800,
            created_at=None,
            last_accessed=None,
        )

        result = cache.get_by_session("session-1")
        assert result is not None


class TestToolCache:
    @patch('redis.Redis')
    def test_set_and_get(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = '{"value": {"result": "42"}, "_hit_count": 0}'

        cache = ToolCache("redis://localhost:6379/0")
        cache._client = mock_client

        cache.set_tool("calculator", "25*4+10", {"result": "42"}, deterministic=True)
        result = cache.get_tool("calculator", "25*4+10")

        assert result == {"result": "42"}

    @patch('redis.Redis')
    def test_deterministic_check(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client

        cache = ToolCache("redis://localhost:6379/0")
        cache._client = mock_client

        cache.set_tool("calculator", "2+2", "4", deterministic=True)
        mock_client.setex.assert_called_once()


class TestCacheManager:
    @patch('redis.Redis')
    def test_exact_hit(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = '{"value": "cached response", "_hit_count": 0}'
        mock_client.scan_iter.return_value = []

        manager = CacheManager()
        manager.exact._client = mock_client

        result = manager.get("test query")
        assert result is not None
        assert result["cache_type"] == "exact"

    @patch('redis.Redis')
    def test_miss(self, mock_redis):
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = None
        mock_client.scan_iter.return_value = []

        manager = CacheManager()
        manager.exact._client = mock_client

        result = manager.get("nonexistent query")
        assert result is None

    def test_clear_all(self):
        manager = CacheManager()
        manager.exact = Mock()
        manager.semantic = Mock()
        manager.context = Mock()
        manager.tool = Mock()

        manager.clear_all()

        manager.exact.clear.assert_called_once()
        manager.semantic.clear.assert_called_once()
        manager.context.clear.assert_called_once()
        manager.tool.clear.assert_called_once()


class TestLLMProviders:
    def test_mock_provider_basic(self):
        provider = MockProvider(latency_ms=10)
        response = provider.generate("What is 2+2?")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_mock_provider_deterministic(self):
        provider = MockProvider(latency_ms=10)
        response1 = provider.generate("test query")
        response2 = provider.generate("test query")
        assert response1 == response2

    def test_mock_provider_different_queries(self):
        provider = MockProvider(latency_ms=10)
        response1 = provider.generate("query A")
        response2 = provider.generate("query B")
        assert response1 != response2


class TestEmbeddings:
    def test_encode_returns_list(self):
        encoder = EmbeddingEncoder.__new__(EmbeddingEncoder)
        mock_arr = Mock()
        mock_arr.tolist.return_value = [0.1] * 384
        encoder._model = Mock()
        encoder._model.encode.return_value = mock_arr
        encoder._dimension = 384

        result = encoder.encode("test text")
        assert isinstance(result, list)
        assert len(result) == 384

    def test_encode_batch(self):
        encoder = EmbeddingEncoder.__new__(EmbeddingEncoder)
        mock_arr = Mock()
        mock_arr.tolist.return_value = [[0.1] * 384, [0.2] * 384]
        encoder._model = Mock()
        encoder._model.encode.return_value = mock_arr
        encoder._dimension = 384

        result = encoder.encode_batch(["text1", "text2"])
        assert len(result) == 2
        assert all(len(r) == 384 for r in result)


class TestIntelligence:
    def test_scorer_initialization(self):
        scorer = CachePolicyScorer()
        assert scorer.weights is not None
        assert abs(sum(scorer.weights.values()) - 1.0) < 0.01

    def test_should_cache_threshold(self):
        scorer = CachePolicyScorer()
        policy = scorer.compute_score("test query", "response", {
            "frequency_score": 0.8,
            "similarity_score": 0.8,
            "recency_score": 0.8,
            "reuse_probability": 0.8,
            "estimated_cost": 0.8,
            "memory_penalty": 0.1,
        })
        assert policy["decision"] in ("CACHE", "CACHE_WITH_SHORT_TTL", "CACHE_WITH_LONG_TTL")

    def test_eviction_policy(self):
        policy = LRUEvictionPolicy()
        policy.record_access("a")
        policy.record_access("b")
        policy.record_access("c")
        policy.record_access("a")

        entries = {
            "a": {"last_accessed": 1},
            "b": {"last_accessed": 2},
            "c": {"last_accessed": 3},
            "d": {"last_accessed": 4}
        }
        evicted = policy.evict_if_needed(entries, max_size=3)
        assert len(evicted) >= 1


class TestMetrics:
    def test_record_and_compute(self):
        metrics = MetricsCollector()
        metrics.record_request()
        metrics.record_request()
        metrics.record_cache_hit("exact")
        metrics.record_cache_miss()
        metrics.record_latency(100.0)
        metrics.record_latency(200.0)

        stats = metrics.get_stats()
        assert stats["total_requests"] == 2
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["avg_latency_ms"] == 150.0

    def test_percentiles(self):
        metrics = MetricsCollector()
        for latency in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            metrics.record_latency(float(latency))

        stats = metrics.get_stats()
        assert stats["p50_latency_ms"] == pytest.approx(55.0, abs=5)
        assert stats["p95_latency_ms"] >= 90.0


class TestAgentTools:
    def test_calculator_basic(self):
        tools = AgentTools()
        result = tools.calculator("2 + 2")
        assert "4" in result

    def test_calculator_complex(self):
        tools = AgentTools()
        result = tools.calculator("25 * 4 + 10")
        assert "110" in result

    def test_calculator_power(self):
        tools = AgentTools()
        result = tools.calculator("2 ** 3")
        assert "8" in result

    def test_calculator_sqrt(self):
        tools = AgentTools()
        result = tools.calculator("sqrt(16)")
        assert "4" in result

    def test_document_lookup_found(self):
        tools = AgentTools()
        result = tools.document_lookup("python")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_document_lookup_not_found(self):
        tools = AgentTools()
        result = tools.document_lookup("xyznonexistent123")
        assert "not found" in result.lower()


class TestIntegration:
    @patch('redis.Redis')
    def test_full_flow(self, mock_redis):
        """Test a full request flow through the system."""
        import time
        from app.llm.mock_provider import MockProvider
        from app.metrics.collector import MetricsCollector

        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = None
        mock_client.scan_iter.return_value = []
        mock_client.setex.return_value = True
        mock_client.set.return_value = True

        llm = MockProvider(latency_ms=50)
        metrics = MetricsCollector()
        cache_manager = CacheManager()
        cache_manager.exact._client = mock_client

        # First request - cache miss
        query = "test query"
        start = time.time()
        cached = cache_manager.get(query)
        latency1 = (time.time() - start) * 1000

        assert cached is None

        # Simulate LLM call
        response = llm.generate(query)
        cache_manager.set(query, response)

        # Second request - cache hit
        start = time.time()
        mock_client.get.return_value = '{"value": "' + response + '", "_hit_count": 0}'
        cached = cache_manager.get(query)
        latency2 = (time.time() - start) * 1000

        assert cached is not None
        assert cached["cache_type"] == "exact"
        assert cached["response"] == response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
