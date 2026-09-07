"""Cache eviction policies module."""

import logging
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


class LRUEvictionPolicy:
    """Least Recently Used (LRU) eviction policy for cache management.

    Uses an OrderedDict to maintain insertion order and track access recency.
    When the cache exceeds max_size, the least recently used entries are evicted.
    """

    def __init__(self) -> None:
        """Initialize the LRU eviction policy with an empty ordered dictionary."""
        self._cache: OrderedDict[str, Any] = OrderedDict()

    def record_access(self, key: str) -> None:
        """Record an access to a cache entry, moving it to the end (most recent).

        Args:
            key: The cache key that was accessed.
        """
        if key not in self._cache:
            self._cache[key] = None
            logger.debug("Recorded new access for key '%s'", key)
        else:
            self._cache.move_to_end(key)
            logger.debug("Recorded access for key '%s'", key)

    def evict_if_needed(
        self, cache_entries: dict[str, Any], max_size: int
    ) -> list[str]:
        """Evict least recently used entries if the cache exceeds max_size.

        Args:
            cache_entries: Dictionary of current cache entries.
            max_size: Maximum allowed number of entries in the cache.

        Returns:
            List of evicted keys.
        """
        if max_size <= 0:
            logger.warning("max_size is %d, evicting all entries", max_size)
            evicted = list(cache_entries.keys())
            cache_entries.clear()
            return evicted

        current_size = len(cache_entries)
        if current_size <= max_size:
            logger.debug(
                "Cache size %d is within limit %d, no eviction needed",
                current_size,
                max_size,
            )
            return []

        overflow = current_size - max_size
        evicted: list[str] = []

        for _ in range(overflow):
            if self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                if oldest_key in cache_entries:
                    del cache_entries[oldest_key]
                    evicted.append(oldest_key)
                    logger.debug("Evicted key '%s'", oldest_key)

        logger.info("Evicted %d keys: %s", len(evicted), evicted)
        return evicted

    def get_order(self) -> list[str]:
        """Return the current access order from most recent to least recent.

        Returns:
            List of keys ordered from most recent to least recent.
        """
        return list(reversed(list(self._cache.keys())))
