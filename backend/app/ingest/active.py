"""Live-market sync: active-market clients + the stateless reconcile loop.

This is the "constantly add/remove with the news" engine behind the
play-money trading surface: it mirrors what Polymarket and Kalshi currently
list, keeps synced venue prices fresh, and flips events off the tradable
surface when the venue settles or delists them. Virtual credits only — the
prices are real, the money never is.

Live-API notes (probed 2026-08-10):
- gamma /markets?closed=false&active=true is offset-paginated with the same
  ~2000 depth cap as the closed feed (422 "offset too large"). Active rows
  keep the JSON-encoded string list fields (`outcomes`, `outcomePrices`,
  `clobTokenIds`); `closedTime` is null and `category` is null on newer
  rows, so tags are the category fallback. Ordering by volumeNum descending
  makes "first N pages" mean "top-N markets by volume".
- Kalshi /markets?status=open is a firehose of multivariate combo junk:
  60,000 rows walked contained 312 real markets, first at page 17 — so
  client-side filtering alone makes a 3-page pull useless. The undocumented
  `mve_filter=exclude` param (probed working) removes combos server-side;
  what remains is mostly intraday micro-strikes (hourly Brent/silver
  ladders, open→close under 3 hours), which the lifetime filter drops.
- gamma /markets?id=<id> returns a one-element list — the settlement
  sweep's per-event lookup. Kalshi GET /markets/{ticker} returns
  {"market": {...}} with `result` set to "yes"/"no" once settled.
"""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from . import kalshi
from .polymarket import (
    GAMMA_MARKETS_URL,
    _get_json,
    _json_list,
    _outcome_from_prices,
    _parse_end_date,
)
from .polymarket import (
    SOURCE as POLYMARKET,
)
from .polymarket import (
    normalize_category as normalize_polymarket_category,
)

KALSHI = kalshi.SOURCE
_TIMEOUT = 30.0

# Tradable-price band: a synced price at (or beyond) the rails is either a
# near-settled market or one nobody is pricing — junk for paper trading.
MIN_PRICE = 0.01
MAX_PRICE = 0.99

# Kalshi open markets shorter than this are the intraday micro-strike flood
# (hourly commodity ladders) — noise, not news-driven markets.
MIN_KALSHI_LIFETIME_DAYS = 3


# ---------------------------------------------------------------- Polymarket


def fetch_active_polymarket(offset: int, limit: int = 100) -> list[dict]:
    """One offset page of open gamma markets, top volume first. [] means
    exhaustion — including gamma's ~2000 offset depth cap, which for the
    live surface just means "you already have the top markets"."""
    params = {
        "closed": "false",
        "active": "true",
        "limit": limit,
        "offset": offset,
        "order": "volumeNum",
        "ascending": "false",
        "include_tag": "true",
    }
    try:
        payload = _get_json(GAMMA_MARKETS_URL, params)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 422 and "offset too large" in exc.response.text:
            return []
        raise
    return payload if isinstance(payload, list) else []


def normalize_active(market: dict) -> dict | None:
    """Turn a raw gamma active row into live MarketEvent kwargs, or None.

    Keeps binary Yes/No markets with a real question and a current YES price
    inside [0.01, 0.99] — anything pinned to the rails is near-settled junk
    that shouldn't be tradable. Category may be "other": the markets surface
    is the whole venue, not the curated feed."""
    source_id = str(market.get("id") or "").strip()
    question = str(market.get("question") or "").strip()
    if not source_id or len(question) < 10:
        return None
    if _json_list(market.get("outcomes")) != ["Yes", "No"]:
        return None

    prices: list[float] = []
    for value in _json_list(market.get("outcomePrices")):
        try:
            prices.append(float(value))
        except (TypeError, ValueError):
            return None
    if not prices:
        return None
    yes_price = prices[0]
    if not (MIN_PRICE <= yes_price <= MAX_PRICE):
        return None

    volume = market.get("volumeNum")
    if volume is None:
        try:
            volume = float(market.get("volume") or 0.0)
        except (TypeError, ValueError):
            volume = 0.0

    tags = [tag["label"] for tag in market.get("tags") or [] if isinstance(tag, dict) and tag.get("label")]
    closed = bool(market.get("closed"))
    return {
        "source": POLYMARKET,
        "source_id": source_id,
        "question": question,
        "category": normalize_polymarket_category(market.get("category"), tags),
        "close_time": _parse_end_date(market.get("endDate")),
        "volume_usd": float(volume),
        "yes_price": yes_price,
        # Trimmed raw — full gamma rows run 5-10 KB; keep what later needs.
        "raw": {
            "slug": market.get("slug"),
            "clobTokenIds": [str(token) for token in _json_list(market.get("clobTokenIds"))],
            "endDate": market.get("endDate"),
        },
        # Venue-state markers for sync_active (not MarketEvent columns).
        "closed": closed,
        "outcome": _outcome_from_prices(prices) if closed and len(prices) == 2 else None,
    }


