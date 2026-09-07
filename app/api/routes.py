from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.api.schemas import (
    GenerateRequest, GenerateResponse, HealthResponse,
    CacheStatsResponse, MetricsResponse
)
from app.cache.manager import CacheManager
from app.llm.factory import get_llm
from app.agent.tools import AgentTools
from app.metrics.collector import MetricsCollector
from app.embeddings.encoder import EmbeddingEncoder
from app.config import get_settings
import time
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()
cache_manager = CacheManager()
metrics = MetricsCollector()
encoder = EmbeddingEncoder()
agent_tools = AgentTools()


def get_llm_provider():
    return get_llm()


@router.get("/health", response_model=HealthResponse)
async def health():
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    try:
        from app.database.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres_status = "healthy"
    except Exception:
        postgres_status = "unhealthy"

    provider = get_llm_provider()
    llm_status = "healthy" if hasattr(provider, 'generate') else "degraded"

    return HealthResponse(
        status="healthy" if redis_status == "healthy" and postgres_status == "healthy" else "degraded",
        redis=redis_status,
        postgres=postgres_status,
        llm=llm_status,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    start = time.perf_counter()
    cache_hit = False
    cache_type = None
    similarity_score = None
    llm_called = False
    tool_used = None
    policy_decision = None
    response_text = ""
    tokens_saved = 0
    estimated_cost_saved = 0.0

    if request.use_tools:
        tool_name = "calculator" if any(c in request.prompt for c in ["+", "-", "*", "/"]) else "document_lookup"
        tool_entry = cache_manager.get_tool(tool_name, request.prompt)
        if tool_entry:
            cache_hit = True
            cache_type = "tool"
            response_text = tool_entry if isinstance(tool_entry, str) else str(tool_entry)
            tool_used = tool_name
            metrics.record_cache_hit("tool")
        else:
            if tool_name == "calculator":
                result = agent_tools.calculator(request.prompt)
            else:
                result = agent_tools.document_lookup(request.prompt)
            tool_used = tool_name
            cache_manager.set_tool(tool_name, request.prompt, result)
            response_text = result
            metrics.record_cache_miss()
    else:
        embedding = encoder.encode(request.prompt)
        cache_result = cache_manager.get(request.prompt, context=embedding)

        if cache_result:
            cache_hit = True
            response_text = cache_result.get("response", "")
            cache_type = cache_result.get("cache_type")
            similarity_score = cache_result.get("similarity_score")
            if cache_type == "exact":
                metrics.record_cache_hit("exact")
            elif cache_type == "semantic":
                metrics.record_cache_hit("semantic")
            metrics.record_llm_call_avoided()
        else:
            llm_called = True
            provider = get_llm_provider()
            try:
                response_text = provider.generate(request.prompt)
                metrics.record_llm_call()
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

            policy = cache_manager.set(request.prompt, response_text, context=embedding)
            policy_decision = policy.get("decision")
            metrics.record_cache_miss()
            metrics.record_cache_decision(
                policy_decision,
                policy.get("score", 0.0),
                policy.get("reasons", []),
            )

        if request.session_id:
            cache_manager.set_context(request.session_id, {
                "session_id": request.session_id,
                "last_query": request.prompt,
                "last_response": response_text,
            })

    latency = (time.perf_counter() - start) * 1000
    tokens_saved = len(request.prompt.split()) if cache_hit else 0
    estimated_cost_saved = tokens_saved * 0.00002

    metrics.record_request()
    metrics.record_latency(latency)
    if cache_hit:
        metrics.record_tokens_saved(tokens_saved)
        metrics.record_cost_saved(estimated_cost_saved)

    return GenerateResponse(
        response=response_text,
        cache_status="HIT" if cache_hit else "MISS",
        cache_type=cache_type,
        similarity_score=similarity_score,
        llm_called=llm_called,
        latency_ms=round(latency, 2),
        tokens_saved=tokens_saved if cache_hit else None,
        estimated_cost_saved=estimated_cost_saved if cache_hit else None,
        tool_used=tool_used,
        policy_decision=policy_decision,
    )


@router.get("/metrics")
async def get_metrics_endpoint():
    return metrics.get_metrics()


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    stats = cache_manager.stats()
    return CacheStatsResponse(**stats)


@router.get("/cache/entries")
async def get_cache_entries():
    return cache_manager.stats()


@router.get("/cache/decisions")
async def get_cache_decisions():
    return {
        "decisions": cache_manager._cache_decisions[-50:],
        "total": len(cache_manager._cache_decisions),
    }


@router.delete("/cache")
async def clear_cache():
    cache_manager.clear_all()
    metrics.clear()
    return {"status": "cleared"}


@router.post("/cache/invalidate")
async def invalidate_cache(request: dict):
    query = request.get("query")
    if not query:
        return {"status": "error", "message": "query is required"}
    success = cache_manager.invalidate(query)
    return {"status": "invalidated" if success else "not_found", "query": query}
