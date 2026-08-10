from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Forecast, Question, utcnow
from ..schemas import FeedCard, MoverCard

router = APIRouter(prefix="/api/feed", tags=["feed"])


def latest_forecasts(db: Session) -> list[tuple[Question, Forecast]]:
    """(question, latest forecast) pairs for live (unresolved) questions.

    One query, not one per question: join each live question to its
    max-timestamp forecast (max id breaks same-timestamp ties)."""
    # Newest forecast id per question — ids are monotonic within a question's
    # append-only history, so max(id) is the latest without a tie-break join.
    newest = (
        select(Forecast.question_id, func.max(Forecast.id).label("forecast_id"))
        .group_by(Forecast.question_id)
        .subquery()
    )
    rows = db.execute(
        select(Question, Forecast)
        .join(newest, newest.c.question_id == Question.id)
        .join(Forecast, Forecast.id == newest.c.forecast_id)
        .where(Question.resolved.is_(False))
        .order_by(Question.id)
    ).all()
    return [(question, forecast) for question, forecast in rows]


def previous_forecasts(db: Session, cutoff: datetime) -> dict[int, Forecast]:
    """Newest forecast at-or-before `cutoff`, per question — one query."""
    prev = (
        select(Forecast.question_id, func.max(Forecast.id).label("forecast_id"))
        .where(Forecast.timestamp <= cutoff)
        .group_by(Forecast.question_id)
        .subquery()
    )
    rows = db.scalars(select(Forecast).join(prev, Forecast.id == prev.c.forecast_id)).all()
    return {forecast.question_id: forecast for forecast in rows}


def _headline(question: Question, forecast: Forecast) -> str:
    edge = forecast.probability - question.market_probability
    if edge >= 0.05:
        return f"The market may be underestimating: {question.question.rstrip('?')}"
    if edge <= -0.05:
        return f"The market may be overestimating: {question.question.rstrip('?')}"
    return f"vanta agrees with the market on: {question.question.rstrip('?')}"


@router.get("/movers", response_model=list[MoverCard])
def movers(
    days: int = Query(3, ge=1, le=30),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Where vanta's own probability moved most over the window — the
    questions whose evidence picture is changing fastest."""
    cutoff = utcnow() - timedelta(days=days)
    previous_by_question = previous_forecasts(db, cutoff)
    cards: list[MoverCard] = []
    for question, latest in latest_forecasts(db):
        previous = previous_by_question.get(question.id)
        if previous is None or previous.id == latest.id:
            # Younger than the window, or nothing new inside it — a question
            # whose forecasts all predate the window hasn't "moved".
            continue
        delta = latest.probability - previous.probability
        cards.append(
            MoverCard(
                question_id=question.id,
                question=question.question,
                category=question.category,
                current=latest.probability,
                previous=previous.probability,
                delta=round(delta, 4),
                window_days=days,
            )
        )
    cards.sort(key=lambda c: abs(c.delta), reverse=True)
    return cards[:limit]


SORT_KEYS = {
    "edge": lambda q, f: abs(f.probability - q.market_probability),
    "confidence": lambda q, f: f.confidence,
    "volume": lambda q, f: q.market_volume_usd,
}


@router.get("/sparklines")
def sparklines(db: Session = Depends(get_db)):
    """All live questions' probability series in one payload — the feed
    renders 12+ sparklines without 12+ requests."""
    live_ids = select(Question.id).where(Question.resolved.is_(False)).scalar_subquery()
    rows = db.execute(
        select(Forecast.question_id, Forecast.probability)
        .where(Forecast.question_id.in_(live_ids))
        .order_by(Forecast.question_id, Forecast.timestamp.asc(), Forecast.id.asc())
    ).all()
    series: dict[int, list[float]] = {}
    for question_id, probability in rows:
        series.setdefault(question_id, []).append(probability)
    return series


@router.get("", response_model=list[FeedCard])
def intelligence_feed(
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("edge", pattern="^(edge|confidence|volume)$"),
    db: Session = Depends(get_db),
):
    """Discovery cards for live questions. Default ranking: |edge| — where
    vanta most disagrees with markets. Also sortable by confidence or volume."""
    pairs = latest_forecasts(db)
    key = SORT_KEYS[sort]
    pairs.sort(key=lambda pair: key(pair[0], pair[1]), reverse=True)
    return [
        FeedCard(
            question_id=q.id,
            question=q.question,
            category=q.category,
            market_probability=q.market_probability,
            vanta_probability=f.probability,
            confidence=f.confidence,
            edge=round(f.probability - q.market_probability, 4),
            horizon_days=q.horizon_days,
            headline=_headline(q, f),
        )
        for q, f in pairs[:limit]
    ]


@router.get("/rss")
def feed_rss(db: Session = Depends(get_db)):
    """The intelligence feed as RSS — top edges, one item per live question."""
    import html as html_mod

    pairs = latest_forecasts(db)
    pairs.sort(key=lambda pair: abs(pair[1].probability - pair[0].market_probability), reverse=True)
    def entry(q, f):
        title = html_mod.escape(f"{q.question} — market {q.market_probability:.0%}, vanta {f.probability:.0%}")
        desc = html_mod.escape(f"Edge {f.probability - q.market_probability:+.0%}, conf {f.confidence}/10.")
        guid = f"vanta-feed-{q.id}-{round(f.probability * 1000)}"
        return (
            f"\n  <item>\n    <title>{title}</title>\n    <description>{desc}</description>"
            f'\n    <guid isPermaLink="false">{guid}</guid>\n  </item>'
        )

    entries = "".join(entry(q, f) for q, f in pairs[:15])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>vanta Intelligence Feed</title>
  <link>https://sunkalpchandra.github.io/vanta/</link>
  <description>Where vanta's agent pipeline most disagrees with prediction markets.</description>{entries}
</channel>
</rss>"""
    return Response(content=xml, media_type="application/rss+xml")
