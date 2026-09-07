import hashlib
import json
import logging
import os
from typing import Any, Optional

import redis

from app.cache.base import BaseCache
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class ExactCache(BaseCache):
    """Redis-based exact match cache with TTL, hit counting, and LRU eviction."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: str = "exact:",
        max_entries: int = 10000,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.prefix = prefix
        self.max_entries = max_entries
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> Optional[redis.Redis]:
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._client.ping()
            except Exception as exc:
                logger.warning("Redis unavailable for ExactCache: %s", exc)
                self._client = None
        return self._client

    def _normalize_query(self, query: str) -> str:
        """Normalize query for better exact matching."""
        normalized = query.lower().strip()
        normalized = " ".join(normalized.split())
        return normalized

    def _generate_key(self, *parts: Any) -> str:
        normalized_parts = [self._normalize_query(str(p)) for p in parts]
        raw = json.dumps(normalized_parts, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"{self.prefix}{digest}"

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, default=str)

    def _deserialize(self, raw: str) -> Any:
        return json.loads(raw)

    def _enforce_lru(self, key: str) -> None:
        if self.client is None:
            return
        try:
            count = sum(1 for _ in self.client.scan_iter(match=f"{self.prefix}*"))
            if count >= self.max_entries:
                candidates = [
                    k
                    for k in self.client.scan_iter(match=f"{self.prefix}*", count=100)
                ]
                if candidates:
                    self.client.delete(*candidates[: max(1, count - self.max_entries + 1)])
        except redis.RedisError as exc:
            logger.warning("LRU enforcement failed: %s", exc)

    def get(self, key: str) -> Optional[Any]:
        if self.client is None:
            return None
        try:
            raw = self.client.get(key)
            if raw is None:
                return None
            payload = self._deserialize(raw)
            payload["_hit_count"] = int(payload.get("_hit_count", 0)) + 1
            payload["_last_accessed"] = __import__("datetime").datetime.utcnow().isoformat()
            self.client.set(key, self._serialize(payload))
            return payload.get("value")
        except (redis.RedisError, json.JSONDecodeError) as exc:
            logger.warning("ExactCache get failed for %s: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if self.client is None:
            return False
        try:
            payload = {
                "value": value,
                "_hit_count": 0,
                "_last_accessed": __import__("datetime").datetime.utcnow().isoformat(),
            }
            if ttl:
                self._enforce_lru(key)
                return bool(self.client.setex(key, ttl, self._serialize(payload)))
            self._enforce_lru(key)
            return bool(self.client.set(key, self._serialize(payload)))
        except redis.RedisError as exc:
            logger.warning("ExactCache set failed for %s: %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        if self.client is None:
            return False
        try:
            return bool(self.client.delete(key))
        except redis.RedisError as exc:
            logger.warning("ExactCache delete failed for %s: %s", key, exc)
            return False

    def clear(self) -> None:
        if self.client is None:
            return
        try:
            keys = list(self.client.scan_iter(match=f"{self.prefix}*"))
            if keys:
                self.client.delete(*keys)
        except redis.RedisError as exc:
            logger.warning("ExactCache clear failed: %s", exc)
