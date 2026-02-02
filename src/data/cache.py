"""Redis/disk cache decorator for data source methods.

Caches API responses with configurable TTLs to avoid hitting rate limits
and reduce latency on repeated lookups.
"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable

import redis.asyncio as redis

from src.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Generate a deterministic cache key from function arguments."""
    raw = json.dumps({"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}}, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"reanalyzer:{prefix}:{h}"


def cached(prefix: str, ttl_seconds: int = 86400):
    """Cache decorator for async data source methods.

    Args:
        prefix: Cache key prefix (e.g., "rentcast:property")
        ttl_seconds: Time-to-live in seconds (default 24 hours)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _cache_key(prefix, *args[1:], **kwargs)  # Skip self
            try:
                r = await get_redis()
                cached_value = await r.get(key)
                if cached_value is not None:
                    logger.debug("Cache hit: %s", key)
                    return json.loads(cached_value)
            except Exception:
                logger.warning("Redis unavailable, skipping cache for %s", key)

            result = await func(*args, **kwargs)

            try:
                r = await get_redis()
                await r.setex(key, ttl_seconds, json.dumps(result, default=str))
            except Exception:
                logger.warning("Failed to write cache for %s", key)

            return result
        return wrapper
    return decorator
