import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_meta_identity(client):
    body = client.get("/api/meta").json()
    assert body["name"] == "vanta"
    assert body["version"]
    assert body["source"].startswith("https://github.com/")


def test_meta_commit_stamp(client, monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc1234")
    assert client.get("/api/meta").json()["commit"] == "abc1234"
    monkeypatch.delenv("GIT_SHA")
    assert client.get("/api/meta").json()["commit"] is None
