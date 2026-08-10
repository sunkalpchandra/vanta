"""CSV export of a trader's trades and positions.

Shares the suite SQLite (conftest binds it before app import). Rows are scoped
to a unique source ('test-w8-csv') so other modules' writes never leak in. The
export router lands in main.py at integration; until then this module wires it
onto the app (idempotent — a no-op once main.py includes it).
"""

import csv
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent

# Wire the export router until main.py includes it (shared file — integration
# step). The guard makes this a no-op once main.py registers it.

# A question with a comma AND a double quote — the two cases CSV must escape.
COMMA_QUESTION = 'Will Apple, Google, and "others" ship this quarter?'


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client) -> dict:
    resp = client.post("/api/users", json={"email": f"csv-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _auth(user: dict) -> dict:
    return {"X-API-Key": user["api_key"]}


def _make_event(yes_price=0.4, question=None) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w8-csv",
            source_id=f"csv-{uuid.uuid4().hex}",
            question=question or f"Will csv market {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=True,
            yes_price=yes_price,
        )
        db.add(event)
        db.commit()
        return event.id


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


# --- identity -----------------------------------------------------------------


def test_exports_require_a_key(client):
    assert client.get("/api/export/trades.csv").status_code == 401
    assert client.get("/api/export/positions.csv").status_code == 401
    for path in ("/api/export/trades.csv", "/api/export/positions.csv"):
        assert client.get(path, headers={"X-API-Key": "vk_bogus"}).status_code == 401


# --- trades.csv ---------------------------------------------------------------


def test_trades_csv_headers_and_escaped_row(client):
    user = _register(client)
    event_id = _make_event(yes_price=0.4, question=COMMA_QUESTION)
    trade = client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": "yes", "action": "buy", "shares": 100},
        headers=_auth(user),
    )
    assert trade.status_code == 200

    resp = client.get("/api/export/trades.csv", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="vanta-trades.csv"'

    # The comma+quote question must be quoted in the raw payload, not split.
    assert '"Will Apple, Google, and ""others"" ship this quarter?"' in resp.text

    rows = _rows(resp.text)
    assert rows[0] == ["id", "created_at", "event_id", "question", "side", "action", "shares", "price", "cost"]
    mine = [r for r in rows[1:] if r[2] == str(event_id)]
    assert len(mine) == 1
    row = mine[0]
    # csv.reader round-trips the escaped question back to the exact original.
    assert row[3] == COMMA_QUESTION
    assert row[4] == "yes" and row[5] == "buy"
    assert float(row[6]) == pytest.approx(100.0)
    assert float(row[7]) == pytest.approx(0.4)
    assert float(row[8]) == pytest.approx(-40.0)  # signed cost: spent
    assert row[1].endswith("Z") or "+00:00" in row[1]  # UTC-stamped


def test_trades_csv_is_scoped_to_the_caller(client):
    mine = _register(client)
    other = _register(client)
    event_id = _make_event(yes_price=0.5)
    client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": "yes", "action": "buy", "shares": 10},
        headers=_auth(other),
    )
    rows = _rows(client.get("/api/export/trades.csv", headers=_auth(mine)).text)
    # Header only — the caller placed no trades, other's trade must not appear.
    assert all(r[2] != str(event_id) for r in rows[1:])


# --- positions.csv ------------------------------------------------------------


def test_positions_csv_headers_and_row(client):
    user = _register(client)
    event_id = _make_event(yes_price=0.4, question=COMMA_QUESTION)
    client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": "yes", "action": "buy", "shares": 100},
        headers=_auth(user),
    )

    resp = client.get("/api/export/positions.csv", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="vanta-positions.csv"'
    assert '"Will Apple, Google, and ""others"" ship this quarter?"' in resp.text

    rows = _rows(resp.text)
    assert rows[0] == [
        "event_id",
        "question",
        "side",
        "shares",
        "avg_price",
        "current_price",
        "unrealized_pnl",
        "realized_pnl",
        "settled",
    ]
    mine = [r for r in rows[1:] if r[0] == str(event_id)]
    assert len(mine) == 1
    row = mine[0]
    assert row[1] == COMMA_QUESTION
    assert row[2] == "yes"
    assert float(row[3]) == pytest.approx(100.0)  # shares
    assert float(row[4]) == pytest.approx(0.4)  # avg_price basis
    assert float(row[5]) == pytest.approx(0.4)  # current price (synced)
    assert float(row[6]) == pytest.approx(0.0)  # unrealized at entry price
    assert float(row[7]) == pytest.approx(0.0)  # realized: nothing closed yet
    assert row[8] == "False"  # unsettled


def test_csv_defuses_formula_injection(client):
    """A market question that starts with =/+/-/@ (untrusted venue text) must
    be neutralized so spreadsheets don't execute it as a formula."""
    from app.db import SessionLocal
    from app.models import MarketEvent

    reg = client.post("/api/users", json={"email": "csv-injection@example.com"})
    key = reg.json()["api_key"]
    with SessionLocal() as db:
        ev = MarketEvent(
            source="test-w8-csv-inj",
            source_id="inj-1",
            question='=HYPERLINK("http://evil.example","x")',
            category="other",
            active=True,
            yes_price=0.5,
            outcome=None,
        )
        db.add(ev)
        db.commit()
        event_id = ev.id
    client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": "yes", "action": "buy", "shares": 10},
        headers={"X-API-Key": key},
    )
    body = client.get("/api/export/trades.csv", headers={"X-API-Key": key}).text
    # The dangerous field is present but prefixed with a quote so it's inert.
    assert "'=HYPERLINK" in body
    # And it never appears as a live formula (bare leading =).
    for line in body.splitlines():
        for cell in line.split(","):
            assert not cell.lstrip('"').startswith("=")
