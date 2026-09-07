from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    use_cache: bool = True
    cache_type: Optional[str] = None
    use_tools: bool = False
    tool_calls: Optional[list[dict]] = None


class GenerateResponse(BaseModel):
    response: str
    cache_status: str
    cache_type: Optional[str] = None
    similarity_score: Optional[float] = None
    llm_called: bool
    latency_ms: float
    tokens_saved: Optional[int] = None
    estimated_cost_saved: Optional[float] = None
    tool_used: Optional[str] = None
    policy_decision: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    redis: str
    postgres: str
    llm: str


class CacheStatsResponse(BaseModel):
    exact_entries: int
    semantic_entries: int
    context_entries: int
    tool_entries: int
    total_entries: int
    max_size: int
    avg_hits_per_entry: float
    evictions: int
    cache_decision_distribution: Dict[str, int]


class MetricsResponse(BaseModel):
    total_requests: int
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    exact_hits: int
    semantic_hits: int
    context_hits: int
    tool_hits: int
    llm_calls: int
    llm_calls_avoided: int
    tokens_saved: int
    estimated_cost_saved: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    evictions: int
    expired_entries: int
    cache_decision_distribution: Dict[str, int]
