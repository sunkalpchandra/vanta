"""Kalshi settled-market client + normalizer for the backtest corpus.

Live-API notes (probed 2026-08-10 against api.elections.kalshi.com):
- GET /markets is public and cursor-paginated. `status=settled` works, but the
  most recent pages are almost entirely multivariate combo junk (ticker prefix
  KXMVE..., comma-joined leg titles, zero volume) — normalize() rejects those.
- Market rows use the new field shapes: `last_price_dollars` / `volume_fp`
  strings. The older integer-cent `last_price` / contract-count `volume`
  fields are absent from live responses; both shapes are handled here.
- Market rows carry NO category field (only /events does), so category is
  inferred from series-ticker keywords rather than a per-market event fetch.
  Callers that did fetch the event can pass its category to normalize().
- GET /series/{series}/markets/{ticker}/candlesticks is public (no auth) and
  returns daily candles with `price.close_dollars`, nullable in no-trade
  periods. `end_period_ts` is unix seconds.
"""

from datetime import UTC, datetime

import httpx

from .polymarket import price_at  # noqa: F401 — re-exported: shared leakage-safe lookup

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
SOURCE = "kalshi"
_TIMEOUT = 30.0

# Kalshi event/series categories -> vanta's normalized set.
_KALSHI_CATEGORY_MAP = {
    "politics": "politics",
    "elections": "politics",
    "world": "politics",
    "economics": "finance",
    "financials": "finance",
    "companies": "finance",
    "science and technology": "technology",
    "technology": "technology",
    "climate and weather": "science",
    "health": "science",
    "science": "science",
    "crypto": "crypto",
    "cryptocurrency": "crypto",
    "sports": "sports",
}

