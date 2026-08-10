import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import get_settings
from .db import Base, SessionLocal, engine
from .llm import llm_available
from .routers import agents, brief, cards, discover, feed, leaderboard, questions, stats
from .seed import seed_if_empty

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
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    yield


app = FastAPI(
    title="vanta",
    description="Autonomous multi-agent forecasting intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def timing_and_cache_headers(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    if request.method == "GET" and "cache-control" not in response.headers:
        for prefix, max_age in CACHE_RULES:
            if request.url.path.startswith(prefix):
                response.headers["Cache-Control"] = f"public, max-age={max_age}"
                break
    return response

app.include_router(questions.router)
app.include_router(feed.router)
app.include_router(leaderboard.router)
app.include_router(brief.router)
app.include_router(cards.router)
app.include_router(stats.router)
app.include_router(discover.router)
app.include_router(agents.router)


@app.get("/api/meta")
def meta():
    """Build identity for clients and monitors."""
    return {
        "name": "vanta",
        "version": app.version,
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
