"""Manifold Markets client + normalizers — the third venue.

Two surfaces, same as Polymarket/Kalshi:
- `normalize` feeds the backtest corpus (market_events): resolved binary
  questions with a YES/NO outcome (MKT/unresolved keep the row with a NULL
  outcome; CANCEL rows are dropped entirely — a voided market has no signal).
- `normalize_active` feeds the play-money trading surface via
  `app.ingest.active.sync_active`: only non-resolved binary markets that
  still close in the future and whose current probability sits strictly
  inside the tradable band.

Play money · paper trading · real market prices — the probabilities are
Manifold's real numbers; the ⓥ credits they trade against never are.

Live-API notes (probed 2026-08-10 against api.manifold.markets):
- GET /v0/markets?limit=1000&before=<id> is a lite-market firehose sorted
  newest-created first; `before` takes a market id and returns markets
  created before it, so paginating means passing the last row's id as the
  next `before`. [] means exhaustion.
- Binary markets carry `probability` (0-1 current YES price); `outcomeType`
  gates the shape (only 'BINARY' is a clean yes/no — MULTIPLE_CHOICE,
  MULTI_NUMERIC, POLL, DATE, PSEUDO_NUMERIC, PERP all rejected).
- `closeTime` is epoch milliseconds; `isResolved` + `resolution`
  ('YES'|'NO'|'MKT'|'CANCEL'|null, plus per-answer ids on multi markets we
  never see) carry settlement. `volume` is the traded total.
- GET /v0/market/{id} returns a single full row (404 when unknown) — the
  settlement sweep's per-event lookup; `resolution_of` reads it.
"""

from datetime import UTC, datetime

import httpx

from .active import MAX_PRICE, MIN_PRICE
from .polymarket import _get_json

MARKETS_URL = "https://api.manifold.markets/v0/markets"
MARKET_URL = "https://api.manifold.markets/v0/market"
SOURCE = "manifold"

# Manifold has topic groups, but they're per-market group slugs rather than a
# clean category field — skip them for now and file every row under "other".
DEFAULT_CATEGORY = "other"

# A real question, not a blank or one-word stub (mirrors the Polymarket
# active-surface floor).
MIN_QUESTION_LEN = 10

_RESOLUTION_OUTCOME = {"YES": 1, "NO": 0}


def fetch_markets(before: str | None = None, limit: int = 1000) -> list[dict]:
    """One page of lite markets, newest-created first, with retry/backoff.

    `before` is the previous page's last id (the cursor); None starts from
    the newest market. Returns the raw rows; [] means pagination is
    exhausted. Reuses Polymarket's `_get_json` for the shared 429/5xx
    exponential-backoff behavior."""
    params: dict = {"limit": limit}
    if before:
        params["before"] = before
    payload = _get_json(MARKETS_URL, params)
    return payload if isinstance(payload, list) else []


def fetch_market(market_id: str) -> dict | None:
    """Full single-market row — the settlement sweep's per-event lookup.
    None when Manifold no longer knows the id (404)."""
    try:
        payload = _get_json(f"{MARKET_URL}/{market_id}", {})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    return payload if isinstance(payload, dict) else None


def _close_time(value) -> datetime | None:
    """Epoch-ms closeTime -> tz-aware UTC datetime; None when absent or out
    of the representable range (Manifold has year-9999 sentinels)."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _volume(market: dict) -> float:
    try:
        return float(market.get("volume") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def normalize(market: dict) -> dict | None:
    """Turn a raw Manifold row into corpus MarketEvent kwargs, or None.

    Keeps only clean binary questions. Settlement: YES->1, NO->0; MKT and
    unresolved rows keep a NULL outcome (they may resolve later); CANCEL
    rows are rejected outright — a voided market carries no backtest signal.
    Category is always "other" (topics skipped for now)."""
    if market.get("outcomeType") != "BINARY":
        return None
    source_id = str(market.get("id") or "").strip()
    question = str(market.get("question") or "").strip()
    if not source_id or not question:
        return None

    resolution = market.get("resolution")
    if resolution == "CANCEL":
        return None
    outcome = _RESOLUTION_OUTCOME.get(resolution)  # MKT / None -> None

    probability = market.get("probability")
    final_price = float(probability) if isinstance(probability, int | float) else None
    return {
        "source": SOURCE,
        "source_id": source_id,
        "question": question,
        "category": DEFAULT_CATEGORY,
        "close_time": _close_time(market.get("closeTime")),
        "outcome": outcome,
        "volume_usd": _volume(market),
        "final_price": final_price,
        # Trimmed raw — the lite row is small, but only url/slug earn a place.
        "raw": {"url": market.get("url"), "slug": market.get("slug")},
    }


def normalize_active(market: dict) -> dict | None:
    """Turn a raw Manifold row into live-trading MarketEvent kwargs, or None.

    The tradable-surface filter (mirrors `active.normalize_active`): binary,
    a real question, NOT resolved, a close time still in the future, and a
    current probability strictly inside the (0.01, 0.99) band — anything on
    the rails is near-settled junk that shouldn't be tradable paper. `source`
    is set here so the row drops straight into `sync_active`."""
    if market.get("outcomeType") != "BINARY" or market.get("isResolved"):
        return None
    source_id = str(market.get("id") or "").strip()
    question = str(market.get("question") or "").strip()
    if not source_id or len(question) < MIN_QUESTION_LEN:
        return None

    close_time = _close_time(market.get("closeTime"))
    if close_time is None or close_time <= datetime.now(UTC):
        return None

    probability = market.get("probability")
    if not isinstance(probability, int | float):
        return None
    yes_price = float(probability)
    if not (MIN_PRICE < yes_price < MAX_PRICE):
        return None

    return {
        "source": SOURCE,
        "source_id": source_id,
        "question": question,
        "category": DEFAULT_CATEGORY,
        "close_time": close_time,
        "volume_usd": _volume(market),
        "yes_price": yes_price,
        "raw": {"url": market.get("url"), "slug": market.get("slug")},
        # Venue-state markers for sync_active: an active row is by definition
        # open (the resolved/past-close ones were filtered out above).
        "closed": False,
        "outcome": None,
    }


def resolution_of(row: dict | None) -> int | None:
    """1/0 when a single-market row shows a final YES/NO resolution; None
    while the market is open, voided (CANCEL), or resolved to the ambiguous
    MKT (probabilistic) outcome. The settlement-sweep parity of the
    active-module `resolution_of`."""
    if row is None:
        return None
    return _RESOLUTION_OUTCOME.get(row.get("resolution"))