# Series-ticker keyword fallback (market rows have no category field). First
# match wins, so the more specific buckets come before the generic ones.
_TICKER_KEYWORDS = [
    ("crypto", ("BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "LTC", "CRYPTO", "COIN", "STABLE")),
    ("sports", ("NBA", "NFL", "MLB", "NHL", "NCAA", "UFC", "PGA", "ATP", "WTA", "OLYMP", "SOCCER", "TENNIS", "GOLF",
                "BOXING", "CRICKET", "ODIMATCH", "SERIESGAME", "GRANDPRIX")),
    ("politics", ("PRES", "POTUS", "SENATE", "HOUSE", "GOVERNOR", "ELECT", "MAYOR", "NOMINEE", "IMPEACH", "SCOTUS",
                  "CABINET", "SPEAKER", "TRUMP", "BIDEN", "LEADER", "CEASEFIRE", "NATO", "UKRAINE", "ISRAEL", "IRAN")),
    ("finance", ("CPI", "GDP", "FED", "RATECUT", "INX", "NASDAQ", "SP500", "RECESSION", "PAYROLL", "JOBS", "MORTGAGE",
                 "DEBT", "TARIFF", "OIL", "GOLD", "ECB", "TREASURY", "EARNINGS", "IPO", "FEAR", "MINWAGE")),
    ("science", ("HIGH", "LOWTEMP", "TEMP", "RAIN", "SNOW", "HURRICANE", "STORM", "QUAKE", "CLIMATE", "WEATHER",
                 "NASA", "SPACEX", "STARSHIP", "MOON", "MARS", "FLU", "COVID", "VACCINE", "ECLIPSE")),
    ("technology", ("AI", "OPENAI", "GPT", "TIKTOK", "APPLE", "IPHONE", "TESLA", "GOOGLE", "META", "MSFT", "ROBO",
                    "CHIP", "CYBER", "TECH", "SMARTPHONE")),
]


def normalize_category(kalshi_category: str | None, ticker: str) -> str:
    """Map a Kalshi category (or, failing that, series-ticker keywords) onto
    vanta's normalized category set; "other" when nothing matches."""
    if kalshi_category:
        mapped = _KALSHI_CATEGORY_MAP.get(kalshi_category.strip().lower())
        if mapped:
            return mapped
    series = ticker.split("-")[0].upper().removeprefix("KX")
    for category, keywords in _TICKER_KEYWORDS:
        if any(keyword in series for keyword in keywords):
            return category
    return "other"


def series_ticker_of(market: dict) -> str:
    """Series ticker for the candlesticks endpoint: the segment of the event
    ticker before the first dash (probed working against the live API)."""
    return str(market.get("event_ticker") or market.get("ticker") or "").split("-")[0]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)  # 3.11+ accepts the trailing Z
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _final_price(market: dict) -> float | None:
    """Last traded YES price in [0,1]. Handles both the legacy integer-cent
    `last_price` and the current `last_price_dollars` string."""
    if market.get("last_price") is not None:
        price = float(market["last_price"]) / 100
    elif market.get("last_price_dollars") is not None:
        price = float(market["last_price_dollars"])
    else:
        return None
    return min(max(price, 0.0), 1.0)


def _volume(market: dict) -> float | None:
    """Traded contracts (~USD at $1 notional). Handles `volume` int and
    `volume_fp` string shapes; None when the field is absent entirely."""
    for key in ("volume", "volume_fp"):
        if market.get(key) is not None:
            return float(market[key])
    return None


def normalize(market: dict, category: str | None = None) -> dict | None:
    """Turn a raw /markets row into MarketEvent kwargs, or None for junk.

    Rejects the multivariate combo markets that dominate recent settled pages
    (KXMVE tickers / mve_* fields, comma-joined "yes X,no Y" titles), rows
    without a yes/no result, and zero-volume strikes that never traded — a
    market nobody priced has no history to backtest against.
    """
    ticker = market.get("ticker") or ""
    title = (market.get("title") or "").strip()
    result = market.get("result")
    if not ticker or result not in ("yes", "no"):
        return None
    if market.get("market_type", "binary") != "binary":
        return None
    if ticker.startswith("KXMVE") or market.get("mve_collection_ticker") or market.get("mve_selected_legs"):
        return None
    # A real title reads as a question/statement, not a comma-joined leg list.
    if len(title) < 10 or " " not in title or title.startswith(("yes ", "no ")):
        return None
    volume = _volume(market)
    if not volume or volume <= 0:
        return None

    question = title.replace("**", "").strip()
    # Multi-outcome events ("What will X be?") carry the strike in the
    # subtitle; append it when the title alone doesn't pin down the market.
    subtitle = (market.get("yes_sub_title") or "").strip()
    if subtitle and subtitle.lower() not in question.lower():
        question = f"{question} ({subtitle})"

    raw = {key: value for key, value in market.items() if key not in ("rules_primary", "rules_secondary")}
    return {
        "source": SOURCE,
        "source_id": ticker,
        "question": question,
        "category": normalize_category(category or market.get("category"), ticker),
        "close_time": _parse_time(market.get("close_time")),
        "outcome": 1 if result == "yes" else 0,
        "volume_usd": volume,
        "final_price": _final_price(market),
        "raw": raw,
    }


def fetch_markets(
    cursor: str | None = None,
    limit: int = 1000,
    status: str = "settled",
    *,
    max_close_ts: int | None = None,
    min_close_ts: int | None = None,
    client: httpx.Client | None = None,
) -> tuple[list[dict], str | None]:
    """One page of /markets. Returns (rows, next_cursor); next_cursor is None
    when pagination is exhausted. max/min_close_ts (unix seconds) let callers
    skip past the KXMVE-junk era that dominates the most recent settled pages.
    """
    params: dict = {"limit": limit, "status": status}
    if cursor:
        params["cursor"] = cursor
    if max_close_ts is not None:
        params["max_close_ts"] = max_close_ts
    if min_close_ts is not None:
        params["min_close_ts"] = min_close_ts
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=_TIMEOUT)
    try:
        response = client.get(f"{BASE_URL}/markets", params=params)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            client.close()
    return payload.get("markets", []), (payload.get("cursor") or None)


def fetch_candles(
    series_ticker: str,
    ticker: str,
    start_ts: int,
    end_ts: int,
    *,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Daily close history as [{"t": unix_seconds, "p": yes_price_0_to_1}],
    oldest first. Degrades to [] on any HTTP failure (the endpoint is public
    today; if Kalshi ever gates it, ingestion still works minus price_7d/30d).
    No-trade candles (null close) are skipped rather than invented.
    """
    url = f"{BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks"
    params = {"start_ts": int(start_ts), "end_ts": int(end_ts), "period_interval": 1440}
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=_TIMEOUT)
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        return []
    finally:
        if owns_client:
            client.close()
    closes = []
    for candle in payload.get("candlesticks", []):
        price = candle.get("price") or {}
        if price.get("close") is not None:  # legacy integer cents
            value = float(price["close"]) / 100
        elif price.get("close_dollars") is not None:
            value = float(price["close_dollars"])
        else:
            continue
        closes.append({"t": int(candle["end_period_ts"]), "p": min(max(value, 0.0), 1.0)})
    closes.sort(key=lambda point: point["t"])
    return closes



def upsert_event(db, values: dict):
    """Insert or update a market_events row keyed by (source, source_id).
    Returns (row, created). Never touches price_7d/price_30d — the slower
    price pass owns those and re-ingesting must not wipe them."""
    from app.models import MarketEvent

    row = db.query(MarketEvent).filter_by(source=values["source"], source_id=values["source_id"]).one_or_none()
    if row is None:
        row = MarketEvent(**values)
        db.add(row)
        return row, True
    for key, value in values.items():
        setattr(row, key, value)
    return row, False
