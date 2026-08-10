from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, SessionLocal, engine
from .llm import llm_available
from .routers import brief, cards, feed, leaderboard, questions, stats
from .seed import seed_if_empty


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

app.include_router(questions.router)
app.include_router(feed.router)
app.include_router(leaderboard.router)
app.include_router(brief.router)
app.include_router(cards.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_narratives": llm_available()}
