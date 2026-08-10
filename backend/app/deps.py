"""Shared FastAPI dependencies."""

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User


def require_operator(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
) -> None:
    """Gate for mutating endpoints. Open by default (demo mode); when
    VANTA_REQUIRE_API_KEY is set, a valid user key must accompany the call.
    Tests can override via app.state.require_api_key."""
    required = getattr(request.app.state, "require_api_key", None)
    if required is None:
        required = get_settings().require_api_key
    if not required:
        return
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    user = db.scalar(select(User).where(User.api_key == x_api_key))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid API key")
