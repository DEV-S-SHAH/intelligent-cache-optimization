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


class ToolCache(BaseCache):
    """Redis-based tool result cache with deterministic argument hashing."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: str = "tool:",
        default_ttl: Optional[int] = None,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.prefix = prefix
        self.default_ttl = default_ttl or settings.cache_tool_ttl
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
            except (redis.ConnectionError, redis.TimeoutError) as exc:
                logger.warning("Redis unavailable for ToolCache: %s", exc)
                self._client = None
        return self._client

    def _generate_key(self, *parts: Any) -> str:
        raw = json.dumps(parts, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"{self.prefix}{digest}"

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, default=str)

    def _deserialize(self, raw: str) -> Any:
        return json.loads(raw)

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
            logger.warning("ToolCache get failed for %s: %s", key, exc)
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        deterministic: bool = True,
    ) -> bool:
        if self.client is None:
            return False
        try:
            payload = {
                "value": value,
                "deterministic": deterministic,
                "_hit_count": 0,
                "_last_accessed": __import__("datetime").datetime.utcnow().isoformat(),
            }
            ttl = ttl or self.default_ttl
            if ttl:
                return bool(self.client.setex(key, ttl, self._serialize(payload)))
            return bool(self.client.set(key, self._serialize(payload)))
        except redis.RedisError as exc:
            logger.warning("ToolCache set failed for %s: %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        if self.client is None:
            return False
        try:
            return bool(self.client.delete(key))
        except redis.RedisError as exc:
            logger.warning("ToolCache delete failed for %s: %s", key, exc)
            return False

    def clear(self) -> None:
        if self.client is None:
            return
        try:
            keys = list(self.client.scan_iter(match=f"{self.prefix}*"))
            if keys:
                self.client.delete(*keys)
        except redis.RedisError as exc:
            logger.warning("ToolCache clear failed: %s", exc)

    def get_tool(self, tool_name: str, args: Any) -> Optional[Any]:
        """Retrieve cached tool result by tool name and args."""
        key = self._generate_key(tool_name, args)
        return self.get(key)

    def set_tool(
        self,
        tool_name: str,
        args: Any,
        result: Any,
        ttl: Optional[int] = None,
        deterministic: bool = True,
    ) -> bool:
        """Cache tool result by tool name and args."""
        key = self._generate_key(tool_name, args)
        return self.set(key, result, ttl=ttl, deterministic=deterministic)