# -------------------------------------------------------------------- Kalshi


def normalize_active_kalshi(market: dict) -> dict | None:
    """Turn a raw Kalshi open-market row into live MarketEvent kwargs, or
    None for junk. Active variant of `kalshi.normalize` (which requires a
    settled result): same junk rules — binary, non-MVE, a title that reads
    as a question — plus two live-surface filters: lifetime >= 3 days
    (kills the intraday micro-strike flood) and a last price strictly
    inside (0.01, 0.99) (a market nobody priced isn't tradeable paper)."""
    ticker = market.get("ticker") or ""
    title = (market.get("title") or "").strip()
    if not ticker or market.get("market_type", "binary") != "binary":
        return None
    if ticker.startswith("KXMVE") or market.get("mve_collection_ticker") or market.get("mve_selected_legs"):
        return None
    if len(title) < 10 or " " not in title or title.startswith(("yes ", "no ")):
        return None
    open_time = kalshi._parse_time(market.get("open_time"))
    close_time = kalshi._parse_time(market.get("close_time"))
    if open_time is None or close_time is None:
        return None
    if close_time - open_time < timedelta(days=MIN_KALSHI_LIFETIME_DAYS):
        return None
    yes_price = kalshi._final_price(market)
    if yes_price is None or not (MIN_PRICE < yes_price < MAX_PRICE):
        return None

    question = title.replace("**", "").strip()
    subtitle = (market.get("yes_sub_title") or "").strip()
    if subtitle and subtitle.lower() not in question.lower():
        question = f"{question} ({subtitle})"

    result = market.get("result")
    outcome = {"yes": 1, "no": 0}.get(result)
    return {
        "source": KALSHI,
        "source_id": ticker,
        "question": question,
        "category": kalshi.normalize_category(market.get("category"), ticker),
        "close_time": close_time,
        "volume_usd": kalshi._volume(market) or 0.0,
        "yes_price": yes_price,
        "raw": {key: value for key, value in market.items() if key not in ("rules_primary", "rules_secondary")},
        "closed": market.get("status") in ("closed", "settled", "finalized") or outcome is not None,
        "outcome": outcome,
    }


def fetch_active_kalshi(
    cursor: str | None = None,
    limit: int = 1000,
    *,
    client: httpx.Client | None = None,
) -> tuple[list[dict], str | None]:
    """One page of open Kalshi markets, normalized and filtered. Returns
    (rows, next_cursor); next_cursor None means pagination is exhausted.

    Not routed through `kalshi.fetch_markets` because it can't pass
    `mve_filter=exclude`, and without that server-side filter the open feed
    is unusable (probed 2026-08-10: 60k rows -> 312 real markets)."""
    params: dict = {"limit": limit, "status": "open", "mve_filter": "exclude"}
    if cursor:
        params["cursor"] = cursor
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=_TIMEOUT)
    try:
        response = client.get(f"{kalshi.BASE_URL}/markets", params=params)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            client.close()
    rows = [row for row in (normalize_active_kalshi(m) for m in payload.get("markets", [])) if row is not None]
    return rows, (payload.get("cursor") or None)


# ------------------------------------------------------- stateless reconcile


