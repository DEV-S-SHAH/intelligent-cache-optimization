import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.cache.manager import CacheManager
from app.llm.mock_provider import MockProvider
from app.metrics.collector import MetricsCollector


client = TestClient(app)


def test_health():
    with patch("app.api.routes.get_llm_provider") as mock_provider:
        mock_provider.return_value = MagicMock()
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data


def test_generate_cache_miss():
    with patch("app.api.routes.cache_manager") as mock_mgr, \
         patch("app.api.routes.get_llm_provider") as mock_provider, \
         patch("app.api.routes.encoder") as mock_encoder:
        mock_mgr.get.return_value = None
        mock_mgr.set.return_value = {
            "decision": "CACHE",
            "score": 0.8,
            "reasons": ["high frequency"],
        }
        mock_provider.return_value.generate.return_value = "Mock response"
        mock_encoder.encode.return_value = [0.1] * 384
        payload = {"prompt": "Unique query 12345", "session_id": "s1"}
        r = client.post("/generate", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["cache_status"] == "MISS"
        assert data["llm_called"] is True


def test_generate_cache_hit():
    with patch("app.api.routes.cache_manager") as mock_mgr, \
         patch("app.api.routes.encoder") as mock_encoder:
        mock_mgr.get.return_value = {
            "response": "Cached response",
            "cache_type": "exact",
            "similarity_score": None,
        }
        mock_encoder.encode.return_value = [0.1] * 384
        payload = {"prompt": "Cached query", "session_id": "s1"}
        r = client.post("/generate", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["cache_status"] == "HIT"
        assert data["llm_called"] is False


def test_metrics_endpoint():
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "total_requests" in data
    assert "cache_hit_rate" in data


def test_cache_stats():
    with patch("app.api.routes.cache_manager") as mock_mgr:
        mock_mgr.stats.return_value = {
            "exact_entries": 0,
            "semantic_entries": 0,
            "context_entries": 0,
            "tool_entries": 0,
            "total_entries": 0,
            "max_size": 10000,
            "avg_hits_per_entry": 0.0,
            "total_decisions": 0,
            "cache_decision_distribution": {},
            "evictions": 0,
            "expired_entries": 0,
        }
        r = client.get("/cache/stats")
        assert r.status_code == 200


def test_clear_cache():
    with patch("app.api.routes.cache_manager") as mock_mgr, \
         patch("app.api.routes.metrics") as mock_metrics:
        mock_mgr.clear_all.return_value = None
        mock_metrics.clear.return_value = None
        r = client.delete("/cache")
        assert r.status_code == 200
