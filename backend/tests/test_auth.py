import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def gated_client():
    app.state.require_api_key = True
    with TestClient(app) as c:
        yield c
    app.state.require_api_key = None


def test_user_registration_and_whoami(client):
    created = client.post("/api/users", json={"email": "ops@vanta.test"}).json()
    assert created["api_key"].startswith("vk_")
    me = client.get("/api/users/me", headers={"X-API-Key": created["api_key"]}).json()
    assert me["email"] == "ops@vanta.test"
    assert client.post("/api/users", json={"email": "ops@vanta.test"}).status_code == 409
    assert client.post("/api/users", json={"email": "not-an-email"}).status_code == 422


def test_mutations_open_by_default(client):
    body = {"question": "Will the open-by-default auth probe question resolve YES soon?", "category": "science"}
    assert client.post("/api/questions", json=body).status_code == 201


def test_gated_mutations_require_key(gated_client):
    qid = gated_client.get("/api/questions?resolved=false").json()[0]["id"]
    assert gated_client.post(f"/api/questions/{qid}/refresh").status_code == 401
    assert (
        gated_client.post(
            f"/api/questions/{qid}/refresh", headers={"X-API-Key": "vk_bogus"}
        ).status_code
        == 401
    )
    key = gated_client.post("/api/users", json={"email": "gated@vanta.test"}).json()["api_key"]
    assert (
        gated_client.post(f"/api/questions/{qid}/refresh", headers={"X-API-Key": key}).status_code
        == 200
    )


def test_gated_reads_stay_open(gated_client):
    assert gated_client.get("/api/feed").status_code == 200
    assert gated_client.get("/api/questions").status_code == 200
