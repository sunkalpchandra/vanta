"""Polymarket closed-market client + normalizer for the backtest corpus.

Live-API notes (probed 2026-08-10 against gamma-api.polymarket.com):
- GET /markets?closed=true is offset-paginated but rejects offsets past
  ~2000 with a 422 ("offset too large, use /markets/keyset"). The keyset
  endpoint takes the same filters plus `after_cursor` and returns
  {"markets": [...], "next_cursor": "..."} (param name from the openapi
  spec; `cursor` is silently ignored).
- `outcomes`, `outcomePrices` and `clobTokenIds` are JSON-encoded *strings*
  (e.g. '["Yes", "No"]'), not arrays.
- Resolved binary markets settle to exact "1"/"0" (CLOB era) or floats a
  hair off 1/0 (AMM era, e.g. "0.9999998..."). '["0", "0"]' means the
  resolution never reached the API — outcome unknown.
- `include_tag=true` adds a `tags` list ([{"label": ...}, ...]); newer
  markets have no `category` field, so tags are the category fallback.
- GET clob.polymarket.com/prices-history?market=TOKEN&interval=max&fidelity=1440
  returns {"history": [{"t": unix_seconds, "p": yes_price}, ...]} oldest
  first; empty for markets that lived less than a daily bucket.
"""

import json
import time
from datetime import UTC, datetime

import httpx

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GAMMA_KEYSET_URL = "https://gamma-api.polymarket.com/markets/keyset"
CLOB_HISTORY_URL = "https://clob.polymarket.com/prices-history"
SOURCE = "polymarket"
_TIMEOUT = 30.0
_MAX_RETRIES = 5
_BACKOFF_SECONDS = 1.0  # doubles per attempt on 429/5xx/transport errors

# A settled side must be at least this close to 1 to count as the winner
# (AMM-era markets settle to e.g. 0.9999998 rather than exactly 1).
_WINNER_THRESHOLD = 0.99

# Polymarket `category` values and tag labels (lowercased) -> vanta's set.
# Tag lists put specific labels first ("Ethereum") and generic last
# ("Crypto"), so every alias worth catching needs its own entry.
_CATEGORY_MAP = {
    "politics": "politics",
    "us-current-affairs": "politics",
    "u.s. politics": "politics",
    "global politics": "politics",
    "geopolitics": "politics",
    "elections": "politics",
    "crypto": "crypto",
    "crypto prices": "crypto",
    "cryptocurrency": "crypto",
    "nfts": "crypto",
    "bitcoin": "crypto",
    "ethereum": "crypto",
    "solana": "crypto",
    "sports": "sports",
    "olympics": "sports",
    "esports": "sports",
    "nba": "sports",
    "nfl": "sports",
    "mlb": "sports",
    "nhl": "sports",
    "soccer": "sports",
    "tennis": "sports",
    "golf": "sports",
    "boxing": "sports",
    "ufc": "sports",
    "mma": "sports",
    "f1": "sports",
    "cricket": "sports",
    "science": "science",
    "space": "science",
    "coronavirus": "science",
    "covid": "science",
    "climate": "science",
    "weather": "science",
    "health": "science",
    "medicine": "science",
    "business": "finance",
    "finance": "finance",
    "economics": "finance",
    "economy": "finance",
    "inflation": "finance",
    "interest rates": "finance",
    "fed rates": "finance",
    "stocks": "finance",
    "earnings": "finance",
    "tech": "technology",
    "technology": "technology",
    "big tech": "technology",
    "ai": "technology",
    "artificial intelligence": "technology",
    "openai": "technology",
    "cybersecurity": "technology",
}


class OffsetCapReached(Exception):
    """gamma rejects deep /markets offsets; callers switch to keyset paging."""


