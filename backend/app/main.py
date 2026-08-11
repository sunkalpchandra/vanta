import logging
import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import Base, SessionLocal, engine
from .llm import llm_available
from .routers import (
    activity,
    agents,
    alerts,
    backtest,
    brief,
    cards,
    chat,
    discover,
    export_data,
    feed,
    leaderboard,
    market_forecast,
    market_history,
    market_stats,
    market_watch,
    markets,
    portfolio_history,
    questions,
    search,
    stats,
    trader_profile,
    users,
)
from .seed import seed_if_empty

logger = logging.getLogger("vanta")

# Read endpoints that tolerate short staleness get client/proxy caching.
# Writes and operator reads stay uncached.
CACHE_RULES: list[tuple[str, int]] = [
    ("/api/cards/", 300),
    ("/api/feed", 30),
    ("/api/brief", 60),
    ("/api/leaderboard", 60),
    ("/api/stats", 60),
    ("/api/categories", 300),
    ("/api/agents/leaderboard", 60),
    ("/api/quant/backtest", 3600),
    ("/api/backtest/real", 300),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # VANTA_NO_SEED lets the snapshot exporter reuse a pre-populated corpus DB
    # (real markets, synced prices) without the demo seeder writing into it.
    if not os.environ.get("VANTA_NO_SEED"):
        with SessionLocal() as db:
            seed_if_empty(db)
    yield


app = FastAPI(
    title="vanta",
    description="Autonomous multi-agent forecasting intelligence platform",
    version="0.4.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "questions", "description": "The question lifecycle: ask, forecast, evidence, resolve, notes."},
        {"name": "feed", "description": "Discovery cards ranked by edge, movers, sparklines, RSS."},
        {"name": "brief", "description": "The morning brief — top mispricings, optionally per category."},
        {"name": "leaderboard", "description": "Accuracy and calibration, vanta vs market."},
        {"name": "agents", "description": "The internal forecaster competition and per-agent receipts."},
        {"name": "alerts", "description": "Derived attention signals: big moves and live edges."},
        {"name": "discover", "description": "The autonomous watchlist and question minting."},
        {"name": "stats", "description": "Corpus-wide scores and the analog-engine backtest."},
        {"name": "search", "description": "Unified search over live questions and the archive."},
        {"name": "users", "description": "Operator registration and identity."},
        {"name": "cards", "description": "Self-contained SVG share cards."},
        {"name": "backtest", "description": "Leakage-free backtest of the pipeline over real ingested markets."},
        {"name": "chat", "description": "Real-time reasoning chat — SSE stream of the agent debate."},
        {"name": "markets", "description": "Play-money prediction market over real synced events."},
        {"name": "activity", "description": "Public trade tape across all traders."},
    ],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)


# Sliding-window limiter for mutating requests. In-memory and per-process —
# honest scope: a demo-grade guard against runaway clients, not DDoS armor.
_rate_buckets: dict[str, deque] = {}

# Per-process request counters exposed at /metrics (Prometheus text format).
_request_counts: dict[tuple[str, int], int] = {}


@app.middleware("http")
async def request_id_and_error_shield(request: Request, call_next):
    """Every response carries an id; unhandled errors become a clean 500 that
    cites it instead of a bare traceback response."""
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(
            status_code=500,
            content={"detail": "internal error", "request_id": request_id},
        )
    response.headers["X-Request-Id"] = request_id
    return response


@app.middleware("http")
async def rate_limit_mutations(request: Request, call_next):
    limit = getattr(app.state, "rate_limit_per_minute", None)
    if limit is None:
        limit = get_settings().rate_limit_per_minute
    if limit and request.method in {"POST", "DELETE"} and request.url.path.startswith("/api"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        if len(_rate_buckets) > 1024:  # bound per-IP key growth (scanners, NAT churn)
            for ip in [ip for ip, b in _rate_buckets.items() if not b or now - b[-1] > 60]:
                del _rate_buckets[ip]
        bucket = _rate_buckets.setdefault(client_ip, deque())
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded; slow down"},
                headers={"Retry-After": "60"},
            )
        bucket.append(now)
    return await call_next(request)


@app.middleware("http")
async def timing_and_cache_headers(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    if request.url.path.startswith("/api"):
        # Route template when resolved, else the raw path bucket "other".
        route = request.scope.get("route")
        path_label = getattr(route, "path", "other")
        key = (f"{request.method} {path_label}", response.status_code)
        _request_counts[key] = _request_counts.get(key, 0) + 1
    if (
        request.method == "GET"
        and 200 <= response.status_code < 300
        and "cache-control" not in response.headers
    ):
        for prefix, max_age in CACHE_RULES:
            if request.url.path.startswith(prefix):
                response.headers["Cache-Control"] = f"public, max-age={max_age}"
                break
    return response

# Registered last so CORS is the OUTERMOST middleware: rate-limit 429s and
# error-shield 500s must still carry CORS headers or the browser shows an
# opaque network error instead of the status and Retry-After/request_id.
# FRONTEND_ORIGIN may be a comma-separated list — a Vercel deployment has a
# stable production URL plus rotating preview URLs, and a regex covers those.
_origins = [o.strip() for o in get_settings().frontend_origin.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Any *.vercel.app preview build of the frontend can call the API too.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions.router)
app.include_router(feed.router)
app.include_router(leaderboard.router)
app.include_router(brief.router)
app.include_router(cards.router)
app.include_router(stats.router)
app.include_router(discover.router)
app.include_router(agents.router)
app.include_router(alerts.router)
app.include_router(users.router)
app.include_router(search.router)
app.include_router(backtest.router)
app.include_router(chat.router)
app.include_router(markets.router)
app.include_router(market_history.router)
app.include_router(market_forecast.router)
app.include_router(market_stats.router)
app.include_router(market_watch.router)
app.include_router(portfolio_history.router)
app.include_router(trader_profile.router)
app.include_router(export_data.router)
app.include_router(activity.router)


@app.get("/metrics")
def metrics():
    """Per-process request counters, Prometheus text exposition format.
    Honest scope: counters reset on restart and are per-worker."""
    from fastapi.responses import PlainTextResponse

    lines = [
        "# HELP vanta_requests_total API requests by route and status.",
        "# TYPE vanta_requests_total counter",
    ]
    for (route, status), count in sorted(_request_counts.items()):
        lines.append(f'vanta_requests_total{{route="{route}",status="{status}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n")


@app.get("/api/meta")
def meta():
    """Build identity for clients and monitors. GIT_SHA is stamped by the
    deploy environment (Pages workflow, docker build) — absent locally."""
    return {
        "name": "vanta",
        "version": app.version,
        "commit": os.environ.get("GIT_SHA"),
        "docs": "/docs",
        "source": "https://github.com/sunkalpchandra/vanta",
    }


@app.get("/api/health")
def health():
    from sqlalchemy import text

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "llm_narratives": llm_available(),
    }
