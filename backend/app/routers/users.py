import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    """Register an operator. The API key is returned once — store it."""
    if not EMAIL_RE.match(body.email):
        raise HTTPException(status_code=422, detail="invalid email")
    if db.scalar(select(User).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=body.email, api_key=f"vk_{uuid.uuid4().hex}")
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, email=user.email, api_key=user.api_key, created_at=user.created_at)


@router.get("/me")
def whoami(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    user = db.scalar(select(User).where(User.api_key == x_api_key))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return {"id": user.id, "email": user.email}
