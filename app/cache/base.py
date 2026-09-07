import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Base cache entry."""
    query_hash: str
    query_text: str
    response_text: str
    cache_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    hit_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)


class BaseCache(ABC):
    """Abstract base cache class with common interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key."""
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store value with optional TTL in seconds."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove value by key."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries."""
        raise NotImplementedError

    @abstractmethod
    def _generate_key(self, *parts: Any) -> str:
        """Generate deterministic cache key from parts."""
        raise NotImplementedError


class BaseCacheLayer(BaseCache):
    """Extended cache layer with entry support."""
    pass