def _get_json(url: str, params: dict):
    """GET with retry + exponential backoff on 429/5xx and transport blips.
    Other 4xx raise httpx.HTTPStatusError immediately (caller bug or cap)."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = httpx.get(url, params=params, timeout=_TIMEOUT)
        except httpx.TransportError as exc:
            last_error = exc
            time.sleep(_BACKOFF_SECONDS * 2**attempt)
            continue
        if response.status_code == 429 or response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                f"{response.status_code} from {url}", request=response.request, response=response
            )
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else _BACKOFF_SECONDS * 2**attempt
            except ValueError:
                delay = _BACKOFF_SECONDS * 2**attempt
            time.sleep(delay)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"gave up on {url} after {_MAX_RETRIES} attempts") from last_error


def fetch_markets(offset: int, limit: int = 100) -> list[dict]:
    """One offset page of closed markets, oldest ids first. Raises
    OffsetCapReached at gamma's depth limit; [] means exhaustion."""
    params = {
        "closed": "true",
        "limit": limit,
        "offset": offset,
        "order": "id",
        "ascending": "true",
        "include_tag": "true",
    }
    try:
        payload = _get_json(GAMMA_MARKETS_URL, params)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 422 and "offset too large" in exc.response.text:
            raise OffsetCapReached(f"gamma rejected offset {offset}") from exc
        raise
    return payload if isinstance(payload, list) else []


def fetch_markets_keyset(after_cursor: str | None = None, limit: int = 100) -> tuple[list[dict], str | None]:
    """One keyset page of closed markets (same ordering/filters as
    fetch_markets, no depth cap). Returns (rows, next_cursor); next_cursor
    None means pagination is exhausted."""
    params = {"closed": "true", "limit": limit, "order": "id", "ascending": "true", "include_tag": "true"}
    if after_cursor:
        params["after_cursor"] = after_cursor
    payload = _get_json(GAMMA_KEYSET_URL, params)
    return payload.get("markets") or [], (payload.get("next_cursor") or None)


def fetch_price_history(clob_token_id: str) -> list[dict]:
    """Daily YES-price history as [{"t": unix_seconds, "p": price}], oldest
    first. Empty for markets shorter than one daily bucket."""
    params = {"market": clob_token_id, "interval": "max", "fidelity": 1440}
    payload = _get_json(CLOB_HISTORY_URL, params)
    return payload.get("history") or []


def _json_list(value) -> list:
    """Decode gamma's JSON-encoded string fields; [] for anything malformed."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _parse_end_date(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)  # 3.11+ accepts the trailing Z
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _outcome_from_prices(prices: list[float]) -> int | None:
    """1/0 when exactly one side settled at ~1; None when the resolution
    never reached the API (["0", "0"]) or the prices are ambiguous."""
    yes_price, no_price = prices
    if yes_price >= _WINNER_THRESHOLD and no_price <= 1 - _WINNER_THRESHOLD:
        return 1
    if no_price >= _WINNER_THRESHOLD and yes_price <= 1 - _WINNER_THRESHOLD:
        return 0
    return None


def normalize_category(category: str | None, tags: list[str] = ()) -> str:
    """Map Polymarket's category (or, failing that, its tag labels in order)
    onto vanta's normalized set; "other" when nothing matches."""
    for label in (category, *tags):
        if not label:
            continue
        mapped = _CATEGORY_MAP.get(label.strip().lower())
        if mapped:
            return mapped
    return "other"


