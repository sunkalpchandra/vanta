"""Morning brief — the N things the world is most wrong about today.

Cached for 10 minutes (Redis when REDIS_URL is set, in-process otherwise).
"""

import html
import json
import time

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..schemas import BriefItem, Category
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
            keys = client.keys("vanta:brief:*")
            if keys:
                client.delete(*keys)
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
def morning_brief(
    count: int = Query(5, ge=1, le=MAX_COUNT),
    category: Category | None = Query(None),
    db: Session = Depends(get_db),
):
    cache_key = f"vanta:brief:{count}:{category or 'all'}"
    cached = _cache_get(cache_key)
    if cached:
        return [BriefItem(**item) for item in json.loads(cached)]

    pairs = latest_forecasts(db)
    if category:
        pairs = [pair for pair in pairs if pair[0].category == category]
    pairs.sort(key=lambda pair: abs(pair[1].probability - pair[0].market_probability), reverse=True)
    # A brief that's five takes on the same sector isn't a brief: cap each
    # category at 2 slots, backfilling with the next-best edges if the cap
    # would leave slots empty.
    MAX_PER_CATEGORY = 2
    picked: list = []
    per_category: dict[str, int] = {}
    for pair in pairs:
        if len(picked) >= count:
            break
        cat = pair[0].category
        if per_category.get(cat, 0) >= MAX_PER_CATEGORY:
            continue
        per_category[cat] = per_category.get(cat, 0) + 1
        picked.append(pair)
    if len(picked) < count:  # not enough category diversity — fill by edge
        chosen = {id(p) for p in picked}
        for pair in pairs:
            if len(picked) >= count:
                break
            if id(pair) not in chosen:
                picked.append(pair)
    # Backfill can append a skipped high-edge pair after lower-edge picks;
    # ranks must stay monotonic in |edge| for the UI, RSS, and copy text.
    picked.sort(key=lambda pair: abs(pair[1].probability - pair[0].market_probability), reverse=True)
    items = []
    for rank, (q, f) in enumerate(picked[:count], start=1):
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


@router.get("/rss")
def morning_brief_rss(
    count: int = Query(5, ge=1, le=MAX_COUNT),
    category: Category | None = Query(None),
    db: Session = Depends(get_db),
):
    """The brief as RSS — subscribe to what the world is wrong about."""
    # Direct call: every default must be passed explicitly, or FastAPI Query
    # sentinels leak in as truthy values (this emptied the whole feed once).
    items = morning_brief(count=count, category=category, db=db)
    entries = "".join(
        f"""
  <item>
    <title>{html.escape(f"{i.question} — market {i.market_probability:.0%}, vanta {i.vanta_probability:.0%}")}</title>
    <description>{html.escape(i.one_liner)}</description>
    <guid isPermaLink="false">vanta-brief-{i.question_id}</guid>
  </item>"""
        for i in items
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>vanta Morning Brief</title>
  <link>https://sunkalpchandra.github.io/vanta/brief/</link>
  <description>The things the world is most wrong about, from the vanta agent pipeline.</description>{entries}
</channel>
</rss>"""
    return Response(content=xml, media_type="application/rss+xml")