def sync_active(db, rows: list[dict], source: str) -> dict:
    """Reconcile one fetch's normalized rows against market_events. Stateless
    by design: presence in the active feed means tradable, a venue-reported
    close means not. Returns {"added", "updated", "closed"} counts.

    - unseen (source, source_id) -> insert with active=True, last_synced=now
    - existing, row still open   -> refresh yes_price/volume_usd/last_synced
      (and relist if a stale deactivation was premature)
    - existing, row closed/resolved -> set outcome when derivable and flip
      active off; paying out positions is the settlement sweep's job.

    Never touches price_7d/price_30d (the backtest price pass owns those)
    and never overwrites an already-recorded outcome."""
    from app.models import MarketEvent

    counts = {"added": 0, "updated": 0, "closed": 0}
    rows = [row for row in rows if row["source"] == source]
    if not rows:
        return counts
    now = datetime.now(UTC)
    ids = [row["source_id"] for row in rows]
    existing = {
        event.source_id: event
        for event in db.scalars(
            select(MarketEvent).where(MarketEvent.source == source, MarketEvent.source_id.in_(ids))
        )
    }
    for row in rows:
        venue_closed = bool(row.get("closed")) or row.get("outcome") is not None
        event = existing.get(row["source_id"])
        if event is None:
            event = MarketEvent(
                source=source,
                source_id=row["source_id"],
                question=row["question"],
                category=row["category"],
                close_time=row.get("close_time"),
                outcome=row.get("outcome"),
                volume_usd=row.get("volume_usd") or 0.0,
                raw=row.get("raw") or {},
                active=not venue_closed,
                yes_price=row.get("yes_price"),
                last_synced=now,
            )
            db.add(event)
            existing[row["source_id"]] = event  # in-batch duplicates update, not double-insert
            counts["added"] += 1
        elif venue_closed:
            if event.outcome is None and row.get("outcome") is not None:
                event.outcome = row["outcome"]
            if row.get("yes_price") is not None:
                event.yes_price = row["yes_price"]
            event.active = False
            event.last_synced = now
            counts["closed"] += 1
        else:
            event.yes_price = row["yes_price"]
            event.volume_usd = row.get("volume_usd") or 0.0
            event.close_time = row.get("close_time") or event.close_time
            event.last_synced = now
            # Reappearing after a stale deactivation relists it — unless it
            # already resolved, which permanently removes it from trading.
            if event.outcome is None:
                event.active = True
            counts["updated"] += 1
    return counts


def deactivate_stale(db, source: str, older_than_hours: float) -> int:
    """Delist events the venue no longer returns: active rows whose
    last_synced predates the cutoff flip active=False but stay in the
    corpus (and open positions are untouched — settlement handles those
    if the venue later reports a resolution). Returns the flip count."""
    from app.models import MarketEvent

    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
    flipped = 0
    for event in db.scalars(
        select(MarketEvent).where(MarketEvent.source == source, MarketEvent.active.is_(True))
    ):
        last = event.last_synced
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)  # SQLite drops tzinfo
        if last is None or last < cutoff:
            event.active = False
            flipped += 1
    return flipped


# ---------------------------------------------------------- settlement probe


def fetch_venue_row(source: str, source_id: str, *, client: httpx.Client | None = None) -> dict | None:
    """Current venue row for one event — the settlement sweep's lookup.
    None when the venue no longer knows the id (delisted/purged)."""
    if source == POLYMARKET:
        payload = _get_json(GAMMA_MARKETS_URL, {"id": source_id})
        return payload[0] if isinstance(payload, list) and payload else None
    if source == KALSHI:
        owns_client = client is None
        if owns_client:
            client = httpx.Client(timeout=_TIMEOUT)
        try:
            response = client.get(f"{kalshi.BASE_URL}/markets/{source_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json().get("market")
        finally:
            if owns_client:
                client.close()
    from . import manifold  # local: manifold imports from this module

    if source == manifold.SOURCE:
        return manifold.fetch_market(source_id)
    raise ValueError(f"unknown source {source!r}")


def resolution_of(source: str, row: dict | None) -> int | None:
    """1/0 when a venue row shows a final YES/NO resolution; None while the
    market is open, ambiguous, or the resolution hasn't reached the API."""
    if row is None:
        return None
    if source == POLYMARKET:
        if not row.get("closed"):
            return None
        prices: list[float] = []
        for value in _json_list(row.get("outcomePrices")):
            try:
                prices.append(float(value))
            except (TypeError, ValueError):
                return None
        return _outcome_from_prices(prices) if len(prices) == 2 else None
    if source == KALSHI:
        return {"yes": 1, "no": 0}.get(row.get("result"))
    from . import manifold  # local: manifold imports from this module

    if source == manifold.SOURCE:
        return manifold.resolution_of(row)
    raise ValueError(f"unknown source {source!r}")