def normalize(market: dict) -> dict | None:
    """Turn a raw gamma market into MarketEvent kwargs, or None for junk.

    Keeps only clean binary markets: outcomes exactly ["Yes", "No"], a
    question, and a parseable endDate. Multi-outcome buckets, scalar
    markets and rows without dates are rejected — the backtest corpus is
    strictly yes/no events."""
    source_id = str(market.get("id") or "").strip()
    question = str(market.get("question") or "").strip()
    # Anchor to the ACTUAL close when gamma provides it: markets that
    # resolve early ("...by Dec 31" settling in June) would otherwise get
    # their T-h snapshot taken AFTER resolution — pure leakage.
    close_time = _parse_end_date(market.get("closedTime")) or _parse_end_date(market.get("endDate"))
    if not source_id or not question or close_time is None:
        return None
    if _json_list(market.get("outcomes")) != ["Yes", "No"]:
        return None

    prices: list[float] = []
    for value in _json_list(market.get("outcomePrices")):
        try:
            prices.append(float(value))
        except (TypeError, ValueError):
            prices = []
            break
    outcome = _outcome_from_prices(prices) if len(prices) == 2 else None
    final_price = prices[0] if len(prices) == 2 else None  # YES side

    volume = market.get("volumeNum")
    if volume is None:
        try:
            volume = float(market.get("volume") or 0.0)
        except (TypeError, ValueError):
            volume = 0.0

    tags = [tag["label"] for tag in market.get("tags") or [] if isinstance(tag, dict) and tag.get("label")]
    # Trimmed raw: the full gamma row (description + nested events) runs
    # 5-10 KB — untenable at 100k rows. Keep what later stages need.
    raw = {
        "clobTokenIds": [str(token) for token in _json_list(market.get("clobTokenIds"))],
        "slug": market.get("slug"),
        "category": market.get("category"),
        "tags": tags,
        "outcomePrices": prices,
        "endDate": market.get("endDate"),
        "closedTime": market.get("closedTime"),
    }
    return {
        "source": SOURCE,
        "source_id": source_id,
        "question": question,
        "category": normalize_category(market.get("category"), tags),
        "close_time": close_time,
        "outcome": outcome,
        "volume_usd": float(volume),
        "final_price": final_price,
        "raw": raw,
    }


def price_at(history: list[dict], close_time: datetime, days_before: int) -> float | None:
    """Last known price at or before close_time - days_before. Only ever
    looks backwards from the cutoff — the leakage-safety contract: a point
    AFTER the cutoff is never read, however close. None when no history
    exists that early. history points are {"t": unix seconds, "p": price};
    naive close_time is treated as UTC (SQLite drops tzinfo)."""
    if close_time.tzinfo is None:
        close_time = close_time.replace(tzinfo=UTC)
    cutoff = close_time.timestamp() - days_before * 86400
    best_t = None
    best_p = None
    for point in history:
        t = point.get("t")
        p = point.get("p")
        if t is None or p is None or t > cutoff:
            continue
        if best_t is None or t > best_t:
            best_t, best_p = t, p
    return float(best_p) if best_p is not None else None


def upsert_events(session, rows: list[dict]) -> tuple[int, int]:
    """Insert normalized rows whose (source, source_id) isn't already in the
    DB; existing rows are skipped untouched (idempotent re-runs, and the
    price pass owns price_7d/price_30d). Returns (kept, skipped)."""
    from sqlalchemy import select

    from app.models import MarketEvent

    if not rows:
        return 0, 0
    kept = skipped = 0
    existing_unresolved: dict[tuple[str, str], object] = {}
    seen: set[tuple[str, str]] = set()
    for source in {row["source"] for row in rows}:
        ids = [row["source_id"] for row in rows if row["source"] == source]
        for row_obj in session.scalars(
            select(MarketEvent).where(MarketEvent.source == source, MarketEvent.source_id.in_(ids))
        ):
            seen.add((source, row_obj.source_id))
            if row_obj.outcome is None:
                existing_unresolved[(source, row_obj.source_id)] = row_obj
    for row in rows:
        key = (row["source"], row["source_id"])
        if key in seen:
            # Resolution can reach gamma AFTER first ingest ("0","0" prices):
            # refresh the settlement fields on rows we stored as unresolved.
            # Price columns stay untouched — the price pass owns those.
            stale = existing_unresolved.get(key)
            if stale is not None and row.get("outcome") is not None:
                stale.outcome = row["outcome"]
                stale.final_price = row.get("final_price")
                stale.close_time = row.get("close_time") or stale.close_time
                stale.raw = row.get("raw") or stale.raw
                existing_unresolved.pop(key)
            skipped += 1
            continue
        session.add(MarketEvent(**row))
        seen.add(key)  # duplicates within one batch skip too
        kept += 1
    return kept, skipped
