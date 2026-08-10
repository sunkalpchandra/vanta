"""Shareable prediction cards — self-contained SVG, no external assets."""

import html

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Forecast, Question

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _wrap(text: str, width: int = 38, max_lines: int = 3) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1] + "…"]
    return lines


@router.get("/{question_id}.svg")
def share_card(question_id: int, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="question not found")
    forecast = db.scalar(
        select(Forecast)
        .where(Forecast.question_id == question_id)
        .order_by(Forecast.timestamp.desc())
        .limit(1)
    )
    if forecast is None:
        raise HTTPException(status_code=404, detail="no forecast yet")

    edge = forecast.probability - question.market_probability
    edge_color = "#34d399" if edge >= 0 else "#f87171"
    title_lines = "".join(
        f'<tspan x="60" dy="{34 if i else 0}">{html.escape(line)}</tspan>'
        for i, line in enumerate(_wrap(question.question))
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="418" viewBox="0 0 800 418">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0a0f1c"/><stop offset="1" stop-color="#111827"/>
    </linearGradient>
  </defs>
  <rect width="800" height="418" rx="24" fill="url(#bg)" stroke="#1f2937"/>
  <text x="60" y="64" fill="#6b7280" font-family="ui-monospace,Menlo,monospace" font-size="15" letter-spacing="4">VANTA · INTELLIGENCE</text>
  <text x="60" y="120" fill="#f9fafb" font-family="-apple-system,Segoe UI,sans-serif" font-size="26" font-weight="600">{title_lines}</text>
  <text x="60" y="268" fill="#6b7280" font-family="ui-monospace,Menlo,monospace" font-size="13" letter-spacing="2">MARKET</text>
  <text x="60" y="316" fill="#9ca3af" font-family="ui-monospace,Menlo,monospace" font-size="44" font-weight="700">{question.market_probability:.0%}</text>
  <text x="300" y="268" fill="#6b7280" font-family="ui-monospace,Menlo,monospace" font-size="13" letter-spacing="2">VANTA</text>
  <text x="300" y="316" fill="#e5e7eb" font-family="ui-monospace,Menlo,monospace" font-size="44" font-weight="700">{forecast.probability:.0%}</text>
  <text x="540" y="268" fill="#6b7280" font-family="ui-monospace,Menlo,monospace" font-size="13" letter-spacing="2">EDGE</text>
  <text x="540" y="316" fill="{edge_color}" font-family="ui-monospace,Menlo,monospace" font-size="44" font-weight="700">{edge:+.0%}</text>
  <text x="60" y="374" fill="#4b5563" font-family="ui-monospace,Menlo,monospace" font-size="14">confidence {forecast.confidence}/10 · {html.escape(question.category)} · {question.horizon_days}d horizon</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")
