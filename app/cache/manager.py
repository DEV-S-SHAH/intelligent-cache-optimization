"""Cache manager coordinating all cache layers."""

import logging
import time
from collections import defaultdict
from typing import Any, Optional

from app.cache.base import BaseCache
from app.cache.context_cache import ContextCache
from app.cache.exact_cache import ExactCache
from app.cache.semantic_cache import SemanticCache
from app.cache.tool_cache import ToolCache
from app.embeddings.encoder import EmbeddingEncoder
from app.intelligence.scorer import CachePolicyScorer
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class CacheManager:
    """Coordinates multiple cache layers with fallback and error handling."""

    def __init__(
        self,
        exact_cache: Optional[ExactCache] = None,
        semantic_cache: Optional[SemanticCache] = None,
        context_cache: Optional[ContextCache] = None,
        tool_cache: Optional[ToolCache] = None,
        embedding_encoder: Optional[EmbeddingEncoder] = None,
        policy_scorer: Optional[CachePolicyScorer] = None,
    ):
        self.exact = exact_cache or ExactCache()
        self.semantic = semantic_cache or SemanticCache()
        self.context = context_cache or ContextCache()
        self.tool = tool_cache or ToolCache()
        self.encoder = embedding_encoder or EmbeddingEncoder()
        self.scorer = policy_scorer or CachePolicyScorer()

        self._query_frequency: dict[str, int] = defaultdict(int)
        self._cache_decisions: list[dict[str, Any]] = []
        self._hits_per_entry: dict[str, int] = defaultdict(int)

    def get(self, query: str, context: Optional[Any] = None) -> Optional[Any]:
        """Get cached response with layer fallback: exact -> semantic -> None."""
        self._query_frequency[query] += 1
        key = self.exact._generate_key(query)
        try:
            result = self.exact.get(key)
            if result is not None:
                self._hits_per_entry[key] += 1
                logger.debug("Cache hit (exact) for query: %s", query[:100])
                return {"response": result, "cache_type": "exact", "similarity_score": None}
        except Exception as exc:
            logger.warning("ExactCache get failed: %s", exc)

        try:
            embedding = context if isinstance(context, list) else None
            if embedding is not None:
                hit = self.semantic.search_by_similarity(
                    query_embedding=embedding,
                    threshold=self.semantic.similarity_threshold,
                    limit=1,
                )
                if hit is not None:
                    entry, similarity = hit
                    entry_id = entry.get("id")
                    if entry_id:
                        self._hits_per_entry[entry_id] += 1
                    logger.debug("Cache hit (semantic) for query: %s", query[:100])
                    return {
                        "response": entry.get("response"),
                        "cache_type": "semantic",
                        "similarity_score": similarity,
                    }
        except Exception as exc:
            logger.warning("SemanticCache search failed: %s", exc)

        logger.debug("Cache miss for query: %s", query[:100])
        return None

    def set(
        self,
        query: str,
        response: Any,
        context: Optional[Any] = None,
        ttl: Optional[int] = None,
    ) -> dict[str, Any]:
        """Store response using intelligent cache policy.

        Returns policy decision details.
        """
        metadata = self._build_metadata(query, response, context)
        policy = self.scorer.compute_score(query, response, metadata)
        decision = policy["decision"]
        ttl = self.scorer.get_ttl_for_decision(decision)

        key = self.exact._generate_key(query)
        success = True

        if decision == "CACHE":
            try:
                self.exact.set(key, response, ttl=ttl)
            except Exception as exc:
                logger.warning("ExactCache set failed: %s", exc)
                success = False
            if isinstance(context, list):
                try:
                    self.semantic.store(
                        query_text=query,
                        embedding=context,
                        response=response,
                        ttl=ttl,
                        threshold=self.semantic.similarity_threshold,
                    )
                except Exception as exc:
                    logger.warning("SemanticCache store failed: %s", exc)

        elif decision == "CACHE_WITH_SHORT_TTL":
            try:
                self.exact.set(key, response, ttl=self.scorer.short_ttl)
            except Exception as exc:
                logger.warning("ExactCache set failed: %s", exc)
                success = False

        elif decision == "CACHE_WITH_LONG_TTL":
            if isinstance(context, list):
                try:
                    self.semantic.store(
                        query_text=query,
                        embedding=context,
                        response=response,
                        ttl=self.scorer.long_ttl,
                        threshold=self.semantic.similarity_threshold,
                    )
                except Exception as exc:
                    logger.warning("SemanticCache store failed: %s", exc)

        return policy

    def _build_metadata(self, query: str, response: Any, context: Optional[Any]) -> dict[str, Any]:
        """Build metadata for cache policy scoring."""
        freq = self._query_frequency.get(query, 0)
        frequency_score = min(1.0, freq / 3.0)

        similarity_score = 0.0
        if isinstance(context, list):
            try:
                hit = self.semantic.search_by_similarity(
                    query_embedding=context,
                    threshold=self.semantic.similarity_threshold,
                    limit=1,
                )
                if hit is not None:
                    _, similarity = hit
                    similarity_score = similarity
            except Exception:
                pass

        recency_score = 1.0

        reuse_probability = 0.0
        if freq > 0:
            reuse_probability = min(1.0, 0.4 + freq * 0.3)

        response_size = len(str(response)) if response is not None else 0
        memory_penalty = min(1.0, response_size / 10000.0)

        estimated_cost = min(1.0, reuse_probability * 0.7 + frequency_score * 0.3)

        return {
            "frequency_score": frequency_score,
            "similarity_score": similarity_score,
            "recency_score": recency_score,
            "reuse_probability": reuse_probability,
            "estimated_cost": estimated_cost,
            "memory_penalty": memory_penalty,
        }

    def get_context(self, session_id: str) -> Optional[Any]:
        """Get conversation context by session_id."""
        try:
            return self.context.get_by_session(session_id)
        except Exception as exc:
            logger.warning("ContextCache get failed: %s", exc)
            return None

    def set_context(
        self,
        session_id: str,
        context: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Store conversation context by session_id."""
        try:
            return self.context.set_context(session_id, context, ttl=ttl)
        except Exception as exc:
            logger.warning("ContextCache set failed: %s", exc)
            return False

    def get_tool(self, tool_name: str, args: Any) -> Optional[Any]:
        """Get cached tool result."""
        try:
            return self.tool.get_tool(tool_name, args)
        except Exception as exc:
            logger.warning("ToolCache get failed: %s", exc)
            return None

    def set_tool(
        self,
        tool_name: str,
        args: Any,
        result: Any,
        ttl: Optional[int] = None,
        deterministic: bool = True,
    ) -> bool:
        """Cache tool result."""
        try:
            return self.tool.set_tool(
                tool_name, args, result, ttl=ttl, deterministic=deterministic
            )
        except Exception as exc:
            logger.warning("ToolCache set failed: %s", exc)
            return False

    def invalidate(self, query: str) -> bool:
        """Invalidate exact and semantic cache entries for a query."""
        key = self.exact._generate_key(query)
        success = True
        try:
            if not self.exact.delete(key):
                success = False
        except Exception as exc:
            logger.warning("ExactCache invalidate failed: %s", exc)
            success = False

        try:
            self.semantic.invalidate(query)
        except Exception as exc:
            logger.warning("SemanticCache invalidate failed: %s", exc)
            success = False

        return success

    def clear_all(self) -> None:
        """Clear all cache layers and internal tracking."""
        for cache in (self.exact, self.semantic, self.context, self.tool):
            try:
                cache.clear()
            except Exception as exc:
                logger.warning("Cache clear failed: %s", exc)

        self._query_frequency.clear()
        self._cache_decisions.clear()
        self._hits_per_entry.clear()

    def stats(self) -> dict[str, Any]:
        """Return cache statistics including efficiency metrics."""
        exact_entries = 0
        try:
            if self.exact.client:
                exact_entries = sum(1 for _ in self.exact.client.scan_iter(match=f"{self.exact.prefix}*"))
        except Exception:
            pass

        semantic_entries = 0
        try:
            from app.database.session import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM semantic_cache"))
                semantic_entries = result.scalar() or 0
        except Exception:
            pass

        context_entries = 0
        try:
            from app.database.session import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM context_cache"))
                context_entries = result.scalar() or 0
        except Exception:
            pass

        tool_entries = 0
        try:
            if self.tool.client:
                tool_entries = sum(1 for _ in self.tool.client.scan_iter(match=f"{self.tool.prefix}*"))
        except Exception:
            pass

        total_entries = exact_entries + semantic_entries + context_entries + tool_entries
        avg_hits = 0.0
        if self._hits_per_entry:
            avg_hits = sum(self._hits_per_entry.values()) / len(self._hits_per_entry)

        decision_counts: dict[str, int] = defaultdict(int)
        for d in self._cache_decisions:
            decision_counts[d.get("decision", "unknown")] += 1

        return {
            "exact_entries": exact_entries,
            "semantic_entries": semantic_entries,
            "context_entries": context_entries,
            "tool_entries": tool_entries,
            "total_entries": total_entries,
            "max_size": settings.cache_max_size,
            "avg_hits_per_entry": round(avg_hits, 2),
            "total_decisions": len(self._cache_decisions),
            "cache_decision_distribution": dict(decision_counts),
            "evictions": 0,
            "expired_entries": 0,
        }
