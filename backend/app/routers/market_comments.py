"""Per-market discussion — a light social layer over the play-money markets.

Public read, authenticated write. A comment is addressed by the author's email
LOCAL-PART only (the same handle shown on the leaderboard, activity tape, and
trader profiles); the full registration email never leaves this endpoint. The
write identity is the same X-API-Key returned once by POST /api/users — reusing
`markets._require_trader` so the 401 semantics never drift from the money
surface. Posting a comment moves no balance; it's rate-limited by the global
POST middleware like every other mutation.

The routes live under the /api/markets prefix but never shadow GET
/api/markets/{event_id}: /{event_id}/comments is a two-segment path, so a
market-detail request (one segment) can't match it and vice-versa.

play money · paper trading · real market prices — never real money.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketComment, MarketEvent, User
from ..schemas import UTCDateTime
from .markets import _require_trader

router = APIRouter(prefix="/api/markets", tags=["markets"])


def _handle(email: str) -> str:
    """Public display handle: the email local-part, never the full email —
    the same redaction the leaderboard, activity tape, and profiles use."""
    return email.split("@")[0]


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def _strip_and_recheck(cls, v: str) -> str:
        # min_length counts whitespace; validate the content, not the padding
        # (mirrors schemas.NoteIn so a blank comment can't slip through).
        v = v.strip()
        if not v:
            raise ValueError("comment body must contain at least one non-whitespace character")
        return v


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    handle: str  # email local-part — never the full email
    body: str
    created_at: UTCDateTime


def _require_event(db: Session, event_id: int) -> MarketEvent:
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="market not found")
    return event


@router.get("/{event_id}/comments", response_model=list[CommentOut])
def list_comments(
    event_id: int,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Newest-first comments on a market. Public — no identity needed. Each row
    carries the author's handle (email local-part), never the full email. 404
    for an unknown event."""
    _require_event(db, event_id)
    rows = db.execute(
        select(MarketComment, User.email)
        .join(User, MarketComment.user_id == User.id)
        .where(MarketComment.event_id == event_id)
        .order_by(MarketComment.created_at.desc(), MarketComment.id.desc())
        .limit(limit)
    ).all()
    return [
        CommentOut(id=c.id, handle=_handle(email), body=c.body, created_at=c.created_at)
        for c, email in rows
    ]


@router.post("/{event_id}/comments", response_model=CommentOut, status_code=201)
def post_comment(
    event_id: int,
    body: CommentIn,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Post a comment on a market. Requires the trading X-API-Key (401 without);
    404 for an unknown event. Moves no balance; rate-limited by the global POST
    middleware."""
    user = _require_trader(db, x_api_key)
    _require_event(db, event_id)
    comment = MarketComment(event_id=event_id, user_id=user.id, body=body.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentOut(
        id=comment.id, handle=_handle(user.email), body=comment.body, created_at=comment.created_at
    )


@router.delete("/{event_id}/comments/{comment_id}", status_code=204)
def delete_comment(
    event_id: int,
    comment_id: int,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Delete your own comment. Requires the trading X-API-Key; only the author
    can delete (403 otherwise); 404 when no such comment exists on this market."""
    user = _require_trader(db, x_api_key)
    comment = db.scalar(
        select(MarketComment).where(
            MarketComment.id == comment_id, MarketComment.event_id == event_id
        )
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")
    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="only the author can delete this comment")
    db.delete(comment)
    db.commit()
