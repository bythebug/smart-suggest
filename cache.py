"""
In-memory recommendation cache with TTL.

Production note: swap _store for a Redis client to share cache across
multiple API workers. The public interface (cache_recommendations,
get_cached_recommendations, invalidate_user_cache) is unchanged.

Redis drop-in example:
    import redis
    _redis = redis.Redis.from_url(os.environ["REDIS_URL"])

    def cache_recommendations(user_id, recs, ttl=3600):
        import json
        _redis.setex(f"recs:{user_id}", ttl, json.dumps(recs))
"""

import time
from typing import Any

from sqlalchemy.orm import Session

# {cache_key: (value, expiry_monotonic_timestamp)}
_store: dict[str, tuple[Any, float]] = {}


# ---------------------------------------------------------------------------
# Low-level primitives
# ---------------------------------------------------------------------------


def _key(user_id: int, strategy: str) -> str:
    return f"recs:{strategy}:{user_id}"


def cache_recommendations(
    user_id: int,
    recommendations: list[dict],
    strategy: str = "v1",
    ttl: int = 3600,
) -> None:
    """Store a recommendation list in the cache."""
    _store[_key(user_id, strategy)] = (recommendations, time.monotonic() + ttl)


def get_cached_recommendations(
    user_id: int,
    strategy: str = "v1",
) -> list[dict] | None:
    """
    Return cached recommendations if present and not expired.
    Evicts the entry on cache miss due to expiry.
    """
    entry = _store.get(_key(user_id, strategy))
    if entry is None:
        return None
    value, expiry = entry
    if time.monotonic() > expiry:
        _store.pop(_key(user_id, strategy), None)
        return None
    return value


def invalidate_user_cache(user_id: int) -> int:
    """
    Remove all cached recommendation lists for a user (all strategies).
    Returns the number of entries removed.
    """
    prefix = f"recs:"
    keys = [k for k in _store if k.startswith(f"recs:") and k.endswith(f":{user_id}")]
    for k in keys:
        _store.pop(k, None)
    return len(keys)


def clear_all() -> int:
    """Flush the entire cache. Returns number of entries removed."""
    count = len(_store)
    _store.clear()
    return count


# ---------------------------------------------------------------------------
# High-level helper: get from cache or generate
# ---------------------------------------------------------------------------


def get_or_generate(
    user_id: int,
    strategy: str,
    db: Session,
    count: int = 10,
    ttl: int = 3600,
) -> list[dict]:
    """
    Return cached recommendations for a user, generating and caching them
    on a cache miss.

    strategy: 'v1' (collaborative filtering) or 'v2' (content-based)
    """
    cached = get_cached_recommendations(user_id, strategy)
    if cached is not None:
        return cached[:count]

    if strategy == "v1":
        from recommenders.cf import get_cf_recommendations
        recs = get_cf_recommendations(db, user_id=user_id, n=count)
    elif strategy == "v2":
        from recommenders.content import get_content_recommendations
        recs = get_content_recommendations(db, user_id=user_id, n=count)
    else:
        raise ValueError(f"Unknown strategy {strategy!r}. Choose 'v1' or 'v2'.")

    if recs:
        cache_recommendations(user_id, recs, strategy=strategy, ttl=ttl)

    return recs
