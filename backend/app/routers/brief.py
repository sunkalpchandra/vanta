"""Morning brief — the N things the world is most wrong about today.

Cached for 10 minutes (Redis when REDIS_URL is set, in-process otherwise).
"""

import json
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..schemas import BriefItem
from .feed import latest_forecasts

router = APIRouter(prefix="/api/brief", tags=["brief"])

CACHE_TTL_SECONDS = 600
MAX_COUNT = 20
_local_cache: dict[str, tuple[float, str]] = {}


def invalidate_brief_cache() -> None:
    """Drop all cached briefs — called when a resolution changes what's live."""
    _local_cache.clear()
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url)
            client.delete(*[f"vanta:brief:{n}" for n in range(1, MAX_COUNT + 1)])
        except Exception:
            pass  # cache is best-effort; stale entries expire by TTL anyway


def _cache_get(key: str) -> str | None:
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis

            return redis.Redis.from_url(settings.redis_url).get(key)
        except Exception:
            pass  # fall through to local cache
    hit = _local_cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    if hit:
        del _local_cache[key]
    return None


def _cache_set(key: str, value: str) -> None:
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis

            redis.Redis.from_url(settings.redis_url).setex(key, CACHE_TTL_SECONDS, value)
            return
        except Exception:
            pass
    now = time.monotonic()
    for stale in [k for k, (t, _) in _local_cache.items() if now - t >= CACHE_TTL_SECONDS]:
        del _local_cache[stale]
    _local_cache[key] = (now, value)


@router.get("", response_model=list[BriefItem])
def morning_brief(count: int = Query(5, ge=1, le=MAX_COUNT), db: Session = Depends(get_db)):
    cache_key = f"vanta:brief:{count}"
    cached = _cache_get(cache_key)
    if cached:
        return [BriefItem(**item) for item in json.loads(cached)]

    pairs = latest_forecasts(db)
    pairs.sort(key=lambda pair: abs(pair[1].probability - pair[0].market_probability), reverse=True)
    items = []
    for rank, (q, f) in enumerate(pairs[:count], start=1):
        edge = f.probability - q.market_probability
        direction = "underpricing" if edge > 0 else "overpricing"
        items.append(
            BriefItem(
                rank=rank,
                question_id=q.id,
                question=q.question,
                category=q.category,
                market_probability=q.market_probability,
                vanta_probability=f.probability,
                confidence=f.confidence,
                edge=round(edge, 4),
                one_liner=(
                    f"Markets say {q.market_probability:.0%}, vanta says {f.probability:.0%} — "
                    f"the crowd looks to be {direction} this by {abs(edge):.0%}."
                ),
            )
        )
    _cache_set(cache_key, json.dumps([i.model_dump() for i in items]))
    return items
