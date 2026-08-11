"""Per-market discussion (comments).

Shares the suite SQLite (conftest binds it before app import). Every market this
module writes is scoped to the unique source 'test-w10-comments', and each test
registers its own trader(s), so other modules' writes never matter here.

main.py wiring the router is the integration step, so this module mounts the
router onto the shared app itself — guarded so it's a no-op once main.py
includes it (mirrors the market_watch bring-up).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent
from app.routers import market_comments

# Idempotent self-mount: register the router only if main.py hasn't yet.
if not any(getattr(r, "path", "").endswith("/comments") for r in app.routes):
    app.include_router(market_comments.router)

SOURCE = "test-w10-comments"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _auth(user: dict) -> dict:
    return {"X-API-Key": user["api_key"]}


def _make_event() -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source=SOURCE,
            source_id=f"c-{uuid.uuid4().hex}",
            question=f"Will comment-market {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=True,
            yes_price=0.5,
        )
        db.add(event)
        db.commit()
        return event.id


# --- identity -----------------------------------------------------------------


def test_post_requires_a_valid_key(client):
    event_id = _make_event()
    # No key at all → 401.
    assert client.post(f"/api/markets/{event_id}/comments", json={"body": "hi"}).status_code == 401
    # A bogus key → 401.
    bogus = {"X-API-Key": "vk_bogus"}
    assert (
        client.post(f"/api/markets/{event_id}/comments", json={"body": "hi"}, headers=bogus).status_code
        == 401
    )
    # Reads stay open — no key needed.
    assert client.get(f"/api/markets/{event_id}/comments").status_code == 200


# --- post / list / redaction --------------------------------------------------


def test_post_then_list_newest_first_with_handle_redaction(client):
    user = _register(client, "poster")
    event_id = _make_event()

    first = client.post(f"/api/markets/{event_id}/comments", json={"body": "first"}, headers=_auth(user))
    assert first.status_code == 201
    body = first.json()
    assert body["body"] == "first"
    # Handle is the email local-part — never the full email.
    assert body["handle"] == user["email"].split("@")[0]
    assert "@" not in body["handle"]

    client.post(f"/api/markets/{event_id}/comments", json={"body": "second"}, headers=_auth(user))

    listed = client.get(f"/api/markets/{event_id}/comments").json()
    assert [c["body"] for c in listed] == ["second", "first"]  # newest first
    for c in listed:
        assert "@" not in c["handle"]
        assert set(c.keys()) == {"id", "handle", "body", "created_at"}  # no user_id/email leak
    # A comment thread is scoped to its own market.
    other_event = _make_event()
    assert client.get(f"/api/markets/{other_event}/comments").json() == []


def test_body_is_stripped_and_blank_is_rejected(client):
    user = _register(client, "stripper")
    event_id = _make_event()

    ok = client.post(
        f"/api/markets/{event_id}/comments", json={"body": "  spaced out  "}, headers=_auth(user)
    )
    assert ok.status_code == 201
    assert ok.json()["body"] == "spaced out"  # trimmed

    # Whitespace-only and empty are rejected by validation (422).
    for blank in ("   ", ""):
        resp = client.post(
            f"/api/markets/{event_id}/comments", json={"body": blank}, headers=_auth(user)
        )
        assert resp.status_code == 422
    # Over-long (>1000) rejected too.
    too_long = client.post(
        f"/api/markets/{event_id}/comments", json={"body": "x" * 1001}, headers=_auth(user)
    )
    assert too_long.status_code == 422


def test_limit_caps_and_bounds(client):
    user = _register(client, "limiter")
    event_id = _make_event()
    for i in range(3):
        client.post(f"/api/markets/{event_id}/comments", json={"body": f"c{i}"}, headers=_auth(user))
    assert len(client.get(f"/api/markets/{event_id}/comments?limit=2").json()) == 2
    # Out-of-range limit is rejected (<=100, >=1).
    assert client.get(f"/api/markets/{event_id}/comments?limit=0").status_code == 422
    assert client.get(f"/api/markets/{event_id}/comments?limit=101").status_code == 422


# --- unknown event ------------------------------------------------------------


def test_unknown_event_is_404_on_read_and_post(client):
    user = _register(client, "ghost")
    assert client.get("/api/markets/99999999/comments").status_code == 404
    assert (
        client.post("/api/markets/99999999/comments", json={"body": "hi"}, headers=_auth(user)).status_code
        == 404
    )


# --- delete: author-only ------------------------------------------------------


def test_author_can_delete_but_others_cannot(client):
    author = _register(client, "author")
    intruder = _register(client, "intruder")
    event_id = _make_event()

    made = client.post(
        f"/api/markets/{event_id}/comments", json={"body": "mine to delete"}, headers=_auth(author)
    ).json()
    comment_id = made["id"]

    # A different trader may not delete it → 403, and it survives.
    assert (
        client.delete(f"/api/markets/{event_id}/comments/{comment_id}", headers=_auth(intruder)).status_code
        == 403
    )
    assert any(c["id"] == comment_id for c in client.get(f"/api/markets/{event_id}/comments").json())

    # Delete needs a key at all → 401.
    assert client.delete(f"/api/markets/{event_id}/comments/{comment_id}").status_code == 401

    # The author deletes it (204); a second delete is 404.
    assert (
        client.delete(f"/api/markets/{event_id}/comments/{comment_id}", headers=_auth(author)).status_code
        == 204
    )
    assert (
        client.delete(f"/api/markets/{event_id}/comments/{comment_id}", headers=_auth(author)).status_code
        == 404
    )
    assert all(c["id"] != comment_id for c in client.get(f"/api/markets/{event_id}/comments").json())


def test_delete_unknown_comment_is_404(client):
    user = _register(client, "nodel")
    event_id = _make_event()
    assert client.delete(f"/api/markets/{event_id}/comments/99999999", headers=_auth(user)).status_code == 404


# --- routing: /{event_id}/comments must not shadow /{event_id} -----------------


def test_comments_path_does_not_shadow_market_detail(client):
    user = _register(client, "router")
    event_id = _make_event()
    client.post(f"/api/markets/{event_id}/comments", json={"body": "hello"}, headers=_auth(user))

    # Market detail (one path segment) resolves to the market, not the thread.
    detail = client.get(f"/api/markets/{event_id}")
    assert detail.status_code == 200
    assert "question" in detail.json()
    assert "handle" not in detail.json()

    # The two-segment comments path resolves to the thread, a list.
    thread = client.get(f"/api/markets/{event_id}/comments")
    assert thread.status_code == 200
    assert isinstance(thread.json(), list)
    assert thread.json()[0]["body"] == "hello"
